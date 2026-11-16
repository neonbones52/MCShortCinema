"""Look-dev renders. Run in background Blender, one look per call:
    blender -b blender/test_sky.blend    --python tests/test_look.py -- village
    blender -b blender/test_sky.blend    --python tests/test_look.py -- cold
    blender -b blender/test_sky.blend    --python tests/test_look.py -- memory
    blender -b blender/test_volley.blend --python tests/test_look.py -- night
Extra args: 'raw' (no grade, Standard), 'agx' (no grade, AgX) for the view-transform comparison.
The source .blend files are not saved.
"""
import os
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, r"C:\Dev\Projects\CinemaShort\tools")
sys.path.insert(0, r"C:\Dev\Projects\CinemaShort\tests")
import mc_look as L
import mc_sky as SKY

LOOK_OUT = r"C:\Dev\Projects\CinemaShort\renders\tests\look"
os.makedirs(LOOK_OUT, exist_ok=True)
args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else ["village"]
look, mode = args[0], (args[1] if len(args) > 1 else "grade")
sc = bpy.context.scene


def cam(name, loc, target, lens):
    c = bpy.data.objects.get(name) or bpy.data.objects.new(name, bpy.data.cameras.new(name))
    if c.name not in sc.collection.objects:
        sc.collection.objects.link(c)
    c.location = loc
    c.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    c.data.lens = lens
    sc.camera = c
    return c


if look in ("village", "cold", "memory"):
    exec(open(r"C:\Dev\Projects\CinemaShort\tests\test_sky.py", encoding="utf-8").read())
    if look == "memory":
        # shot 22: wheat and the farmer, low and close
        cam("Cam.Memory", (1.5, -14.0, 3.1), (8.5, -11.5, 3.0), 45)
        tick, rain = 1000, 0.0
    else:
        s = SHOTS["morning" if look == "village" else "overcast"]
        cam(*s["cam"])
        tick, rain = s["tick"], s["rain"]
    haze = L.LOOKS[look]["haze"] if mode == "grade" else None
    SKY.apply(tick=tick, rain=rain, render_distance=12, ground_mc_y=62.0, haze=haze)
elif look == "night":
    sc.frame_set(96)                     # the volley's explosions
    haze = L.LOOKS[look]["haze"] if mode == "grade" else None
    SKY.apply(tick=14500, rain=0.0, render_distance=12, ground_mc_y=62.0, haze=haze, frame_start=1)

if mode == "grade":
    L.apply(look)
elif mode == "raw":
    L.apply("none", view_transform="Standard")
else:
    L.apply("none", view_transform="AgX")
sc.render.filepath = os.path.join(LOOK_OUT, f"{look}_{mode}_v1.png")
bpy.ops.render.render(write_still=True)
print("WROTE", sc.render.filepath)
