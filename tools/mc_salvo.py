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
