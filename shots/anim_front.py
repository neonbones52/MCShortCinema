"""Animatic, location 4 (the front at night, moon): shots 16-20.

    blender -b blender/sets/front.blend --python shots/anim_front.py -- stills|render|save [shot ...]

16  the hero's face, the camera pulls back: comrades take off around him on white rocket trails
17  from the ground looking up: the hero takes off, a white trail, the square moon
18  wide in the air: the squad over the dark land, the trench lines ahead below
19  in the trench, close: Alex's crossbowmen load fireworks, raise, a multishot volley
20  behind the hero: bursts, comrades shot down, a rocket bursts right ahead of him (frame 2236)

Two squads on the same rigs' kit, cheated between cuts (as cuts allow): the flight of 18 has
the hero over no-man's land mid-shot; the flight of 19-20 is timed so that the burst in front
of him lands on frame 2236, over the first line. The take-off (16-17) is on Steve's side of the
plain, far west. Crossbow physics and the volleys as on the ambush stand (tests/test_ambush.py),
turned to fly east (+X) towards Alex's lines.
"""
import math
import random
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, r"C:\Dev\Projects\CinemaShort\shots")
import importlib
import anim as A
importlib.reload(A)
import mc_camera as CAM
import mc_character as C
import mc_crossbow as XB
import mc_firework as FW
import mc_flight as F
import mc_look as L
import mc_motion as M
import mc_set as SET
import mc_sky as SKY

K = SET.marks("front")
HX, HY, HZ = K["hero"]
LINES = K["lines_x"]
EAST = math.pi / 2                     # yaw facing +X
WEST = -math.pi / 2
KIT = dict(helmet="iron", legs="iron", boots="iron", elytra=True)
SKINS = ("plains_plain", "plains_armorer", "plains_weaponsmith")
PALETTE = ('red', 'orange', 'yellow', 'lime', 'light_blue', 'magenta', 'pink', 'cyan', 'white', 'purple')
LIGHT_PEAK = 5000.0                    # bursts 5-15 blocks from the flyers (ambush stand)
SITE = (60.0, 160.0)                   # the take-off, Steve's side of the plain
LANE_Z = HZ + 0.5                      # the squad flies east along the hero's row
# ranks: (blocks ahead of the hero's rank, lateral offsets (z), climb trim in ticks)
RANKS = ((14.0, (-10, -5, 0, 5, 10), -4.0),
         (7.0, (-12.5, -7.5, -2.5, 2.5, 7.5, 12.5), -2.0),
         (0.0, (-10, -5, 0, 5, 10), 0.0))
VICTIMS = ((0, 1, 2190), (1, 4, 2204), (0, 3, 2214), (1, 1, 2226))     # (rank, index, frame of the hit)
HERO_BURST = 2236


def g(x, z):
    return SET.ground(x, z, "front")


def b(x, y, z):
    return SET.b(x, y, z)


def smooth(x):
    return A.smooth(x)


def moon_dir():
    st = SKY.state(14500)
    return SKY.sun_direction(st['moon_angle']).normalized()


# ------------------------------------------------------------------ 16-17: the take-off
def takeoff(cloud):
    sx, sz = SITE
    gy = g(sx + 0.5, sz + 0.5)
    with A.quiet():
        hero = C.villager("HeroTO", skin="plains_farmer", **KIT)
    a = M.Actor(hero, pos=Vector((sx + 0.5, -(sz + 0.5), gy)), yaw=EAST)
    a.look(0, 200, Vector((sx + 40, -(sz + 0.5), gy + 6)))
    M.bake([a], int(A.tick_of_frame(1972, 1877)), frame0=1877)
    # his own take-off in 17
    def climb(t):
        c = dict(heading=90.0 + 3 * math.sin(t * 0.1), pitch=0.0, jump=t == 2, deploy=t >= 5, rocket=t >= 5)
        if t >= 5:
            c['pitch'] = -48.0 * (1.0 - smooth((t - 30) / 25.0)) - 6.0
        return c
    st = F.simulate(climb, (sx + 0.5, -(sz + 0.5), gy), 80, ground_z=gy, seed=16)
    F.apply(hero, st, 1975 - 2 * 1.2, trail=cloud, rocket_item=F.rocket_in_hand(hero, "HeroTO.rocket"))
    A.key_visible(hero, [(1877, 2036)])
    # comrades around and behind him, taking off one after another during 16
    rng = random.Random(16)
    spots = [(-3.0, -2.5), (-2.5, 2.8), (-6.0, 0.5), (-5.5, -5.0), (-6.5, 5.0), (-9.5, -2.0), (-9.0, 3.5),
             (-12.0, 0.0), (1.5, -5.5), (1.0, 5.5)]
    for i, (dx, dz) in enumerate(spots):
        x, z = sx + 0.5 + dx, sz + 0.5 + dz
        gz = g(x, z)
        with A.quiet():
            r = C.villager(f"MateTO{i}", skin=SKINS[i % 3], **KIT)
        trim = rng.uniform(-6, 6)

        def climb_i(t, trim=trim):
            c = dict(heading=90.0 + trim * 0.5, pitch=0.0, jump=t == 2, deploy=t >= 5, rocket=t >= 5)
            if t >= 5:
                c['pitch'] = -42.0 + trim
            return c
        st = F.simulate(climb_i, (x, -z, gz), 90, ground_z=gz, seed=160 + i)
        f0 = 1882 + 7 * i + rng.uniform(-2, 2)
        r.location = (x, -z, gz)
        r.rotation_mode = 'QUATERNION'
        r.rotation_quaternion = (math.cos(EAST / 2), 0, 0, math.sin(EAST / 2))
        r.keyframe_insert("location", frame=1870)
        r.keyframe_insert("rotation_quaternion", frame=1870)
        F.apply(r, st, f0, trail=cloud, rocket_item=F.rocket_in_hand(r, f"MateTO{i}.rocket"))
        A.key_visible(r, [(1877, 2036)])
    return hero, Vector((sx + 0.5, -(sz + 0.5), gy))


# ------------------------------------------------------------------ 18-20: the squad over the lines
def make_pilot(seed, climb_trim=0.0, hit=None):
    rng = random.Random(seed)
    trim, phase, spin = rng.uniform(-0.25, 0.25), rng.uniform(0.0, 6.28), rng.choice((-1.0, 1.0))
    climb_end = 30.0 + climb_trim + rng.uniform(-1.5, 1.5)

    def pilot(t):
        c = dict(heading=90.0 + 2.0 * math.sin(t * 0.05 + phase), pitch=0.0, jump=t == 2, deploy=t >= 4,
                 rocket=t >= 4)
        if t >= 4:
            c['pitch'] = -30.0 * (1.0 - smooth((t - climb_end) / 20.0)) + trim + 1.2 * math.sin(t * 0.08 + phase)
        if hit is not None and t >= hit:
            u = t - hit
            c['pitch'] = min(78.0, c['pitch'] + 11.0 * u)
            c['heading'] += spin * 28.0 * u
            c['rocket'] = False
        return c
    return pilot


def squad(tag, slot_frame, hero_x, pre, ticks, cloud, visible, hits=None):
    """Sixteen in three ranks; the hero (last rank, middle) over (hero_x, LANE_Z) at slot_frame.
    hits: {(rank, index): frame}. Returns flyers [dict(name, rig, states, hit, frame0)]."""
    hits = hits or {}
    frame0 = slot_frame - pre * 1.2
    rng = random.Random(hash(tag) & 0xFFFF)
    gz0 = g(SITE[0], SITE[1])
    out = []
    n = 0
    for r, (ahead, zs, trim) in enumerate(RANKS):
        for i, dz in enumerate(zs):
            hero = r == 2 and dz == 0
            name = f"Hero{tag}" if hero else f"Mate{tag}{n:02d}"
            n += 0 if hero else 1
            seed = 100 + 10 * r + i
            hf = hits.get((r, i))
            hit = None if hf is None else round(pre + (hf - slot_frame) / 1.2)
            probe = F.simulate(make_pilot(seed, trim), (0, 0, 0), pre + 1, ground_z=-1000.0, seed=seed)[pre]['pos']
            slot = Vector((hero_x + ahead + rng.uniform(-1, 1), -(LANE_Z + dz + rng.uniform(-0.8, 0.8)), 0))
            start = (slot.x - probe.x, slot.y - probe.y, gz0)
            states = F.simulate(make_pilot(seed, trim, hit), start, ticks, ground_z=gz0 - 200, seed=seed)
            with A.quiet():
                rig = C.villager(name, skin="plains_farmer" if hero else SKINS[(r + i) % 3], **KIT)
            F.apply(rig, states, frame0, trail=cloud, rocket_item=F.rocket_in_hand(rig, name + ".rocket"))
            A.key_visible(rig, [visible])
            out.append(dict(name=name, rig=rig, states=states, hit=hit, frame0=frame0, hero=hero))
    return out


def soldiers():
    """Alex's crossbowmen on the fire steps (36, plus two more in the bay of shot 19), facing west."""
    out = []
    pts = [tuple(p) for p in K["soldiers"]]
    s5 = K["soldiers"][5]
    pts += [(s5[0], s5[1], s5[2] - 2.0), (s5[0], s5[1], s5[2] + 2.5)]
    mail = dict(helmet="chainmail", chest="chainmail", legs="chainmail", boots="chainmail")
    for i, (x, y, z) in enumerate(pts):
        with A.quiet():
            rig = C.villager(f"Alex{i:02d}", skin="plains_plain", **mail)
        rig.location = b(x, y, z)
        rig.rotation_euler = (0, 0, WEST)
        bpy.context.view_layer.update()
        out.append(dict(name=f"Alex{i:02d}", rig=rig, items=XB.attach_crossbow(rig),
                        eye=b(x, y, z) + Vector((0, 0, 1.5)), volleys=[]))
    return out


def ambush(cloud, fx, flyers, shooters):
    """Volleys (crossbow physics): aimed hits on the victims and the burst before the hero, and
    everyone else firing at the squad while it is in front of his trench."""
    def light(nm, pos, f, col):
        FW.glow_light(nm, pos, f, col, peak=LIGHT_PEAK, collection=fx)

    def body(f, frame):
        fl = f['states']
        t = round((frame - f['frame0']) / 1.2)
        s = fl[max(0, min(len(fl) - 1, t))]
        return s['pos'] + Vector((0, 0, 1.0))

    def aimed(point_at, frame_hit, tag):
        p = point_at(frame_hit)
        ahead = [s for s in shooters if s['eye'].x > p.x + 6.0]
        s = min(ahead, key=lambda s: abs((p - s['eye']).length - 45.0))
        k = max(1, round((p - s['eye']).length / 1.6))
        s['volleys'].append(dict(f=frame_hit - k * 1.2, dir=(p - s['eye']).normalized(), life=(k, None, None), tag=tag))

    for f in flyers:
        if f['hit'] is not None:
            aimed(lambda fr, f=f: body(f, fr), f['frame0'] + f['hit'] * 1.2, "hit." + f['name'])
    hero = next(f for f in flyers if f['hero'])
    aimed(lambda fr: body(hero, fr) + Vector((5.0, 0.0, 0.3)), HERO_BURST, "hero")

    # shot 19: the bay in front of the camera loads and fires together at ~2156
    bay = shooters[5:6] + shooters[-2:]
    for j, s in enumerate(bay):
        tgt = body(hero, 2200) + Vector((-30 + 8 * j, 6 * (j - 1), 4))
        s['volleys'].append(dict(f=2154 + 3 * j, dir=(tgt - s['eye']).normalized(), life=None, tag="bay"))

    for s in shooters:
        srng = random.Random(hash((round(s['eye'].x, 2), round(s['eye'].y, 2))) & 0xFFFF)
        busy = sorted(v['f'] for v in s['volleys'])
        fr = 2110.0
        ready = None
        while fr < 2236:
            alive = [f for f in flyers if (f['hit'] is None or f['frame0'] + f['hit'] * 1.2 > fr + 36)
                     and body(f, fr).x < s['eye'].x - 10 and (body(f, fr) - s['eye']).length < 165]
            if alive and ready is None:
                ready = fr + srng.uniform(0, 80)
            if not alive or fr < ready or any(abs(fr - bf) < 24 for bf in busy):
                fr += 3.6
                continue
            f = srng.choice(alive)
            k = 40
            for kk in range(1, 47):
                if 1.6 * kk >= (body(f, fr + kk * 1.2) - s['eye']).length:
                    k = kk
                    break
            miss = Vector((srng.uniform(-3, 7) * srng.choice((-1, 1)), srng.uniform(-7, 7), srng.uniform(-3, 3)))
            s['volleys'].append(dict(f=fr, dir=(body(f, fr + k * 1.2) + miss - s['eye']).normalized(), life=None, tag="v"))
            fr += (17 + srng.randrange(45, 110)) * 1.2

    rng = random.Random(20)
    tk = 1.2
    n = 0
    for s in shooters:
        s['volleys'].sort(key=lambda v: v['f'])
        XB.pose_hold(s['rig'], -0.3, 0.0, 2000)
        XB.set_loaded(s['items'], True, 2000)
        for j, v in enumerate(s['volleys']):
            f = v['f']
            head_x = -math.asin(max(-0.95, min(0.95, v['dir'].z)))
            for i in range(11):                               # reload (Quick Charge III), then aim
                XB.pose_charge(s['rig'], i / 10.0, f - (17 - i) * tk)
            XB.set_loaded(s['items'], True, f - 7 * tk)
            XB.pose_hold(s['rig'], head_x, 0.0, f - 6 * tk)
            XB.pose_hold(s['rig'], head_x, 0.0, f)
            XB.shoot(cloud, s['eye'], v['dir'], round(f, 2), rng, PALETTE, flight=3, multishot=True, explode=True,
                     light=True, collection=fx, name=f"{s['name']}.{j}", light_fn=light, life=v['life'])
            XB.set_loaded(s['items'], False, f + 0.01)
            n += 1
    print("VOLLEYS", n)


# ------------------------------------------------------------------ cameras
def cameras(hero_to, site, squad_a, squad_b):
    sc = bpy.context.scene
    face = site + Vector((0, 0, 1.75))
    # 16: extreme close-up in front of his face, pulling back east and up: comrades rise behind him
    A.camera("Shot16", [(1877, face + Vector((1.6, 0.0, 0.0)), face, 50),
                        (1900, face + Vector((1.8, 0.05, 0.02)), face, 50),
                        (1955, face + Vector((10.0, 2.5, 1.6)), face + Vector((-4.0, 0.0, 0.5)), 28)])
    # 17: low on the ground, the moon behind him: the lens follows him up
    md = moon_dir()
    h = Vector((md.x, md.y, 0)).normalized()
    cpos = site - h * 12.0 + Vector((0, 0, 1.6))       # back and at eye height: over the grass, the moon in frame
    pts = []
    for f in range(1956, 2036):
        sc.frame_set(f)
        pts.append(hero_to.matrix_world.translation.copy() + Vector((0, 0, 1.0)))
    sm = [sum(pts[max(0, i - 8):i + 9], Vector()) / len(pts[max(0, i - 8):i + 9]) for i in range(len(pts))]
    A.camera_path("Shot17", range(1956, 2036), lambda f: (cpos, sm[f - 1956]), lens=20)
    print("MOON elevation", round(math.degrees(math.asin(md.z)), 1), "camera at", tuple(round(v, 1) for v in cpos))
    # 18: wide, alongside the squad, the lines ahead and below
    CAM.follow("Shot18", [f['rig'] for f in squad_a if f['hit'] is None], 2036, 2116, side=34.0, back=-16.0,
               up=5.0, lens=24, lag=0.6, aim_lag=0.3, heading=90.0, screen=(0.1, 0.1))
    # 19: in the trench bay, low, on the shooters
    s5 = K["soldiers"][5]
    # (the shooters stand on the back block of a 2-wide step; the camera is on the floor behind them)
    A.camera("Shot19", [(2116, b(s5[0] + 1.1, s5[1] + 0.2, s5[2] - 4.6), b(s5[0] - 1.2, s5[1] + 1.8, s5[2])),
                        (2175, b(s5[0] + 1.2, s5[1] + 0.15, s5[2] - 4.4), b(s5[0] - 2.0, s5[1] + 3.0, s5[2] + 0.5))],
             lens=20)
    # 20: close behind the hero
    hero = next(f['rig'] for f in squad_b if f['hero'])
    CAM.follow("Shot20", hero, 2176, 2236, side=0.6, back=5.5, up=1.2, lens=20, lag=0.40, aim_lag=0.10,
               lead=0.04, screen=(0.0, -0.25))


def night():
    SKY.apply(tick=14500, rain=0.0, render_distance=12, ground_mc_y=64.0 - HY, frame_start=1877,
              haze=L.LOOKS["night"]["haze"])
    A.apply_look("night")


def build():
    A.setup()
    A.remove_collections(["Alex", "Hero"])
    FW.set_flash_gain(0.35)
    fx = A.collection("FX")
    cloud = FW.Cloud(seed=20)
    hero_to, site = takeoff(cloud)
    squad_a = squad("A", 2076, 250.0, 100, 150, cloud, (2036, 2116))
    squad_b = squad("B", 2116, 140.0, 100, 230, cloud, (2116, 2240), hits={(r, i): f for r, i, f in VICTIMS})
    shooters = soldiers()
    hb = next(f for f in squad_b if f['hero'])
    t = round((HERO_BURST - hb['frame0']) / 1.2)
    print("HERO at the burst", tuple(round(v, 1) for v in hb['states'][t]['pos']))
    cameras(hero_to, site, squad_a, squad_b)
    bpy.context.scene.camera = bpy.data.objects["Shot20"]
    ambush(cloud, fx, squad_b, shooters)
    cloud.build("FX.Particles", fx)


PLAN = [dict(shot=n, cam=f"Shot{n:02d}", prepare=night) for n in range(16, 21)]

if __name__ == "__main__":
    mode, shots = A.args()
    build()
    A.run(mode, shots, PLAN, "anim_front.blend")
