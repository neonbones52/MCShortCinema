"""Location 4 in Blender: the front (shots 18-28). Imports the front OBJ, night sky with the moon
(the ambush; the finale's black sky is mc_sky's business at shot time), the night look, Alex's
36 soldiers (stand-ins: villagers in chainmail) on the fire steps facing west, Alex's banners in
the rear, the hero standing on his finale spot facing west; survey cameras; saves
blender/sets/front.blend.

First build the set:   python tools/build_set.py front
Then (in the live Blender through MCP, or in background):
    exec(open(r"C:\\Dev\\Projects\\CinemaShort\\tests\\test_front.py", encoding="utf-8").read())
    blender -b --python tests/test_front.py          (user prefs: MCprep needs them)
Survey stills (background, the .blend is not saved):
    blender -b blender/sets/front.blend --python tests/test_front.py -- render [percent]
-> renders/tests/front/<camera>_v1.png
"""
import contextlib
import io
import math
import os
import sys

import bpy

sys.path.insert(0, r"C:\Dev\Projects\CinemaShort\tools")
import importlib
import mc_banner as BN
import mc_character as C
import mc_look as L
import mc_motion as M
import mc_set as SET
import mc_sky as SKY
for _m in (SET, BN, M):
    importlib.reload(_m)

ROOT = r"C:\Dev\Projects\CinemaShort"
OUT = os.path.join(ROOT, "renders", "tests", "front")
LOOK = "night"
TICK = 14500
K = SET.marks("front")
HX, HY, HZ = K["hero"]
L1 = K["lines_x"][0]
Above = SET.Above
WEST = -math.pi / 2                                  # yaw facing -X
S5 = K["soldiers"][5]                                # a fire-step place on the first line

CAMS = {
    "Cam.Wide": ((170, Above(28), 110), (305, Above(0), 175), 24),                    # shot 18: over the lines
    "Cam.Trench": ((S5[0] + 2.0, S5[1] + 0.4, S5[2] - 4.5), (S5[0], S5[1] + 1.7, S5[2]), 20),   # shot 19 (same bay)
    "Cam.Nomans": ((K["wire_x"] - 26, Above(1.8), 150), (L1, Above(1.2), 160), 28),   # no-man's land to the lines
    "Cam.Hero": ((HX + 3.5, Above(1.7), HZ + 0.6), (HX - 40, Above(9), HZ), 28),      # shot 25: over his shoulder, west
    "Cam.Field": ((HX + 28, Above(16), HZ + 14), (HX - 25, Above(0), HZ - 4), 24),    # shot 27: the end of the dolly
}


def use_camera(name):
    sc = bpy.context.scene
    sc.camera = bpy.data.objects[name]
    SKY.apply(tick=TICK, rain=0.0, render_distance=12, ground_mc_y=64.0 - HY, haze=L.LOOKS[LOOK]["haze"])


def cast():
    actors = []
    mail = dict(helmet="chainmail", chest="chainmail", legs="chainmail", boots="chainmail")
    with contextlib.redirect_stdout(io.StringIO()):
        for i, (x, y, z) in enumerate(K["soldiers"]):
            rig = C.villager(f"Alex{i:02d}", skin="plains_plain", **mail)
            actors.append(M.Actor(rig, pos=SET.b(x, y, z), yaw=WEST))
        hero = C.villager("Hero", skin="plains_farmer", helmet="iron", legs="iron", boots="iron", elytra=True)
        actors.append(M.Actor(hero, pos=SET.b(HX + 0.5, HY + 1, HZ + 0.5), yaw=WEST))
    M.bake(actors, 2)
    for i, blk in enumerate(K["alex_banners"]):
        b = BN.empire("alex", f"Banner.Alex{i}")
        BN.place(b, blk, rotation=4)                   # front to the west (towards the plain)
        BN.animate(b, 1, 250)


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
    sc.eevee.taa_render_samples = 32
    sc.eevee.shadow_pool_size = '1024'
    SET.load("front")
    cast()
    SET.cameras(CAMS, "front")
    use_camera("Cam.Wide")
    L.apply(LOOK)


def render(percent=100):
    sc = bpy.context.scene
    os.makedirs(OUT, exist_ok=True)
    sc.render.resolution_percentage = percent
    sc.render.image_settings.file_format = 'PNG'
    for name in CAMS:
        use_camera(name)
        sc.render.filepath = os.path.join(OUT, name.replace("Cam.", "").lower() + "_v1.png")
        bpy.ops.render.render(write_still=True)
        print("RENDERED", sc.render.filepath)
    sc.render.resolution_percentage = 100
    use_camera("Cam.Wide")


args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if args[:1] == ["render"]:
    render(int(args[1]) if len(args) > 1 else 100)
else:
    build()
    os.makedirs(os.path.join(ROOT, "blender", "sets"), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, "blender", "sets", "front.blend"))
    print("SAVED", len(bpy.data.objects["Set.front"].data.polygons), "faces")
