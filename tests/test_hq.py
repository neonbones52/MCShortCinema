"""Location 3 in Blender: the HQ (shots 14-15). Imports the hq OBJ, night sky outside, the map in
its item frame on the north wall, Steve's banners either side, a lamp at every lantern, the
squad (16 stand-ins) seated, the officer at the map, Steve in the doorway; survey cameras;
saves blender/sets/hq.blend.

First build the set:   python tools/build_set.py hq      (and the map: python tools/mc_mapgen.py)
Then (in the live Blender through MCP, or in background):
    exec(open(r"C:\\Dev\\Projects\\CinemaShort\\tests\\test_hq.py", encoding="utf-8").read())
    blender -b --python tests/test_hq.py          (user prefs: MCprep needs them)
Survey stills (background, the .blend is not saved):
    blender -b blender/sets/hq.blend --python tests/test_hq.py -- render [percent]
-> renders/tests/hq/<camera>_v1.png
"""
import io
import contextlib
import math
import os
import sys

import bpy

sys.path.insert(0, r"C:\Dev\Projects\CinemaShort\tools")
import importlib
import mc_banner as BN
import mc_character as C
import mc_look as L
import mc_map as MAP
import mc_motion as M
import mc_set as SET
import mc_sky as SKY
for _m in (SET, BN, MAP, M):
    importlib.reload(_m)

ROOT = r"C:\Dev\Projects\CinemaShort"
OUT = os.path.join(ROOT, "renders", "tests", "hq")
LOOK = "night"
TICK = 14500                      # night, full moon (approved night sky)
K = SET.marks("hq")
F = K["floor"]
HX0, HX1, HZ0, HZ1 = K["hall"]
MX, MY, MZ = K["map_block"]
Above = SET.Above
LANTERN_W = 45.0                  # watts per lantern lamp
LANTERN_RGB = (1.0, 0.72, 0.42)   # warm block light
SKINS = ("plains_farmer", "plains_plain", "plains_armorer", "plains_weaponsmith")

CAMS = {
    "Cam.Map": ((MX + 2.6, F + 1.6, MZ + 3.6), (MX + 0.1, F + 1.45, MZ), 28),        # shot 14: officer, map
    "Cam.Hall": ((HX0 + 1.2, F + 3.6, HZ0 + 1.6), (MX, F + 0.8, HZ1 - 1), 18),       # shot 15: hall to the door
    "Cam.Door": ((MX + 1.5, F + 2.2, HZ1 - 1.0), (MX + 0.5, F + 1.5, HZ0 + 1), 24),   # from the back to the map
    "Cam.Outside": ((MX + 16, Above(3), HZ1 + 18), (MX, F + 3, HZ0 + 9), 24),
}


def use_camera(name):
    sc = bpy.context.scene
    sc.camera = bpy.data.objects[name]
    SKY.apply(tick=TICK, rain=0.0, render_distance=12, ground_mc_y=64.0 - (F - 1), haze=L.LOOKS[LOOK]["haze"])


def props():
    MAP.wall("HQ.Map", K["map_block"], facing=K["map_facing"])
    for i, blk in enumerate(K["banners"]):
        b = BN.empire("steve", f"Banner.HQ{i}", standing=False)
        BN.place(b, blk, wall_facing=K["banner_facing"])
        BN.animate(b, 1, 250)
    col = bpy.data.collections.new("HQ.Lights")
    bpy.context.scene.collection.children.link(col)
    for i, (x, y, z) in enumerate(K["lanterns"]):
        ld = bpy.data.lights.new(f"Lantern{i:02d}", 'POINT')
        ld.energy, ld.color, ld.shadow_soft_size = LANTERN_W, LANTERN_RGB, 0.12
        ob = bpy.data.objects.new(f"Lantern{i:02d}", ld)
        ob.location = SET.b(x, y, z)
        col.objects.link(ob)


def cast():
    """Stand-ins for scale and staging: 16 of the squad seated facing the map, the officer by the
    map turned to the hall, Steve (netherite) in the doorway."""
    actors = []
    iron = dict(helmet="iron", chest="iron", legs="iron", boots="iron")
    with contextlib.redirect_stdout(io.StringIO()):
        for i, (x, _y, z) in enumerate(K["seats"][:16]):
            rig = C.villager(f"Squad{i:02d}", skin=SKINS[i % len(SKINS)], **iron)
            a = M.Actor(rig, pos=SET.b(x, F, z), yaw=math.pi)            # facing north, the map
            a.sit(0, 10 ** 6, seat_height_px=8)
            actors.append(a)
        off = C.villager("Officer", skin="plains_plain", helmet="diamond", chest="iron", legs="iron",
                         boots="iron", item_r="stick")
        ox, oy, oz = K["officer"]
        actors.append(M.Actor(off, pos=SET.b(ox, F, oz), yaw=math.radians(-20)))
        steve = C.player("Steve", helmet="netherite", chest="netherite", legs="netherite", boots="netherite")
        dx, dy, dz = K["door"]
        actors.append(M.Actor(steve, pos=SET.b(dx + 1.0, F, dz + 0.4), yaw=math.pi))
    M.bake(actors, 2)


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
    SET.load("hq")
    props()
    cast()
    SET.cameras(CAMS, "hq")
    use_camera("Cam.Hall")
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
    use_camera("Cam.Hall")


args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if args[:1] == ["render"]:
    render(int(args[1]) if len(args) > 1 else 100)
else:
    build()
    os.makedirs(os.path.join(ROOT, "blender", "sets"), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, "blender", "sets", "hq.blend"))
    print("SAVED", len(bpy.data.objects["Set.hq"].data.polygons), "faces")
