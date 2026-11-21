"""Humanoid motion for mc_character rigs (villagers and players), simulated per game tick.

From the game (26.2, read with javap):
  HumanoidModel.setupAnim       walk: arms cos(pos*0.6662 [+pi]) * 2 * speed * 0.5,
                                legs cos(pos*0.6662 [+pi]) * 1.4 * speed, legs y/z +-0.005;
                                ITEM arm pose xRot*0.5 - pi/10
  AnimationUtils.bobModelPart   idle arm sway: z += s*(cos(age*0.09)*0.05+0.05), x += s*sin(age*0.067)*0.05
  HumanoidModel.setupAttackAnimation + SwingAnimation.DEFAULT (WHACK, 6 ticks): the swing / punch
  LivingEntity.updateWalkAnimation  speed += (min(dist*4, 1) - speed) * 0.4; pos += speed
  LookControl                   head turns at most 10 deg per tick
Not in the game, staged from the same part rotations: salute, point (stick), hold out (hand an
item over), sit / stand up.

Usage (inside Blender):
    import mc_motion as M
    a = M.Actor(rig, yaw=0)                        # yaw: Blender radians, 0 = facing -Y
    a.walk(t0, [(x, y, 0), ...], speed=0.2159)     # blocks per tick (player walk 4.317 m/s)
    a.look(t0, t1, target)                         # world point, or an Actor (looks at its head)
    a.salute(t0, t1); a.point(t0, t1, target); a.hold_out(t0, t1, target); a.swing(t)
    a.hold_item(t0, t1); a.sit(t0, t1, seat_height_px=8)
    M.bake([a, ...], ticks, frame0=1)              # keys every tick at frame0 + t*fps/20
"""
import math

from mathutils import Euler, Matrix, Quaternion, Vector

import mc_character as C

TPS = 20.0
HEAD_STEP = math.radians(10.0)       # LookControl: max yaw / pitch change per tick
HEAD_YAW_MAX = math.radians(75.0)    # head relative to body
SWING_TICKS = 6                      # SwingAnimation.DEFAULT
EYE_PX = 4.0                         # eyes 4 px below the top of the head box (model y = -4 .. -6)


def wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


def smooth(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def yaw_of(d):
    """Blender yaw that makes a character face horizontal direction d (0 = facing -Y)."""
    return math.atan2(d.x, -d.y)


def mc_euler_to_mat(x, y, z):
    return C.rot_model(x, y, z)


def mat_to_mc_euler(R):
    """Inverse of rot_model (R = Rz*Ry*Rx) -> (x, y, z)."""
    e = R.to_euler('XYZ')            # Blender 'XYZ' euler means R = Rz*Ry*Rx too
    return e.x, e.y, e.z


def aim_rot(d, twist=0.0):
    """MC (x, y, z) rotation that turns a hanging arm (model +y) to model direction d.
    Picks the solution with the arm's front kept forward (small z)."""
    d = Vector(d).normalized()
    dz = max(-1.0, min(1.0, d.z))
    if d.y >= 0:
        x = math.asin(dz)
    else:
        x = (-math.pi if dz <= 0 else math.pi) - math.asin(dz)
    cx = math.cos(x)
    z = math.atan2(-d.x / cx, d.y / cx) if abs(cx) > 1e-6 else 0.0
    return (x, twist, z)


def to_model(rig_yaw, d_world):
    """World direction -> model-space direction of a character with yaw rig_yaw."""
    db = Matrix.Rotation(-rig_yaw, 3, 'Z') @ Vector(d_world)
    return Vector((db.x, -db.z, db.y))          # inverse of m2b's axes: b = (mx, mz, -my)


class Actor:
    def __init__(self, rig, pos=None, yaw=0.0):
        self.rig = rig
        self.pos = Vector(rig.location if pos is None else pos)
        self.yaw = yaw
        self.scale = rig.scale[0]
        kind = dict(rig.get("mc_character", {})).get("kind", "villager")
        # villager head is 10 px tall; the baby villager (26.x model) is 16 px tall in all
        self.head_top_px = {"player": 32.0, "baby_villager": 16.0}.get(kind, 34.0)
        self.paths, self.looks, self.faces, self.gestures, self.swings = [], [], [], [], []
        self.sits = []
        self.state = {}

    # ---- authoring
    def walk(self, t0, points, speed=0.2159):
        pts = [Vector(p) for p in points]
        self.paths.append((t0, pts, speed))
        return self

    def face(self, t, target):
        """Turn the body (when standing) towards a world point / Actor / yaw angle from tick t."""
        self.faces.append((t, target))
        return self

    def look(self, t0, t1, target):
        self.looks.append((t0, t1, target))
        return self

    def _gesture(self, kind, t0, t1, ramp, **kw):
        self.gestures.append(dict(kind=kind, t0=t0, t1=t1, ramp=ramp, **kw))
        return self

    def salute(self, t0, t1, ramp=5):
        return self._gesture('salute', t0, t1, ramp)

    def point(self, t0, t1, target, ramp=6, jabs=()):
        """Arm aimed at a world point (e.g. with a stick). jabs: ticks of short pokes."""
        return self._gesture('point', t0, t1, ramp, target=target, jabs=tuple(jabs))

    def hold_out(self, t0, t1, target, ramp=6):
        """Arm held out low towards a world point / Actor (handing over an item)."""
        return self._gesture('hold_out', t0, t1, ramp, target=target)

    def hold_item(self, t0, t1, ramp=3):
        """The game's ITEM arm pose (holding something in the right hand)."""
        return self._gesture('item', t0, t1, ramp)

    def swing(self, t):
        """The game's swing (punch / whack) with the right arm, starting at tick t."""
        self.swings.append(t)
        return self

    def sit(self, t0, t1, seat_height_px=8.0, ramp=8):
        """Seated (riding-pose legs) from t0 until t1, getting up over `ramp` ticks."""
        self.sits.append((t0, t1, seat_height_px, ramp))
        return self

    # ---- helpers
    def head_world(self, st=None):
        st = st or self.state
        pos = st.get('pos', self.pos)
        h = (self.head_top_px - EYE_PX) / 16.0 * self.scale    # eye height above the feet
        return pos + Vector((0, 0, h - st.get('drop', 0.0)))

    def _target_point(self, target):
        if isinstance(target, Actor):
            return target.head_world()
        return Vector(target)

    def _shoulder_world(self, st):
        sh = C.m2b((-5, 2, 0)) * self.scale
        sh = Matrix.Rotation(st['yaw'], 3, 'Z') @ sh
        return st['pos'] + sh - Vector((0, 0, st.get('drop', 0.0)))

    def _weight(self, g, t):
        r = max(1, g['ramp'])
        return smooth((t - g['t0']) / r) * (1.0 - smooth((t - g['t1']) / r))

    # ---- simulation of one tick
    def tick(self, t):
        st = self.state
        if not st:
            st.update(pos=self.pos.copy(), yaw=self.yaw, speed=0.0, wpos=0.0, hyaw=0.0, hpitch=0.0,
                      drop=0.0)
        prev = st['pos'].copy()
        moving = False
        for t0, pts, speed in self.paths:
            segs = [(a, b, (b - a).length) for a, b in zip(pts, pts[1:])]
            total = sum(s[2] for s in segs)
            if t < t0:
                continue
            dist = min(total, (t - t0) * speed)
            acc = 0.0
            for a, b, L in segs:
                if acc + L >= dist - 1e-9:
                    st['pos'] = a + (b - a) * ((dist - acc) / L if L else 0.0)
                    if dist < total:
                        moving, direction = True, (b - a).normalized()
                    break
                acc += L
        moved = (st['pos'] - prev).xy.length
        st['speed'] += (min(moved * 4.0, 1.0) - st['speed']) * 0.4
        st['wpos'] += st['speed']

        # body yaw: towards the movement, else the latest face() target
        target_yaw = None
        if moving:
            target_yaw = yaw_of(direction)
        else:
            for tf, tgt in sorted(self.faces, key=lambda x: x[0]):
                if t >= tf:
                    if isinstance(tgt, (int, float)):
                        target_yaw = float(tgt)
                    else:
                        d = self._target_point(tgt) - st['pos']
                        target_yaw = yaw_of(d)
        if target_yaw is not None:
            st['yaw'] += wrap(target_yaw - st['yaw']) * (0.3 if moving else 0.25)

        # sitting: root drop (model px -> m) and leg blend
        st['sitw'], st['drop'] = 0.0, 0.0
        for t0, t1, seat, ramp in self.sits:
            w = 1.0 if t0 <= t < t1 else (1.0 - smooth((t - t1) / ramp) if t >= t1 else 0.0)
            if w > st['sitw']:
                st['sitw'] = w
                st['drop'] = w * (12.0 - (seat + 2.0)) / 16.0 * self.scale

        # head look (LookControl: limited step)
        want_y, want_p = 0.0, 0.0
        for t0, t1, tgt in self.looks:
            if t0 <= t < t1:
                d = self._target_point(tgt) - self.head_world(st)
                want_y = max(-HEAD_YAW_MAX, min(HEAD_YAW_MAX, wrap(yaw_of(d) - st['yaw'])))
                want_p = math.atan2(-d.z, d.xy.length)      # MC xRot: + = looking down
        st['hyaw'] += max(-HEAD_STEP, min(HEAD_STEP, want_y - st['hyaw']))
        st['hpitch'] += max(-HEAD_STEP, min(HEAD_STEP, want_p - st['hpitch']))
        return st

    def pose(self, t):
        """Bone rotations (MC euler, model space) for tick t, after tick(t)."""
        st = self.state
        wp, ws = st['wpos'], st['speed']
        P = {}
        P['head'] = [st['hpitch'], -st['hyaw'], 0.0]
        armR = [math.cos(wp * 0.6662 + math.pi) * 2.0 * ws * 0.5, 0.0, 0.0]
        armL = [math.cos(wp * 0.6662) * 2.0 * ws * 0.5, 0.0, 0.0]
        legR = [math.cos(wp * 0.6662) * 1.4 * ws, 0.005, 0.005]
        legL = [math.cos(wp * 0.6662 + math.pi) * 1.4 * ws, -0.005, -0.005]
        sw = st['sitw']
        if sw > 0:                               # HumanoidModel passenger pose
            for leg, s in ((legR, 1), (legL, -1)):
                tgt = (-1.4137167, s * 0.31415927, s * 0.07853982)
                for i in range(3):
                    leg[i] += (tgt[i] - leg[i]) * sw
            armR[0] += -0.62831855 * sw
            armL[0] += -0.62831855 * sw
        # idle bob (both arms, always)
        age = t
        armR[2] += math.cos(age * 0.09) * 0.05 + 0.05
        armR[0] += math.sin(age * 0.067) * 0.05
        armL[2] -= math.cos(age * 0.09) * 0.05 + 0.05
        armL[0] -= math.sin(age * 0.067) * 0.05

        # gestures on the right arm: blend (slerp) from the base pose
        qR = mc_euler_to_mat(*armR).to_quaternion()
        for g in self.gestures:
            w = self._weight(g, t)
            if w <= 0:
                continue
            k = g['kind']
            if k == 'item':
                gr = (armR[0] * 0.5 - 0.31415927, 0.0, armR[2])
            elif k == 'salute':
                # fist at the right temple, palm out (tuned by eye)
                gr = SALUTE
            else:
                tp = self._target_point(g['target'])
                d = to_model(st['yaw'], tp - self._shoulder_world(st))
                if k == 'hold_out':
                    d = d.normalized()
                    d.y = max(d.y, 0.55)            # keep the arm low, forearm-height offer
                gr = aim_rot(d)
                if k == 'point' and g.get('jabs'):
                    j = sum(math.sin(math.pi * min(1, max(0, (t - tj) / 4.0))) for tj in g['jabs'])
                    gr = (gr[0] - 0.25 * j, gr[1], gr[2])
            q = mc_euler_to_mat(*gr).to_quaternion()
            if q.dot(qR) < 0:
                q.negate()
            qR = qR.slerp(q, w)
        armR = list(mat_to_mc_euler(qR.to_matrix()))

        # the game's swing (WHACK), right arm
        body = [0.0, 0.0, 0.0]
        for ts in self.swings:
            if ts <= t < ts + SWING_TICKS:
                a = (t - ts) / SWING_TICKS
                by = math.sin(math.sqrt(a) * 2 * math.pi) * 0.2
                body[1] = by
                # arms are children of the body here, so the game's arm.yRot += body.yRot is implicit;
                # WHACK adds body.yRot * 2 on top
                armR[1] += by * 2.0
                armL[0] += by
                f4 = 1 - (1 - a) ** 4                       # Ease.outQuart
                f5 = math.sin(f4 * math.pi)
                f6 = math.sin(a * math.pi) * -(P['head'][0] - 0.7) * 0.75
                armR[0] -= f5 * 1.2 + f6
                armR[2] += math.sin(a * math.pi) * -0.4
                P['head'][1] -= by                          # head is not turned by the body in the game
        P.update({'body': body, 'arm.R': armR, 'arm.L': armL, 'leg.R': legR, 'leg.L': legL})
        return P


SALUTE = (-2.611, 0.0, 0.082)   # aim_rot: shoulder (-5,2,0) -> fist at the brow corner (-4.3,-6.5,-5)


def _key_bone(rig, bone, rot, frame):
    if bone in rig.pose.bones:
        C.set_bone_mc_rot(rig, bone, *rot, frame=frame)


def bake(actors, ticks, frame0=1, fps=24.0):
    """Simulate every actor tick by tick and key the rigs at frame0 + t * fps / 20."""
    prev_q = {}
    for a in actors:
        a.state = {}
        a.rig.rotation_mode = 'QUATERNION'
    for t in range(ticks + 1):
        for a in actors:
            a.tick(t)
        for a in actors:
            st = a.state
            f = frame0 + t * fps / TPS
            a.rig.location = st['pos'] - Vector((0, 0, st['drop']))
            q = Quaternion((0, 0, 1), st['yaw'])
            p = prev_q.get(a.rig.name)
            if p is not None and q.dot(p) < 0:
                q.negate()
            prev_q[a.rig.name] = q.copy()
            a.rig.rotation_quaternion = q
            a.rig.keyframe_insert("location", frame=f)
            a.rig.keyframe_insert("rotation_quaternion", frame=f)
            for bone, rot in a.pose(t).items():
                _key_bone(a.rig, bone, rot, f)
    for a in actors:
        linearize(a.rig)
    return ticks


def linearize(ob):
    """Linear interpolation between tick keys, as the game lerps between ticks (partialTick)."""
    ad = ob.animation_data
    if not ad or not ad.action:
        return
    for layer in ad.action.layers:
        for strip in layer.strips:
            for cb in strip.channelbags:
                for fc in cb.fcurves:
                    for k in fc.keyframe_points:
                        k.interpolation = 'LINEAR'
