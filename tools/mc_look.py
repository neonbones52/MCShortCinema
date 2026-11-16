"""Film looks (grades) for Memory Reboot, built in the Blender compositor so every render comes
out graded. Run inside Blender.

    import mc_look as L
    L.apply("village")            # 'village', 'cold', 'night', 'memory', 'finale', or 'none'

Chain (scene linear, before the view transform):
  Render Layers -> exposure -> white balance -> lift/gamma/gain -> contrast (around 0.18)
  -> saturation -> bloom (Glare) -> highlight roll-off (soft clip, so fireworks and the sun
  keep detail under the Standard view transform) -> vignette -> grain -> output
Distance haze is not here: it lives in the materials (mc_sky.apply(haze=LOOKS[n]['haze'])),
so it sits behind the characters and does not veil them.
"""
import bpy

# Values are starting points from look-dev 2026-11-16 (approved / tuned values go here).
LOOKS = {
    # Sensitivities (measured in Blender 5.2, input 0.05 linear): Color Lift 0.98 -> -38 %,
    # Base Lift 0.02 -> +38 %, Color Gamma 0.96 -> -12 %. So lift/gamma colours stay within a
    # few thousandths / hundredths of 1.0; warmth and coolness come mainly from the white point.
    # warm, saturated village: sun-warmed, gentle contrast, soft bloom, light air
    'village': dict(exposure=0.0, temp=(6500, 5900), tint=(10, 11), lift=(1.0, 1.0, 0.996, 0.0),
                    gamma=(1.0, 1.0, 0.985, 1.0), gain=(1.03, 1.01, 0.97, 1.0), contrast=1.04,
                    saturation=1.07, bloom=dict(threshold=1.0, strength=0.12, size=0.6),
                    vignette=0.18, grain=0.0, knee=0.8,
                    haze=dict(start=40, end=260, amount=0.30)),
    # after the summons: cold grey-blue, drained, flat, heavier air
    'cold': dict(exposure=-0.1, temp=(6500, 7800), tint=(10, 7), lift=(0.997, 0.999, 1.006, 0.006),
                 gamma=(0.99, 1.0, 1.015, 1.0), gain=(0.97, 0.99, 1.02, 1.0), contrast=0.93,
                 saturation=0.55, bloom=dict(threshold=1.2, strength=0.06, size=0.5),
                 vignette=0.22, grain=0.0, knee=0.8,
                 haze=dict(start=20, end=170, amount=0.55)),
    # night flight / ambush: blue shadows that do not crush, fireworks bloom, colours kept
    'night': dict(exposure=0.2, temp=(6500, 7600), tint=(10, 9), lift=(0.997, 0.999, 1.008, 0.003),
                  gamma=(0.985, 1.0, 1.02, 1.0), gain=(1.0, 1.0, 1.0, 1.0), contrast=1.04,
                  saturation=0.9, bloom=dict(threshold=0.7, strength=0.35, size=0.6),
                  vignette=0.28, grain=0.0, knee=0.75,
                  haze=dict(start=30, end=200, amount=0.35)),
    # memories (shot 22): overexposed, warm beige-yellow, glowing, lifted shadows, low contrast,
    # haze, vignette, grain
    'memory': dict(exposure=0.7, temp=(6500, 4400), tint=(10, 16), lift=(1.0, 0.996, 0.984, 0.030),
                   gamma=(1.05, 1.02, 0.95, 1.0), gain=(1.03, 0.99, 0.86, 1.0), contrast=0.80,
                   saturation=0.9, bloom=dict(threshold=0.35, strength=0.85, size=0.9),
                   vignette=0.38, grain=0.09, knee=0.7,
                   haze=dict(start=6, end=80, amount=0.45, color=(0.95, 0.85, 0.62))),
    # finale: night look, darker; the fireworks carry the colour
    'finale': dict(exposure=0.0, temp=(6500, 7400), tint=(10, 9), lift=(0.998, 0.999, 1.005, 0.002),
                   gamma=(0.99, 1.0, 1.015, 1.0), gain=(1.0, 1.0, 1.0, 1.0), contrast=1.08,
                   saturation=0.95, bloom=dict(threshold=0.7, strength=0.30, size=0.6),
                   vignette=0.30, grain=0.0, knee=0.75,
                   haze=dict(start=30, end=200, amount=0.25)),
}


def _menu(sock, *choices):
    for c in choices:
        try:
            sock.default_value = c
            return c
        except (TypeError, ValueError):
            continue
    raise ValueError(f"none of {choices} accepted")


def _per_channel_math(nt, src, fn):
    """Apply fn(nt, value_socket) -> socket to R, G, B; alpha passes through."""
    sep = nt.nodes.new('CompositorNodeSeparateColor')
    nt.links.new(src, sep.inputs[0])
    comb = nt.nodes.new('CompositorNodeCombineColor')
    for i, ch in enumerate(('Red', 'Green', 'Blue')):
        nt.links.new(fn(nt, sep.outputs[i]), comb.inputs[i])
    nt.links.new(sep.outputs[3], comb.inputs[3])
    return comb.outputs[0]


def _math(nt, op, a, b=None, clamp=False):
    m = nt.nodes.new('ShaderNodeMath')
    m.operation = op
    m.use_clamp = clamp
    for i, v in enumerate((a, b)):
        if v is None:
            continue
        if isinstance(v, (int, float)):
            m.inputs[i].default_value = v
        else:
            nt.links.new(v, m.inputs[i])
    return m.outputs[0]


def _contrast(nt, src, c, pivot=0.18):
    """x -> pivot * (x / pivot) ^ c per channel (log contrast in linear light)."""
    if abs(c - 1.0) < 1e-4:
        return src

    def f(nt, v):
        x = _math(nt, 'MAXIMUM', v, 0.0)
        return _math(nt, 'MULTIPLY', _math(nt, 'POWER', _math(nt, 'DIVIDE', x, pivot), c), pivot)
    return _per_channel_math(nt, src, f)


def _soft_clip(nt, src, knee):
    """Highlight roll-off: identity below `knee`, then knee + (1-knee)(1 - exp(-(x-knee)/(1-knee)))."""
    w = 1.0 - knee

    def f(nt, v):
        over = _math(nt, 'MAXIMUM', _math(nt, 'SUBTRACT', v, knee), 0.0)
        rolled = _math(nt, 'MULTIPLY', _math(nt, 'SUBTRACT', 1.0, _math(nt, 'EXPONENT', _math(nt, 'DIVIDE', over, -w))), w)
        return _math(nt, 'ADD', _math(nt, 'MINIMUM', v, knee), rolled)
    return _per_channel_math(nt, src, f)


def build(name):
    """Build (or rebuild) the compositor group for look `name` and make it the scene's."""
    sc = bpy.context.scene
    gname = "MC.Look"
    nt = bpy.data.node_groups.get(gname)
    if nt is None:
        nt = bpy.data.node_groups.new(gname, 'CompositorNodeTree')
        nt.interface.new_socket("Image", in_out='OUTPUT', socket_type='NodeSocketColor')
    nt.nodes.clear()
    rl = nt.nodes.new('CompositorNodeRLayers')
    rl.scene = sc
    out = nt.nodes.new('NodeGroupOutput')
    src = rl.outputs['Image']
    sc.compositing_node_group = nt
    sc["mc_look"] = name
    if name == 'none' or name not in LOOKS:
        nt.links.new(src, out.inputs[0])
        return nt
    P = LOOKS[name]

    ex = nt.nodes.new('CompositorNodeExposure')
    ex.inputs['Exposure'].default_value = P['exposure']
    nt.links.new(src, ex.inputs['Image'])
    src = ex.outputs[0]

    wb = nt.nodes.new('CompositorNodeColorBalance')
    _menu(wb.inputs['Type'], 'White Point', 'Whitepoint', 'WHITEPOINT')
    wb.inputs['Input Temperature'].default_value, wb.inputs['Output Temperature'].default_value = P['temp']
    wb.inputs['Input Tint'].default_value, wb.inputs['Output Tint'].default_value = P['tint']
    nt.links.new(src, wb.inputs['Image'])
    src = wb.outputs[0]

    lgg = nt.nodes.new('CompositorNodeColorBalance')
    _menu(lgg.inputs['Type'], 'Lift/Gamma/Gain', 'Lift Gamma Gain', 'LIFT_GAMMA_GAIN')
    lr, lg_, lb, base = P['lift']
    lgg.inputs['Color Lift'].default_value = (lr, lg_, lb, 1)
    lgg.inputs['Base Lift'].default_value = base
    lgg.inputs['Color Gamma'].default_value = P['gamma']
    lgg.inputs['Color Gain'].default_value = P['gain']
    nt.links.new(src, lgg.inputs['Image'])
    src = lgg.outputs[0]

    src = _contrast(nt, src, P['contrast'])

    hs = nt.nodes.new('CompositorNodeHueSat')
    hs.inputs['Saturation'].default_value = P['saturation']
    nt.links.new(src, hs.inputs['Image'])
    src = hs.outputs[0]

    b = P.get('bloom')
    if b:
        gl = nt.nodes.new('CompositorNodeGlare')
        _menu(gl.inputs['Type'], 'Bloom', 'BLOOM')
        _menu(gl.inputs['Quality'], 'High', 'HIGH', 'Medium')
        gl.inputs['Threshold'].default_value = b['threshold']
        gl.inputs['Strength'].default_value = b['strength']
        gl.inputs['Size'].default_value = b['size']             # 0..1, fraction of the image
        nt.links.new(src, gl.inputs['Image'])
        src = gl.outputs[0]

    src = _soft_clip(nt, src, P['knee'])

    # vignette: darken by distance from the centre (aspect-correct), smooth
    if P.get('vignette', 0) > 0:
        ic = nt.nodes.new('CompositorNodeImageCoordinates')
        nt.links.new(src, ic.inputs[0])
        ln = nt.nodes.new('ShaderNodeVectorMath')
        ln.operation = 'LENGTH'
        nt.links.new(ic.outputs['Normalized'], ln.inputs[0])
        mr = nt.nodes.new('ShaderNodeMapRange')
        mr.clamp = True
        mr.interpolation_type = 'SMOOTHSTEP'
        mr.inputs['From Min'].default_value = 0.45
        mr.inputs['From Max'].default_value = 1.25
        mr.inputs['To Min'].default_value = 1.0
        mr.inputs['To Max'].default_value = 1.0 - P['vignette']
        nt.links.new(ln.outputs['Value'], mr.inputs['Value'])
        mul = nt.nodes.new('ShaderNodeMix')
        mul.data_type = 'RGBA'
        mul.blend_type = 'MULTIPLY'
        mul.inputs['Factor'].default_value = 1.0
        nt.links.new(src, mul.inputs['A'])
        nt.links.new(mr.outputs['Result'], mul.inputs['B'])
        src = mul.outputs['Result']

    # grain (memories only, per the approved look): per-frame white noise applied as a
    # multiplicative +-grain in linear light, so it reads evenly from shadows to highlights
    # like film grain instead of speckling the darks (an additive noise did that, 2026-11-16)
    if P.get('grain', 0) > 0:
        ic2 = nt.nodes.new('CompositorNodeImageCoordinates')
        nt.links.new(src, ic2.inputs[0])
        st = nt.nodes.new('CompositorNodeSceneTime')
        wn = nt.nodes.new('ShaderNodeTexWhiteNoise')
        wn.noise_dimensions = '4D'
        nt.links.new(ic2.outputs['Pixel'], wn.inputs['Vector'])
        nt.links.new(st.outputs['Frame'], wn.inputs['W'])
        factor = _math(nt, 'ADD', _math(nt, 'MULTIPLY', _math(nt, 'SUBTRACT', wn.outputs['Value'], 0.5), P['grain'] * 2.0), 1.0)
        mul = nt.nodes.new('ShaderNodeMix')
        mul.data_type = 'RGBA'
        mul.blend_type = 'MULTIPLY'
        mul.inputs['Factor'].default_value = 1.0
        nt.links.new(src, mul.inputs['A'])
        nt.links.new(factor, mul.inputs['B'])
        src = mul.outputs['Result']

    nt.links.new(src, out.inputs[0])
    return nt


def apply(name, view_transform='Standard'):
    """Grade the scene with look `name`. Standard view transform keeps the game's colours in the
    mid-tones; the soft clip in the grade handles highlights."""
    sc = bpy.context.scene
    sc.view_settings.view_transform = view_transform
    sc.view_settings.look = 'None'
    return build(name)
