"""Follow-camera test (shots 12, 17, 20): the hero takes off, gets thrown about, levels out and
glides at ~30 blocks/s over a training ground; several cameras on the same flight.

Build (in the live Blender through MCP, or in background):
    exec(open(r"C:\\Dev\\Projects\\CinemaShort\\tests\\test_follow_cam.py", encoding="utf-8").read())
    blender -b --factory-startup --python tests/test_follow_cam.py
-> blender/test_follow_cam.blend
Render one camera (background, the .blend is not saved):
    blender -b blender/test_follow_cam.blend --python tests/test_follow_cam.py -- render Cam.Chase [percent]
-> renders/tests/follow_cam/<camera>/f####.png

Cameras:
    Cam.Chase    three-quarter from behind (shot 12)       mc_camera.follow
    Cam.Side     profile tracking, fixed compass direction  mc_camera.follow(heading=90)
    Cam.Behind   close behind, looking ahead (shot 20)      mc_camera.follow(lead=...)
    Cam.Tripod   on the ground, only the aim follows (17)   mc_camera.follow(fixed=...)
    Cam.Parent   plainly parented to the hero's rig: the comparison, not for the film
"""
import math
import os
import random
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, r"C:\Dev\Projects\CinemaShort\tools")
import importlib
import mc_camera as CAM
import mc_character as C
import mc_firework as FW
import mc_flight as F
import mc_look as L
import mc_sky as SKY
import mc_stage as ST
importlib.reload(CAM)

ROOT = r"C:\Dev\Projects\CinemaShort"
OUT = os.path.join(ROOT, "renders", "tests", "follow_cam")
FRAMES = (1, 192)                 # 8 s
TICKS = 160
LOOK = "cold"                     # the training ground: overcast, drained
START = (0.0, 0.0, 0.0)

# side/back/up in blocks from the hero's mid-body, relative to his direction of travel
CAMS = {
    "Cam.Chase": dict(side=4.5, back=6.5, up=1.2, lens=28, lag=0.55, aim_lag=0.18, screen=(-0.15, 0.0)),
    "Cam.Side": dict(side=9.0, back=-1.0, up=0.3, lens=35, lag=0.45, aim_lag=0.15, heading=90.0,
                     screen=(-0.25, 0.0)),
    # lead: 0.04 s of 33 blocks/s looks 1.3 blocks ahead; 0.25 s (8 blocks, more than the
    # camera's distance) threw him out of the frame at the take-off kick
    "Cam.Behind": dict(side=0.6, back=5.5, up=1.2, lens=24, lag=0.40, aim_lag=0.10, lead=0.04,
                       screen=(0.0, 0.05)),
    "Cam.Tripod": dict(fixed=(14.0, -9.0, 1.0), lens=35, aim_lag=0.25),
}


def smooth(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3.0 - 2.0 * x)


def pilot(t):
    """Shot 12: jump, open the wings, a rocket; thrown about; levels out; glides; one more rocket."""
    c = dict(heading=90.0, pitch=0.0, jump=t == 10, deploy=t >= 12)
    if t >= 12:
        u = t - 12
        wob = smooth(u / 8.0) * (1.0 - smooth((u - 45.0) / 25.0))        # the rough part: ticks 12..82
        c['heading'] = 90.0 + 30.0 * math.sin(u * 0.19) * wob
        # nose up, then level: stays 8-15 blocks up, low enough for the ground to rush past
        climb = -24.0 * (1.0 - smooth((u - 6.0) / 22.0))
        c['pitch'] = climb + 14.0 * math.sin(u * 0.31 + 0.8) * wob + 1.0 * smooth((u - 50.0) / 30.0)
        c['rocket'] = u < 2 or 44 <= u < 46 or 100 <= u < 102
    return c


def training_ground():
    """Things to fly past: without them a camera that keeps pace shows no speed at all."""
    rng = random.Random(12)
    ST.boxes("Set.Grass", ST.grass(), [((-400, -400, -1), (800, 400, 0))])
    # a dirt track under the flight path and a line of posts along it, one every 12 blocks
    ST.boxes("Set.Track", ST.block_mat("coarse_dirt"), [((-30, 5, 0), (520, 8, 0.02))])
    ST.boxes("Set.Posts", ST.block_mat("oak_log"), [((x, 10, 0), (x + 1, 11, 4)) for x in range(-24, 520, 12)])
    hay, stone = [], []
    for _ in range(170):
        x, y = rng.uniform(-30, 520), rng.uniform(-70, 70)
        if abs(y) < 4 or 4.5 < y < 11.5:
            continue
        x, y = math.floor(x), math.floor(y)
        w, d, h = rng.choice(((1, 1, 1), (2, 1, 1), (2, 2, 1), (2, 2, 2), (3, 2, 2)))
        (hay if rng.random() < 0.7 else stone).append(((x, y, 0), (x + w, y + d, h)))
    ST.boxes("Set.Hay", ST.block_mat("hay_block_side"), hay)
    ST.boxes("Set.Stone", ST.block_mat("cobblestone"), stone)


def use_camera(name):
    """Make `name` the scene camera: the sky and the particle billboards follow the camera."""
    sc = bpy.context.scene
    sc.camera = bpy.data.objects[name]
    SKY.apply(tick=6000, rain=1.0, render_distance=12, ground_mc_y=64.0, cloud_center=(200.0, 0.0),
              frame_start=FRAMES[0], haze=L.LOOKS[LOOK]['haze'])
    trail = bpy.data.objects.get("FX.rocket_trail")
    if trail is not None:
        FW.set_input(trail.modifiers[0], "Camera", sc.camera)


def build():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE'
    sc.render.resolution_x, sc.render.resolution_y = 1920, 804
    sc.render.fps = 24
    sc.eevee.taa_render_samples = 32
    sc.frame_start, sc.frame_end = FRAMES

    training_ground()

    hero = C.villager("Hero", skin="plains_farmer", helmet="iron", legs="iron", boots="iron", elytra=True,
                      location=START)
    fx = bpy.data.collections.new("FX")
    sc.collection.children.link(fx)
    cloud = FW.Cloud(seed=12)
    states = F.simulate(pilot, START, TICKS, ground_z=0.0, seed=12)
    F.apply(hero, states, FRAMES[0], trail=cloud, rocket_item=F.rocket_in_hand(hero, "Hero.rocket"))

    for name, kw in CAMS.items():
        CAM.follow(name, hero, FRAMES[0], FRAMES[1], **kw)

    # the comparison: a camera simply parented to the rig, at the Chase offset
    # (rig space: the model faces -Y, its right hand is -X)
    pc = bpy.data.objects.new("Cam.Parent", bpy.data.cameras.new("Cam.Parent"))
    sc.collection.objects.link(pc)
    pc.parent = hero
    pc.location = (-4.5, 6.5, 2.2)
    pc.rotation_euler = (Vector((0, 0, 1.0)) - Vector(pc.location)).to_track_quat('-Z', 'Y').to_euler()
    pc.data.lens = 28

    sc.camera = bpy.data.objects["Cam.Chase"]
    cloud.build("FX.rocket_trail", fx)
    use_camera("Cam.Chase")
    L.apply(LOOK)
    return hero, states


def render(name, percent=50):
    sc = bpy.context.scene
    use_camera(name)
    sc.render.resolution_percentage = percent
    sc.render.image_settings.file_format = 'PNG'
    sc.render.filepath = os.path.join(OUT, name.replace("Cam.", "").lower(), "f")
    bpy.ops.render.render(animation=True)
    print("RENDERED", name, sc.render.filepath)


args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if args[:1] == ["render"]:
    render(args[1], int(args[2]) if len(args) > 2 else 50)
else:
    HERO, STATES = build()
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, "blender", "test_follow_cam.blend"))
    print("SAVED", len(STATES), "ticks")
