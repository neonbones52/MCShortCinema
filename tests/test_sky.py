"""Test scene: vanilla sky (morning, overcast, night). Run inside Blender on blender/test_sky.blend:
    exec(open(r"C:\\Dev\\Projects\\CinemaShort\\tests\\test_sky.py", encoding="utf-8").read())
    shoot("morning")    # or "overcast", "night"; renders/tests/sky_<name>_v1.png
The test_farm set sits on a grass plane out to the render distance (12 chunks), so the horizon
works the game's way: terrain fades into the fog colour, which is the sky's horizon colour.
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

sys.path.insert(0, r"C:\Dev\Projects\CinemaShort\tools")
import importlib
import mc_character as C
import mc_sky as SKY
importlib.reload(SKY)

RP = r"C:\Dev\Projects\CinemaShort\assets\mc_rp\assets\minecraft\textures\block"
OUT = r"C:\Dev\Projects\CinemaShort\renders\tests"
GROUND_Z = 2.0            # the sets' ground top (Mineways export)
GRASS = "#91bd59"         # plains grass tint (colormap at temperature 0.8, downfall 0.4)
sc = bpy.context.scene


def grass_plane(radius=200.0):
    name = "Set.GrassPlane"
    if name in bpy.data.objects:
        return bpy.data.objects[name]
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    cx, cy = 13.0, -12.0
    pts = [(cx - radius, cy - radius), (cx + radius, cy - radius), (cx + radius, cy + radius), (cx - radius, cy + radius)]
    f = bm.faces.new([bm.verts.new((x, y, GROUND_Z - 0.02)) for x, y in pts])
    for loop in f.loops:
        loop[uvl].uv = (loop.vert.co.x, loop.vert.co.y)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    mat = bpy.data.materials.new("block.grass_plane")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    tex = nt.nodes.new('ShaderNodeTexImage')
    tex.image = C.image(os.path.join(RP, "grass_block_top.png"))
    tex.interpolation = 'Closest'
    mix = nt.nodes.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    mix.blend_type = 'MULTIPLY'
    mix.inputs['Factor'].default_value = 1.0
    nt.links.new(tex.outputs['Color'], mix.inputs['A'])
    a, r, g, b = SKY.parse_color(GRASS)
    mix.inputs['B'].default_value = (*SKY.lin((r, g, b)), 1)
    nt.links.new(mix.outputs['Result'], bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.9
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    sc.collection.objects.link(ob)
    return ob


def camera(name, loc, target, lens):
    cam = bpy.data.objects.get(name)
    if cam is None:
        cam = bpy.data.objects.new(name, bpy.data.cameras.new(name))
        sc.collection.objects.link(cam)
    cam.location = loc
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = lens
    return cam


grass_plane()
F = Vector((8.5, -11.5, GROUND_Z))       # the farmer
SHOTS = {
    # morning: looking east, the sun 27.5 deg up behind the village
    "morning": dict(tick=1000, rain=0.0, cam=("Cam.Morning", (-4.0, -16.0, 3.4), (F.x + 30, F.y + 6, F.z + 9.5), 18)),
    # overcast training ground: rain level 1 without the rain (WeatherAttributes)
    "overcast": dict(tick=6000, rain=1.0, cam=("Cam.Overcast", (2.0, -27.0, 4.2), (F.x + 4, F.y + 14, F.z + 4), 22)),
    # night: the full moon 28.5 deg up in the east, stars
    "night": dict(tick=14500, rain=0.0, cam=("Cam.Night", (-4.0, -16.0, 3.4), (F.x + 30, F.y + 6, F.z + 10.5), 18)),
}


def shoot(name, render=True, percentage=100, version=1):
    s = SHOTS[name]
    sc.camera = camera(*s["cam"])
    st = SKY.apply(tick=s["tick"], rain=s["rain"], render_distance=12, ground_mc_y=64.0 - GROUND_Z)
    if render:
        sc.render.resolution_percentage = percentage
        sc.render.filepath = os.path.join(OUT, f"sky_{name}_v{version}.png")
        bpy.ops.render.render(write_still=True)
        sc.render.resolution_percentage = 100
    return st
