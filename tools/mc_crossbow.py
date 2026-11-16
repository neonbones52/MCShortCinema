"""Crossbows firing fireworks ("rocket launcher"), as in Minecraft 26.2 (read with javap).

CrossbowItem            FIREWORK_POWER 1.6 b/tick (arrows 3.15), inaccuracy 1.0
ProjectileWeaponItem    multishot: 3 projectiles, yaw offsets 0, -10, +10 deg (spread 10)
Projectile.shoot        dir = normalize(dir) + gauss * 0.0172275 * inaccuracy, then * power
FireworkRocketEntity    shot at angle: no acceleration, no gravity, straight line; a white spark
                        every tick with v = (gauss*0.05, -vy*0.5, gauss*0.05); lifetime
                        10*(1+flight) + rand(6) + rand(7) ticks, then it explodes
AnimationUtils          hold:   R.y = -0.3 + head.y, L.y = 0.6 + head.y,
                                R.x = -pi/2 + head.x + 0.1, L.x = -1.5 + head.x
                        charge: R.y = -0.8, R.x = L.x = -0.9708, L.y = lerp(t, 0.4, 0.85),
                                L.x -> lerp(t, L.x, -pi/2), t = use ticks / charge ticks
Quick Charge III        charge 10 ticks (0.5 s)
Range                   lifetime x 1.6 b/tick: flight 1 -> 32-48 blocks, 2 -> 48-64, 3 -> 64-80 (default 3,
                        three gunpowder: the ambush needs the long range)
"""
import math
import os
import random

import bpy
from mathutils import Matrix, Vector

import mc_character as C
import mc_firework as FW

TPS = 20.0
POWER = 1.6
CHARGE_TICKS_QC3 = 10
GRIP = (11, 12)                     # sprite pixel the fist closes on (stock)
MUZZLE_DIR = (-1, 1)                # from the stock towards the loaded rocket, sprite (right, up)


def fps():
    s = bpy.context.scene
    return s.render.fps / s.render.fps_base


def attach_crossbow(rig):
    """Two sprites on the right hand: loaded (with a firework) and drawn-back/empty.
    Returns (loaded, empty); toggle with set_loaded()."""
    col = rig.users_collection[0]
    out = []
    for tex in ("crossbow_firework", "crossbow_pulling_2"):
        it = C.item_mesh(f"{rig.name[:-4]}.{tex}", os.path.join(C.TEX, "item", tex + ".png"), col, grip=GRIP)
        # muzzle along the arm (down at rest -> forward when aiming); bow lies flat when aimed
        it.matrix_world = rig.matrix_world @ (Matrix.Translation(C.m2b((-6, 11, -0.5)))
                                              @ Matrix.Rotation(math.radians(225), 4, 'Y')
                                              @ Matrix.Scale(0.9, 4))
        bpy.context.view_layer.update()
        mw = it.matrix_world.copy()
        C.parent_to_bone(it, rig, 'hand.R')
        it.matrix_world = mw
        out.append(it)
    return tuple(out)


def set_loaded(items, loaded, frame):
    a, b = items
    a.scale = (1, 1, 1) if loaded else (0, 0, 0)
    b.scale = (0, 0, 0) if loaded else (1, 1, 1)
    for it in items:
        it.keyframe_insert("scale", frame=frame)
        if it.animation_data and it.animation_data.action:
            for fc in _fcurves(it.animation_data.action):
                for kp in fc.keyframe_points:
                    kp.interpolation = 'CONSTANT'


def _fcurves(action):
    if hasattr(action, "fcurves") and len(getattr(action, "fcurves", [])):
        return list(action.fcurves)
    out = []
    for layer in getattr(action, "layers", []):
        for strip in layer.strips:
            for bag in getattr(strip, "channelbags", []):
                out.extend(bag.fcurves)
    return out


def pose_hold(rig, head_x, head_y, frame):
    """Aiming (right-handed). head_x: pitch in radians, negative = up (the game's xRot)."""
    C.set_bone_mc_rot(rig, 'head', head_x, head_y, 0, frame)
    C.set_bone_mc_rot(rig, 'arm.R', -math.pi / 2 + head_x + 0.1, -0.3 + head_y, 0, frame)
    C.set_bone_mc_rot(rig, 'arm.L', -1.5 + head_x, 0.6 + head_y, 0, frame)


def pose_charge(rig, t, frame):
    t = max(0.0, min(1.0, t))
    C.set_bone_mc_rot(rig, 'head', 0.2, 0, 0, frame)
    C.set_bone_mc_rot(rig, 'arm.R', -0.97079635, -0.8, 0, frame)
    lx = -0.97079635 + t * (-math.pi / 2 + 0.97079635)
    C.set_bone_mc_rot(rig, 'arm.L', lx, 0.4 + t * 0.45, 0, frame)


def look_dir(rig, head_x):
    """World direction the rig looks at: its facing (-Y local) pitched by head_x."""
    q = rig.matrix_world.to_quaternion()
    p = -head_x                                    # up positive
    return (q @ Vector((0, -math.cos(p), math.sin(p)))).normalized()


def fire(cloud, rig, head_x, frame, rng, colors, fades=(), flight=3, multishot=True, explode=True,
         light=True, light_shadow=False, collection=None):
    """Shoot 1 or 3 firework rockets; returns a list of (track, burst_frame, burst_pos)."""
    base = look_dir(rig, head_x)
    origin = rig.matrix_world.translation + Vector((0, 0, 1.5))       # eye height - 0.1, villager
    offsets = (0.0, -10.0, 10.0) if multishot else (0.0,)
    up = Vector((0, 0, 1))
    shots = []
    for k, yaw in enumerate(offsets):
        d = (Matrix.Rotation(math.radians(yaw), 3, up) @ base).normalized()
        d = Vector((d.x + rng.gauss(0, 1) * 0.0172275, d.y + rng.gauss(0, 1) * 0.0172275,
                    d.z + rng.gauss(0, 1) * 0.0172275)).normalized() * POWER
        life = 10 * (1 + flight) + rng.randrange(6) + rng.randrange(7)
        pos = origin.copy()
        track = [(frame, pos.copy())]
        for t in range(1, life + 1):
            pos += d
            f = frame + t * fps() / TPS
            track.append((f, pos.copy()))
            cloud.spark(pos.copy(), (rng.gauss(0, 1) * 0.05, -rng.gauss(0, 1) * 0.05, -d.z * 0.5), f, FW.WHITE)
        bf, bp = track[-1]
        FW.rocket_object(f"{rig.name[:-4]}.shot.{int(frame)}.{k}", track, collection)
        if explode:
            col = rng.choice(colors)
            cloud.large_ball(bp, bf, colors=(col,), fades=fades, trail=rng.random() < 0.3,
                             twinkle=rng.random() < 0.4)
            if light:
                lo = FW.burst_light(f"{rig.name[:-4]}.burst.{int(frame)}.{k}", bp, [bf], col, energy=40000,
                                    collection=collection)
                lo.data.use_shadow = light_shadow
        shots.append((track, bf, bp))
    return shots


def volley_cycle(cloud, rig, items, frame0, cycles, head_x, rng, colors, start_loaded=True,
                 charge_ticks=CHARGE_TICKS_QC3, aim_ticks=6, collection=None, **kw):
    """aim -> fire -> charge (Quick Charge III) -> aim -> fire ... ; keys pose, item and shots."""
    tick = fps() / TPS
    f = frame0
    pose_hold(rig, head_x, 0.0, f); set_loaded(items, start_loaded, f)
    shots = []
    for c in range(cycles):
        f += aim_ticks * tick
        pose_hold(rig, head_x, 0.0, f); set_loaded(items, True, f - 0.01)
        shots += fire(cloud, rig, head_x, f, rng, colors, collection=collection, **kw)
        set_loaded(items, False, f + 0.01)
        if c == cycles - 1:
            break
        for i in range(charge_ticks + 1):
            pose_charge(rig, i / charge_ticks, f + (1 + i) * tick)
        f += (charge_ticks + 1) * tick
        set_loaded(items, True, f)
    return shots
