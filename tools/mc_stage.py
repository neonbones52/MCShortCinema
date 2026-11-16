"""Stand-in sets for the test scenes: boxes of block textures laid out by script (no Mineways).
Real locations go through sets/*.py -> build_set.py; this is only for technical stands.

    import mc_stage as ST
    ST.boxes("Set.Grass", ST.grass(), [((-400, -400, -1), (400, 400, 0))])
    ST.boxes("Set.Posts", ST.block_mat("oak_log"), [((x, 10, 0), (x + 1, 11, 4)) for x in range(0, 200, 12)])
"""
import os

import bmesh
import bpy
from mathutils import Vector

import mc_character as C
import mc_sky as SKY

ROOT = r"C:\Dev\Projects\CinemaShort"
RP = os.path.join(ROOT, r"assets\mc_rp\assets\minecraft\textures\block")
GRASS = "#91bd59"                 # plains grass tint (colormap at temperature 0.8, downfall 0.4)


def block_mat(tex):
    """Material of a block texture, tiled once per block."""
    mat = C.material("block." + tex, os.path.join(RP, tex + ".png"), rough=0.9, spec=0.15)
    next(n for n in mat.node_tree.nodes if n.type == 'TEX_IMAGE').extension = 'REPEAT'
    return mat


def tinted(name, tex, tint):
    """A greyscale block texture multiplied by a biome colour (sRGB hex)."""
    mat = bpy.data.materials.get(name)
    if mat is not None:
        return mat
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    img = nt.nodes.new('ShaderNodeTexImage')
    img.image = C.image(os.path.join(RP, tex + ".png"))
    img.interpolation = 'Closest'
    mix = nt.nodes.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    mix.blend_type = 'MULTIPLY'
    mix.inputs['Factor'].default_value = 1.0
    nt.links.new(img.outputs['Color'], mix.inputs['A'])
    a, r, g, b = SKY.parse_color(tint)
    mix.inputs['B'].default_value = (*SKY.lin((r, g, b)), 1)
    nt.links.new(mix.outputs['Result'], bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.9
    return mat


def grass():
    return tinted("block.grass_tinted", "grass_block_top", GRASS)


def boxes(name, mat, items, collection=None):
    """One mesh of axis-aligned boxes [(lo, hi), ...]; UVs = world coordinates (1 block = 1 tile)."""
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    for lo, hi in items:
        lo, hi = Vector(lo), Vector(hi)
        ret = bmesh.ops.create_cube(bm, size=1.0)
        for v in ret['verts']:
            v.co = Vector(lo[i] + (v.co[i] + 0.5) * (hi[i] - lo[i]) for i in range(3))
    bm.normal_update()
    for f in bm.faces:
        ax = max(range(3), key=lambda i: abs(f.normal[i]))
        u_ax, v_ax = ((0, 1) if ax == 2 else ((1, 2) if ax == 0 else (0, 2)))
        for loop in f.loops:
            loop[uvl].uv = (loop.vert.co[u_ax], loop.vert.co[v_ax])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    (collection or bpy.context.scene.collection).objects.link(ob)
    return ob
