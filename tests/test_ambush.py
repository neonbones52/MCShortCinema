"""Ambush stand (shots 18-20) for the render-time measurement: the heaviest thing in the film.
16 elytra flyers in three ranks (the hero in the middle of the last one) cross three trench lines
of Alex's crossbowmen at night; multishot volleys by the crossbow physics, bursts at the end of
the range, five comrades shot down, one burst in front of the hero at the end.

A technical stand, not choreography: numbers are the upper bound, the shooters only pitch their
aim (no yaw towards the target), the shot-down flyers simply dive.

Build (in the live Blender through MCP, or in background):
    exec(open(r"C:\\Dev\\Projects\\CinemaShort\\tests\\test_ambush.py", encoding="utf-8").read())
    blender -b --factory-startup --python tests/test_ambush.py
-> blender/test_ambush.blend
Render (background, the .blend is not saved), with per-frame timings:
    blender -b blender/test_ambush.blend --python tests/test_ambush.py -- render Cam.Behind [percent] [first last]
-> renders/tests/ambush/<camera>/f####.png, renders/tests/ambush_render_times_<camera>_v1.txt
"""
import math
import os
import random
import sys
import time

import bpy
from mathutils import Vector

sys.path.insert(0, r"C:\Dev\Projects\CinemaShort\tools")
import importlib
import mc_camera as CAM
import mc_character as C
import mc_crossbow as XB
import mc_firework as FW
import mc_flight as F
import mc_look as L
import mc_sky as SKY
import mc_stage as ST
for _m in (CAM, XB, ST):
    importlib.reload(_m)

ROOT = r"C:\Dev\Projects\CinemaShort"
OUT = os.path.join(ROOT, "renders", "tests")
FRAMES = (1, 192)                 # 8 s
PRE = 100                         # ticks of flight before the first frame (take-off, climb)
SHOT = 160                        # ticks in the shot
TICKS = PRE + SHOT
FRAME0 = FRAMES[0] - PRE * 24.0 / 20.0     # frame of tick 0
LOOK = "night"
TRENCHES = (120.0, 200.0, 280.0)  # y of the three lines; the flyers travel +Y from y = 0
PER_LINE = 10                     # crossbowmen per line: 30 in all
LIGHT_PEAK = 5000.0               # finale: 150000 at ~70 blocks; here bursts go off 5-15 blocks from
                                  # the flyers (25000 burnt the hero out to white)
FLASH_GAIN = 0.35                 # as approved for the finale
PAUSE = (45, 110)                 # ticks a crossbowman waits between volleys (on top of the reload)

# ranks from the front: (blocks ahead of the hero's rank, x of each flyer, climb trim in ticks)
RANKS = ((14.0, (-10, -5, 0, 5, 10), -4.0),
         (7.0, (-12.5, -7.5, -2.5, 2.5, 7.5, 12.5), -2.0),
         (0.0, (-10, -5, 0, 5, 10), 0.0))
# shot down: (rank, index in the rank, tick of the shot when the rocket reaches him)
VICTIMS = ((0, 1, 48), (1, 4, 86), (0, 3, 100), (1, 1, 132), (2, 3, 142))
HERO_BURST = 154                  # tick of the shot: a rocket bursts 5 blocks ahead of the hero


def smooth(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3.0 - 2.0 * x)


def tick_frame(t):
    return FRAME0 + t * 24.0 / 20.0


def make_pilot(seed, climb_trim=0.0, hit=None):
    """Take off, climb ~1.5 s, then level at ~30 blocks, rockets one after another (the squad
    keeps one speed, ~33 blocks/s). hit: absolute tick after which he dives out of control."""
    rng = random.Random(seed)
    trim, phase, spin = rng.uniform(-0.25, 0.25), rng.uniform(0.0, 6.28), rng.choice((-1.0, 1.0))
    climb_end = 30.0 + climb_trim + rng.uniform(-1.5, 1.5)

    def pilot(t):
        c = dict(heading=180.0 + 2.0 * math.sin(t * 0.05 + phase), pitch=0.0, jump=t == 2, deploy=t >= 4,
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


def fly(seed, slot, climb_trim, hit=None):
    """Simulate so that the flyer is over `slot` (x, y) at the first tick of the shot."""
    pilot = make_pilot(seed, climb_trim, None)
    probe = F.simulate(pilot, (0, 0, 0), PRE + 1, ground_z=0.0, seed=seed)[PRE]['pos']
    start = (slot[0] - probe.x, slot[1] - probe.y, 0.0)
    return F.simulate(make_pilot(seed, climb_trim, hit), start, TICKS, ground_z=0.0, seed=seed)


def battlefield():
    rng = random.Random(20)
    slabs, floors, parapets = [], [], []
    edges = [-300.0] + [v for y in TRENCHES for v in (y, y + 2.0)] + [600.0]
    for a, b in zip(edges[0::2], edges[1::2]):
        slabs.append(((-400, a, -3), (400, b, 0)))
    for y in TRENCHES:
        slabs.append(((-400, y, -3), (-52, y + 2, 0)))
        slabs.append(((52, y, -3), (400, y + 2, 0)))
        floors.append(((-52, y, -3), (52, y + 2, -1)))
        parapets.append(((-52, y - 1.0, 0), (52, y, 0.5)))
    ST.boxes("Set.Ground", ST.grass(), slabs)
    ST.boxes("Set.TrenchFloor", ST.block_mat("dirt"), floors)
    ST.boxes("Set.Parapet", ST.block_mat("coarse_dirt"), parapets)
    stone, dirt = [], []
    for _ in range(260):
        x, y = math.floor(rng.uniform(-90, 90)), math.floor(rng.uniform(-40, 330))
        if any(yt - 3 <= y <= yt + 3 for yt in TRENCHES):
            continue
        w, d, h = rng.choice(((1, 1, 1), (2, 1, 1), (2, 2, 1), (3, 2, 2), (4, 3, 0.03), (6, 4, 0.03)))
        (stone if h >= 1 and rng.random() < 0.5 else dirt).append(((x, y, 0), (x + w, y + d, h)))
    ST.boxes("Set.Stone", ST.block_mat("cobblestone"), stone)
    ST.boxes("Set.Dirt", ST.block_mat("coarse_dirt"), dirt)


def use_camera(name):
    """Make `name` the scene camera: sky, particle billboards and rocket sprites follow it."""
    sc = bpy.context.scene
    cam = sc.camera = bpy.data.objects[name]
    SKY.apply(tick=14500, rain=0.0, render_distance=12, ground_mc_y=64.0, cloud_center=(0.0, 150.0),
              frame_start=FRAMES[0], haze=L.LOOKS[LOOK]['haze'])
    fxp = bpy.data.objects.get("FX.Particles")
    if fxp is not None:
        FW.set_input(fxp.modifiers[0], "Camera", cam)
    for ob in bpy.data.objects:
        for con in ob.constraints:
            if con.type == 'DAMPED_TRACK':
                con.target = cam


def build():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE'
    sc.render.resolution_x, sc.render.resolution_y = 1920, 804
    sc.render.fps = 24
    sc.eevee.taa_render_samples = 32
    sc.frame_start, sc.frame_end = FRAMES
    # 46 shadow-casting characters in a wide view overflow the default 512 MB shadow pool
    # ("Shadow buffer full", 2255 / 2048 pages, shadows go missing); 1024 MB costs no time
    sc.eevee.shadow_pool_size = '1024'
    rng = random.Random(20)
    fx = bpy.data.collections.new("FX")
    sc.collection.children.link(fx)
    FW.set_flash_gain(FLASH_GAIN)
    cloud = FW.Cloud(seed=20)

    battlefield()

    # ---------------------------------------------------------------- the squad
    hits = {(r, i): PRE + t for r, i, t in VICTIMS}
    flyers = []                       # dict(name, rig, states, hit)
    n = 0
    for r, (ahead, xs, trim) in enumerate(RANKS):
        for i, x in enumerate(xs):
            hero = r == 2 and x == 0
            name = "Hero" if hero else f"Mate{n:02d}"
            n += 0 if hero else 1
            hit = hits.get((r, i))
            states = fly(100 + 10 * r + i, (x + rng.uniform(-0.8, 0.8), ahead + rng.uniform(-1.0, 1.0)), trim, hit)
            rig = C.villager(name, skin="plains_farmer" if hero else rng.choice(("plains_plain", "plains_armorer",
                                                                                 "plains_weaponsmith")),
                             helmet="iron", legs="iron", boots="iron", elytra=True,
                             location=states[0]['pos'])
            flyers.append(dict(name=name, rig=rig, states=states, hit=hit))
    hero = next(f for f in flyers if f['name'] == "Hero")

    for f in flyers:
        F.apply(f['rig'], f['states'], FRAME0, trail=cloud,
                rocket_item=F.rocket_in_hand(f['rig'], f['name'] + ".rocket"), flop_on_land=f['hit'] is not None)

    # the camera samples the hero's keys, and it has to exist before rockets and particles are
    # built (they face the scene camera)
    CAM.follow("Cam.Behind", hero['rig'], FRAMES[0], FRAMES[1], side=0.6, back=5.5, up=1.2, lens=20,
               lag=0.40, aim_lag=0.10, lead=0.04, screen=(0.0, -0.25))
    sc.camera = bpy.data.objects["Cam.Behind"]

    def body(f, t):                    # mid-body of a flyer at absolute tick t
        s = f['states'][max(0, min(TICKS - 1, t))]
        return s['pos'] + Vector((0.0, 1.0, 0.0))

    # ---------------------------------------------------------------- Alex's crossbowmen
    soldiers = []
    for li, y in enumerate(TRENCHES):
        for k in range(PER_LINE):
            x = -45.0 + 90.0 * k / (PER_LINE - 1) + rng.uniform(-2.0, 2.0)
            name = f"Alex{li}{k}"
            rig = C.villager(name, skin="plains_plain", helmet="chainmail", chest="chainmail", legs="chainmail",
                             boots="chainmail", location=(x, y + 1.0, -1.0))
            soldiers.append(dict(name=name, rig=rig, items=XB.attach_crossbow(rig),
                                 eye=Vector((x, y + 1.0, 0.5)), volleys=[]))

    def light(nm, pos, f, col):
        FW.glow_light(nm, pos, f, col, peak=LIGHT_PEAK, collection=fx)

    def intercept(eye, target, t0, limit):
        """Ticks for a 1.6 b/tick rocket fired at t0 to meet target(t); None if out of reach."""
        for k in range(1, limit + 1):
            if 1.6 * k >= (target(t0 + k) - eye).length:
                return k
        return None

    # aimed hits first: a rocket reaches the victim exactly at his hit tick
    def aimed(point_at, t_hit, tag):
        p = point_at(t_hit)
        ahead = [s for s in soldiers if s['eye'].y > p.y + 6.0]
        s = min(ahead, key=lambda s: abs((p - s['eye']).length - 45.0))
        k = max(1, round((p - s['eye']).length / 1.6))
        if k > 40:                    # the shortest lifetime of a 3-gunpowder rocket
            print("OUT OF RANGE", tag, "ticks", k)
        s['volleys'].append(dict(t=t_hit - k, dir=(p - s['eye']).normalized(), life=(k, None, None), tag=tag))

    for f in flyers:
        if f['hit'] is not None:
            aimed(lambda t, f=f: body(f, t), f['hit'], "hit." + f['name'])
    aimed(lambda t: body(hero, t) + Vector((0.0, 5.0, 0.3)), PRE + HERO_BURST, "hero")

    # the rest: everyone keeps firing at the squad while it is in front of his trench
    for s in soldiers:
        srng = random.Random(hash((round(s['eye'].x, 2), s['eye'].y)) & 0xFFFF)
        busy = sorted(v['t'] for v in s['volleys'])
        t = PRE - 25
        ready = None                  # his own reaction time once the squad comes into range
        while t < TICKS - 12:
            alive = [f for f in flyers if (f['hit'] is None or f['hit'] > t + 30)
                     and body(f, t).y < s['eye'].y - 10.0 and (body(f, t) - s['eye']).length < 165.0]
            if alive and ready is None:
                ready = t + srng.randrange(0, 70)
            if not alive or t < ready or any(abs(t - b) < 20 for b in busy):
                t += 3
                continue
            f = srng.choice(alive)
            k = intercept(s['eye'], lambda tt: body(f, tt), t, 46) or 46
            miss = Vector((srng.uniform(-7, 7), srng.uniform(-3, 3), srng.uniform(2.5, 7) * srng.choice((-1, 1))))
            s['volleys'].append(dict(t=t, dir=(body(f, t + k) + miss - s['eye']).normalized(), life=None, tag="v"))
            t += 17 + srng.randrange(*PAUSE)

    bursts = []
    tk = 24.0 / 20.0
    for s in soldiers:
        s['volleys'].sort(key=lambda v: v['t'])
        f_first = tick_frame(PRE - 40)
        XB.pose_hold(s['rig'], -0.5, 0.0, f_first)
        XB.set_loaded(s['items'], True, f_first)
        for j, v in enumerate(s['volleys']):
            f = tick_frame(v['t'])
            head_x = -math.asin(max(-0.95, min(0.95, v['dir'].z)))
            for i in range(11):                               # reload (Quick Charge III), then aim
                XB.pose_charge(s['rig'], i / 10.0, f - (17 - i) * tk)
            XB.set_loaded(s['items'], True, f - 7 * tk)
            XB.pose_hold(s['rig'], head_x, 0.0, f - 6 * tk)
            XB.pose_hold(s['rig'], head_x, 0.0, f)
            shots = XB.shoot(cloud, s['eye'], v['dir'], round(f, 2), rng, PALETTE,
                             flight=3, multishot=True, explode=True, light=True, collection=fx,
                             name=f"{s['name']}.{j}", light_fn=light, life=v['life'])
            XB.set_loaded(s['items'], False, f + 0.01)
            bursts += [(bf, bp, v['tag']) for _, bf, bp, _ in shots]

    CAM.follow("Cam.Wide", [f['rig'] for f in flyers if f['hit'] is None], FRAMES[0], FRAMES[1],
               side=34.0, back=-16.0, up=5.0, lens=24, lag=0.6, aim_lag=0.3, heading=180.0, screen=(0.1, 0.1))

    cloud.build("FX.Particles", fx)
    use_camera("Cam.Behind")
    L.apply(LOOK)
    info = dict(flyers=len(flyers), soldiers=len(soldiers), volleys=sum(len(s['volleys']) for s in soldiers),
                bursts=len(bursts), in_shot=sum(1 for b in bursts if FRAMES[0] <= b[0] <= FRAMES[1]),
                particles=len(cloud.pts), lights=sum(1 for o in bpy.data.objects if o.type == 'LIGHT'),
                objects=len(bpy.data.objects))
    return flyers, soldiers, bursts, info


PALETTE = ('red', 'orange', 'yellow', 'lime', 'light_blue', 'magenta', 'pink', 'cyan', 'white', 'purple')


def render(name, percent=100, first=None, last=None):
    sc = bpy.context.scene
    use_camera(name)
    tag = name.replace("Cam.", "").lower()
    sc.render.resolution_percentage = percent
    sc.render.image_settings.file_format = 'PNG'
    sc.render.filepath = os.path.join(OUT, "ambush", tag, "f")
    if first is not None:
        sc.frame_start, sc.frame_end = first, last
    times, mark = [], [0.0]

    def pre(*_):
        mark[0] = time.time()

    def post(*_):
        times.append((bpy.context.scene.frame_current, time.time() - mark[0]))

    bpy.app.handlers.render_pre.append(pre)
    bpy.app.handlers.render_post.append(post)
    t0 = time.time()
    bpy.ops.render.render(animation=True)
    total = time.time() - t0
    per = sorted(t for _, t in times)
    lines = [f"{name}: {len(times)} frames, {sc.render.resolution_x * percent // 100}x"
             f"{sc.render.resolution_y * percent // 100}, EEVEE {sc.eevee.taa_render_samples} samples",
             f"total {total:.1f} s, mean {total / max(1, len(times)):.2f} s/frame (with PNG writing)",
             f"render only: median {per[len(per) // 2]:.2f}, max {per[-1]:.2f}, min {per[0]:.2f} s/frame",
             "frame seconds"] + [f"{f} {t:.2f}" for f, t in times]
    with open(os.path.join(OUT, f"ambush_render_times_{tag}_v1.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("RENDERED", lines[0], "|", lines[1], "|", lines[2])


args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if args[:1] == ["render"]:
    render(args[1], int(args[2]) if len(args) > 2 else 100,
           int(args[3]) if len(args) > 4 else None, int(args[4]) if len(args) > 4 else None)
else:
    FLYERS, SOLDIERS, BURSTS, INFO = build()
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, "blender", "test_ambush.blend"))
    print("SAVED", INFO)
