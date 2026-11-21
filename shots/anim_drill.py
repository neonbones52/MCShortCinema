"""Animatic, location 2 (training ground, overcast): shots 09-13.

    blender -b blender/sets/drill.blend --python shots/anim_drill.py -- stills|render|save [shot ...]

09  the hero's face in the iron helmet, the camera pulls back and the line with elytra opens up
10  the sergeant walks the line and hands each recruit a rocket (the camera tracks with him)
11  the range: recruits take off one by one; one flounders and drops into a haystack
12  the hero takes off, gets thrown about, levels out and glides (follow camera, as approved)
13  from below: the group glides over against the grey sky
"""
import math
import os
import random
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, r"C:\Dev\Projects\CinemaShort\shots")
import importlib
import anim as A
importlib.reload(A)
import mc_banner as BN
import mc_camera as CAM
import mc_character as C
import mc_firework as FW
import mc_flight as F
import mc_look as L
import mc_motion as M
import mc_set as SET
import mc_sky as SKY

K = SET.marks("drill")
LV = K["level"]
FEET = LV + 1
LINE = K["line"]
HERO_I = 7
SKINS = ("plains_plain", "plains_armorer", "plains_weaponsmith", "plains_farmer")
NORTH = math.pi
LAUNCH = K["launch_x"]
RZ = K["range_centre_z"]
KIT = dict(helmet="iron", legs="iron", boots="iron", elytra=True)      # no chestplate: the elytra


def b(x, y, z):
    return SET.b(x, y, z)


def gz(x, z):
    return SET.ground(x, z, "drill")


def smooth(x):
    return A.smooth(x)


# ------------------------------------------------------------------ 09-10: the line
def line(cloud):
    """16 recruits (the hero 8th from the west) and the sergeant handing out rockets."""
    t0 = 1118                                                     # tick 0 of shot 10
    rigs, actors = [], []
    for i, (x, y, z) in enumerate(LINE):
        hero = i == HERO_I
        with A.quiet():
            rig = C.villager("Hero" if hero else f"Recruit{i:02d}", skin="plains_farmer" if hero else SKINS[i % 3],
                             item_r="firework_rocket", **KIT)
        a = M.Actor(rig, pos=b(x + 0.5, FEET, z + 0.5), yaw=NORTH)
        rigs.append(rig)
        actors.append(a)
    with A.quiet():
        sg = C.villager("Sergeant", skin="plains_weaponsmith", helmet="iron", chest="iron", legs="iron",
                        boots="iron", item_r="firework_rocket")
    sx, _sy, sz = K["sergeant"]
    zf = LINE[0][2] + 0.5 - 1.3                                   # walks 1.3 blocks in front of the line
    s = M.Actor(sg, pos=b(sx + 0.5, FEET, zf), yaw=-math.pi / 2)
    s.hold_item(0, 10 ** 6)
    tick = 2.0
    prev = b(sx + 0.5, FEET, zf)
    given = {}
    for i in range(HERO_I + 1):
        x = LINE[i][0] + 0.5
        stop = b(x - 0.2, FEET, zf)
        s.walk(tick, [prev, stop], speed=0.17)
        tick += (stop - prev).length / 0.17
        s.face(tick, actors[i])
        s.hold_out(tick, tick + 8, actors[i], ramp=3)
        given[i] = tick + 6
        actors[i].look(tick - 14, tick + 10, s)
        actors[i].hold_item(tick + 6, 10 ** 6, ramp=4)
        tick += 10
        prev = stop
    M.bake(actors + [s], int(A.tick_of_frame(1278, t0)) + 2, frame0=t0)
    # rockets in the recruits' hands only once given
    for i, rig in enumerate(rigs):
        item = bpy.data.objects[rig.name.replace(".rig", "") + ".item.R"]
        f = A.frame_of_tick(given[i], t0) if i in given else None
        A.key_visible(item, [(round(f), 1278)] if f else [])
    for r in rigs + [sg]:
        A.key_visible(r, [(958, 1278)])
    return rigs, sg


def banners():
    for ob in bpy.data.objects:
        if ob.name.startswith("Banner.") and "mc_block" in ob:
            BN.animate(ob, 958, 1597)


# ------------------------------------------------------------------ 11-13: flights
def pilot_takeoff(seed, climb_end=26.0, heading=90.0):
    rng = random.Random(seed)
    trim, phase = rng.uniform(-1.5, 1.5), rng.uniform(0, 6.28)

    def pilot(t):
        c = dict(heading=heading + 3.0 * math.sin(t * 0.06 + phase), pitch=0.0, jump=t == 2, deploy=t >= 5,
                 rocket=t >= 5 and t < 30)
        if t >= 5:
            c['pitch'] = -28.0 * (1.0 - smooth((t - climb_end) / 18.0)) + 3.0 + trim
        return c
    return pilot


def pilot_flounder(t):
    """Loses it straight away: the rocket carries him round in a tight loop, then he drops."""
    c = dict(heading=90.0, pitch=0.0, jump=t == 2, deploy=t >= 5, rocket=5 <= t < 7)
    if 5 <= t < 33:
        c['heading'] = 90.0 + 360.0 * (t - 5) / 28.0
        c['pitch'] = -12.0 + 10.0 * math.sin(t * 0.7)
    elif t >= 33:
        c['heading'] = 90.0 + 25.0 * math.sin(t * 0.5)
        c['pitch'] = min(65.0, 10.0 + (t - 33) * 8.0)
    return c


def pilot_hero(t):
    """Shot 12 as approved on the follow-cam stand: jump, wings, a rocket; thrown about; level."""
    c = dict(heading=90.0, pitch=0.0, jump=t == 10, deploy=t >= 12)
    if t >= 12:
        u = t - 12
        wob = smooth(u / 8.0) * (1.0 - smooth((u - 45.0) / 25.0))
        c['heading'] = 90.0 + 30.0 * math.sin(u * 0.19) * wob
        climb = -24.0 * (1.0 - smooth((u - 6.0) / 22.0))
        c['pitch'] = climb + 14.0 * math.sin(u * 0.31 + 0.8) * wob + 1.0 * smooth((u - 50.0) / 30.0)
        c['rocket'] = u < 2 or 44 <= u < 46 or 100 <= u < 102
    return c


def pilot_glide(seed):
    rng = random.Random(seed)
    phase, trim = rng.uniform(0, 6.28), rng.uniform(-1.0, 1.0)

    def pilot(t):
        return dict(heading=90.0 + 4.0 * math.sin(t * 0.04 + phase), pitch=2.0 + trim + 2.0 * math.sin(t * 0.07 + phase),
                    jump=t == 2, deploy=t >= 5, rocket=t >= 5 and (t < 40 or t % 60 < 3))
    return pilot


def flyer(name, skin, states, frame0, cloud, visible, flop=False):
    with A.quiet():
        rig = C.villager(name, skin=skin, **KIT)
    F.apply(rig, states, frame0, trail=cloud, rocket_item=F.rocket_in_hand(rig, name + ".rocket"), flop_on_land=flop)
    A.key_visible(rig, [visible])
    return rig


def range_flights(cloud):
    """Shot 11: five take off from the launch line one by one, the fourth flounders into the hay."""
    rigs = []
    zs = (124.5, 128.0, 131.5, 135.0, 138.5)
    for i, z in enumerate(zs):
        f0 = 1286 + 22 * i
        x = LAUNCH + 0.5
        if i == 3:
            states = F.simulate(pilot_flounder, (0, 0, 0), 90, ground_z=-50.0, seed=40 + i)
            land = next((k for k, st in enumerate(states) if k > 34 and st['vel'].z < 0 and st['pos'].z <= 3.0),
                        len(states) - 1)
            off = states[land]['pos']
            # the haystack nearest to where he comes down from this place on the line
            hx, _hy, hz = min(K["haystacks"], key=lambda h: math.hypot(h[0] + 0.5 - (x + off.x), h[2] + 0.5 - (z - off.y)))
            top = gz(hx + 0.5, hz + 0.5)
            shift = Vector((hx + 0.5 - off.x, -(hz + 0.5) - off.y, top - 3.0))
            states = states[:land + 1]
            for st in states:
                st['pos'] = st['pos'] + shift
            states[-1]['pos'].z = top
            states[-1]['landed'] = True
            print("FLOUNDER from", round(shift.x, 1), round(-shift.y, 1), "lands on the hay at", hx, hz,
                  "peak", round(max(st['pos'].z for st in states) - top + 3, 1))
        else:
            start = (x, -z, gz(x, z))
            states = F.simulate(pilot_takeoff(30 + i), start, 140, ground_z=start[2], seed=30 + i)
        rigs.append(flyer(f"Trainee{i}", SKINS[i % 3], states, f0, cloud, (1278, 1398), flop=i == 3))
    return rigs


def hero_flight(cloud):
    """Shot 12: tick 0 at frame 1388, the jump at tick 10 = frame 1400."""
    x, z = LAUNCH + 0.5, RZ + 0.5
    start = (x, -z, gz(x, z))
    states = F.simulate(pilot_hero, start, 110, ground_z=start[2], seed=12)
    # through the middle of every gate he reaches, under the crossbar (he went through a post)
    for gx, bar_y, z0, z1 in K["gates"]:
        k = next((i for i, st in enumerate(states) if st['pos'].x >= gx + 0.5), None)
        if k is None:
            continue
        p = states[k]['pos']
        mid = -((z0 + z1 + 1) / 2.0)
        dy = mid - p.y
        top = bar_y - 1.6                                          # his body under the bar
        dz = min(0.0, top - p.z)
        for st in states[max(0, k - 30):]:
            w = A.smooth((st['t'] - (k - 30)) / 30.0)
            st['pos'] = st['pos'] + Vector((0, dy * w, dz * w))
        print("GATE", gx, "height", round(p.z, 1), "bar", bar_y, "shift z", round(-dy, 2), "down", round(dz, 2))
    return flyer("HeroFly", "plains_farmer", states, 1388, cloud, (1398, 1517))


def group_overhead(cloud):
    """Shot 13: seven gliders cross over the low camera at the gates (x ~ 235) around frame 1557."""
    rigs = []
    slots = ((0.0, 0.0), (-4.0, 3.0), (-4.5, -3.2), (-9.0, 6.0), (-9.0, -0.5), (-9.5, -6.5), (-14.0, 2.0))
    for i, (ahead, side) in enumerate(slots):
        pilot = pilot_glide(60 + i)
        pre = 140
        probe = F.simulate(pilot, (0, 0, 0), pre + 1, ground_z=-1000.0, seed=60 + i)[pre]['pos']
        want = Vector((236.0 + ahead, -(RZ + 0.5 + side), gz(236, RZ) + 17.0 + 1.2 * (i % 3)))
        start = want - probe
        states = F.simulate(pilot, start, pre + 80, ground_z=-1000.0, seed=60 + i)
        frame0 = 1557 - pre * 1.2
        rigs.append(flyer("HeroGlide" if i == 0 else f"Glider{i}", "plains_farmer" if i == 0 else SKINS[i % 3],
                          states, frame0, cloud, (1517, 1597)))
    return rigs


# ------------------------------------------------------------------ cameras
def cameras(hero_fly, hero_line, sergeant):
    hx, _hy, hz = LINE[HERO_I]
    face = b(hx + 0.5, FEET + 1.75, hz + 0.5)
    # 09: extreme close-up on the face, pulling back and up a little: the line opens up
    A.camera("Shot09", [(958, b(hx + 0.5, FEET + 1.75, hz + 0.5 - 1.7), face, 50),
                        (990, b(hx + 0.5, FEET + 1.75, hz + 0.5 - 1.8), face, 50),
                        (1117, b(hx - 1.5, FEET + 2.4, hz + 0.5 - 11.0), b(hx + 0.5, FEET + 1.0, hz + 0.5), 32)])
    # 10: tracking along the line with the sergeant, in front of the recruits
    sc = bpy.context.scene
    pts = []
    for f in range(1118, 1278):
        sc.frame_set(f)
        pts.append(sergeant.matrix_world.translation.copy())
    sm = []
    for i in range(len(pts)):
        win = pts[max(0, i - 18):i + 19]
        sm.append(sum(win, Vector()) / len(win))

    def track(f):
        p = sm[f - 1118]
        return (Vector((p.x + 2.6, p.y + 4.2, FEET + 1.7)), Vector((p.x + 0.3, p.y - 0.6, FEET + 1.2)))
    A.camera_path("Shot10", range(1118, 1278), track, lens=28)
    # 11: the range from the south-east: the launch line, the stacks
    A.camera("Shot11", [(1278, b(124, gz(124, 158) + 4.5, 158), b(108, FEET + 4.0, 131)),
                        (1397, b(123, gz(123, 158) + 4.5, 158), b(110, FEET + 5.0, 131))], lens=28)
    # 12: the approved chase camera on the hero
    CAM.follow("Shot12", hero_fly, 1398, 1517, side=4.5, back=6.5, up=1.2, lens=28, lag=0.55, aim_lag=0.18,
               screen=(-0.15, 0.0))
    # 13: low between the gates, looking up as they pass over
    cx, cz = 228.0, 142.0
    A.camera("Shot13", [(1517, b(cx, gz(cx, cz) + 0.6, cz), b(226, gz(cx, cz) + 30, 133)),
                        (1596, b(cx, gz(cx, cz) + 0.6, cz), b(246, gz(cx, cz) + 26, 131))], lens=18)


def overcast():
    SKY.apply(tick=6000, rain=1.0, render_distance=12, ground_mc_y=64.0 - LV, frame_start=958,
              haze=L.LOOKS["cold"]["haze"])
    L.apply("cold")


def build():
    A.setup()
    A.remove_collections(["Recruit"])
    fx = A.collection("FX")
    cloud = FW.Cloud(seed=9)
    rigs, sg = line(cloud)
    banners()
    range_flights(cloud)
    hero = hero_flight(cloud)
    group_overhead(cloud)
    cameras(hero, rigs[HERO_I], sg)
    bpy.context.scene.camera = bpy.data.objects["Shot12"]
    cloud.build("FX.rocket_trail", fx)


PLAN = [dict(shot=n, cam=f"Shot{n:02d}", prepare=overcast) for n in range(9, 14)]

if __name__ == "__main__":
    mode, shots = A.args()
    build()
    A.run(mode, shots, PLAN, "anim_drill.blend")
