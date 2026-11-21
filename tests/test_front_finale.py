"""Finale stand on the real front (shots 25-27): the hero on his knees 55 blocks in front of Alex's
first trench, looking west, back where he flew from; dozens of the fallen around him (torn
wings, poses from mc_fallen); Alex's barrage from the first line flying over his back and
bursting ahead of him (approved density: 3.5 shots/s, pitch 12-28, light 150000, flash x0.35);
black sky (no stars, moon, sun, clouds), the finale look. The camera (shot 27, user 2026-11-21):
a dolly straight back along its own axis, the back of the hero's head kept dead centre, a
slight downward pitch so the field of the fallen is in frame, no crane up.

    blender -b --python tests/test_front_finale.py            -> blender/front_finale.blend
    blender -b blender/front_finale.blend --python tests/test_front_finale.py -- render [percent] [frames...]
-> renders/tests/front/finale_<frame>_v1.png
"""
import contextlib
import io
import math
import os
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, r"C:\Dev\Projects\CinemaShort\tools")
import importlib
import mc_character as C
import mc_fallen as FL
import mc_firework as FW
import mc_look as L
import mc_salvo as SV
import mc_set as SET
import mc_sky as SKY
for _m in (SET, FL):
    importlib.reload(_m)

ROOT = r"C:\Dev\Projects\CinemaShort"
OUT = os.path.join(ROOT, "renders", "tests", "front")
K = SET.marks("front")
HX, HY, HZ = K["hero"]
L1 = K["lines_x"][0]
FRAMES = (1, 320)                 # shot 27: 13.3 s
N_FALLEN = 48
PITCH = math.radians(-9.0)        # slight look down onto the field
DOLLY = (3.6, 30.0)               # camera distance from the back of the head, start -> end
LENS = 35
# the approved barrage burst ~70 blocks from the field (test_finale) with lights of 150000; here the
# bursts are 64-80 blocks from the first line, 10-35 blocks from the hero, so the same perceived
# light is about (70 / 31)^2 = 5 times less
LIGHT = 30000.0


def sky():
    SKY.apply(tick=18000, rain=0.0, render_distance=12, ground_mc_y=64.0 - HY, frame_start=FRAMES[0],
              haze=L.LOOKS["finale"]["haze"])
    for n in ("MC.Stars", "MC.Moon", "MC.Sun", "MC.Clouds"):
        bpy.data.objects[n].hide_render = bpy.data.objects[n].hide_viewport = True
    bpy.data.objects["MC.SunLight"].data.energy = 0.0


def hero():
    with contextlib.redirect_stdout(io.StringIO()):
        rig = C.villager("Hero", skin="plains_farmer", helmet="iron", legs="iron", boots="iron", elytra=True)
    FL.kneel(rig, "front", HX + 0.5, HZ + 0.5, yaw=-math.pi / 2)          # facing west (-X)
    bpy.context.view_layer.update()
    pb = rig.pose.bones["head"]
    neck, top = rig.matrix_world @ pb.head, rig.matrix_world @ pb.tail
    return rig, (neck + top) / 2


def fallen():
    avoid = [(HX + 0.5, HZ + 0.5, 3.0), (K["poppy"][0] + 0.5, K["poppy"][2] + 0.5, 1.5),
             (HX + 4.0, HZ + 0.5, 2.6)]                                   # the camera's first metres
    area = (HX - 45, K["wire_x"] - 4, HZ - 42, HZ + 42)
    spots = FL.scatter(N_FALLEN, area, "front", avoid=avoid, seed=27)
    rigs = FL.field(spots, "front", seed=27)
    print("FALLEN", len(rigs), sorted({r["mc_fallen"] for r in rigs}))
    return rigs


def camera(head):
    """Dolly straight back along the view axis: the head stays centred, the pitch is constant."""
    sc = bpy.context.scene
    cam = bpy.data.objects.get("Cam.Finale")
    if cam is None:
        cam = bpy.data.objects.new("Cam.Finale", bpy.data.cameras.new("Cam.Finale"))
        sc.collection.objects.link(cam)
        cam.data.lens = LENS
    look = Vector((-math.cos(PITCH), 0.0, math.sin(PITCH)))               # west and a little down
    cam.rotation_euler = look.to_track_quat('-Z', 'Y').to_euler()
    f0, f1 = FRAMES
    for f in range(f0, f1 + 1, 4):
        t = (f - f0) / (f1 - f0)
        t = t * t * (3 - 2 * t)                                           # ease in and out
        d = DOLLY[0] + (DOLLY[1] - DOLLY[0]) * t
        cam.location = head - look * d
        cam.keyframe_insert("location", frame=f)
    sc.camera = cam
    return cam


def barrage():
    fx = bpy.data.collections.new("FX")
    bpy.context.scene.collection.children.link(fx)
    FW.set_flash_gain(0.35)
    cloud = FW.Cloud(seed=27)
    eye = HY + 1.5
    bursts = SV.barrage(cloud, (L1, -(HZ - 70), eye), (L1, -(HZ + 70), eye), (-1, 0), FRAMES[0] - 140, FRAMES[1],
                        seed=27, shots_per_second=3.5, pitch=(12.0, 28.0), light_peak=LIGHT,
                        collection=fx, name="Alex")
    cloud.build("FX.Particles", fx)
    print("BURSTS", len(bursts))


def build():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for c in list(bpy.data.collections):
        bpy.data.collections.remove(c)
    bpy.data.orphans_purge(do_recursive=True)
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE'
    sc.render.resolution_x, sc.render.resolution_y = 1920, 804
    sc.render.fps = 24
    sc.frame_start, sc.frame_end = FRAMES
    sc.eevee.taa_render_samples = 32
    sc.eevee.shadow_pool_size = '1024'
    SET.load("front")
    _rig, head = hero()
    fallen()
    camera(head)
    sky()
    barrage()                     # after the scene camera: particles face it (HANDOFF pitfall 23)
    L.apply("finale")


def render(percent, frames):
    sc = bpy.context.scene
    os.makedirs(OUT, exist_ok=True)
    sc.render.resolution_percentage = percent
    for f in frames:
        sc.frame_set(f)
        sc.render.filepath = os.path.join(OUT, f"finale_{f:03d}_v1.png")
        bpy.ops.render.render(write_still=True)
        print("RENDERED", sc.render.filepath)


args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if args[:1] == ["render"]:
    render(int(args[1]) if len(args) > 1 else 50, [int(a) for a in args[2:]] or [1, 160, 320])
else:
    build()
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, "blender", "front_finale.blend"))
    print("SAVED")
