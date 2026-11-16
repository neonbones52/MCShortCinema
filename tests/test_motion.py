"""Test scene: walk + gestures (staff room). Run inside Blender on blender/test_motion.blend:
    exec(open(r"C:\\Dev\\Projects\\CinemaShort\\tests\\test_motion.py", encoding="utf-8").read())
Soldiers sit on slabs, the officer points at the map with a stick, Steve (netherite) walks in,
everyone gets up and salutes, the sergeant hands a rocket over, a soldier swings (game punch).
"""
import math
import os
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, r"C:\Dev\Projects\CinemaShort\tools")
import importlib
import mc_character as C
import mc_motion as M
importlib.reload(C)
importlib.reload(M)

RP = r"C:\Dev\Projects\CinemaShort\assets\mc_rp\assets\minecraft\textures\block"
sc = bpy.context.scene


def wipe(prefix):
    for col in [c for c in bpy.data.collections if c.name.startswith(prefix)]:
        for o in list(col.all_objects):
            bpy.data.objects.remove(o, do_unlink=True)
        bpy.data.collections.remove(col)


for p in ("Set", "Officer", "S1", "S2", "S3", "S4", "SalTest"):
    wipe(p)
if "LookDev.Ground" in bpy.data.objects:
    bpy.data.objects["LookDev.Ground"].hide_render = True
    bpy.data.objects["LookDev.Ground"].hide_viewport = True

setcol = bpy.data.collections.new("Set")
sc.collection.children.link(setcol)


def block_box(name, png, lo, hi, tile=True):
    """Axis-aligned box in blocks, UVs one texture per block face (like the game)."""
    import bmesh
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    lo, hi = Vector(lo), Vector(hi)
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((lo[i] + (v.co[i] + 0.5) * (hi[i] - lo[i]) for i in range(3)))
    for f in bm.faces:
        n = f.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        u_ax, v_ax = [i for i in range(3) if i != ax]
        if ax != 2:
            u_ax, v_ax = (0 if ax == 1 else 1), 2
        for loop in f.loops:
            co = loop.vert.co
            loop[uvl].uv = (co[u_ax], co[v_ax]) if tile else (0, 0)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    mat = C.material("block." + os.path.basename(png)[:-4], png, rough=0.85, spec=0.2)
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    setcol.objects.link(ob)
    return ob


floor = block_box("Set.Floor", os.path.join(RP, "spruce_planks.png"), (-5, -5, -1), (6, 8, 0))
wall = block_box("Set.Wall", os.path.join(RP, "stone_bricks.png"), (-6, -5, 0), (-5, 8, 4))
seats = []
SEAT_Y = (-2.1, -0.9, 0.3, 1.5)
for i, y in enumerate(SEAT_Y):
    seats.append(block_box(f"Set.Slab{i}", os.path.join(RP, "oak_planks.png"),
                           (-0.3 - 0.5 + 0.3, y - 0.5, 0), (-0.3 + 0.5 + 0.3, y + 0.5, 0.5)))
for m in bpy.data.materials:
    if m.name.startswith("block."):
        tex = next(n for n in m.node_tree.nodes if n.type == 'TEX_IMAGE')
        tex.extension = 'REPEAT'

# the map on the wall: 2x2 maps (placeholder texture until the user's 128x128 map)
import bmesh
bm = bmesh.new()
uvl = bm.loops.layers.uv.new("UVMap")
vs = [bm.verts.new(p) for p in ((-4.97, 1.0, 1.0), (-4.97, -1.0, 1.0), (-4.97, -1.0, 3.0), (-4.97, 1.0, 3.0))]
f = bm.faces.new(vs)
for loop, uv in zip(f.loops, ((0, 0), (2, 0), (2, 2), (0, 2))):
    loop[uvl].uv = uv
me = bpy.data.meshes.new("Set.Map")
bm.to_mesh(me)
bm.free()
mmat = C.material("map.background", r"C:\Dev\Projects\CinemaShort\assets\mc\textures\map\map_background.png", rough=0.95, spec=0.1)
next(n for n in mmat.node_tree.nodes if n.type == 'TEX_IMAGE').extension = 'REPEAT'
me.materials.append(mmat)
mapob = bpy.data.objects.new("Set.Map", me)
setcol.objects.link(mapob)
MAP_POINT = Vector((-4.95, 0.3, 2.2))

# ---------------------------------------------------------------- cast
EAST, WEST = math.pi / 2, -math.pi / 2          # facing +X / -X
steve = bpy.data.objects["Steve.rig"]
for b in steve.pose.bones:
    b.rotation_mode = 'QUATERNION'
    b.rotation_quaternion = (1, 0, 0, 0)
officer = C.villager("Officer", skin="plains_plain", helmet="diamond", chest="iron", legs="iron", boots="iron",
                     item_r="stick", location=(-3.9, 0.3, 0))
iron = dict(helmet="iron", chest="iron", legs="iron", boots="iron")
s1 = C.villager("S1", skin="plains_weaponsmith", location=(0.0, SEAT_Y[0], 0), **iron)
s2 = C.villager("S2", skin="plains_armorer", location=(0.0, SEAT_Y[1], 0), **iron)
s3 = C.villager("S3", skin="plains_farmer", helmet="iron", legs="iron", boots="iron", elytra=True,
                location=(0.0, SEAT_Y[2], 0))                      # the hero: no chestplate + elytra
s4 = C.villager("S4", skin="plains_plain", item_r="firework_rocket", location=(0.0, SEAT_Y[3], 0), **iron)   # sergeant
rocket2 = C.attach_item("S3", s3, bpy.data.collections["S3"], "firework_rocket")
rocket1 = bpy.data.objects["S4.item.R"]
for r in (officer, s1, s2, s3, s4):
    print(r.name, C.coplanar_report(r))

# ---------------------------------------------------------------- performance (ticks, 20/s)
A_off = M.Actor(officer, yaw=M.yaw_of(MAP_POINT - Vector((-3.9, 0.3, 0))))
A_st = M.Actor(steve, pos=(3.2, 7.5, 0), yaw=M.yaw_of(Vector((-0.8, -3.0, 0))))
soldiers = [M.Actor(r, yaw=WEST) for r in (s1, s2, s3, s4)]
A1, A2, A3, A4 = soldiers

STEVE_IN, STEVE_STOP = 50, None
A_st.walk(STEVE_IN, [(3.2, 7.5, 0), (2.4, 4.5, 0), (-0.9, 3.4, 0)], speed=0.2159)
A_st.face(0, Vector((-0.3, -0.3, 0)))
A_st.look(60, 220, Vector((-0.3, -0.3, 1.5)))
A_st.salute(96, 128)

A_off.face(0, MAP_POINT)
A_off.look(0, 62, MAP_POINT)
A_off.point(4, 58, MAP_POINT, jabs=(18, 34))
A_off.face(62, A_st)
A_off.look(62, 220, A_st)
A_off.salute(86, 128)

for i, a in enumerate(soldiers):
    a.sit(0, 74 + 2 * i, seat_height_px=8)
    a.look(0, 56 + 3 * i, MAP_POINT)
    a.look(56 + 3 * i, 140, A_st)
    a.salute(86 + 2 * i, 128)

# sergeant (S4) steps out and hands a rocket to the hero (S3); placed so that both stay in profile
A4.walk(138, [(0.0, SEAT_Y[3], 0), (-0.88, 0.96, 0)], speed=0.12)
A4.face(150, A3)
A4.look(138, 220, A3)
A4.hold_out(150, 176, A3)
A3.face(140, A4)
A3.look(140, 220, A4)
A3.hold_out(156, 168, A4, ramp=5)
A3.hold_item(166, 220)
HANDOVER = 164
# S1 (nearest to the camera) swings twice: the game's punch
A1.face(150, Vector((-2.0, -3.6, 0)))
A1.look(150, 220, Vector((-2.0, -3.6, 1.2)))
A1.swing(184)
A1.swing(196)

TICKS = 220
actors = [A_st, A_off] + soldiers
for r in [a.rig for a in actors]:
    if r.animation_data:
        r.animation_data_clear()
M.bake(actors, TICKS, frame0=1)

# the rocket changes hands
f_hand = 1 + HANDOVER * 24 / 20
for ob, vis_before in ((rocket1, True), (rocket2, False)):
    if ob.animation_data:
        ob.animation_data_clear()
    for fr, vis in ((1, vis_before), (f_hand, not vis_before)):
        ob.hide_render = ob.hide_viewport = not vis
        ob.keyframe_insert("hide_render", frame=fr)
        ob.keyframe_insert("hide_viewport", frame=fr)

sc.frame_start, sc.frame_end = 1, int(1 + TICKS * 24 / 20)

# ---------------------------------------------------------------- camera
cam = bpy.data.objects.get("Motion.Cam")
if cam is None:
    cd = bpy.data.cameras.new("Motion.Cam")
    cam = bpy.data.objects.new("Motion.Cam", cd)
    sc.collection.objects.link(cam)
cam.data.lens = 24
cam.location = (-4.7, -4.4, 1.75)
d = Vector((-0.4, 1.0, 1.0)) - cam.location
cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
sc.camera = cam
print("frames", sc.frame_start, sc.frame_end)
