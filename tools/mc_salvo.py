"""Barrages of Alex's crossbowmen for the ambush and the finale (shots 19-21, 25-28).

Rockets follow the crossbow shot of the game (mc_crossbow.shoot: multishot fan of 3, straight
flight at 1.6 blocks/tick, explosion at the end of the lifetime, 64-80 blocks with three
gunpowder). The shooters themselves need not be in frame: shots start on a trench line.

Photosensitivity (approved: no more than ~3 bright flashes per second, no global flicker):
  - explosion light rises and falls smoothly (FW.glow_light), no shadows, modest peak, so the
    lit ground and characters change by well under 10 % relative luminance;
  - the explosion flash particle is dimmed (FW.set_flash_gain);
  - firing times come from a smooth wave-shaped rate, so explosions spread instead of landing
    in one frame;
  - every render is then measured with tools/flash_check.py (WCAG 2.3.1).
"""
import math
import random
import bpy

from mathutils import Vector

import mc_crossbow as XB
import mc_firework as FW

PALETTE = ('red', 'orange', 'yellow', 'lime', 'light_blue', 'magenta', 'pink', 'cyan', 'white', 'purple')


def barrage(cloud, line_a, line_b, aim_dir, frame0, frame1, seed=7, shots_per_second=1.6,
            wave_period=3.5, wave_depth=0.6, pitch=(22.0, 42.0), yaw_spread=22.0, flight=3,
            colors=PALETTE, light_peak=6000.0, collection=None, name="Salvo"):
    """Crossbowmen along the segment line_a -> line_b (eye height included) fire multishot
    volleys towards horizontal aim_dir between frame0 and frame1. The firing rate swells and
    ebbs in waves (wave_period seconds, wave_depth 0..1). Returns the list of
    (burst_frame, burst_pos, colour) for the lights / checks."""
    rng = random.Random(seed)
    fps = XB.fps()
    a, b = Vector(line_a), Vector(line_b)
    aim = Vector((aim_dir[0], aim_dir[1], 0)).normalized()
    bursts = []

    def light(nm, pos, f, col):
        FW.glow_light(nm, pos, f, col, peak=light_peak, collection=collection)

    f = float(frame0)
    k = 0
    while f < frame1:
        rate = shots_per_second * (1.0 - wave_depth * 0.5 * (1 + math.cos(2 * math.pi * (f / fps) / wave_period)))
        rate = max(rate, 0.15)
        f += rng.expovariate(rate) * fps                  # Poisson firing at the current rate
        if f >= frame1:
            break
        origin = a.lerp(b, rng.random())
        yaw = math.radians(rng.uniform(-yaw_spread, yaw_spread))
        p = math.radians(rng.uniform(*pitch))
        d = Vector((aim.x * math.cos(yaw) - aim.y * math.sin(yaw), aim.x * math.sin(yaw) + aim.y * math.cos(yaw), 0))
        d = Vector((d.x * math.cos(p), d.y * math.cos(p), math.sin(p)))
        shots = XB.shoot(cloud, origin, d, round(f, 2), rng, colors, flight=flight, multishot=True,
                         explode=True, light=True, collection=collection, name=f"{name}.{k}", light_fn=light)
        bursts += [(bf, bp, col) for _, bf, bp, col in shots]
        k += 1
    return bursts


def key_light(lights, target, frame0, frame1, share=0.75, name="Barrage.Key", collection=None):
    """One shadowed key light standing in for many shadowless burst lights (the bursts are far
    off and each has use_shadow off: alone they flood the field flat, with no form). Every frame
    the burst lights' irradiance at `target` is summed (point light of P watts: P / (4 pi^2 d^2));
    a sun lamp takes `share` of it, from the weighted direction of the bursts and in their
    weighted colour, with shadows; the burst lights keep the rest (coloured glints).
    lights: the burst light objects (FW.glow_light, energy keyed)."""
    target = Vector(target)

    def energy_curve(ob):
        ad = ob.data.animation_data
        for layer in ad.action.layers:
            for strip in layer.strips:
                for cb in strip.channelbags:
                    for fc in cb.fcurves:
                        if fc.data_path == "energy":
                            return fc
        return None

    data = []
    for ob in lights:
        fc = energy_curve(ob)
        if fc is None:
            continue
        d2 = max((ob.location - target).length_squared, 1.0)
        data.append((fc, ob.location.copy(), Vector(ob.data.color), d2))
    ld = bpy.data.lights.new(name, 'SUN')
    ld.angle = math.radians(1.5)
    ld.use_shadow = True
    sun = bpy.data.objects.new(name, ld)
    (collection or bpy.context.scene.collection).objects.link(sun)
    sun.rotation_mode = 'QUATERNION'
    prev_q = None
    for f in range(int(frame0), int(frame1) + 1):
        tot, pos, col = 0.0, Vector((0, 0, 0)), Vector((0, 0, 0))
        for fc, p, c, d2 in data:
            e = max(fc.evaluate(f), 0.0) / (4 * math.pi * math.pi * d2)
            tot += e
            pos += p * e
            col += c * e
        ld.energy = tot * share
        ld.keyframe_insert("energy", frame=f)
        if tot > 1e-9:
            src = pos / tot
            ld.color = tuple(col / max(col) if max(col) > 0 else Vector((1, 1, 1)))
            q = (target - src).to_track_quat('-Z', 'Y')
            if prev_q is not None and q.dot(prev_q) < 0:
                q.negate()
            sun.rotation_quaternion = q
            prev_q = q
        ld.keyframe_insert("color", frame=f)
        sun.keyframe_insert("rotation_quaternion", frame=f)
    for fc, _p, _c, _d in data:                     # the burst lights keep the rest
        for k in fc.keyframe_points:
            k.co.y *= (1.0 - share)
            k.handle_left.y *= (1.0 - share)
            k.handle_right.y *= (1.0 - share)
    return sun
