"""Location 2 in Blender: the training ground (shots 09-13). Imports the drill OBJ, sets the
overcast sky and the cold look, puts the line of 16 recruits (stand-ins: villagers in iron
without the chestplate, with elytra) on the square, survey cameras, saves blender/sets/drill.blend.

First build the set:   python tools/build_set.py drill
Then (in the live Blender through MCP, or in background):
    exec(open(r"C:\\Dev\\Projects\\CinemaShort\\tests\\test_drill.py", encoding="utf-8").read())
    blender -b --python tests/test_drill.py        (user prefs: MCprep needs them, not --factory-startup)
Survey stills (background, the .blend is not saved):
    blender -b blender/sets/drill.blend --python tests/test_drill.py -- render [percent]
-> renders/tests/drill/<camera>_v1.png
"""
import math
import os
import sys

import bpy

sys.path.insert(0, r"C:\Dev\Projects\CinemaShort\tools")
import importlib
import mc_banner as BN
import mc_character as C
import mc_look as L
import mc_set as SET
import mc_sky as SKY
importlib.reload(SET)
importlib.reload(BN)

ROOT = r"C:\Dev\Projects\CinemaShort"
OUT = os.path.join(ROOT, "renders", "tests", "drill")
LOOK = "cold"
TICK, RAIN = 6000, 1.0            # overcast as approved (sky v2): rain level 1 without the rain
M = SET.marks("drill")
LV = M["level"]                   # top block of the square: feet at LV + 1
LINE = M["line"]
Above = SET.Above
SKINS = ("plains_farmer", "plains_plain", "plains_armorer", "plains_weaponsmith")

# name: (position, target, lens) in set coordinates (X east, Y up, Z south)
CAMS = {
    "Cam.Wide": ((150, Above(24), 178), (82, LV + 2, 116), 24),                        # the whole ground
    "Cam.Line": ((55, Above(2.0), LINE[0][2] - 8), (71, LV + 3.0, LINE[0][2] + 5), 28),     # shots 09-10
    "Cam.Fort": ((72, Above(1.7), LINE[0][2] + 6), (70, LV + 5, M["gate_south"][2]), 24),   # behind the line
    "Cam.Range": ((128, Above(5), 160), (126, LV + 2, M["range_centre_z"]), 24),       # shot 11: haystacks
    "Cam.Flight": ((140, Above(12), 140), (260, Above(10), M["range_centre_z"]), 35),  # shot 12 height
    "Cam.Low": ((228, Above(0.5), 142), (240, Above(16), 130), 18),                    # shot 13: from below
}


def use_camera(name):
    sc = bpy.context.scene
    sc.camera = bpy.data.objects[name]
    SKY.apply(tick=TICK, rain=RAIN, render_distance=12, ground_mc_y=64.0 - LV, haze=L.LOOKS[LOOK]["haze"])


def recruits():
    """Stand-ins for scale: the line faces north (the fort); rigs face -Y unturned."""
    for i, (x, y, z) in enumerate(LINE):
        rig = C.villager(f"Recruit{i:02d}", skin=SKINS[i % len(SKINS)], helmet="iron", legs="iron",
                         boots="iron", elytra=True)
        rig.location = SET.b(x + 0.5, y + 1, z + 0.5)          # feet on the block top y
        rig.rotation_euler = (0, 0, math.pi)


def banners(frame_end=250):
    """Steve's banner (user, 2026-11-21: "wherever, as long as it reads in the shots"), placed
    as the game would allow: wall banners hang on the block face behind them, standing ones stand
    on a block. Gatehouse: two on the south gallery under the eaves (Cam.Fort, behind the line).
    Square: four on fence posts along the south edge facing the line, above the recruits' heads
    (the background of shots 09-10).
    Range: one on the west face of every gate's crossbar, facing the launch line (shots 12-13)."""
    gx0 = M["fort_origin"][0] + 26                    # the south gatehouse: x gx0..gx0+7 (fort.py bx0..bx1)
    gz = M["gate_south"][2] + 2                       # the block in front of its gallery wall
    sx0, sx1, sz0, sz1 = M["square"]
    spots = [("Gate.W", (gx0 + 1, LV + 8, gz), dict(wall_facing="south")),
             ("Gate.E", (gx0 + 6, LV + 8, gz), dict(wall_facing="south"))]
    for i, (x, top, z) in enumerate(M["banner_posts"]):                         # on 2-high fence posts
        spots.append((f"Square{i}", (x, top + 1, z), dict(rotation=8)))           # front to the north
    for gx, bar_y, _z0, _z1 in M["gates"]:
        spots.append((f"Range{gx}", (gx - 1, bar_y, M["range_centre_z"]), dict(wall_facing="west")))
    for tag, block, kw in spots:
        root = BN.empire("steve", "Banner." + tag, standing="wall_facing" not in kw)
        BN.place(root, block, **kw)
        BN.animate(root, 1, frame_end)


def build():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for c in list(bpy.data.collections):
        bpy.data.collections.remove(c)
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE'
    sc.render.resolution_x, sc.render.resolution_y = 1920, 804
    sc.render.fps = 24
    sc.eevee.taa_render_samples = 32
    sc.eevee.shadow_pool_size = '1024'
    SET.load("drill")
    recruits()
    banners()
    SET.cameras(CAMS, "drill")
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
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, "blender", "sets", "drill.blend"))
    print("SAVED", len(bpy.data.objects["Set.drill"].data.polygons), "faces")
