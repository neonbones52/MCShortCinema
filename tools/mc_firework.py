"""Vanilla Minecraft fireworks in Blender, following the 26.2 game code (read with javap):

FireworkParticles.Starter   large ball = createParticleBall(speed 0.5, size 4): sparks on the
                            shell of a 9x9x9 lattice (386), jittered +-0.5, velocity ~0.5 b/tick
                            small ball = (0.25, 2); burst/star/creeper not needed yet.
SparkParticle               lifetime 48 + rand(12) ticks, gravity 0.1 (0.004 b/tick^2),
                            friction 0.91, quad half-size 0.1*(0.5..1)*2*0.75, full bright,
                            trail: every 2nd tick while age < life/2 drops a still spark (age=life/2),
                            twinkle: hidden when age >= life/3 and (age+life)/3 is odd.
SimpleAnimatedParticle      after half-life: alpha = 1-(age-life/2)/life, colour -> fade by 0.2/tick
                            sprite spark_7 .. spark_0 over the lifetime.
OverlayParticle (flash)     4 ticks, half-size 7.1*sin((age-1)*pi/4), alpha 0.6-(age-1)*0.125.
FireworkRocketEntity        unattached: v *= (1.15, 1, 1.15) + (0, 0.04, 0) per tick, each tick a
                            white spark with v = (gauss*0.05, -vy*0.5, gauss*0.05).
DyeColor.fireworkColor      colours below.

Particles are a point cloud with per-point attributes; a Geometry Nodes group evaluates the
closed-form motion against the scene frame, so nothing is baked and any frame renders alone.
"""
import math
import os
import random

import bpy
from mathutils import Vector

ROOT = r"C:\Dev\Projects\CinemaShort"
FX = os.path.join(ROOT, "assets", "fx")
ITEM = os.path.join(ROOT, "assets", "mc", "textures", "item")
TPS = 20.0
G_SPARK = 0.04 * 0.1
F_SPARK = 0.91

DYE = {'white': 0xF0F0F0, 'orange': 0xEB8844, 'magenta': 0xC354CD, 'light_blue': 0x6689D3,
       'yellow': 0xDECF2A, 'lime': 0x41CD34, 'pink': 0xD88198, 'gray': 0x434343,
       'light_gray': 0xABABAB, 'cyan': 0x287697, 'purple': 0x7B2FBE, 'blue': 0x253192,
       'brown': 0x51301A, 'green': 0x3B511A, 'red': 0xB3312C, 'black': 0x1E1B1B}
WHITE = (1.0, 1.0, 1.0)


def rgb(c):
    if isinstance(c, str):
        c = DYE[c]
    if isinstance(c, int):
        return ((c >> 16 & 255) / 255.0, (c >> 8 & 255) / 255.0, (c & 255) / 255.0)
    return tuple(c)


def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def mcv(x, y, z):
    """game vector (y up) -> Blender (z up); a proper rotation"""
    return Vector((x, -z, y))


# ------------------------------------------------------------------ particle sources
class Cloud:
    """Accumulates particles; build() turns them into one mesh object with attributes."""

    def __init__(self, seed=1):
        self.rng = random.Random(seed)
        self.pts = []

    def spark(self, pos, vel, frame, col, fade=None, trail=False, twinkle=False, age0=0.0, life=None):
        r = self.rng
        life = life if life is not None else 48 + r.randrange(12)
        q = 0.1 * (r.random() * 0.5 + 0.5) * 2.0 * 0.75
        p = dict(p0=Vector(pos), v0=Vector(vel), birth=frame, age0=age0, life=life, col=rgb(col),
                 fade=rgb(fade) if fade is not None else rgb(col), hasfade=1.0 if fade is not None else 0.0,
                 twinkle=1.0 if twinkle else 0.0, q=q, kind=0.0, g=G_SPARK, f=F_SPARK)
        self.pts.append(p)
        if trail:
            self._trail(p)
        return p

    def _trail(self, p):
        """Trail sparks: discrete parent motion, drop a still spark every 2nd tick before half-life."""
        pos, vz = Vector(p['p0']), p['v0'].z
        vx, vy = p['v0'].x, p['v0'].y
        life = p['life']
        for age in range(1, int(life)):
            vz -= G_SPARK
            pos += Vector((vx, vy, vz))
            vx *= F_SPARK; vy *= F_SPARK; vz *= F_SPARK
            if age < life // 2 and (age + life) % 2 == 0:
                child_life = 48 + self.rng.randrange(12)
                self.spark(pos.copy(), (0, 0, 0), p['birth'] + age * fps() / TPS, p['col'],
                           fade=p['fade'] if p['hasfade'] else None, twinkle=bool(p['twinkle']),
                           age0=float(child_life // 2), life=child_life)

    def flash(self, pos, frame, col):
        self.pts.append(dict(p0=Vector(pos), v0=Vector(), birth=frame, age0=0.0, life=4, col=rgb(col),
                             fade=rgb(col), hasfade=0.0, twinkle=0.0, q=0.0, kind=1.0, g=0.0, f=0.0))

    # ---- explosions (FireworkParticles.Starter)
    def ball(self, origin, frame, speed=0.5, size=4, colors=('red',), fades=(), trail=False, twinkle=False):
        r = self.rng
        for i in range(-size, size + 1):
            for j in range(-size, size + 1):
                k = -size
                while k <= size:
                    dx = j + (r.random() - r.random()) * 0.5
                    dy = i + (r.random() - r.random()) * 0.5
                    dz = k + (r.random() - r.random()) * 0.5
                    d = math.sqrt(dx * dx + dy * dy + dz * dz) / speed + r.gauss(0, 1) * 0.05
                    self.spark(origin, mcv(dx / d, dy / d, dz / d), frame, r.choice(colors),
                               fade=r.choice(fades) if fades else None, trail=trail, twinkle=twinkle)
                    if i not in (-size, size) and j not in (-size, size) and k == -size:
                        k = size
                    else:
                        k += 1
        self.flash(origin, frame, colors[0])

    def large_ball(self, origin, frame, **kw):
        self.ball(origin, frame, 0.5, 4, **kw)

    def small_ball(self, origin, frame, **kw):
        self.ball(origin, frame, 0.25, 2, **kw)

    # ---- rocket (FireworkRocketEntity), returns per-tick positions and the explosion frame
    def rocket(self, start, frame, flight=1, launch=True):
        r = self.rng
        tri = lambda: 0.002297 * (r.random() - r.random())                       # random.triangle(0, 0.002297)
        vel = Vector((tri(), 0.05, tri()))                                       # game axes
        pos = Vector((0, 0, 0))
        life = 10 * (1 + flight) + r.randrange(6) + r.randrange(7)                 # i = 1 + flight duration
        track = [(frame, Vector(start))]
        for t in range(1, life + 1):
            vel = Vector((vel.x * 1.15, vel.y + 0.04, vel.z * 1.15))
            pos += vel
            b = Vector(start) + mcv(*pos)
            f = frame + t * fps() / TPS
            track.append((f, b))
            self.spark(b, mcv(r.gauss(0, 1) * 0.05, -vel.y * 0.5, r.gauss(0, 1) * 0.05), f, WHITE)
        return track

    def build(self, name, collection=None):
        me = bpy.data.meshes.new(name)
        me.vertices.add(len(self.pts))
        me.vertices.foreach_set("co", [0.0] * 3 * len(self.pts))

        def attr(key, typ, vals):
            a = me.attributes.new(key, typ, 'POINT')
            a.data.foreach_set("vector" if typ == 'FLOAT_VECTOR' else ("color" if typ == 'FLOAT_COLOR' else "value"), vals)

        P = self.pts
        attr("fw_p0", 'FLOAT_VECTOR', [c for p in P for c in p['p0']])
        attr("fw_v0", 'FLOAT_VECTOR', [c for p in P for c in p['v0']])
        # game colours are sRGB; colour attributes are scene-linear
        attr("fw_col", 'FLOAT_COLOR', [c for p in P for c in (*map(srgb_to_linear, p['col']), 1.0)])
        attr("fw_fade", 'FLOAT_COLOR', [c for p in P for c in (*map(srgb_to_linear, p['fade']), 1.0)])
        for k in ("birth", "age0", "life", "hasfade", "twinkle", "q", "kind", "g", "f"):
            attr("fw_" + k, 'FLOAT', [float(p[k]) for p in P])
        ob = bpy.data.objects.new(name, me)
        (collection or bpy.context.scene.collection).objects.link(ob)
        # particles never cast shadows in the game; in EEVEE thousands of shadow-casting quads
        # overflow the shadow buffer ("Shadow buffer full") and stall the render
        ob.visible_shadow = False
        mod = ob.modifiers.new("MC Firework", 'NODES')
        mod.node_group = node_group()
        cam = bpy.context.scene.camera
        if cam is not None:
            set_input(mod, "Camera", cam)
        set_input(mod, "FPS", float(fps()))
        return ob


def fps():
    s = bpy.context.scene
    return s.render.fps / s.render.fps_base


def set_input(mod, name, value):
    """Set a Geometry Nodes modifier input by its interface name (Blender 5.x API, 4.x fallback)."""
    sid = socket_id(mod.node_group, name)
    props = getattr(mod, "properties", None)
    if props is not None and hasattr(props, "inputs"):
        getattr(props.inputs, sid).value = value
    else:
        mod[sid] = value


def socket_id(ng, name):
    return next(i.identifier for i in ng.interface.items_tree if getattr(i, "name", None) == name and i.in_out == 'INPUT')


# ------------------------------------------------------------------ geometry nodes
class _B:
    """Tiny helper to build math node chains."""

    def __init__(self, nt):
        self.nt, self.x = nt, -1600

    def node(self, typ, **props):
        n = self.nt.nodes.new(typ)
        for k, v in props.items():
            setattr(n, k, v)
        n.location = (self.x, 0)
        self.x += 40
        return n

    def link(self, out, inp):
        if isinstance(out, (int, float)):
            inp.default_value = out
        else:
            self.nt.links.new(out, inp)

    def math(self, op, a, b=0.0, c=None):
        n = self.node('ShaderNodeMath', operation=op)
        self.link(a, n.inputs[0]); self.link(b, n.inputs[1])
        if c is not None:
            self.link(c, n.inputs[2])
        return n.outputs[0]

    def vmath(self, op, a, b=None, s=None):
        n = self.node('ShaderNodeVectorMath', operation=op)
        self.link(a, n.inputs[0])
        if b is not None:
            self.link(b, n.inputs[1])
        if s is not None:
            self.link(s, n.inputs['Scale'])
        return n.outputs['Vector'] if op != 'LENGTH' else n.outputs['Value']

    def attr(self, name, dtype='FLOAT'):
        n = self.node('GeometryNodeInputNamedAttribute', data_type=dtype)
        n.inputs['Name'].default_value = name
        return n.outputs['Attribute']

    def cmp(self, op, a, b):
        n = self.node('FunctionNodeCompare', data_type='FLOAT', operation=op)
        self.link(a, n.inputs[0]); self.link(b, n.inputs[1])
        return n.outputs[0]

    def mix_col(self, fac, a, b):
        n = self.node('ShaderNodeMix', data_type='RGBA')
        self.link(fac, n.inputs['Factor']); self.link(a, n.inputs[6]); self.link(b, n.inputs[7])
        return n.outputs[2]

    def comb(self, x, y, z):
        n = self.node('ShaderNodeCombineXYZ')
        self.link(x, n.inputs[0]); self.link(y, n.inputs[1]); self.link(z, n.inputs[2])
        return n.outputs[0]

    def sep(self, v):
        n = self.node('ShaderNodeSeparateXYZ')
        self.link(v, n.inputs[0])
        return n.outputs


GN_NAME = "MC Firework v1"


def node_group():
    ng = bpy.data.node_groups.get(GN_NAME)
    if ng:
        return ng
    ng = bpy.data.node_groups.new(GN_NAME, 'GeometryNodeTree')
    ng.interface.new_socket("Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket("Camera", in_out='INPUT', socket_type='NodeSocketObject')
    s = ng.interface.new_socket("FPS", in_out='INPUT', socket_type='NodeSocketFloat'); s.default_value = 24.0
    ng.interface.new_socket("Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    nt, B = ng, _B(ng)
    gin, gout = B.node('NodeGroupInput'), B.node('NodeGroupOutput')

    pts = B.node('GeometryNodeMeshToPoints')
    B.link(gin.outputs['Geometry'], pts.inputs['Mesh'])
    t = B.node('GeometryNodeInputSceneTime').outputs['Frame']
    fps_val = gin.outputs['FPS']                                                  # frames per second

    birth, age0, life = B.attr("fw_birth"), B.attr("fw_age0"), B.attr("fw_life")
    g, fr, kind, q = B.attr("fw_g"), B.attr("fw_f"), B.attr("fw_kind"), B.attr("fw_q")
    dt = B.math('SUBTRACT', t, birth)                                             # frames since birth
    n = B.math('MULTIPLY', B.math('DIVIDE', dt, fps_val), TPS)                    # ticks since birth
    n = B.math('MAXIMUM', n, 0.0)
    age = B.math('ADD', age0, n)
    alive = B.node('FunctionNodeBooleanMath', operation='AND')
    B.link(B.cmp('GREATER_EQUAL', dt, 0.0), alive.inputs[0])
    B.link(B.cmp('LESS_THAN', age, life), alive.inputs[1])

    # motion: S = (1 - f^n)/(1 - f); xy = v0.xy*S; z = n*w* + (w0 - w*)*S, w* = -g/(1-f), w0 = v0z - g
    fsafe = B.math('MINIMUM', fr, 0.9999)
    one_m_f = B.math('SUBTRACT', 1.0, fsafe)
    S = B.math('DIVIDE', B.math('SUBTRACT', 1.0, B.math('POWER', fsafe, n)), one_m_f)
    v0 = B.sep(B.attr("fw_v0", 'FLOAT_VECTOR'))
    wstar = B.math('DIVIDE', B.math('MULTIPLY', g, -1.0), one_m_f)
    w0 = B.math('SUBTRACT', v0[2], g)
    dz = B.math('ADD', B.math('MULTIPLY', n, wstar), B.math('MULTIPLY', B.math('SUBTRACT', w0, wstar), S))
    disp = B.comb(B.math('MULTIPLY', v0[0], S), B.math('MULTIPLY', v0[1], S), dz)
    pos = B.vmath('ADD', B.attr("fw_p0", 'FLOAT_VECTOR'), disp)
    setp = B.node('GeometryNodeSetPosition')
    B.link(pts.outputs['Points'], setp.inputs['Geometry']); B.link(pos, setp.inputs['Position'])

    # sparks: alpha + colour fade after half-life
    half = B.math('MULTIPLY', life, 0.5)
    past = B.math('MAXIMUM', B.math('SUBTRACT', age, half), 0.0)
    a_spark = B.math('MULTIPLY', 0.99, B.math('SUBTRACT', 1.0, B.math('DIVIDE', past, life)))
    lerp = B.math('MULTIPLY', B.attr("fw_hasfade"), B.math('SUBTRACT', 1.0, B.math('POWER', 0.8, past)))
    col = B.mix_col(lerp, B.attr("fw_col", 'FLOAT_COLOR'), B.attr("fw_fade", 'FLOAT_COLOR'))
    idx = B.math('MINIMUM', B.math('FLOOR', B.math('DIVIDE', B.math('MULTIPLY', B.math('FLOOR', age), 7.0), life)), 7.0)
    # twinkle: hidden if twinkle and age >= life/3 and floor((floor(age)+life)/3) is odd
    odd = B.math('FLOORED_MODULO', B.math('FLOOR', B.math('DIVIDE', B.math('ADD', B.math('FLOOR', age), life), 3.0)), 2.0)
    hide_tw = B.math('MULTIPLY', B.math('MULTIPLY', B.attr("fw_twinkle"), B.cmp('GREATER_EQUAL', age, B.math('DIVIDE', life, 3.0))), odd)
    # flash: half-size 7.1 sin((age-1) pi/4), alpha 0.6 - (age-1)*0.125
    am1 = B.math('SUBTRACT', age, 1.0)
    q_flash = B.math('MAXIMUM', B.math('MULTIPLY', 7.1, B.math('SINE', B.math('MULTIPLY', am1, math.pi * 0.25))), 0.0)
    a_flash = B.math('MAXIMUM', B.math('SUBTRACT', 0.6, B.math('MULTIPLY', am1, 0.125)), 0.0)
    is_flash = B.cmp('GREATER_THAN', kind, 0.5)
    qsize = B.math('ADD', B.math('MULTIPLY', is_flash, q_flash), B.math('MULTIPLY', B.math('SUBTRACT', 1.0, is_flash), q))
    alpha = B.math('ADD', B.math('MULTIPLY', is_flash, a_flash), B.math('MULTIPLY', B.math('SUBTRACT', 1.0, is_flash), a_spark))

    keep = B.node('FunctionNodeBooleanMath', operation='AND')
    B.link(alive.outputs[0], keep.inputs[0])
    B.link(B.cmp('LESS_THAN', hide_tw, 0.5), keep.inputs[1])
    delete = B.node('GeometryNodeDeleteGeometry', domain='POINT')
    B.link(setp.outputs[0], delete.inputs['Geometry'])
    notkeep = B.node('FunctionNodeBooleanMath', operation='NOT')
    B.link(keep.outputs[0], notkeep.inputs[0])
    B.link(notkeep.outputs[0], delete.inputs['Selection'])

    def store(geo, name, value, dtype, domain='POINT'):
        st = B.node('GeometryNodeStoreNamedAttribute', data_type=dtype, domain=domain)
        B.link(geo, st.inputs['Geometry']); st.inputs['Name'].default_value = name
        B.link(value, st.inputs['Value'])
        return st.outputs['Geometry']

    geo = delete.outputs['Geometry']
    geo = store(geo, "p_col", col, 'FLOAT_COLOR')
    geo = store(geo, "p_alpha", alpha, 'FLOAT')
    geo = store(geo, "p_idx", idx, 'FLOAT')
    geo = store(geo, "p_kind", kind, 'FLOAT')

    # camera-facing quad, 1 x 1 m, scaled to 2 * half-size
    grid = B.node('GeometryNodeMeshGrid')
    grid.inputs['Size X'].default_value = 1.0; grid.inputs['Size Y'].default_value = 1.0
    grid.inputs['Vertices X'].default_value = 2; grid.inputs['Vertices Y'].default_value = 2
    quad = store(grid.outputs['Mesh'], "UVMap", grid.outputs['UV Map'], 'FLOAT2', 'CORNER')
    cam = B.node('GeometryNodeObjectInfo', transform_space='ORIGINAL')
    B.link(gin.outputs['Camera'], cam.inputs['Object'])
    inst = B.node('GeometryNodeInstanceOnPoints')
    B.link(geo, inst.inputs['Points']); B.link(quad, inst.inputs['Instance'])
    B.link(cam.outputs['Rotation'], inst.inputs['Rotation'])
    B.link(B.math('MULTIPLY', qsize, 2.0), inst.inputs['Scale'])
    real = B.node('GeometryNodeRealizeInstances')
    B.link(inst.outputs['Instances'], real.inputs['Geometry'])
    setm = B.node('GeometryNodeSetMaterial')
    B.link(real.outputs['Geometry'], setm.inputs['Geometry'])
    setm.inputs['Material'].default_value = particle_material()
    B.link(setm.outputs['Geometry'], gout.inputs['Geometry'])
    return ng


# ------------------------------------------------------------------ material
def _img(path):
    for im in bpy.data.images:
        if os.path.normpath(bpy.path.abspath(im.filepath)) == os.path.normpath(path):
            return im
    im = bpy.data.images.load(path)
    im.alpha_mode = 'STRAIGHT'
    return im


def particle_material(strength=12.0):
    name = "MC Firework Particle"
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for nd in list(nt.nodes):
        nt.nodes.remove(nd)
    N = lambda t, x, y: (lambda n: (setattr(n, "location", (x, y)), n)[1])(nt.nodes.new(t))
    L = nt.links.new
    out = N('ShaderNodeOutputMaterial', 900, 0)
    uv = N('ShaderNodeUVMap', -900, 200); uv.uv_map = "UVMap"
    sep = N('ShaderNodeSeparateXYZ', -720, 200); L(uv.outputs[0], sep.inputs[0])
    a_idx = N('ShaderNodeAttribute', -900, -100); a_idx.attribute_name = "p_idx"
    add = N('ShaderNodeMath', -540, 260); add.operation = 'ADD'; L(sep.outputs[0], add.inputs[0]); L(a_idx.outputs['Fac'], add.inputs[1])
    div = N('ShaderNodeMath', -380, 260); div.operation = 'DIVIDE'; L(add.outputs[0], div.inputs[0]); div.inputs[1].default_value = 8.0
    comb = N('ShaderNodeCombineXYZ', -220, 220); L(div.outputs[0], comb.inputs[0]); L(sep.outputs[1], comb.inputs[1])
    t_sp = N('ShaderNodeTexImage', -40, 260); t_sp.image = _img(os.path.join(FX, "spark_atlas.png")); t_sp.interpolation = 'Closest'
    t_sp.extension = 'CLIP'; L(comb.outputs[0], t_sp.inputs[0])
    t_fl = N('ShaderNodeTexImage', -40, -40); t_fl.image = _img(os.path.join(FX, "flash.png")); t_fl.interpolation = 'Linear'
    L(uv.outputs[0], t_fl.inputs[0])
    a_kind = N('ShaderNodeAttribute', -40, -300); a_kind.attribute_name = "p_kind"
    a_col = N('ShaderNodeAttribute', -40, -460); a_col.attribute_name = "p_col"
    a_alp = N('ShaderNodeAttribute', -40, -620); a_alp.attribute_name = "p_alpha"
    mixc = N('ShaderNodeMix', 220, 200); mixc.data_type = 'RGBA'
    L(a_kind.outputs['Fac'], mixc.inputs['Factor']); L(t_sp.outputs['Color'], mixc.inputs[6]); L(t_fl.outputs['Color'], mixc.inputs[7])
    mixa = N('ShaderNodeMix', 220, -40); mixa.data_type = 'FLOAT'
    L(a_kind.outputs['Fac'], mixa.inputs['Factor']); L(t_sp.outputs['Alpha'], mixa.inputs[2]); L(t_fl.outputs['Alpha'], mixa.inputs[3])
    tint = N('ShaderNodeMix', 400, 200); tint.data_type = 'RGBA'; tint.blend_type = 'MULTIPLY'
    tint.inputs['Factor'].default_value = 1.0; L(mixc.outputs[2], tint.inputs[6]); L(a_col.outputs['Color'], tint.inputs[7])
    em = N('ShaderNodeEmission', 560, 200); L(tint.outputs[2], em.inputs['Color']); em.inputs['Strength'].default_value = strength
    em.label = "Strength"
    alpha = N('ShaderNodeMath', 400, -40); alpha.operation = 'MULTIPLY'
    L(mixa.outputs[0], alpha.inputs[0]); L(a_alp.outputs['Fac'], alpha.inputs[1])
    tr = N('ShaderNodeBsdfTransparent', 560, 40)
    ms = N('ShaderNodeMixShader', 740, 100)
    L(alpha.outputs[0], ms.inputs[0]); L(tr.outputs[0], ms.inputs[1]); L(em.outputs[0], ms.inputs[2])
    L(ms.outputs[0], out.inputs['Surface'])
    for attr, val in (('surface_render_method', 'BLENDED'), ('use_transparent_shadow', True)):
        try:
            setattr(m, attr, val)
        except (AttributeError, TypeError):
            pass
    m.use_backface_culling = False
    return m


def set_flash_gain(gain=1.0):
    """Scale the explosion flash (OverlayParticle) opacity; sparks are untouched. The game's
    flash is 0.6 alpha; the finale keeps it lower so no flash swamps the frame (photosensitivity)."""
    m = particle_material()
    nt = m.node_tree
    g = nt.nodes.get("FlashGain")
    if g is None:
        ms = next(n for n in nt.nodes if n.type == 'MIX_SHADER')
        alpha = ms.inputs[0].links[0].from_node
        kind = next(n for n in nt.nodes if n.type == 'ATTRIBUTE' and n.attribute_name == "p_kind")
        g = nt.nodes.new('ShaderNodeMapRange')            # kind 0 -> 1, kind 1 -> gain
        g.name = g.label = "FlashGain"
        nt.links.new(kind.outputs['Fac'], g.inputs['Value'])
        g.inputs['To Min'].default_value = 1.0
        mul = nt.nodes.new('ShaderNodeMath')
        mul.operation = 'MULTIPLY'
        nt.links.new(alpha.outputs[0], mul.inputs[0])
        nt.links.new(g.outputs['Result'], mul.inputs[1])
        nt.links.new(mul.outputs[0], ms.inputs[0])
    g.inputs['To Max'].default_value = gain
    return m


def glow_light(name, pos, frame, col, peak=15000.0, attack=4, hold=2, decay=36, collection=None):
    """Explosion light without a hard on/off: rises over `attack` frames, holds, then fades out
    (smoothstep keys). No shadows. For the finale, where light must flow, not strobe."""
    ld = bpy.data.lights.new(name, 'POINT')
    ld.color = tuple(srgb_to_linear(c) for c in rgb(col))
    ld.shadow_soft_size = 2.0
    ld.use_shadow = False
    ob = bpy.data.objects.new(name, ld)
    (collection or bpy.context.scene.collection).objects.link(ob)
    ob.location = pos
    keys = [(frame - attack, 0.0), (frame, peak), (frame + hold, peak), (frame + hold + decay, 0.0)]
    for f, e in keys:
        ld.energy = e
        ld.keyframe_insert("energy", frame=f)
    ad = ob.data.animation_data
    if ad and ad.action:
        for layer in ad.action.layers:
            for strip in layer.strips:
                for cb in strip.channelbags:
                    for fc in cb.fcurves:
                        for k in fc.keyframe_points:
                            k.interpolation = 'BEZIER'
                            k.handle_left_type = k.handle_right_type = 'AUTO_CLAMPED'
    return ob


# ------------------------------------------------------------------ helpers for a shot
def rocket_object(name, track, collection=None):
    """The flying rocket item as a camera-facing sprite, keyed per tick."""
    me = bpy.data.meshes.new(name)
    s = 0.25
    me.from_pydata([(-s, 0, -s), (s, 0, -s), (s, 0, s), (-s, 0, s)], [], [(0, 1, 2, 3)])
    uvl = me.uv_layers.new(name="UVMap")
    for i, uv in enumerate([(0, 0), (1, 0), (1, 1), (0, 1)]):
        uvl.data[i].uv = uv
    m = bpy.data.materials.get("MC Firework Rocket Item")
    if not m:
        m = bpy.data.materials.new("MC Firework Rocket Item"); m.use_nodes = True
        nt = m.node_tree
        b = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
        t = nt.nodes.new('ShaderNodeTexImage'); t.image = _img(os.path.join(ITEM, "firework_rocket.png")); t.interpolation = 'Closest'
        nt.links.new(t.outputs['Color'], b.inputs['Base Color']); nt.links.new(t.outputs['Alpha'], b.inputs['Alpha'])
        try:
            m.surface_render_method = 'DITHERED'
        except Exception:
            pass
    me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    (collection or bpy.context.scene.collection).objects.link(ob)
    ob.visible_shadow = False
    cam = bpy.context.scene.camera
    if cam:
        c = ob.constraints.new('DAMPED_TRACK'); c.target = cam; c.track_axis = 'TRACK_NEGATIVE_Y'
    for f, p in track:
        ob.location = p
        ob.keyframe_insert("location", frame=f)
    ob.hide_render = False
    end = track[-1][0]
    ob.scale = (1, 1, 1); ob.keyframe_insert("scale", frame=end)
    ob.scale = (0, 0, 0); ob.keyframe_insert("scale", frame=end + 0.01)
    return ob


def burst_light(name, pos, frames, col, energy=60000.0, decay_frames=30, collection=None):
    """One shadowed point light per rocket (not per star): re-flashes at every star's frame."""
    ld = bpy.data.lights.new(name, 'POINT')
    ld.color = tuple(srgb_to_linear(c) for c in rgb(col)); ld.shadow_soft_size = 0.5
    ob = bpy.data.objects.new(name, ld)
    (collection or bpy.context.scene.collection).objects.link(ob)
    ob.location = pos
    keys = {frames[0] - 1: 0.0}
    for i, f in enumerate(frames):
        e = energy if i == 0 else energy * 0.5
        keys[f] = max(keys.get(f, 0.0), e)
        keys[f + 3] = max(keys.get(f + 3, 0.0), e * 0.6)
    keys[frames[-1] + decay_frames] = 0.0
    for f in sorted(keys):
        ld.energy = keys[f]
        ld.keyframe_insert("energy", frame=f)
    return ob


def flash_light(name, pos, frame, col, energy=40000.0, decay_frames=30, collection=None):
    ld = bpy.data.lights.new(name, 'POINT')
    ld.color = tuple(srgb_to_linear(c) for c in rgb(col)); ld.shadow_soft_size = 0.5
    ob = bpy.data.objects.new(name, ld)
    (collection or bpy.context.scene.collection).objects.link(ob)
    ob.location = pos
    for f, e in ((frame - 1, 0.0), (frame, energy), (frame + 3, energy * 0.6), (frame + decay_frames, 0.0)):
        ld.energy = e
        ld.keyframe_insert("energy", frame=f)
    return ob
