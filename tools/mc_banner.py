"""Banners as the game draws them (Minecraft 26.2, read with javap). Run inside Blender.

    import mc_banner as BN
    b = BN.banner("Banner.Steve", "red", [("yellow", "flower"), ("red", "triangle_top"), ("red", "piglin")])
    b = BN.from_give('/give @s minecraft:red_banner[minecraft:banner_patterns=[{color: "yellow", '
                     'pattern: "flower"}, ...]]', name="Banner.Steve")
    BN.place(b, (x, y, z), yaw=0)            # set block coordinates (mc_set.b): the banner's own block
    BN.animate(b, frame_start=1, frame_end=193)   # the game's flag sway, keys every tick

From the game code:
  * BannerModel.createBodyLayer(standing): pole box (-1, -42, -1) 2x42x2 at uv (44, 0); bar
    (-10, -44, -1) 20x2x2 at uv (0, 42) standing, (-10, -20.5, 9.5) on a wall (no pole);
    texture entity/banner/banner_base.png (Sheets.BANNER_BASE).
  * BannerFlagModel.createFlagLayer(standing): flag (-10, 0, -2) 20x40x1 at uv (0, 0), part
    offset (0, -44, 0) standing, (0, -20.5, 10.5) on a wall; setupAnim(phase):
    flag.xRot = (-0.0125 + 0.01 * cos(2 pi phase)) * pi.
  * BannerRenderer: phase = (floorMod(x*7 + y*9 + z*13 + gameTime, 100) + partialTick) / 100;
    pose = translate(0.5, 0, 0.5), rotate Y by the block rotation (16 steps of 22.5 deg, wall:
    facing), scale (2/3, -2/3, -2/3). The flag is drawn with entity/banner/base.png tinted by the
    base colour, then up to 16 pattern layers entity/banner/<pattern>.png, each tinted by its dye
    colour (DyeColor.getTextureDiffuseColor), in order, alpha-blended.
Model units are pixels (1/16 block); y points down in the model.
"""
import math
import os
import re

import bmesh
import bpy
from mathutils import Vector

import mc_character as C

ROOT = r"C:\Dev\Projects\CinemaShort"
BANNER_TEX = os.path.join(ROOT, "assets", "mc_rp", "assets", "minecraft", "textures", "entity", "banner")
OUT = os.path.join(ROOT, "assets", "banners")          # composed flag textures (derived: not in git)
SCALE = 2.0 / 3.0
# DyeColor.textureDiffuseColor (26.2 static init)
DYE = {"white": 0xF9FFFE, "orange": 0xF9801D, "magenta": 0xC74EBD, "light_blue": 0x3AB3DA,
       "yellow": 0xFED83D, "lime": 0x80C71F, "pink": 0xF38BAA, "gray": 0x474F52,
       "light_gray": 0x9D9D97, "cyan": 0x169C9C, "purple": 0x8932B8, "blue": 0x3C44AA,
       "brown": 0x835432, "green": 0x5E7C16, "red": 0xB02E26, "black": 0x1D1D21}

# the empires' banners, as the user gave them (2026-11-21), verbatim /give commands
EMPIRES = {
    "steve": '/give @s minecraft:red_banner[minecraft:banner_patterns=[{color: "yellow", pattern: "flower"},'
             '{color: "red", pattern: "triangle_top"},{color: "red", pattern: "piglin"}]]',
    "alex": '/give @s minecraft:blue_banner[minecraft:banner_patterns=[{color: "yellow", pattern: "border"},'
            '{color: "yellow", pattern: "circle"},{color: "yellow", pattern: "guster"},'
            '{color: "yellow", pattern: "triangles_top"}]]',
}


def empire(who, name=None, standing=True, collection=None):
    """The banner of an empire ("steve" / "alex")."""
    return from_give(EMPIRES[who], name or "Banner." + who.capitalize(), standing, collection)


def parse_give(cmd):
    """'/give @s minecraft:red_banner[minecraft:banner_patterns=[{color: "yellow", pattern:
    "flower"}, ...]]' -> ("red", [("yellow", "flower"), ...])."""
    m = re.search(r"minecraft:([a-z_]+)_banner", cmd)
    if not m:
        raise ValueError("no <colour>_banner in: " + cmd)
    layers = re.findall(r'color:\s*"?([a-z_]+)"?\s*,\s*pattern:\s*"?(?:minecraft:)?([a-z_]+)"?', cmd)
    return m.group(1), layers


def flag_texture(base, layers):
    """Compose the flag texture like BannerRenderer.submitPatterns: base.png x base colour, then
    every layer's mask x its dye colour over it (straight alpha 'over', in the game's sRGB).
    Saved to assets/banners/<key>.png and returned as a Blender image."""
    import numpy as np
    if len(layers) > 16:
        raise ValueError("the game draws at most 16 pattern layers")
    key = "_".join([base] + [f"{c}-{p}" for c, p in layers])
    path = os.path.join(OUT, key + ".png")
    img = bpy.data.images.get(key + ".png")
    if img is not None:
        return img
    if not os.path.exists(path):
        def load(name):
            im = bpy.data.images.load(os.path.join(BANNER_TEX, name + ".png"))
            w, h = im.size
            a = np.array(im.pixels[:], np.float32).reshape(h, w, 4)
            bpy.data.images.remove(im)
            return a                                   # Blender float pixels of an 8-bit PNG = sRGB values

        def tint(c):
            return np.array([(DYE[c] >> 16 & 255) / 255.0, (DYE[c] >> 8 & 255) / 255.0, (DYE[c] & 255) / 255.0])

        out = np.zeros((64, 64, 4), np.float32)
        for color, pattern in [(base, "base")] + list(layers):
            src = load(pattern)
            rgb, a = src[..., :3] * tint(color), src[..., 3:4]
            out_a = a + out[..., 3:4] * (1 - a)
            out[..., :3] = np.where(out_a > 0, (rgb * a + out[..., :3] * out[..., 3:4] * (1 - a)) / np.maximum(out_a, 1e-6), 0)
            out[..., 3:4] = out_a
        os.makedirs(OUT, exist_ok=True)
        tmp = bpy.data.images.new(key + "_tmp", 64, 64, alpha=True)
        tmp.pixels[:] = out.ravel()
        tmp.filepath_raw, tmp.file_format = path, 'PNG'
        tmp.save()
        bpy.data.images.remove(tmp)
    return C.image(path)


def _part(name, tex_path, boxes, collection, mat_name):
    """Boxes in model px -> a mesh in block units with the model axes mapped as by m2b
    (x, z, -y) / 16 and the model origin at the object origin."""
    p = C.Part(name, tex_path, (64, 64), None)
    for uv, origin, size in boxes:
        p.box(uv, origin, size)
    ob = p.build(collection, mat_name)
    o = C.m2b((0, 0, 0))
    for v in ob.data.vertices:
        v.co -= o
    return ob


def _m(p):
    """Model px point -> the same 'model metres' as _part's vertices."""
    return C.m2b(p) - C.m2b((0, 0, 0))


# BannerRenderer pose for a block at the origin, in Blender: B = (2/3) * _m(p) + (0.5, -0.5, 0)
# (translate (0.5, 0, 0.5), scale (2/3, -2/3, -2/3); the y and z flips are what _m already does)
POSE_OFFSET = Vector((0.5, -0.5, 0.0))


def banner(name, base, layers=(), standing=True, collection=None):
    """A banner: an empty '<name>' at its block's corner (move it with place()), with '<name>.pole'
    (pole and bar, or the bar alone on a wall) and '<name>.flag' (origin at its pivot; its X
    rotation is the game's sway). Returns the empty."""
    col = collection or bpy.data.collections.get(name) or bpy.data.collections.new(name)
    if col.name not in [c.name for c in bpy.context.scene.collection.children_recursive]:
        bpy.context.scene.collection.children.link(col)
    root = bpy.data.objects.new(name, None)
    root.empty_display_size = 0.5
    col.objects.link(root)
    body = [((0, 42), (-10, -44, -1) if standing else (-10, -20.5, 9.5), (20, 2, 2))]
    if standing:
        body.insert(0, ((44, 0), (-1, -42, -1), (2, 42, 2)))
    pole = _part(name + ".pole", os.path.join(BANNER_TEX, "banner_base.png"), body, col, "banner_base")
    img = flag_texture(base, list(layers))
    key = os.path.splitext(img.name)[0]
    flag = _part(name + ".flag", bpy.path.abspath(img.filepath), [((0, 0), (-10, 0, -2), (20, 40, 1))],
                 col, "banner." + key)
    pivot = (0, -44, 0) if standing else (0, -20.5, 10.5)
    for ob, loc in ((pole, POSE_OFFSET), (flag, POSE_OFFSET + SCALE * _m(pivot))):
        ob.parent = root
        ob.scale = (SCALE,) * 3
        ob.location = loc
    flag.rotation_euler.x = sway(0.0)
    root["mc_banner"] = key
    root["mc_standing"] = standing
    return root


def sway(phase):
    """BannerFlagModel.setupAnim: the flag's xRot for a phase 0..1 (radians; Blender X = model X)."""
    return (-0.0125 + 0.01 * math.cos(2.0 * math.pi * phase)) * math.pi


def place(root, block, rotation=0, wall_facing=None):
    """Put the banner in its block (set coordinates x east, y up, z south). rotation: the banner
    block's 0..15 (22.5 deg steps, as RotationSegment) for a standing banner."""
    x, y, z = block
    deg = rotation * 22.5 if wall_facing is None else {"south": 0, "west": 90, "north": 180, "east": 270}[wall_facing]
    root.rotation_euler = (0.0, 0.0, -math.radians(deg))      # Axis.YP.rotationDegrees(-deg) = Blender Z -deg
    # rotate about the block centre: the pose's translate (0.5, 0, 0.5) comes before the rotation
    root.location = Vector((x, -z, y)) + POSE_OFFSET - root.rotation_euler.to_matrix() @ POSE_OFFSET
    root["mc_block"] = (x, y, z)
    return root


def animate(root, frame_start=1, frame_end=250, game_time=0, fps=24):
    """Key the flag sway every game tick (frame = start + t * fps / 20), linear between ticks, with
    the game's per-block phase offset (x*7 + y*9 + z*13)."""
    flag = next(o for o in root.children if o.name.endswith(".flag"))
    x, y, z = root.get("mc_block", (0, 0, 0))
    seed = x * 7 + y * 9 + z * 13
    t = 0
    while True:
        f = frame_start + t * fps / 20.0
        if f > frame_end:
            break
        flag.rotation_euler.x = sway(((seed + game_time + t) % 100) / 100.0)
        flag.keyframe_insert("rotation_euler", index=0, frame=f)
        t += 1
    for fc in flag.animation_data.action.layers[0].strips[0].channelbags[0].fcurves:
        for k in fc.keyframe_points:
            k.interpolation = 'LINEAR'
    return flag


def from_give(cmd, name="Banner", standing=True, collection=None):
    base, layers = parse_give(cmd)
    return banner(name, base, layers, standing, collection)
