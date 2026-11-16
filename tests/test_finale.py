"""Finale test (shots 25-28): the wounded hero against the trench wall, fallen elytra soldiers,
black sky without stars or moon, Alex's barrage going on overhead. Build in background:
    blender -b --factory-startup --python tests/test_finale.py
-> blender/test_finale.blend (render it separately, then check with tools/flash_check.py).
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

sys.path.insert(0, r"C:\Dev\Projects\CinemaShort\tools")
import mc_character as C
import mc_firework as FW
import mc_look as L
import mc_motion as M
import mc_salvo as SV
import mc_sky as SKY

ROOT = r"C:\Dev\Projects\CinemaShort"
RP = os.path.join(ROOT, r"assets\mc_rp\assets\minecraft\textures\block")
FRAMES = (1, 192)                 # 8 s

# ---------------------------------------------------------------- empty scene, project settings
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
sc = bpy.context.scene
sc.render.engine = 'BLENDER_EEVEE'
sc.render.resolution_x, sc.render.resolution_y = 1920, 804
sc.render.fps = 24
sc.eevee.taa_render_samples = 32
sc.frame_start, sc.frame_end = FRAMES


def block_box(name, png, lo, hi):
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    lo, hi = Vector(lo), Vector(hi)
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector(lo[i] + (v.co[i] + 0.5) * (hi[i] - lo[i]) for i in range(3))
    for f in bm.faces:
        ax = max(range(3), key=lambda i: abs(f.normal[i]))
        u_ax, v_ax = ((0, 1) if ax == 2 else ((1, 2) if ax == 0 else (0, 2)))
        for loop in f.loops:
            loop[uvl].uv = (loop.vert.co[u_ax], loop.vert.co[v_ax])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    mat = C.material("block." + os.path.basename(png)[:-4], png, rough=0.9, spec=0.15)
    next(n for n in mat.node_tree.nodes if n.type == 'TEX_IMAGE').extension = 'REPEAT'
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    sc.collection.objects.link(ob)
    return ob


# battlefield: mud ground, the trench wall (dirt) the hero leans on, a few coarse-dirt mounds
block_box("Set.Ground", os.path.join(RP, "mud.png"), (-200, -200, -1), (200, 200, 0))
block_box("Set.Wall", os.path.join(RP, "dirt.png"), (-6, 0.35, 0), (6, 1.35, 1.5))
block_box("Set.Parapet", os.path.join(RP, "coarse_dirt.png"), (-6, 1.35, 0), (6, 3.35, 1.0))
for i, (x, y) in enumerate(((-3.5, -2.5), (4.0, -3.5), (-1.0, -6.0))):
    block_box(f"Set.Mound{i}", os.path.join(RP, "coarse_dirt.png"), (x, y, 0), (x + 2, y + 1, 0.5))

# ---------------------------------------------------------------- characters
hero = C.villager("Hero", skin="plains_farmer", helmet="iron", legs="iron", boots="iron", elytra=True,
                  location=(0.0, 0.1, 0.0))
fallen = []
for i, (x, y, rz) in enumerate(((-2.6, -1.6, 30), (2.9, -2.2, -70))):
    r = C.villager(f"Fallen{i}", skin="plains_plain", helmet="iron", legs="iron", boots="iron", elytra=True)
    r.rotation_mode = 'XYZ'
    r.rotation_euler = (math.radians(-90), 0, math.radians(rz))     # face down in the mud
    r.location = (x, y, 0.2)
    C.set_wing_pose(r, *C.WING_GLIDE)
    fallen.append(r)

# the hero sits on the ground against the wall, head raised to the sky, arms slack
A = M.Actor(hero, yaw=0.0)                 # faces -Y: towards the camera, the barrage behind him
A.sit(0, 10_000, seat_height_px=0, ramp=1)
A.look(0, 10_000, Vector((0.6, -15.0, 20.0)))   # up into the sky (head yaw is limited to 75 deg)
M.bake([A], int((FRAMES[1] - FRAMES[0]) * 20 / 24) + 1, frame0=FRAMES[0])
C.set_wing_pose(hero, *C.WING_CROUCH)

# ---------------------------------------------------------------- camera
cd = bpy.data.cameras.new("Cam.Finale")
cam = bpy.data.objects.new("Cam.Finale", cd)
sc.collection.objects.link(cam)
cam.location = (1.7, -3.7, 0.7)
# 2.39:1 at 20 mm is only 41 deg tall: tilt ~8 deg up keeps the seated hero whole and the bursts in
cam.rotation_euler = (Vector((-0.3, 4.0, 1.85)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
cd.lens = 20
sc.camera = cam

# ---------------------------------------------------------------- sky: midnight, then black (no stars, no moon)
SKY.apply(tick=18000, rain=0.0, render_distance=12, ground_mc_y=64.0, frame_start=FRAMES[0],
          haze=L.LOOKS['finale']['haze'])
for n in ("MC.Stars", "MC.Moon", "MC.Sun", "MC.Clouds"):
    bpy.data.objects[n].hide_render = bpy.data.objects[n].hide_viewport = True
bpy.data.objects["MC.SunLight"].data.energy = 0.0

# ---------------------------------------------------------------- the barrage
fx = bpy.data.collections.new("FX")
sc.collection.children.link(fx)
FW.set_flash_gain(0.35)
cloud = FW.Cloud(seed=25)
# Alex's trench 140 blocks behind the hero: rockets (64-80 blocks) burst ~70 blocks from the camera
bursts = SV.barrage(cloud, (-90, 140, 1.5), (90, 140, 1.5), (0, -1), FRAMES[0] - 140, FRAMES[1],
                    seed=25, shots_per_second=3.5, pitch=(12.0, 28.0), light_peak=150000.0,
                    collection=fx, name="Alex")
cloud.build("FX.Particles", fx)
print("BURSTS", len(bursts), "in frames", FRAMES)

L.apply("finale")
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, "blender", "test_finale.blend"))
print("SAVED")
