"""Animatic, location 3 (HQ at night): shots 14-15.

    blender -b blender/sets/hq.blend --python shots/anim_hq.py -- stills|render|save [shot ...]

14  the officer in the diamond helmet jabs the stick at the map; the squad sits and listens
15  Steve in netherite comes in through the door, everyone gets up and salutes
"""
import math
import sys

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, r"C:\Dev\Projects\CinemaShort\shots")
import importlib
import anim as A
importlib.reload(A)
import mc_character as C
import mc_look as L
import mc_motion as M
import mc_set as SET
import mc_sky as SKY

K = SET.marks("hq")
F = K["floor"]
HX0, HX1, HZ0, HZ1 = K["hall"]
MX, MY, MZ = K["map_block"]
T0 = 1597
SKINS = ("plains_plain", "plains_armorer", "plains_weaponsmith")


def T(f):
    return A.tick_of_frame(f, T0)


def b(x, y, z):
    return SET.b(x, y, z)


def pointer(rig, length=1.1, thick=0.07):
    """The officer's pointer: a stick that carries on the line of the forearm out of the fist
    (the hand bone runs shoulder -> fist), so wherever the arm points, the stick points."""
    import bmesh
    me = bpy.data.meshes.new("Officer.pointer")
    bm = bmesh.new()
    h = thick / 2
    v = [bm.verts.new((x, y, z)) for x in (-h, h) for y in (0.0, length) for z in (-h, h)]
    for f in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 2, 6, 4), (1, 5, 7, 3), (0, 4, 5, 1), (2, 3, 7, 6)):
        bm.faces.new([v[i] for i in f])
    bm.to_mesh(me)
    bm.free()
    mat = bpy.data.materials.get("Pointer.wood") or bpy.data.materials.new("Pointer.wood")
    mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (0.20, 0.11, 0.045, 1)
    bsdf.inputs["Roughness"].default_value = 0.8
    me.materials.append(mat)
    ob = bpy.data.objects.new("Officer.pointer", me)
    rig.users_collection[0].objects.link(ob)
    bone = rig.data.bones["hand.R"]
    saved = rig.matrix_world.copy()
    rig.matrix_world = Matrix.Identity(4)
    bpy.context.view_layer.update()
    mw = bone.matrix_local @ Matrix.Translation((0, 0.05, 0))      # from inside the fist, along the arm
    C.parent_to_bone(ob, rig, "hand.R")
    ob.matrix_world = mw
    rig.matrix_world = saved
    bpy.context.view_layer.update()
    return ob


def cast():
    actors = []
    kit = dict(helmet="iron", legs="iron", boots="iron", elytra=True)
    map_pt = b(MX + 0.3, MY + 0.62, MZ + 1 - 0.07)                # a place on the map (west, up)
    stand_up = T(1792)
    with A.quiet():
        for i, (x, _y, z) in enumerate(K["seats"][:16]):
            hero = i == 5
            rig = C.villager("HeroHQ" if hero else f"Squad{i:02d}", skin="plains_farmer" if hero else SKINS[i % 3], **kit)
            a = M.Actor(rig, pos=b(x, F, z), yaw=math.pi)
            up = stand_up + (i % 4) * 1.5
            a.sit(0, up, seat_height_px=8)
            # off the bench: one step forward into the gap in front of the row (the slab is underfoot otherwise)
            a.walk(up + 2, [b(x, F, z), b(x, F, z - 1.05)], speed=0.12)
            a.look(0, T(1770), map_pt)
            a.salute(T(1808) + (i % 5), T(1868), ramp=4)
            actors.append(a)
        squad = list(actors)
        off = C.villager("Officer", skin="plains_plain", helmet="diamond", chest="iron", legs="iron", boots="iron")
        pointer(off)
        # east of the map, his body to the hall and the camera, the map to his front right: the
        # stick points out to his right like a pointer (user 2026-11-21: no arm behind the back)
        oz = K["officer"][2]
        o = M.Actor(off, pos=b(MX + 2.0, F, oz), yaw=math.radians(-50))
        o.point(T(1610), T(1745), map_pt, jabs=[T(f) for f in (1640, 1676, 1700, 1724)])
        hall = b(MX + 0.5, F + 1.2, HZ0 + 7)
        o.look(T(1600), T(1636), hall)
        o.look(T(1636), T(1690), map_pt)                            # a glance at the map, then back to them
        o.look(T(1690), T(1745), hall)
        o.salute(T(1806), T(1868), ramp=4)
        actors.append(o)
        steve = C.player("Steve", helmet="netherite", chest="netherite", legs="netherite", boots="netherite")
        dx, _dy, dz = K["door"]
        s = M.Actor(steve, pos=b(dx + 1.0, F, dz + 1.5), yaw=math.pi)
        s.walk(T(1768), [b(dx + 1.0, F, dz + 1.5), b(dx + 1.0, F, dz - 6.0)], speed=0.16)
        s.salute(T(1838), T(1872), ramp=4)
        actors.append(s)
        # on their feet they turn to the man coming in and look at him while they salute
        for a in squad:
            a.face(stand_up + 4, s)
            a.look(T(1772), T(1877), s)
        o.look(T(1765), T(1877), s)
        o.face(T(1772), s)
    M.bake(actors, int(T(1877)) + 2, frame0=T0)
    return actors


def cameras():
    # 14: the officer and the map; a slow push in
    A.camera("Shot14", [(1597, b(MX - 2.4, F + 1.7, MZ + 4.6), b(MX + 1.3, F + 1.45, MZ + 0.6)),
                        (1756, b(MX - 1.9, F + 1.65, MZ + 3.9), b(MX + 1.3, F + 1.45, MZ + 0.6))], lens=28)
    # 15: the hall from the front corner, towards the door: Steve walks in, everyone rises
    A.camera("Shot15", [(1757, b(HX0 + 1.2, F + 3.4, HZ0 + 1.6), b(MX, F + 0.9, HZ1 - 1)),
                        (1876, b(HX0 + 1.4, F + 3.3, HZ0 + 1.9), b(MX + 0.4, F + 1.0, HZ1 - 2))], lens=18)


def night():
    SKY.apply(tick=14500, rain=0.0, render_distance=12, ground_mc_y=64.0 - (F - 1), frame_start=1597,
              haze=L.LOOKS["night"]["haze"])
    A.apply_look("night")


def build():
    A.setup()
    A.remove_collections(["Squad", "Officer", "Steve"])
    for ob in bpy.data.objects:
        if ob.type == 'LIGHT' and ob.name.startswith("Lantern"):
            ob.data.energy *= A.LANTERN_GAIN
    cast()
    cameras()


PLAN = [dict(shot=14, cam="Shot14", prepare=night), dict(shot=15, cam="Shot15", prepare=night)]

if __name__ == "__main__":
    mode, shots = A.args()
    build()
    A.run(mode, shots, PLAN, "anim_hq.blend")
