"""Maps in item frames on a wall, as the game shows them (26.2). Run inside Blender.

    import mc_map as MAP
    MAP.wall("HQ.Map", block=(x, y, z), facing="south", cols=1, rows=1)   # assets/maps/hq_<c>_<r>.png

The map pictures come from tools/mc_mapgen.py (the game's MapItem.update on our landmass).
From the game code: an item frame holding a map uses the block model item_frame_map: a slab one
pixel thick over the whole block face (birch_planks sides, item_frame back), and
ItemFrameRenderer draws the map over all of it, 128 map pixels to the block (scale 1/128), just in
front of the frame, upright at frame rotation 0, with no parchment border (that is only for a
map in hand). block: the block the frames hang in (set coordinates, x east, y up, z south); the
wall is the block behind it, opposite to `facing`. Several maps make one picture: map (c, r) goes
c blocks to the right and r blocks down from the top-left one (as the viewer sees it).
"""
import math
import os

import bmesh
import bpy
from mathutils import Vector

import mc_character as C

ROOT = r"C:\Dev\Projects\CinemaShort"
MAPS = os.path.join(ROOT, "assets", "maps")
BLOCK_TEX = os.path.join(ROOT, "assets", "mc_rp", "assets", "minecraft", "textures", "block")
FRAME_T = 1.0 / 16.0                              # item_frame_map: z 15.001..16 px
MAP_GAP = 1.0 / 128.0                             # the map sits one map pixel in front of the frame
YAW = {"south": 0.0, "west": -90.0, "north": 180.0, "east": 90.0}   # Blender Z rotation of the front (-Y)


def _quad(bm, uvl, pts, uvs):
    f = bm.faces.new([bm.verts.new(p) for p in pts])
    for loop, uv in zip(f.loops, uvs):
        loop[uvl].uv = uv
    return f


def _frame_mesh(name, w, h):
    """The frame slab of a w x h wall of frames, in local space: wall at y = 0, front towards -y,
    x to the right, z up, origin at the bottom-left corner on the wall."""
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    t = FRAME_T
    sides = [
        ([(0, 0, h), (w, 0, h), (w, -t, h), (0, -t, h)], "top"),
        ([(0, -t, 0), (w, -t, 0), (w, 0, 0), (0, 0, 0)], "bottom"),
        ([(0, 0, 0), (0, 0, h), (0, -t, h), (0, -t, 0)], "left"),
        ([(w, -t, 0), (w, -t, h), (w, 0, h), (w, 0, 0)], "right"),
    ]
    for pts, _ in sides:                           # birch plank strip 1 px wide (uv of the border)
        L = max(abs(pts[1][0] - pts[0][0]), abs(pts[1][2] - pts[0][2]), 1e-6)
        _quad(bm, uvl, pts, [(0, 0), (L, 0), (L, 1 / 16), (0, 1 / 16)])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return me


def _map_mesh(name):
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    y = -FRAME_T - MAP_GAP
    _quad(bm, uvl, [(0, y, 0), (1, y, 0), (1, y, 1), (0, y, 1)], [(0, 0), (1, 0), (1, 1), (0, 1)])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return me


def _map_material(png):
    mat = C.material("map." + os.path.basename(png), png, rough=1.0, spec=0.0)
    return mat


def wall(name, block, facing="south", cols=1, rows=1, prefix="hq", collection=None):
    """Hang cols x rows maps (assets/maps/<prefix>_<c>_<r>.png) in item frames. block: the block
    of the top-left frame. Returns the root empty (its origin: the wall at the bottom-left corner)."""
    col = collection or bpy.data.collections.get(name) or bpy.data.collections.new(name)
    if col.name not in [c.name for c in bpy.context.scene.collection.children_recursive]:
        bpy.context.scene.collection.children.link(col)
    root = bpy.data.objects.new(name, None)
    col.objects.link(root)
    fr = bpy.data.objects.new(name + ".frames", _frame_mesh(name + ".frames", cols, rows))
    fr.data.materials.append(C.material("item_frame.birch", os.path.join(BLOCK_TEX, "birch_planks.png"),
                                        rough=0.9, spec=0.1))
    col.objects.link(fr)
    fr.parent = root
    for c in range(cols):
        for r in range(rows):
            png = os.path.join(MAPS, f"{prefix}_{c}_{r}.png")
            ob = bpy.data.objects.new(f"{name}.map_{c}_{r}", _map_mesh(f"{name}.map_{c}_{r}"))
            ob.data.materials.append(_map_material(png))
            col.objects.link(ob)
            ob.parent = root
            ob.location = (c, 0, rows - 1 - r)
    # place: the wall face is the side of `block` opposite to facing
    x, y, z = block
    yaw = math.radians(YAW[facing])
    root.rotation_euler = (0, 0, yaw)
    centre = Vector((x + 0.5, -(z + 0.5), 0))
    back = Vector((0, 0.5, 0))                     # from the block centre to the wall, for facing south
    left = Vector((-0.5, 0, 0))
    rot = root.rotation_euler.to_matrix()
    root.location = centre + rot @ (back + left) + Vector((0, 0, y - (rows - 1)))
    root["mc_map"] = dict(block=list(block), facing=facing, cols=cols, rows=rows)
    return root


def pixel_point(root, px, pz):
    """World point of map pixel (px, pz) of the whole wall picture (0..128*cols, 0..128*rows from
    the top-left), on the map surface: where a pointer stick touches it."""
    info = root["mc_map"]
    rows = info["rows"]
    lx, lz = px / 128.0, rows - pz / 128.0
    return root.matrix_world @ Vector((lx, -FRAME_T - MAP_GAP, lz))
