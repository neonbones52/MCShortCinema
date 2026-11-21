"""Location 1 in Blender: imports the village OBJ, sets the morning sky and the village look,
puts down survey cameras and saves blender/sets/village.blend.

First build the set:   python tools/build_set.py village
Then (in the live Blender through MCP, or in background):
    exec(open(r"C:\\Dev\\Projects\\CinemaShort\\tests\\test_village.py", encoding="utf-8").read())
    blender -b --python tests/test_village.py      (user prefs: MCprep needs them, not --factory-startup)
Survey stills (background, the .blend is not saved):
    blender -b blender/sets/village.blend --python tests/test_village.py -- render [percent]
-> renders/tests/village/<camera>_v1.png
"""
import os
import sys

import bpy

sys.path.insert(0, r"C:\Dev\Projects\CinemaShort\tools")
import importlib
import mc_look as L
import mc_set as SET
import mc_sky as SKY
importlib.reload(SET)

ROOT = r"C:\Dev\Projects\CinemaShort"
OUT = os.path.join(ROOT, "renders", "tests", "village")
LOOK = "village"
TICK = 1000                       # morning, the sun 27.5 deg up in the east
M = SET.marks("village")
PX, PY, PZ = M["poppy"]
FX0, FX1, FZ0, FZ1 = M["field"]
CX, CY, CZ = M["crest"]
SQ = M["meeting"]

Above = SET.Above


# name: (position, target, lens) in set coordinates (X east, Y up, Z south)
CAMS = {
    "Cam.Wide": ((100, 38, 300), (215, 14, 200), 24),                       # shot 01: the whole place
    "Cam.Poppy": ((PX + 0.5, PY + 0.45, PZ - 1.6), (PX + 0.5, PY + 0.5, PZ + 3), 35),   # shot 02
    "Cam.Farm": ((FX0 - 22, M["field_level"] + 5, FZ1 + 1), (FX0 + 10, M["field_level"] + 0.5, FZ0 + 2), 28),
    "Cam.Field": ((FX0 + 5, M["field_level"] + 2.8, FZ0 + 8), (CX, CY + 2, CZ), 50),    # shot 05: to the crest
    "Cam.Crest": ((CX + 2, CY + 3.5, CZ - 4), (FX0 + 10, M["field_level"] + 1, FZ0 - 4), 35),
    "Cam.Street": ((SQ[0] - 32, Above(1.7), SQ[2] + 3.5), (SQ[0], SQ[1] + 2.5, SQ[2]), 24),
    "Cam.Square": ((SQ[0] - 9, SQ[1] + 4, SQ[2] + 9), (SQ[0], SQ[1] + 1.5, SQ[2] - 1), 22),
}


def use_camera(name):
    sc = bpy.context.scene
    sc.camera = bpy.data.objects[name]
    SKY.apply(tick=TICK, rain=0.0, render_distance=12, ground_mc_y=64.0 - M["field_level"],
              haze=L.LOOKS[LOOK]["haze"])


def build():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE'
    sc.render.resolution_x, sc.render.resolution_y = 1920, 804
    sc.render.fps = 24
    sc.eevee.taa_render_samples = 32
    sc.eevee.shadow_pool_size = '1024'
    SET.load("village")
    SET.cameras(CAMS, "village")
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
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, "blender", "sets", "village.blend"))
    print("SAVED", len(bpy.data.objects["Set.village"].data.polygons), "faces")
