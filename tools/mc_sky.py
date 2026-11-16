"""Vanilla Minecraft 26.2 sky for Blender: sky gradient, sun, moon (phases), stars, clouds,
weather (overcast) and the matching sun/moon lamp. Run inside Blender.

Everything is read from the game (26.2, javap + data files copied to assets/mc/data):
  timeline/day.json            sky/fog/cloud colour multipliers, sun/moon/star angles (cubic-bezier
                               eased), star brightness, sunrise colour, sky light colour/factor
  timeline/moon.json           moon phase per day (8-day cycle)
  dimension_type/overworld     sky #78a7ff, fog #c0d8ff, clouds #ccffffff at y = 192.33
  WeatherAttributes            rain: sky BlendToGray(0.6, 0.75), fog x(0.5, 0.5, 0.6),
                               clouds BlendToGray(0.24, 0.5); sun/moon/stars x (1 - rain)
  AtmosphericFogEnvironment    fog colour: sunrise tint towards the sun, then
                               lerp(1 - clampedLerp(0.25, 1, rd/32)^0.25, fog, weather-darkened sky)
  sky.fsh + fog.glsl           sky disc 16 blocks above the eye, fog = spherical distance / skyEnd
                               (skyEnd = render distance): fog(e) = 16 / (sin(e) * skyEnd)
  SkyRenderer                  sun quad +-30 at 100, moon +-20 at 100 (additive, black = clear),
                               pose Ry(-90) Rx(angle); 1500 stars, seed 10842, size 0.15..0.25
  CloudRenderer + clouds.vsh   clouds.png, cell 12x4x12 blocks, faces top 1.0 / bottom 0.7 /
                               N,S 0.8 / E,W 0.9; drift 0.03 blocks/tick (west), z offset 3.96;
                               alpha fades to 0 at the cloud range
  FogRenderer                  terrain fog: start rd - clamp(rd/10, 4, 64), end rd (cylindrical)
Coordinates: MC +X east = Blender +X, MC -Z north = Blender +Y, MC +Y up = Blender +Z.

    import mc_sky as SKY
    SKY.apply(tick=1000)                 # morning; tick 6000 noon, 18000 midnight
    SKY.apply(tick=6000, rain=1.0)       # overcast (rain without the rain itself)
"""
import json
import math
import os

import bmesh
import bpy
from mathutils import Matrix, Vector

ROOT = r"C:\Dev\Projects\CinemaShort"
DATA = os.path.join(ROOT, "assets", "mc", "data")
ENV = os.path.join(ROOT, "assets", "mc", "textures", "environment")
PERIOD = 24000
SKY_COL = "MC.Sky"


# ------------------------------------------------------------------ colours
def parse_color(v):
    """'#rrggbb' / '#aarrggbb' / signed int -> (a, r, g, b) floats 0..1 (sRGB)."""
    if isinstance(v, str):
        h = v.lstrip('#')
        if len(h) == 6:
            h = "ff" + h
        n = int(h, 16)
    else:
        n = v & 0xFFFFFFFF
    return ((n >> 24) & 255) / 255.0, ((n >> 16) & 255) / 255.0, ((n >> 8) & 255) / 255.0, (n & 255) / 255.0


def s2l(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def lin(rgb):
    return tuple(s2l(max(0.0, min(1.0, c))) for c in rgb)


def lerp(t, a, b):
    return a + (b - a) * t


def lerp3(t, a, b):
    return tuple(lerp(t, x, y) for x, y in zip(a, b))


def greyscale(rgb):
    g = 0.3 * rgb[0] + 0.59 * rgb[1] + 0.11 * rgb[2]
    return (g, g, g)


def blend_to_gray(rgb, brightness, factor):
    g = tuple(c * brightness for c in greyscale(rgb))
    return lerp3(factor, rgb, g)


# ------------------------------------------------------------------ timelines
_cache = {}


def _load(name):
    if name not in _cache:
        with open(os.path.join(DATA, name), encoding="utf-8") as f:
            _cache[name] = json.load(f)
    return _cache[name]


def cubic_bezier(p, x1, y1, x2, y2):
    """CSS-style easing: y for x = p."""
    def bx(t):
        return 3 * (1 - t) ** 2 * t * x1 + 3 * (1 - t) * t * t * x2 + t ** 3

    def by(t):
        return 3 * (1 - t) ** 2 * t * y1 + 3 * (1 - t) * t * t * y2 + t ** 3
    lo, hi = 0.0, 1.0
    for _ in range(50):
        mid = (lo + hi) / 2
        if bx(mid) < p:
            lo = mid
        else:
            hi = mid
    return by((lo + hi) / 2)


def sample_track(track, tick, period=PERIOD, color=False):
    """Value of a timeline track at `tick` (cyclic). Colours (color=True) come back as (a, r, g, b)."""
    keys = track["keyframes"]
    vals = [parse_color(k["value"]) if color else k["value"] for k in keys]
    t = tick % period
    n = len(keys)
    # previous key: the last one (in list order) at or before t; wrap to the last key otherwise
    prev = None
    for i, k in enumerate(keys):
        if k["ticks"] <= t:
            prev = i
    if prev is None:
        prev = n - 1
    nxt = (prev + 1) % n
    t0 = keys[prev]["ticks"]
    t1 = keys[nxt]["ticks"] + (period if nxt <= prev else 0)
    tt = t if t >= t0 else t + period
    f = 0.0 if t1 == t0 else (tt - t0) / (t1 - t0)
    ease = track.get("ease")
    if ease == "constant":
        f = 0.0
    elif isinstance(ease, dict) and "cubic_bezier" in ease:
        f = cubic_bezier(f, *ease["cubic_bezier"])
    a, b = vals[prev], vals[nxt]
    if isinstance(a, (bool, str)):
        return a
    if isinstance(a, tuple):
        return tuple(lerp(f, x, y) for x, y in zip(a, b))
    return lerp(f, a, b)


def state(tick=6000, rain=0.0, render_distance=12, day=0, camera_forward=None):
    """Everything the sky needs at a moment, colours in sRGB 0..1 (as the game holds them)."""
    dt = _load("day.json")["tracks"]
    ow = _load("overworld.json")["attributes"]
    tr = lambda k: dt["minecraft:visual/" + k]
    mul = lambda base, m: tuple(x * y for x, y in zip(base, m))

    sky = mul(parse_color(ow["minecraft:visual/sky_color"])[1:], sample_track(tr("sky_color"), tick, color=True)[1:])
    fog = mul(parse_color(ow["minecraft:visual/fog_color"])[1:], sample_track(tr("fog_color"), tick, color=True)[1:])
    ca = parse_color(ow["minecraft:visual/cloud_color"])
    cmul = sample_track(tr("cloud_color"), tick, color=True)
    cloud = mul(ca[1:], cmul[1:])
    cloud_alpha = ca[0] * cmul[0]
    sunrise = sample_track(tr("sunrise_sunset_color"), tick, color=True)          # (a, r, g, b)
    sun_angle = sample_track(tr("sun_angle"), tick)
    moon_angle = sample_track(tr("moon_angle"), tick)
    star_angle = sample_track(tr("star_angle"), tick)
    stars = sample_track(tr("star_brightness"), tick)
    light_col = sample_track(tr("sky_light_color"), tick, color=True)[1:]
    light_fac = sample_track(tr("sky_light_factor"), tick)
    # weather layer (WeatherAttributes), lerped by the rain level
    if rain > 0:
        sky = lerp3(rain, sky, blend_to_gray(sky, 0.6, 0.75))
        fog = lerp3(rain, fog, mul(fog, (0.5, 0.5, 0.6)))
        cloud = lerp3(rain, cloud, blend_to_gray(cloud, 0.24, 0.5))
        light_fac = lerp(rain, light_fac, lerp(0.3125, light_fac, 0.24))
        light_col = lerp3(rain, light_col, lerp3(0.3125, light_col, (0, 0, 0)))
        stars = 0.0
    rain_bright = 1.0 - rain
    # AtmosphericFogEnvironment.getBaseColor
    fogc = fog
    if render_distance >= 4 and camera_forward is not None and sunrise[0] > 0:
        side = -1.0 if math.sin(math.radians(sun_angle)) > 0 else 1.0     # MC x of the sun's side
        fwd = Vector(camera_forward).normalized()
        d = fwd.x * side                                               # Blender x = MC x
        if d > 0:
            fogc = lerp3(d * sunrise[0], fogc, sunrise[1:])
    dark = (1 - rain * 0.5, 1 - rain * 0.5, 1 - rain * 0.4)
    sky_dark = mul(sky, dark)
    k = 1.0 - (lerp(min(max(render_distance / 32.0, 0.0), 1.0), 0.25, 1.0)) ** 0.25
    fogc = lerp3(k, fogc, sky_dark)
    phases = _load("moon.json")["tracks"]["minecraft:visual/moon_phase"]
    phase = sample_track(phases, (day % 8) * 24000 + tick, period=192000)
    return dict(tick=tick, rain=rain, sky=sky, fog=fogc, cloud=cloud, cloud_alpha=cloud_alpha,
                sunrise=sunrise, sun_angle=sun_angle, moon_angle=moon_angle, star_angle=star_angle,
                stars=stars * rain_bright, rain_bright=rain_bright, light_color=light_col,
                light_factor=light_fac, moon_phase=phase, render_distance=render_distance)


# ------------------------------------------------------------------ geometry helpers
C_MC = Matrix(((1, 0, 0), (0, 0, -1), (0, 1, 0)))      # MC (x, y, z) -> Blender (x, -z, y)


def mc_to_b(v):
    return C_MC @ Vector(v)


def celestial_matrix(angle_deg):
    """SkyRenderer pose for the sun/moon/stars: Ry(-90) * Rx(angle), in Blender axes."""
    R = Matrix.Rotation(math.radians(-90), 3, 'Y') @ Matrix.Rotation(math.radians(angle_deg), 3, 'X')
    return C_MC @ R @ C_MC.inverted()


def sun_direction(angle_deg):
    return celestial_matrix(angle_deg) @ mc_to_b((0, 1, 0))


def _collection():
    col = bpy.data.collections.get(SKY_COL)
    if col is None:
        col = bpy.data.collections.new(SKY_COL)
        bpy.context.scene.collection.children.link(col)
    return col


def _camera_only(ob):
    for attr in ("visible_diffuse", "visible_glossy", "visible_transmission", "visible_volume_scatter",
                 "visible_shadow"):
        if hasattr(ob, attr):
            setattr(ob, attr, False)
    ob.hide_select = True


def _image(path):
    path = os.path.normpath(path)
    for im in bpy.data.images:
        if os.path.normpath(bpy.path.abspath(im.filepath)) == path:
            return im
    return bpy.data.images.load(path)


def _additive_material(name, png, tint=(1, 1, 1), strength=1.0):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    add = nt.nodes.new('ShaderNodeAddShader')
    em = nt.nodes.new('ShaderNodeEmission')
    tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    if png:
        tex = nt.nodes.new('ShaderNodeTexImage')
        tex.image = _image(png)
        tex.interpolation = 'Closest'
        tex.extension = 'CLIP'
        mixc = nt.nodes.new('ShaderNodeMix')
        mixc.data_type = 'RGBA'
        mixc.blend_type = 'MULTIPLY'
        mixc.inputs['Factor'].default_value = 1.0
        nt.links.new(tex.outputs['Color'], mixc.inputs['A'])
        mixc.inputs['B'].default_value = (*tint, 1)
        nt.links.new(mixc.outputs['Result'], em.inputs['Color'])
    else:
        em.inputs['Color'].default_value = (*tint, 1)
    em.inputs['Strength'].default_value = strength
    nt.links.new(em.outputs[0], add.inputs[0])
    nt.links.new(tr.outputs[0], add.inputs[1])
    nt.links.new(add.outputs[0], out.inputs['Surface'])
    mat.surface_render_method = 'BLENDED'
    mat.use_backface_culling = False
    try:
        mat.use_transparency_overlap = True
    except AttributeError:
        pass
    return mat


def _quad(name, half, png, col, mat):
    """Celestial quad (-1,0,-1)..(1,0,1) * half at MC y = 100, UVs as buildCelestialQuad."""
    me = bpy.data.meshes.get(name) or bpy.data.meshes.new(name)
    me.clear_geometry()
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    pts = [(-1, 0, -1), (1, 0, -1), (1, 0, 1), (-1, 0, 1)]
    uvs = [(0, 1), (1, 1), (1, 0), (0, 0)]                # (u0,v0) (u1,v0) (u1,v1) (u0,v1); v0 = top
    vs = [bm.verts.new(mc_to_b((x * half, 100.0, z * half))) for x, _, z in pts]
    f = bm.faces.new(vs)
    for loop, uv in zip(f.loops, uvs):
        loop[uvl].uv = uv
    bm.to_mesh(me)
    bm.free()
    me.materials.clear()
    me.materials.append(mat)
    ob = bpy.data.objects.get(name) or bpy.data.objects.new(name, me)
    if ob.name not in col.objects:
        col.objects.link(ob)
    _camera_only(ob)
    return ob


class JavaRandom:
    """java.util.Random / LegacyRandomSource (what RandomSource seeds with)."""

    def __init__(self, seed):
        self.seed = (seed ^ 0x5DEECE66D) & ((1 << 48) - 1)

    def next(self, bits):                      # bits < 32 here, so no sign handling is needed
        self.seed = (self.seed * 0x5DEECE66D + 0xB) & ((1 << 48) - 1)
        return self.seed >> (48 - bits)

    def next_float(self):
        return self.next(24) / float(1 << 24)

    def next_double(self):
        return ((self.next(26) << 27) + self.next(27)) * (1.0 / (1 << 53))


def _stars_mesh(name, col, mat):
    """SkyRenderer.buildStars: 1500 tries, seed 10842."""
    me = bpy.data.meshes.get(name) or bpy.data.meshes.new(name)
    me.clear_geometry()
    bm = bmesh.new()
    rnd = JavaRandom(10842)
    for _ in range(1500):
        x, y, z = (rnd.next_float() * 2 - 1 for _ in range(3))
        size = 0.15 + rnd.next_float() * 0.1
        d2 = x * x + y * y + z * z
        if d2 <= 0.010000001 or d2 >= 1.0:
            continue
        p = Vector((x, y, z)).normalized() * 100.0
        rot = rnd.next_double() * math.pi * 2.0
        # Matrix3f().rotateTowards(-p, up).rotateZ(-rot): the star quad faces the centre
        fwd = (-p).normalized()
        up = Vector((0, 1, 0))
        right = up.cross(fwd).normalized() if abs(fwd.dot(up)) < 0.999 else Vector((1, 0, 0))
        up2 = fwd.cross(right)
        M = Matrix((right, up2, fwd)).transposed() @ Matrix.Rotation(-rot, 3, 'Z')
        corners = [(size, -size), (size, size), (-size, size), (-size, -size)]
        vs = [bm.verts.new(mc_to_b(M @ Vector((cx, cy, 0)) + p)) for cx, cy in corners]
        bm.faces.new(vs)
    bm.to_mesh(me)
    bm.free()
    me.materials.clear()
    me.materials.append(mat)
    ob = bpy.data.objects.get(name) or bpy.data.objects.new(name, me)
    if ob.name not in col.objects:
        col.objects.link(ob)
    _camera_only(ob)
    return ob


# ------------------------------------------------------------------ clouds
FACE_SHADE = {'top': 1.0, 'bottom': 0.7, 'n': 0.8, 's': 0.8, 'e': 0.9, 'w': 0.9}


def _cloud_cells():
    im = _image(os.path.join(ENV, "clouds.png"))
    w, h = im.size
    px = im.pixels[:]
    ch = im.channels
    cells = [[False] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            # image rows in Blender start at the bottom
            i = ((h - 1 - y) * w + x) * ch
            a = px[i + 3] if ch == 4 else 1.0
            lum = px[i]
            cells[y][x] = a >= 10 / 255 and lum > 0.5
    return cells, w, h


def clouds(center=(0.0, 0.0), radius=600.0, ground_mc_y=64.0, tick=0.0, name="MC.Clouds"):
    col = _collection()
    cells, w, h = _cloud_cells()
    # cloud space = world + (0.03 * t, 0, 3.96): a cell at cloud x shows at world x - 0.03 t
    offx, offz = 0.03 * tick, 3.96
    cx, cz = center[0], -center[1]                       # MC x, z of the centre
    i0, i1 = int(math.floor((cx + offx - radius) / 12)), int(math.ceil((cx + offx + radius) / 12))
    j0, j1 = int(math.floor((cz + offz - radius) / 12)), int(math.ceil((cz + offz + radius) / 12))
    filled = lambda i, j: cells[j % h][i % w]
    bm = bmesh.new()
    shade_layer = bm.faces.layers.float.new("shade")
    y0 = 192.33 - ground_mc_y
    y1 = y0 + 4.0
    for j in range(j0, j1):
        for i in range(i0, i1):
            if not filled(i, j):
                continue
            x0, x1 = i * 12 - offx, (i + 1) * 12 - offx            # MC x
            z0, z1 = j * 12 - offz, (j + 1) * 12 - offz            # MC z
            P = lambda x, y, z: bm.verts.new((x, -z, y))
            faces = [('top', [(x0, y1, z0), (x0, y1, z1), (x1, y1, z1), (x1, y1, z0)]),
                     ('bottom', [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)])]
            if not filled(i, j - 1):
                faces.append(('n', [(x0, y0, z0), (x0, y1, z0), (x1, y1, z0), (x1, y0, z0)]))
            if not filled(i, j + 1):
                faces.append(('s', [(x1, y0, z1), (x1, y1, z1), (x0, y1, z1), (x0, y0, z1)]))
            if not filled(i - 1, j):
                faces.append(('w', [(x0, y0, z1), (x0, y1, z1), (x0, y1, z0), (x0, y0, z0)]))
            if not filled(i + 1, j):
                faces.append(('e', [(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)]))
            for key, pts in faces:
                f = bm.faces.new([P(*p) for p in pts])
                f[shade_layer] = FACE_SHADE[key]
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.get(name) or bpy.data.meshes.new(name)
    me.clear_geometry()
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.get(name) or bpy.data.objects.new(name, me)
    if ob.name not in col.objects:
        col.objects.link(ob)
    _camera_only(ob)
    return ob


def _cloud_material(st, cloud_end):
    mat = bpy.data.materials.get("MC.Clouds") or bpy.data.materials.new("MC.Clouds")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    attr = nt.nodes.new('ShaderNodeAttribute')
    attr.attribute_type = 'GEOMETRY'
    attr.attribute_name = "shade"
    # vertex colour multiplies in sRGB: linear = lin(cloud) * shade^2.2 (close to exact)
    pw = nt.nodes.new('ShaderNodeMath')
    pw.operation = 'POWER'
    pw.inputs[1].default_value = 2.2
    nt.links.new(attr.outputs['Fac'], pw.inputs[0])
    em = nt.nodes.new('ShaderNodeEmission')
    mixc = nt.nodes.new('ShaderNodeMix')
    mixc.data_type = 'RGBA'
    mixc.blend_type = 'MULTIPLY'
    mixc.inputs['Factor'].default_value = 1.0
    mixc.inputs['A'].default_value = (*lin(st['cloud']), 1)
    nt.links.new(pw.outputs[0], mixc.inputs['B'])
    nt.links.new(mixc.outputs['Result'], em.inputs['Color'])
    # alpha = cloud alpha * (1 - distance / cloud_end)
    camd = nt.nodes.new('ShaderNodeCameraData')
    div = nt.nodes.new('ShaderNodeMath')
    div.operation = 'DIVIDE'
    div.inputs[1].default_value = cloud_end
    nt.links.new(camd.outputs['View Distance'], div.inputs[0])
    inv = nt.nodes.new('ShaderNodeMath')
    inv.operation = 'SUBTRACT'
    inv.use_clamp = True
    inv.inputs[0].default_value = 1.0
    nt.links.new(div.outputs[0], inv.inputs[1])
    am = nt.nodes.new('ShaderNodeMath')
    am.operation = 'MULTIPLY'
    am.inputs[1].default_value = st['cloud_alpha']
    nt.links.new(inv.outputs[0], am.inputs[0])
    tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(am.outputs[0], mix.inputs[0])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    mat.surface_render_method = 'BLENDED'
    mat.use_backface_culling = True
    try:
        mat.use_transparency_overlap = False      # depth pre-pass: only the nearest cloud face shows
    except AttributeError:
        pass
    return mat


# ------------------------------------------------------------------ world
def _world(st, ambient=0.35, overcast_fill=0.05):
    sc = bpy.context.scene
    w = bpy.data.worlds.get("MC.World") or bpy.data.worlds.new("MC.World")
    sc.world = w
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputWorld')
    tc = nt.nodes.new('ShaderNodeTexCoord')
    nrm = nt.nodes.new('ShaderNodeVectorMath')
    nrm.operation = 'NORMALIZE'
    nt.links.new(tc.outputs['Generated'], nrm.inputs[0])
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(nrm.outputs[0], sep.inputs[0])
    zc = nt.nodes.new('ShaderNodeMath')
    zc.operation = 'MAXIMUM'
    zc.inputs[1].default_value = 1e-4
    nt.links.new(sep.outputs['Z'], zc.inputs[0])
    sky_end = st['render_distance'] * 16.0
    mulz = nt.nodes.new('ShaderNodeMath')
    mulz.operation = 'MULTIPLY'
    mulz.inputs[1].default_value = sky_end
    nt.links.new(zc.outputs[0], mulz.inputs[0])
    fogv = nt.nodes.new('ShaderNodeMath')
    fogv.operation = 'DIVIDE'
    fogv.use_clamp = True
    fogv.inputs[0].default_value = 16.0                    # the sky disc sits 16 blocks above the eye
    nt.links.new(mulz.outputs[0], fogv.inputs[1])
    mixc = nt.nodes.new('ShaderNodeMix')
    mixc.data_type = 'RGBA'
    mixc.inputs['A'].default_value = (*st['sky'], 1)        # sRGB values, mixed as the shader does
    mixc.inputs['B'].default_value = (*st['fog'], 1)
    nt.links.new(fogv.outputs[0], mixc.inputs['Factor'])
    gam = nt.nodes.new('ShaderNodeGamma')
    gam.inputs['Gamma'].default_value = 2.2                 # sRGB -> linear (approx.)
    nt.links.new(mixc.outputs['Result'], gam.inputs['Color'])
    bg_cam = nt.nodes.new('ShaderNodeBackground')
    nt.links.new(gam.outputs[0], bg_cam.inputs['Color'])
    bg_cam.inputs['Strength'].default_value = 1.0
    # light seen by the scene (not by the camera): sky-tinted ambient, normalised so that
    # `ambient` is a fraction of full daylight on a top face; overcast adds a cloud fill that
    # stands in for the hidden sun. Night keeps the game's sky light factor (0.24).
    bg_amb = nt.nodes.new('ShaderNodeBackground')
    sky_l = lin(lerp3(0.5, st['sky'], st['fog']))
    lum = 0.2126 * sky_l[0] + 0.7152 * sky_l[1] + 0.0722 * sky_l[2]
    tint = tuple(c / lum for c in sky_l) if lum > 1e-4 else lin(st['light_color'])
    tint = lerp3(0.5, tint, (1, 1, 1))                     # half-saturated, the sky is not a dome light
    bg_amb.inputs['Color'].default_value = (*tint, 1)
    bg_amb.inputs['Strength'].default_value = (ambient + st['rain'] * overcast_fill) * st['light_factor']
    lp = nt.nodes.new('ShaderNodeLightPath')
    ms = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(lp.outputs['Is Camera Ray'], ms.inputs[0])
    nt.links.new(bg_amb.outputs[0], ms.inputs[1])
    nt.links.new(bg_cam.outputs[0], ms.inputs[2])
    nt.links.new(ms.outputs[0], out.inputs['Surface'])
    return w


def _lamp(st, sun_strength=3.0, overcast_key=0.35):
    sc = bpy.context.scene
    ob = bpy.data.objects.get("MC.SunLight")
    if ob is None:
        ld = bpy.data.lights.new("MC.SunLight", 'SUN')
        ob = bpy.data.objects.new("MC.SunLight", ld)
        _collection().objects.link(ob)
    for o in sc.objects:                                   # other suns would double the light
        if o.type == 'LIGHT' and o.data.type == 'SUN' and o is not ob:
            o.hide_render = o.hide_viewport = True
    sdir = sun_direction(st['sun_angle'])
    mdir = sun_direction(st['moon_angle'])
    if sdir.z > -0.05:
        d, col, k = sdir, (1, 1, 1), 1.0
    else:
        d, col, k = mdir, lin(st['light_color']), 1.0
    elev = max(0.0, d.z)
    k *= min(1.0, elev / 0.1)                               # fades as the body reaches the horizon
    # overcast: the hidden sun becomes a soft light from above (the cloud deck), so tops stay
    # brighter than sides as in the game's face shading; Lightmap: sky factor x colour ~ 0.5
    r = st['rain']
    if r > 0:
        d = d.lerp(Vector((0, 0, 1)), r).normalized()
    ob.rotation_mode = 'QUATERNION'
    ob.rotation_quaternion = d.to_track_quat('Z', 'Y')
    ob.data.color = col
    ob.data.energy = sun_strength * st['light_factor'] * (st['rain_bright'] * k + r * overcast_key)
    ob.data.angle = math.radians(lerp(r, 1.5, 90.0))
    # 1 cm shadow texels (a character pixel is 6 cm): at the default 1 mm the sun / moon / star
    # quads a kilometre away request shadow pages and overflow EEVEE's buffer
    # ("Shadow buffer full" at night, 2026-11-16)
    ob.data.shadow_maximum_resolution = 0.01
    return ob


def terrain_fog_range(render_distance=12):
    rd = render_distance * 16.0
    return rd - max(4.0, min(64.0, rd / 10.0)), rd


# ------------------------------------------------------------------ all together
def apply(tick=6000, rain=0.0, render_distance=12, day=0, ground_mc_y=64.0, cloud_center=None,
          cloud_radius=600.0, cloud_end=2048.0, sky_scale=10.0, sun_strength=3.0, ambient=0.35,
          overcast_fill=0.05, overcast_key=0.35, frame_start=None, exact_colors=True, haze=None):
    """Build / update the sky for the scene camera. sky_scale: sun, moon and stars are placed at
    100 * sky_scale blocks (the game's 100, scaled so the scene never pokes through them)."""
    sc = bpy.context.scene
    cam = sc.camera
    fwd = (cam.matrix_world.to_3x3() @ Vector((0, 0, -1))) if cam else None
    st = state(tick, rain, render_distance, day, fwd)
    col = _collection()
    _world(st, ambient, overcast_fill)
    _lamp(st, sun_strength, overcast_key)

    anchor = bpy.data.objects.get("MC.SkyAnchor")
    if anchor is None:
        anchor = bpy.data.objects.new("MC.SkyAnchor", None)
        col.objects.link(anchor)
    for c in list(anchor.constraints):
        anchor.constraints.remove(c)
    if cam:
        con = anchor.constraints.new('COPY_LOCATION')
        con.target = cam
    anchor.scale = (sky_scale,) * 3

    def place(ob, angle):
        ob.parent = anchor
        ob.matrix_parent_inverse = Matrix.Identity(4)
        ob.matrix_basis = celestial_matrix(angle).to_4x4()

    rb = st['rain_bright']
    sun = _quad("MC.Sun", 30.0, col=col, png=os.path.join(ENV, "celestial", "sun.png"),
                mat=_additive_material("MC.Sun", os.path.join(ENV, "celestial", "sun.png"), (rb, rb, rb)))
    place(sun, st['sun_angle'])
    moon_png = os.path.join(ENV, "celestial", "moon", st['moon_phase'] + ".png")
    moon = _quad("MC.Moon", 20.0, col=col, png=moon_png,
                 mat=_additive_material("MC.Moon", moon_png, (rb, rb, rb)))
    place(moon, st['moon_angle'])
    sb = st['stars']
    stars = _stars_mesh("MC.Stars", col, _additive_material("MC.Stars", None, (sb, sb, sb)))
    place(stars, st['star_angle'])
    stars.hide_render = stars.hide_viewport = sb <= 0.0

    center = cloud_center or ((cam.location.x, cam.location.y) if cam else (0.0, 0.0))
    cl = clouds(center, cloud_radius, ground_mc_y, tick=0.0)
    cl.data.materials.clear()
    cl.data.materials.append(_cloud_material(st, cloud_end))
    # drift west 0.03 blocks/tick from the shot's first frame
    f0 = sc.frame_start if frame_start is None else frame_start
    cl.animation_data_clear()
    fc = cl.driver_add("location", 0)
    fc.driver.expression = f"-0.03 * (frame - {f0}) * 20 / {sc.render.fps / sc.render.fps_base}"

    if cam:
        cam.data.clip_end = max(cam.data.clip_end, 100.0 * sky_scale * 1.5, cloud_end)
    if exact_colors:
        sc.view_settings.view_transform = 'Standard'
        sc.view_settings.look = 'None'
    terrain_fog(st, haze=haze)
    sc["mc_sky"] = dict(tick=tick, rain=rain, render_distance=render_distance, day=day,
                        moon_phase=st['moon_phase'])
    return st


# ------------------------------------------------------------------ terrain fog (FogRenderer)
def _fog_group(st, haze=None):
    """Node group 'MC.TerrainFog': Shader in -> fogged Shader out. Cylindrical distance
    max(|xy|, |z|) to the camera, linear between the render-distance fog start and end.
    haze (not in the game; look-dev): dict(start, end, amount, color=None) - an extra
    distance haze (spherical distance, smoothstep), colour = the fog colour unless given (sRGB)."""
    start, end = terrain_fog_range(st['render_distance'])
    g = bpy.data.node_groups.get("MC.TerrainFog")
    if g is None:
        g = bpy.data.node_groups.new("MC.TerrainFog", 'ShaderNodeTree')
        g.interface.new_socket("Shader", in_out='INPUT', socket_type='NodeSocketShader')
        g.interface.new_socket("Shader", in_out='OUTPUT', socket_type='NodeSocketShader')
    nt = g.nodes
    nt.clear()
    gi = nt.new('NodeGroupInput')
    go = nt.new('NodeGroupOutput')
    geo = nt.new('ShaderNodeNewGeometry')
    camd = nt.new('ShaderNodeCameraData')
    off = nt.new('ShaderNodeVectorMath')
    off.operation = 'SCALE'
    g.links.new(geo.outputs['Incoming'], off.inputs[0])
    g.links.new(camd.outputs['View Distance'], off.inputs['Scale'])
    sep = nt.new('ShaderNodeSeparateXYZ')
    g.links.new(off.outputs[0], sep.inputs[0])
    comb = nt.new('ShaderNodeCombineXYZ')
    g.links.new(sep.outputs['X'], comb.inputs['X'])
    g.links.new(sep.outputs['Y'], comb.inputs['Y'])
    hlen = nt.new('ShaderNodeVectorMath')
    hlen.operation = 'LENGTH'
    g.links.new(comb.outputs[0], hlen.inputs[0])
    az = nt.new('ShaderNodeMath')
    az.operation = 'ABSOLUTE'
    g.links.new(sep.outputs['Z'], az.inputs[0])
    cyl = nt.new('ShaderNodeMath')
    cyl.operation = 'MAXIMUM'
    g.links.new(hlen.outputs['Value'], cyl.inputs[0])
    g.links.new(az.outputs[0], cyl.inputs[1])
    mr = nt.new('ShaderNodeMapRange')
    mr.clamp = True
    mr.inputs['From Min'].default_value = start
    mr.inputs['From Max'].default_value = end
    g.links.new(cyl.outputs[0], mr.inputs['Value'])
    src = gi.outputs[0]
    if haze and haze.get('amount', 0) > 0:
        hr = nt.new('ShaderNodeMapRange')
        hr.clamp = True
        hr.interpolation_type = 'SMOOTHSTEP'
        hr.inputs['From Min'].default_value = haze['start']
        hr.inputs['From Max'].default_value = haze['end']
        hr.inputs['To Max'].default_value = haze['amount']
        g.links.new(camd.outputs['View Distance'], hr.inputs['Value'])
        hem = nt.new('ShaderNodeEmission')
        hem.inputs['Color'].default_value = (*lin(haze.get('color') or st['fog']), 1)
        hmix = nt.new('ShaderNodeMixShader')
        g.links.new(hr.outputs['Result'], hmix.inputs[0])
        g.links.new(src, hmix.inputs[1])
        g.links.new(hem.outputs[0], hmix.inputs[2])
        src = hmix.outputs[0]
    em = nt.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = (*lin(st['fog']), 1)
    mix = nt.new('ShaderNodeMixShader')
    g.links.new(mr.outputs['Result'], mix.inputs[0])
    g.links.new(src, mix.inputs[1])
    g.links.new(em.outputs[0], mix.inputs[2])
    g.links.new(mix.outputs[0], go.inputs[0])
    return g


def terrain_fog(st, materials=None, haze=None):
    """Insert MC.TerrainFog before the output of every scene material (sky ones excluded)."""
    g = _fog_group(st, haze)
    if materials is None:
        materials = {s.material for o in bpy.context.scene.objects if o.type == 'MESH'
                     for s in o.material_slots if s.material}
    for m in materials:
        if m is None or not m.use_nodes or m.name.startswith("MC."):
            continue
        nt = m.node_tree
        out = next((n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL' and n.is_active_output), None)
        if out is None or not out.inputs['Surface'].links:
            continue
        link = out.inputs['Surface'].links[0]
        if link.from_node.type == 'GROUP' and link.from_node.node_tree == g:
            continue
        src = link.from_socket
        gn = nt.nodes.new('ShaderNodeGroup')
        gn.node_tree = g
        gn.location = (out.location.x - 200, out.location.y - 150)
        nt.links.new(src, gn.inputs[0])
        nt.links.new(gn.outputs[0], out.inputs['Surface'])
    return g
