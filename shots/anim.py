"""Shared helpers for the animatic (2026-11-21): rough blocking of all 27 shots on the real sets,
rendered fast (EEVEE, few samples, 50 %), cut under MemoryReboot_edit_2m36.wav by
shots/assemble.py.

The scene timeline IS the track: Blender frame = track frame (0 .. 3753), so a shot renders
its own range of the one timeline and a performance can run on across a cut. Frames go to
renders/animatic/frames/f####.png (one folder for the whole film); stills to
renders/animatic/stills/sNN_f####.png.

Every location script (shots/anim_<location>.py) is run on its set's .blend:
    blender -b blender/sets/<set>.blend --python shots/anim_<loc>.py -- stills [shot ...]
    blender -b blender/sets/<set>.blend --python shots/anim_<loc>.py -- render [shot ...]
    blender -b blender/sets/<set>.blend --python shots/anim_<loc>.py -- save      (inspect the blocking)
"""
import contextlib
import io
import math
import os
import sys
import time

import bpy
from mathutils import Vector

ROOT = r"C:\Dev\Projects\CinemaShort"
sys.path.insert(0, os.path.join(ROOT, "tools"))
OUT = os.path.join(ROOT, "renders", "animatic")
FRAMES = os.path.join(OUT, "frames")
STILLS = os.path.join(OUT, "stills")
FPS = 24
TRACK_FRAMES = 3754

# shot: (first, end) track frames, end exclusive (shot_list.md, 1 bar = 80 frames)
SHOTS = {
    1: (0, 160), 2: (160, 319), 3: (319, 480), 4: (480, 639), 5: (639, 719), 6: (719, 799),
    7: (799, 878), 8: (878, 958), 9: (958, 1118), 10: (1118, 1278), 11: (1278, 1398),
    12: (1398, 1517), 13: (1517, 1597), 14: (1597, 1757), 15: (1757, 1877), 16: (1877, 1956),
    17: (1956, 2036), 18: (2036, 2116), 19: (2116, 2176), 20: (2176, 2236), 21: (2236, 2476),
    22: (2476, 2674), 23: (2674, 2794), 24: (2794, 2874), 25: (2874, 3034), 26: (3034, 3193),
    27: (3193, 3754),
}


def frame_of_tick(t, frame0):
    return frame0 + t * FPS / 20.0


def tick_of_frame(f, frame0):
    return (f - frame0) * 20.0 / FPS


def smooth(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3.0 - 2.0 * x)


def quiet():
    return contextlib.redirect_stdout(io.StringIO())


def setup(samples=4):
    """Draft settings: the look of the viewport at a fraction of the final cost."""
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE'
    sc.render.resolution_x, sc.render.resolution_y = 1920, 804
    sc.render.resolution_percentage = 50
    sc.render.fps = FPS
    sc.render.fps_base = 1.0
    sc.eevee.taa_render_samples = samples
    sc.eevee.use_raytracing = False
    sc.eevee.shadow_pool_size = '1024'
    sc.render.use_motion_blur = False
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGB'
    sc.frame_start, sc.frame_end = 0, TRACK_FRAMES - 1


def remove_collections(prefixes):
    """Delete the stand-ins a set .blend was saved with (their collections and objects)."""
    for c in list(bpy.data.collections):
        if c.name.startswith(tuple(prefixes)):
            for o in list(c.all_objects):
                bpy.data.objects.remove(o, do_unlink=True)
            bpy.data.collections.remove(c)


def collection(name):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(c)
    return c


def look_quat(pos, target):
    return (Vector(target) - Vector(pos)).to_track_quat('-Z', 'Y')


def camera(name, keys, lens=28.0, ease=True):
    """A shot camera keyed through `keys` = [(frame, position, target[, lens])] (Blender
    coordinates). Rotation as sign-continuous quaternions; Bezier ease between keys (or linear)."""
    old = bpy.data.objects.get(name)
    if old is not None:
        bpy.data.objects.remove(old, do_unlink=True)
    cam = bpy.data.objects.new(name, bpy.data.cameras.new(name))
    collection("Shots").objects.link(cam)
    cam.data.lens = lens
    cam.data.clip_start = 0.05
    cam.rotation_mode = 'QUATERNION'
    prev = None
    for k in keys:
        f, pos, target = k[0], Vector(k[1]), Vector(k[2])
        q = look_quat(pos, target)
        if prev is not None and q.dot(prev) < 0:
            q.negate()
        prev = q.copy()
        cam.location, cam.rotation_quaternion = pos, q
        cam.keyframe_insert("location", frame=f)
        cam.keyframe_insert("rotation_quaternion", frame=f)
        if len(k) > 3:
            cam.data.lens = k[3]
            cam.data.keyframe_insert("lens", frame=f)
    if not ease:
        for fc in fcurves(cam):
            for kp in fc.keyframe_points:
                kp.interpolation = 'LINEAR'
    return cam


def camera_path(name, frames, fn, lens=28.0):
    """A camera keyed every frame from fn(frame) -> (position, target)."""
    old = bpy.data.objects.get(name)
    if old is not None:
        bpy.data.objects.remove(old, do_unlink=True)
    cam = bpy.data.objects.new(name, bpy.data.cameras.new(name))
    collection("Shots").objects.link(cam)
    cam.data.lens = lens
    cam.data.clip_start = 0.05
    cam.rotation_mode = 'QUATERNION'
    prev = None
    for f in frames:
        pos, target = fn(f)
        q = look_quat(pos, target)
        if prev is not None and q.dot(prev) < 0:
            q.negate()
        prev = q.copy()
        cam.location, cam.rotation_quaternion = Vector(pos), q
        cam.keyframe_insert("location", frame=f)
        cam.keyframe_insert("rotation_quaternion", frame=f)
    for fc in fcurves(cam):
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'
    return cam


def focus(cam, keys, fstop=2.0):
    """Depth of field: keys = [(frame, distance)] (a focus pull is two keys close together)."""
    cam.data.dof.use_dof = True
    cam.data.dof.aperture_fstop = fstop
    for f, d in keys:
        cam.data.dof.focus_distance = d
        cam.data.dof.keyframe_insert("focus_distance", frame=f)


def fcurves(idb):
    ad = idb.animation_data
    out = []
    if not ad or not ad.action:
        return out
    for layer in ad.action.layers:
        for strip in layer.strips:
            for cb in strip.channelbags:
                out.extend(cb.fcurves)
    return out


def key_visible(ob, ranges, all_frames=(0, TRACK_FRAMES)):
    """Show `ob` (and its children) only inside the frame ranges [(a, b)], b exclusive."""
    obs = [ob] + list(ob.children_recursive)
    for o in obs:
        o.hide_render = True
        o.keyframe_insert("hide_render", frame=all_frames[0])
        for a, b in ranges:
            o.hide_render = False
            o.keyframe_insert("hide_render", frame=a)
            o.hide_render = True
            o.keyframe_insert("hide_render", frame=b)
        for fc in fcurves(o):
            if fc.data_path == "hide_render":
                for kp in fc.keyframe_points:
                    kp.interpolation = 'CONSTANT'


def face_camera(cam):
    """Particles and rocket sprites turn to the scene camera (HANDOFF pitfall 23)."""
    import mc_firework as FW
    for ob in bpy.data.objects:
        if ob.type == 'MESH' and ob.modifiers and ob.modifiers[0].type == 'NODES':
            try:
                FW.set_input(ob.modifiers[0], "Camera", cam)
            except Exception:
                pass
        for con in ob.constraints:
            if con.type == 'DAMPED_TRACK':
                con.target = cam


def args():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    mode = a[0] if a else "save"
    shots = [int(x) for x in a[1:] if not x.startswith("@")]
    global EXTRA_FRAMES
    EXTRA_FRAMES = [int(f) for x in a[1:] if x.startswith("@") for f in x[1:].split(",")]
    return mode, shots


EXTRA_FRAMES = []          # "-- stills 27 @3640,3660": these frames (inside the shot) instead of the default three


def still_frames(a, b, count=3):
    return [round(a + (b - 1 - a) * i / (count - 1)) for i in range(count)]


def run(mode, shots, plan, blend_name=None):
    """plan: [dict(shot=n, cam=name, prepare=fn[, range=(a, b)])]; prepare() sets the sky and
    the look for that camera (the scene camera is set first)."""
    sc = bpy.context.scene
    todo = [p for p in plan if not shots or p["shot"] in shots]
    if mode == "save":
        os.makedirs(os.path.join(ROOT, "blender", "shots"), exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, "blender", "shots", blend_name))
        print("SAVED", blend_name)
        return
    os.makedirs(FRAMES, exist_ok=True)
    os.makedirs(STILLS, exist_ok=True)
    log = []
    for p in todo:
        n = p["shot"]
        sc.camera = bpy.data.objects[p["cam"]]
        a, b = p.get("range") or SHOTS[n]
        sc.frame_set(a)
        p["prepare"]()
        face_camera(sc.camera)
        t0 = time.time()
        if mode == "stills":
            fr = [f for f in EXTRA_FRAMES if a <= f < b] or still_frames(a, b, 2 if "range" in p else 3)
            for f in fr:
                sc.frame_set(f)
                sc.render.filepath = os.path.join(STILLS, f"s{n:02d}_f{f:04d}.png")
                bpy.ops.render.render(write_still=True)
            per = (time.time() - t0) / len(fr)
        else:
            sc.frame_start, sc.frame_end = a, b - 1
            sc.render.filepath = os.path.join(FRAMES, "f")
            bpy.ops.render.render(animation=True)
            per = (time.time() - t0) / (b - a)
        log.append(f"shot {n:02d} {p['cam']}: {per:.2f} s/frame")
        print("SHOT", n, p["cam"], f"{per:.2f} s/frame", flush=True)
    with open(os.path.join(OUT, f"times_{mode}.txt"), "a", encoding="utf-8") as fh:
        fh.write("\n".join(log) + "\n")


# ------------------------------------------------------------------ readable night (user 2026-11-21)
# "the dark scenes are super dark: the field and the bodies cannot be seen" (from 14, worst from
# 21). The approved looks are graded for a true night; the animatic lifts them, the way a film
# night is always brighter than a real one, without going back to the flat even light the user
# rejected (the shadowed key light stays). Changes live here, not in mc_look.
NIGHT_LIFT = {"night": 0.5, "finale": 0.6}     # exposure, stops added to the approved look
FINALE_AMBIENT = 0.12                          # the finale stand's sky fill (approved 0.07)
LANTERN_GAIN = 1.8                             # HQ lantern lamps


def apply_look(name):
    import mc_look as L
    base = L.LOOKS[name].setdefault("_base_exposure", L.LOOKS[name]["exposure"])
    L.LOOKS[name]["exposure"] = base + NIGHT_LIFT.get(name, 0.0)
    L.apply(name)
