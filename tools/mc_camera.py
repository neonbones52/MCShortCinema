"""Cameras that keep up with fast actors (elytra with a rocket ~30 blocks/s, HANDOFF pitfall 8).

Not a parent: a camera parented to the flyer inherits his body pitch (90 deg at take-off), his
banking and every jolt, and he sits nailed to one spot of the frame, so the flight reads as a
still actor in front of a sliding backdrop. Here the camera is an operator flying next to him:

  position  = the actor + an offset given in his direction of travel (side, back, up), followed
              through a critically damped spring that also matches his velocity. At a steady
              speed there is no lag at all; when the speed changes by dv the actor drifts about
              0.18 * dv * lag blocks in the frame before the camera catches up (lag 0.5 s and a
              rocket kick of 20 blocks/s: ~2 blocks). His wobble stays visible, the camera
              stays calm.
  aim       = the same kind of spring on the look-at point, but stiffer (aim_lag), so he never
              leaves the frame; `lead` looks ahead of him, `screen` places him off-centre.
  heading   = the direction of travel, smoothed (heading_lag): in a turn the camera swings
              round behind him gradually. heading=<degrees> pins the offset to a fixed compass
              direction instead (profile tracking shots).
  fixed     = (x, y, z): a tripod; only the aim follows.

    import mc_camera as CAM
    cam = CAM.follow("Cam.Chase", hero_rig, 1, 192, side=4.5, back=6.5, up=1.2, lens=28)

The keys go on an empty "<name>.mount"; the camera is its child with an identity local
transform. Rebaking rewrites the mount only, so the user can nudge or key the camera itself by
hand (local offset on top of the follow) and nothing here overwrites it. An existing camera
that is not on our mount is left alone. `lens` is applied only when the camera is created.
"""
import math

import bpy
from mathutils import Quaternion, Vector

MIN_SPEED = 1.0          # blocks/s of horizontal travel below which the heading is kept


def fps():
    s = bpy.context.scene
    return s.render.fps / s.render.fps_base


def heading_vec(deg):
    """mc_flight convention: 0 = facing -Y, 90 = facing +X."""
    h = math.radians(deg)
    return Vector((math.sin(h), -math.cos(h), 0.0))


# ------------------------------------------------------------------ sampling the actor
def _own_fcurves(ob):
    ad = ob.animation_data
    if ad is None or ad.action is None:
        return []
    slot = getattr(ad, "action_slot", None)
    out = []
    for layer in getattr(ad.action, "layers", []):
        for strip in layer.strips:
            bag = strip.channelbag(slot) if slot is not None else None
            if bag is not None:
                out.extend(bag.fcurves)
    return out


def _sample_object(ob, frames, anchor):
    """World position of the rig-local point `anchor` on every frame. Reads the f-curves when the
    object is a free root keyed in quaternions (our flight rigs), else steps the scene."""
    anchor = Vector(anchor)
    simple = ob.parent is None and not ob.constraints and ob.rotation_mode == 'QUATERNION'
    if simple:
        fcs = {(fc.data_path, fc.array_index): fc for fc in _own_fcurves(ob)}
        if not any(k[0] == "location" for k in fcs):
            simple = False
    if simple:
        def chan(path, i, default, f):
            fc = fcs.get((path, i))
            return fc.evaluate(f) if fc is not None else default
        out = []
        for f in frames:
            p = Vector([chan("location", i, ob.location[i], f) for i in range(3)])
            q = Quaternion([chan("rotation_quaternion", i, ob.rotation_quaternion[i], f) for i in range(4)])
            q.normalize()
            out.append(p + q @ anchor)
        return out
    sc = bpy.context.scene
    keep = sc.frame_current
    out = []
    for f in frames:
        sc.frame_set(int(f))
        out.append(ob.matrix_world @ anchor)
    sc.frame_set(keep)
    return out


def sample(target, frames, anchor=(0.0, 0.0, 1.0)):
    """target: an object, a list of objects (their centroid: a formation), a function
    frame -> position, or a ready list of positions (one per frame)."""
    if callable(target):
        return [Vector(target(f)) for f in frames]
    if isinstance(target, bpy.types.Object):
        return _sample_object(target, frames, anchor)
    target = list(target)
    if target and isinstance(target[0], bpy.types.Object):
        tracks = [_sample_object(ob, frames, anchor) for ob in target]
        return [sum((t[i] for t in tracks), Vector()) / len(tracks) for i in range(len(frames))]
    if len(target) != len(frames):
        raise ValueError("a list of positions needs one entry per frame")
    return [Vector(p) for p in target]


# ------------------------------------------------------------------ the operator
def spring(targets, lag, rate, substeps=8):
    """Critically damped spring towards a moving target, damped on the *relative* velocity:
    no steady-state lag behind a target that moves at a constant speed. lag <= 0: rigid."""
    if lag <= 0.0 or len(targets) < 2:
        return [t.copy() for t in targets]
    w = 2.0 / lag
    k, c = w * w, 2.0 * w
    h = 1.0 / (rate * substeps)
    x, v = targets[0].copy(), (targets[1] - targets[0]) * rate
    out = [x.copy()]
    for a, b in zip(targets, targets[1:]):
        vt = (b - a) * rate
        for s in range(1, substeps + 1):
            acc = (a.lerp(b, s / substeps) - x) * k + (vt - v) * c
            v += acc * h
            x += v * h
        out.append(x.copy())
    return out


def headings(points, rate, lag, start=None):
    """Smoothed horizontal direction of travel per frame (unit vectors)."""
    raw = []
    for i in range(len(points)):
        a, b = points[max(i - 1, 0)], points[min(i + 1, len(points) - 1)]
        d = Vector((b.x - a.x, b.y - a.y, 0.0)) * (rate / max(1, min(i + 1, len(points) - 1) - max(i - 1, 0)))
        raw.append(d.normalized() if d.length > MIN_SPEED else None)
    first = next((d for d in raw if d is not None), None)
    cur = Vector(start) if start is not None else (first if first is not None else Vector((0.0, 1.0, 0.0)))
    cur = Vector((cur.x, cur.y, 0.0)).normalized()
    a = 1.0 - math.exp(-1.0 / (rate * lag)) if lag > 0.0 else 1.0
    out = []
    want = cur.copy()
    for d in raw:
        if d is not None:
            want = d
        # turn by angle, not by blending vectors: a blend collapses on a reversal
        ang = math.atan2(cur.x * want.y - cur.y * want.x, cur.dot(want))
        cur = Quaternion((0.0, 0.0, 1.0), ang * a) @ cur
        out.append(cur.copy())
    return out


def mount(name, lens=28.0, collection=None):
    """The empty that carries the baked move and the camera on it. Returns (mount, camera);
    mount is None when a camera of that name exists and is not ours (hands off)."""
    sc = bpy.context.scene
    col = collection or sc.collection
    cam = bpy.data.objects.get(name)
    mnt = bpy.data.objects.get(name + ".mount")
    if cam is not None and (mnt is None or cam.parent is not mnt):
        print(f"mc_camera: '{name}' exists and is not on a mount of ours: left untouched")
        return None, cam
    if mnt is None:
        mnt = bpy.data.objects.new(name + ".mount", None)
        mnt.empty_display_type = 'ARROWS'
        mnt.empty_display_size = 0.5
        col.objects.link(mnt)
    if cam is None:
        cam = bpy.data.objects.new(name, bpy.data.cameras.new(name))
        cam.data.lens = lens
        col.objects.link(cam)
        cam.parent = mnt
    return mnt, cam


def follow(name, target, frame0, frame1, side=4.0, back=7.0, up=1.5, lens=28.0, lag=0.5,
           aim_lag=0.15, heading_lag=0.6, heading=None, lead=0.0, screen=(0.0, 0.0),
           anchor=(0.0, 0.0, 1.0), fixed=None, collection=None):
    """Bake a follow camera over frames frame0..frame1 (see the module docstring).

    side / back / up  blocks to the actor's right, behind him and above the anchor point
    lag, aim_lag      seconds; position and look-at springs (0 = rigid)
    heading_lag       seconds; how fast the offset swings round after a turn
    heading           None = direction of travel; degrees = fixed (0 = actor faces -Y, 90 = +X)
    lead              seconds of the actor's velocity to look ahead by
    screen            where the actor sits in the frame, -1..1 (x right, y up); (0, 0) = centre
    anchor            the rig-local point that is followed (default: mid-body, 1 block up)
    fixed             world position of a tripod; then side/back/up/lag are ignored
    """
    mnt, cam = mount(name, lens, collection)
    if mnt is None:
        return cam
    sc = bpy.context.scene
    rate = fps()
    frames = list(range(int(frame0), int(frame1) + 1))
    P = sample(target, frames, anchor)
    n = len(P)
    V = [(P[min(i + 1, n - 1)] - P[max(i - 1, 0)]) * (rate / max(1, min(i + 1, n - 1) - max(i - 1, 0)))
         for i in range(n)]

    if fixed is not None:
        pos = [Vector(fixed) for _ in P]
    else:
        if heading is None:
            H = headings(P, rate, heading_lag)
        else:
            H = [heading_vec(heading)] * n
        want = [p + Vector((h.y, -h.x, 0.0)) * side - h * back + Vector((0.0, 0.0, up)) for p, h in zip(P, H)]
        pos = spring(want, lag, rate)
    aim = spring([p + v * lead for p, v in zip(P, V)], aim_lag, rate)

    # put the actor at `screen` instead of the centre: turn the look-at camera so that the
    # centre ray moves to that point of the frame
    half_w = 0.5 * cam.data.sensor_width / cam.data.lens
    half_h = half_w * sc.render.resolution_y / sc.render.resolution_x
    ray = Vector((screen[0] * half_w, screen[1] * half_h, -1.0)).normalized()
    shift = ray.rotation_difference(Vector((0.0, 0.0, -1.0)))

    mnt.animation_data_clear()
    mnt.rotation_mode = 'QUATERNION'
    prev = None
    for f, c, a in zip(frames, pos, aim):
        q = (a - c).to_track_quat('-Z', 'Y') @ shift
        if prev is not None and q.dot(prev) < 0.0:      # HANDOFF pitfall 1
            q.negate()
        prev = q.copy()
        mnt.location = c
        mnt.rotation_quaternion = q
        mnt.keyframe_insert("location", frame=f)
        mnt.keyframe_insert("rotation_quaternion", frame=f)
    for fc in _own_fcurves(mnt):
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'
    mnt["mc_camera"] = dict(side=side, back=back, up=up, lag=lag, aim_lag=aim_lag, heading_lag=heading_lag,
                            heading=-1.0 if heading is None else float(heading), lead=lead,
                            screen=list(screen), tripod=fixed is not None)
    return cam


def report(cam, target, frame0, frame1, anchor=(0.0, 0.0, 1.0)):
    """Where the actor ends up in the frame: per-frame screen position (-1..1) and distance.
    Returns dict(x=(min, max), y=(min, max), dist=(min, max), out=frames where he leaves the frame)."""
    from bpy_extras.object_utils import world_to_camera_view
    sc = bpy.context.scene
    keep = sc.frame_current
    xs, ys, ds, out = [], [], [], []
    for f in range(int(frame0), int(frame1) + 1):
        sc.frame_set(f)
        p = (target.matrix_world @ Vector(anchor)) if isinstance(target, bpy.types.Object) else Vector(target(f))
        u = world_to_camera_view(sc, cam, p)
        x, y = u.x * 2.0 - 1.0, u.y * 2.0 - 1.0
        xs.append(x); ys.append(y); ds.append((p - cam.matrix_world.translation).length)
        if u.z <= 0.0 or abs(x) > 1.0 or abs(y) > 1.0:
            out.append(f)
    sc.frame_set(keep)
    return dict(x=(min(xs), max(xs)), y=(min(ys), max(ys)), dist=(min(ds), max(ds)), out=out)
