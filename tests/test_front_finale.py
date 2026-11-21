"""Finale stand on the real front (shots 25-27, user 2026-11-21): the field of the fallen is in
Alex's rear, behind the crossbowmen's backs; the hero kneels there 75 blocks behind the last
trench, looking west, back where he flew from; ahead of him, over the trenches, Alex's barrage
keeps going up into the sky (air defence) with the approved density, pitch and flash (3.5
shots/s from the three lines, pitch 12-28, flash x0.35) and bursts 64-80 blocks beyond the
lines, far in the background. Dozens of the fallen (mc_fallen: lying poses only, torn wings, no
profession hats). Black sky, the finale look. The camera (shot 27): a dolly straight back along
its own axis, the back of the hero's head dead centre, a slight downward pitch, no crane up.

    blender -b --python tests/test_front_finale.py            -> blender/front_finale.blend
    blender -b blender/front_finale.blend --python tests/test_front_finale.py -- render [percent] [frames...]
-> renders/tests/front/finale_<frame>_v1.png
"""
import contextlib
import io
import math
import os
import random
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
N_RIGHT = 14                      # extra on the right of the dolly
PITCH = math.radians(-3.0)        # slight look down onto the field; the barrage on the horizon in frame
DOLLY = (3.6, 30.0)               # camera distance from the back of the head, start -> end
LENS = 28                         # a 2.39 frame is only 30 deg high at 28 mm
# the bursts are 135-185 blocks from the field (the approved test lit a field ~70 blocks away
# with 150000): about (160 / 70)^2 ~ 5 times more for the same light on the bodies
LIGHT = 600000.0
FIRE_PITCH = (12.0, 28.0)          # approved
# no moon, no stars: the even sky fill is cut to a fifth (it lit the whole field flat); the
# bursts light the field through one shadowed key light (mc_salvo.key_light) that takes 3/4 of
# their light, the shadowless burst lamps keep 1/4 for the coloured glints
AMBIENT = 0.07
KEY_SHARE = 0.75


def sky():
    SKY.apply(tick=18000, rain=0.0, render_distance=12, ground_mc_y=64.0 - HY, frame_start=FRAMES[0],
              haze=L.LOOKS["finale"]["haze"], ambient=AMBIENT)
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
    # the line of sight from the camera to the hero stays clear for the whole dolly
    avoid += [(HX + 0.5 + d, HZ + 0.5, 1.9) for d in range(6, 34, 2)]
    avoid += [(t[0], t[2] + 2, 6.0) for t in K["tents"]]                  # not on Alex's tents
    area = (K["lines_x"][-1] + 14, K["size"][0] - 8, HZ - 42, HZ + 42)    # Alex's rear
    spots = FL.scatter(N_FALLEN, area, "front", avoid=avoid, seed=27)
    rigs = FL.field(spots, "front", seed=27)
    # the right of the dolly (north of the axis) was a bare patch (user): more of the fallen there
    near = avoid + [(x, z, 2.4) for x, z in spots]
    right = FL.scatter(N_RIGHT, (HX + 3, HX + 40, HZ - 34, HZ - 3), "front", avoid=near, seed=28)
    rigs += FL.field(right, "front", seed=28, start=len(rigs))
    # one face down 7 blocks behind the hero, 2 blocks right of the axis, reaching towards him: the
    # camera passes over him and he stays in frame (user); low, he does not hide the hero
    behind = FL.body(f"Fallen{len(rigs):02d}", "front", HX + 7.5, HZ + 0.5 - 2.2, "prone_reach",
                     -math.pi / 2, random.Random(29), helmet="iron", wings=1)
    C.set_wing_pose(behind, 0.12, 0.0, -0.35)          # wings down on his back: no spike beside the hero
    rigs.append(behind)
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
    low = None                                                            # never into the ground
    for f in range(f0, f1 + 1, 4):
        sc.frame_set(f)
        hit = SET._set_ray(cam.matrix_world.translation, (0, 0, -1), "front")
        h = None if hit is None else cam.matrix_world.translation.z - hit[0].z
        low = h if low is None or (h is not None and h < low) else low
    sc.frame_set(f0)
    print("CAMERA lowest clearance over the dolly", low)
    if low is None or low < 1.2:
        raise RuntimeError(f"the dolly runs too low over the ground: {low}")
    return cam


def barrage():
    fx = bpy.data.collections.new("FX")
    bpy.context.scene.collection.children.link(fx)
    FW.set_flash_gain(0.35)
    cloud = FW.Cloud(seed=27)
    lines = K["lines_x"]
    eye = sum(p[1] for p in K["soldiers"]) / len(K["soldiers"]) + 1.5
    n = 0
    for i, lx in enumerate(lines):                  # every line fires west, a third of the approved rate each
        bursts = SV.barrage(cloud, (lx + 1.5, -(HZ - 80), eye), (lx + 1.5, -(HZ + 80), eye), (-1, 0),
                            FRAMES[0] - 140, FRAMES[1], seed=27 + i, shots_per_second=3.5 / len(lines),
                            pitch=FIRE_PITCH, light_peak=LIGHT, collection=fx, name=f"Alex{i}")
        n += len(bursts)
    cloud.build("FX.Particles", fx)
    lights = [o for o in fx.objects if o.type == 'LIGHT']
    SV.key_light(lights, Vector((HX + 0.5, -(HZ + 0.5), HY + 1.0)), FRAMES[0], FRAMES[1], share=KEY_SHARE,
                 collection=fx)
    bursts = [None] * n
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
    sc.eevee.use_raytracing = True                # horizon scan: contact shading in folds and under bodies
    sc.eevee.ray_tracing_method = 'SCREEN'
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
