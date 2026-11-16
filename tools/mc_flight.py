"""Elytra flight the game's way (Minecraft 26.2, read with javap), keyed onto our villager rigs.

LivingEntity.updateFallFlyingMovement   glide physics (gravity 0.08, lift from pitch, drag .99/.98)
FireworkRocketEntity (attached)         boost: v += look*0.1 + (look*1.5 - v)*0.5 every tick,
                                        a still white spark at the hand every tick
ElytraAnimationState.tick               wing target: gliding (20 deg, -90 deg) folding with dive
                                        f = 1 - (-dir.y)^1.5, eased 0.3 per tick
AvatarRenderer.setupRotations           body pitched from the feet by scale*(-90 - xRot),
                                        scale = clamp(t^2/100, 0, 1); roll = angle(velocity, view)
HumanoidModel.setupAnim                 head xRot = -45 deg while flying; limbs nearly still

A pilot is a function tick -> dict(heading, pitch, jump, deploy, rocket); heading in degrees
(0 = facing -Y, 90 = facing +X), pitch in degrees, positive = nose down (the game's xRot).
"""
import math
import random

import bpy
from mathutils import Matrix, Quaternion, Vector

import mc_character as C
import mc_firework as FW

TPS = 20.0
G = 0.08


def look_vec(heading_deg, pitch_deg):
    h, p = math.radians(heading_deg), math.radians(pitch_deg)
    return Vector((math.sin(h) * math.cos(p), -math.cos(h) * math.cos(p), -math.sin(p)))


def glide(vel, look, pitch_deg):
    """LivingEntity.updateFallFlyingMovement, Blender axes (z up)."""
    p = math.radians(pitch_deg)
    d = math.hypot(look.x, look.y)
    d1 = math.hypot(vel.x, vel.y)
    d3 = math.cos(p) ** 2
    vel = Vector((vel.x, vel.y, vel.z + G * (-1.0 + d3 * 0.75)))
    if vel.z < 0 and d > 0:
        d4 = vel.z * -0.1 * d3
        vel += Vector((look.x * d4 / d, look.y * d4 / d, d4))
    if p < 0 and d > 0:
        d5 = d1 * -math.sin(p) * 0.04
        vel += Vector((-look.x * d5 / d, -look.y * d5 / d, d5 * 3.2))
    if d > 0:
        vel.x += (look.x / d * d1 - vel.x) * 0.1
        vel.y += (look.y / d * d1 - vel.y) * 0.1
    return Vector((vel.x * 0.99, vel.y * 0.99, vel.z * 0.98))


def simulate(pilot, start, ticks, ground_z=0.0, seed=1, flight=1):
    """Run the game's movement for `ticks`; returns one state dict per tick (after the tick)."""
    rng = random.Random(seed)
    pos, vel = Vector(start), Vector((0, 0, 0))
    on_ground, flying, fly_t, rocket_left = True, False, 0, 0
    wing = list(C.WING_STAND)
    out = []
    for t in range(ticks):
        c = pilot(t)
        look = look_vec(c['heading'], c['pitch'])
        if c.get('jump') and on_ground:
            vel.z, on_ground = 0.42, False
        if c.get('deploy') and not on_ground and not flying:
            flying, fly_t = True, 0
        if c.get('rocket') and flying and rocket_left <= 0:
            rocket_left = 10 * (1 + flight) + rng.randrange(6) + rng.randrange(7)
        if flying:
            if rocket_left > 0:
                vel = vel + look * 0.1 + (look * 1.5 - vel) * 0.5
            vel = glide(vel, look, c['pitch'])
            fly_t += 1
        elif not on_ground:
            vel = Vector((vel.x * 0.91, vel.y * 0.91, (vel.z - G) * 0.98))
        else:
            vel = Vector((vel.x * 0.546, vel.y * 0.546, 0.0))
        pos = pos + vel
        landed = False
        if pos.z <= ground_z and t > 0:
            pos.z, vel.z = ground_z, 0.0
            if not on_ground:
                landed = True
            on_ground, flying = True, False
        rocket_on = rocket_left > 0
        rocket_left = max(0, rocket_left - 1)
        # wings (ElytraAnimationState)
        if flying:
            n = vel.normalized() if vel.length > 1e-9 else Vector((0, 0, 0))
            f = 1.0 if vel.z >= 0 else 1.0 - (-n.z) ** 1.5
            target = (0.2617994 + f * (0.34906584 - 0.2617994), 0.0, -0.2617994 + f * (-1.5707964 + 0.2617994))
        else:
            target = C.WING_STAND
        wing = [w + (tg - w) * 0.3 for w, tg in zip(wing, target)]
        # roll: signed horizontal angle between velocity and view (AvatarRenderState.flyingYRot)
        roll = 0.0
        dv, dw = vel.x * vel.x + vel.y * vel.y, look.x * look.x + look.y * look.y
        if flying and dv > 1e-9 and dw > 1e-9:
            cosang = max(-1.0, min(1.0, (vel.x * look.x + vel.y * look.y) / math.sqrt(dv * dw)))
            cross = vel.x * look.y - vel.y * look.x
            roll = math.copysign(math.acos(cosang), cross)
        out.append(dict(t=t, pos=pos.copy(), vel=vel.copy(), heading=c['heading'], pitch=c['pitch'],
                        flying=flying, fly_t=fly_t, rocket=rocket_on, wing=tuple(wing), roll=roll,
                        landed=landed, on_ground=on_ground))
    return out


def fps():
    s = bpy.context.scene
    return s.render.fps / s.render.fps_base


def body_quat(st):
    scale = min(1.0, st['fly_t'] ** 2 / 100.0) if st['flying'] else 0.0
    q = Quaternion((0, 0, 1), math.radians(st['heading']))
    q = q @ Quaternion((1, 0, 0), math.radians(scale * (90.0 + st['pitch'])))
    q = q @ Quaternion((0, 0, 1), -scale * st['roll'])
    return q, scale


def apply(rig, states, frame0, trail=None, rocket_item=None, flop_on_land=False):
    """Key the rig per tick; drop rocket-trail sparks into `trail` (an mc_firework.Cloud)."""
    rig.rotation_mode = 'QUATERNION'
    hand_local = C.m2b((-6, 13, 0))
    rng = random.Random(hash(rig.name) & 0xFFFF)
    flopped = False
    prev_q = None
    for st in states:
        f = frame0 + st['t'] * fps() / TPS
        q, scale = body_quat(st)
        if flop_on_land and (st['landed'] or flopped):
            if not flopped:
                rig.location = st['pos']; rig.rotation_quaternion = q
                rig.keyframe_insert("location", frame=f); rig.keyframe_insert("rotation_quaternion", frame=f)
            flopped = True
            q = Quaternion((0, 0, 1), math.radians(st['heading'])) @ Quaternion((1, 0, 0), math.radians(88))
            f = f + 4
        # q and -q are the same rotation, but keys are interpolated per component: a sign flip
        # between neighbouring keys (heading crossing 180 deg) spins the body for one frame
        if prev_q is not None and q.dot(prev_q) < 0:
            q.negate()
        prev_q = q.copy()
        rig.location = st['pos']
        rig.rotation_quaternion = q
        rig.keyframe_insert("location", frame=f)
        rig.keyframe_insert("rotation_quaternion", frame=f)
        head_x = -0.7853982 * scale + math.radians(st['pitch']) * (1.0 - scale)
        C.set_bone_mc_rot(rig, 'head', head_x, 0, 0, frame=f)
        if 'wing.L' in rig.pose.bones:
            C.set_wing_pose(rig, *st['wing'], frame=f)
        if rocket_item is not None:
            rocket_item.scale = (1, 1, 1) if st['rocket'] else (0, 0, 0)
            rocket_item.keyframe_insert("scale", frame=f)
        if trail is not None and st['rocket']:
            M = Matrix.Translation(st['pos']) @ q.to_matrix().to_4x4()
            hand = M @ hand_local
            trail.spark(hand, (rng.gauss(0, 1) * 0.05, -rng.gauss(0, 1) * 0.05, 0.0), f, FW.WHITE)
        if flopped:
            break
    # step interpolation for rotations would look like the game at 20 fps; linear is smoother
    if rig.animation_data and rig.animation_data.action:
        for fc in _fcurves(rig.animation_data.action):
            for kp in fc.keyframe_points:
                kp.interpolation = 'LINEAR'


def _fcurves(action):
    """F-curves of an action (Blender 5 layered actions, 4.x fallback)."""
    if hasattr(action, "fcurves") and len(getattr(action, "fcurves", [])):
        return list(action.fcurves)
    out = []
    for layer in getattr(action, "layers", []):
        for strip in layer.strips:
            for bag in getattr(strip, "channelbags", []):
                out.extend(bag.fcurves)
    return out


def rocket_in_hand(rig, name):
    """Firework rocket item held in the right hand (scale-keyed on/off by apply())."""
    col = rig.users_collection[0]
    it = C.item_mesh(name, C.os.path.join(C.TEX, "item", "firework_rocket.png"), col, grip=(8, 10))
    it.matrix_world = rig.matrix_world @ (Matrix.Translation(C.m2b((-6, 11, -0.5)))
                                          @ Matrix.Rotation(math.radians(-90), 4, 'Z') @ Matrix.Scale(0.85, 4))
    bpy.context.view_layer.update()
    mw = it.matrix_world.copy()
    C.parent_to_bone(it, rig, 'hand.R')
    it.matrix_world = mw
    it.visible_shadow = True
    return it
