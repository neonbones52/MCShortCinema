"""Animatic, location 1 (village): shots 01-08 and the memory flashes of shot 22.

    blender -b blender/sets/village.blend --python shots/anim_village.py -- stills|render|save [shot ...]

One performance on the track timeline (tick 0 = frame 160): the farmer hoes in the bare rows
(02-03, a stroke every 40 frames), stops and looks round (04), sees the riders on the crest
(05), walks to the field gate while they gallop down the road (06), the two soldiers, on foot by
then, point at him and hand him the paper (07), the hoe drops into the wheat and they lead him
off (08). His two children watch from beside the house, frightened (07), and take a few steps
after him (08). Cows graze about the farm all along. Shot 22, the memory look: the wheat, the
poppy, and the family: father with the hoe, the two children running up to him, a cow by the
fence (user 2026-11-21: its own scene, not a cut from the summons).
"""
import math
import os
import random
import sys

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, r"C:\Dev\Projects\CinemaShort\shots")
import importlib
import anim as A
importlib.reload(A)
import mc_animal as AN
import mc_character as C
import mc_horse as H
import mc_look as L
import mc_motion as M
import mc_set as SET
import mc_sky as SKY

K = SET.marks("village")
FL = K["field_level"]
PX, PY, PZ = K["poppy"]
GX, GY, GZ = K["field_gate"]
CX, CY, CZ = K["crest"]
F0 = 160                                     # tick 0 of the village performance
SEG2 = 2560                                  # tick 0 of the family memory (shot 22)
FEET = FL + 1                                # feet on the field
ROW = (236.5, 222.5)                         # the farmer's place in the bare rows (set x, z)
INSIDE_GATE = (GX + 0.5, GZ + 1.5)
NORTH = math.pi                              # yaw facing north (+Y in Blender)
MEMORIES = {"Wheat": (2484, 2518), "Poppy": (2528, 2566), "Family": (2578, 2664)}   # shot 22 windows


def T(frame, frame0=F0):
    return A.tick_of_frame(frame, frame0)


def g(x, z):
    """Blender z of the ground at set column (x, z)."""
    return SET.ground(x, z, "village")


def at(x, z, dz=0.0):
    return Vector((x, -z, g(x, z) + dz))


def feet(x, z, y=None):
    return Vector((x, -z, (FEET if y is None else y)))


# ------------------------------------------------------------------ cast and performance
def farmer():
    with A.quiet():
        rig = C.villager("Farmer", skin="plains_farmer", item_r="iron_hoe")
    a = M.Actor(rig, pos=feet(*ROW), yaw=NORTH)
    ground_ahead = feet(ROW[0], ROW[1] - 2.6, FEET)              # head down ~30 deg: the face still reads
    a.look(0, T(505), ground_ahead)                              # eyes on the work
    for f in range(180, 505, 40):                                # a stroke every 40 frames (half a beat)
        a.swing(T(f))
    # shot 04: straightens, looks over the field, the village, then up to the crest
    a.look(T(525), T(560), feet(222, 214, FEET + 1.0))
    a.look(T(560), T(600), feet(215, 205, FEET + 3.0))
    a.look(T(600), T(722), Vector((CX, -CZ, CY + 2.0)))
    # walks to the field gate while the riders come down, only after 05 (its camera is his eyes)
    a.walk(T(720), [feet(*ROW), feet(ROW[0] - 2.0, 215.0), feet(*INSIDE_GATE)], speed=0.2159)
    a.face(T(760), NORTH)
    return a


def soldiers(farmer_actor):
    """Two riders, on foot for 07-08 (the riders on horseback are other rigs, hidden then)."""
    iron = dict(helmet="iron", chest="iron", legs="iron", boots="iron")
    with A.quiet():
        r1 = C.villager("SoldierA", skin="plains_weaponsmith", **iron)
        r2 = C.villager("SoldierB", skin="plains_armorer", item_r="paper", **iron)
    pa, pb = at(GX - 0.6, GZ - 2.2), at(GX + 1.8, GZ - 2.0)
    a = M.Actor(r1, pos=pa, yaw=0.0)
    b = M.Actor(r2, pos=pb, yaw=0.0)
    for s in (a, b):
        s.face(0, farmer_actor)
        s.look(0, T(958), farmer_actor)
    a.point(T(806), T(866), farmer_actor, jabs=(T(818), T(836), T(852)))
    b.hold_out(T(826), T(896), farmer_actor)
    # 08: they lead him off along the road to the west
    road = [at(GX - 3.0, GZ - 3.0), at(GX - 14.0, GZ - 4.0)]
    a.walk(T(904), [pa] + road, speed=0.2159)
    b.walk(T(906), [pb, at(GX - 1.0, GZ - 2.6)] + [r + Vector((0, 0.9, 0)) for r in road], speed=0.2159)
    return a, b


def farmer_led_off(a):
    a.look(T(800), T(830), Vector((GX - 0.6, -(GZ - 2.2), FEET + 1.6)))
    a.look(T(830), T(900), Vector((GX + 1.8, -(GZ - 2.0), FEET + 1.6)))
    a.walk(T(908), [feet(*INSIDE_GATE), at(GX + 0.5, GZ - 1.5), at(GX - 2.0, GZ - 3.6), at(GX - 13.0, GZ - 4.6)],
           speed=0.2159)


def drop_hoe(rig, frame):
    """The hoe leaves the hand at `frame` and falls into the wheat at his feet."""
    held = bpy.data.objects["Farmer.item.R"]
    A.key_visible(held, [(0, frame), (2400, A.TRACK_FRAMES)])
    bpy.context.scene.frame_set(frame)
    mw = held.matrix_world.copy()
    free = held.copy()
    free.data = held.data
    free.animation_data_clear()            # the copy shared the held hoe's visibility keys (no hoe in 02-04)
    free.name = "Farmer.hoe.dropped"
    free.parent = None
    A.collection("Shots").objects.link(free)
    free.matrix_world = mw
    free.rotation_mode = 'XYZ'
    loc0, rot0 = mw.to_translation(), mw.to_euler('XYZ')
    land = Vector((loc0.x + 0.15, loc0.y - 0.35, FEET + 0.05))
    for i, f in enumerate(range(frame, frame + 9)):
        u = (i / 8.0) ** 2
        free.location = loc0.lerp(land, u)
        free.rotation_euler = (rot0.x + 1.2 * u, rot0.y + 0.4 * u, rot0.z + 0.6 * u)
        free.keyframe_insert("location", frame=f)
        free.keyframe_insert("rotation_euler", frame=f)
    A.key_visible(free, [(frame, 1200)])


def road_path(points, step=2.0, lift=0.0):
    """Points on the terrain every `step` blocks along a polyline of set (x, z)."""
    out = []
    for (x0, z0), (x1, z1) in zip(points, points[1:]):
        n = max(1, int(math.hypot(x1 - x0, z1 - z0) / step))
        for i in range(n):
            u = i / n
            x, z = x0 + (x1 - x0) * u, z0 + (z1 - z0) * u
            out.append(at(x, z, lift))
    out.append(at(*points[-1], lift))
    return out


ROAD_A, ROAD_B = (268.0, 172.0), (236.0, 200.0)          # the road below the crest (village marks)
_d = (ROAD_B[0] - ROAD_A[0], ROAD_B[1] - ROAD_A[1])
_n = math.hypot(*_d)
ROAD_DIR = (_d[0] / _n, _d[1] / _n)
ROAD_PERP = (-ROAD_DIR[1], ROAD_DIR[0])


def road_point(u, off=0.0):
    return (ROAD_A[0] + _d[0] * u + ROAD_PERP[0] * off, ROAD_A[1] + _d[1] * u + ROAD_PERP[1] * off)


def riders():
    """Two riders in iron on armoured horses: over the crest (05), down the road past the low
    camera (06), then the horses stand by the gate (07-08)."""
    out = []
    for i, (coat, dx, dz, delay) in enumerate((("horse_brown", 0.0, 0.0, 0), ("horse_gray", 2.4, 1.6, 8))):
        with A.quiet():
            h = H.horse(f"Horse{i}", coat=coat, armor="iron")
            r = C.villager(f"Rider{i}", skin="plains_weaponsmith" if i == 0 else "plains_armorer",
                           helmet="iron", chest="iron", legs="iron", boots="iron")
        H.mount(r, h)
        # 05: over the crest from the north-east, frames 620-719
        H.gallop(h, road_path([(322 + dx, 98 + dz), (300 + dx, 126 + dz), (288 + dx, 144 + dz)]), 560 + delay)
        # 06: down the road past the camera, frames 719-799
        off = 1.6 + 1.8 * i
        H.gallop(h, road_path([road_point(0.0, off), road_point(1.0, off), (226 + dx, 203 + dz)]), 719 + delay)
        # 07-08: standing by the road behind the soldiers from the cut on (no gallop keys after 798)
        for fc in A.fcurves(h):
            for i in reversed(range(len(fc.keyframe_points))):
                if fc.keyframe_points[i].co.x > 798.5:
                    fc.keyframe_points.remove(fc.keyframe_points[i], fast=True)
            fc.update()
            last = max((k for k in fc.keyframe_points if k.co.x <= 798.5), key=lambda k: k.co.x, default=None)
            if last is not None:
                last.interpolation = 'CONSTANT'
        h.location = at(GX - 2.5 + 3.5 * i, GZ - 5.0 - 0.6 * i)
        h.rotation_quaternion = Vector((0, -1, 0)).rotation_difference(Vector((-1.0, 0.3 * (1 - 2 * i), 0)).normalized())
        for f in (799, 958):
            h.keyframe_insert("location", frame=f)
            h.keyframe_insert("rotation_quaternion", frame=f)
            H.pose(h, 0.0, 0.0, 0.0, frame=f, head_pitch=0.3)
        A.key_visible(r, [(0, 799)])
        out.append((h, r))
    return out


def children(farmer_actor):
    """The farmer's two children (the 26.x baby villager): by the house in 07, frightened, eyes
    on their father and the soldiers; in 08 they come a few steps towards the fence after him."""
    kids = []
    # at the corner of the field by the road: seen between their father and the soldiers in 07
    spots = ((223.5, 207.4, 227.4, 207.1), (224.6, 206.5, 228.2, 206.2))
    for i, (x, z, x1, z1) in enumerate(spots):
        with A.quiet():
            rig = C.baby_villager(f"Kid{i + 1}", skin="baby_plains")
        k = M.Actor(rig, pos=at(x, z), yaw=-math.pi / 2)
        k.face(0, farmer_actor)
        k.look(T(799), T(840 + 9 * i), farmer_actor)
        k.look(T(840 + 9 * i), T(870 + 6 * i), Vector((GX - 0.6, -(GZ - 2.2), FEET + 1.8)))   # the soldier
        k.look(T(870 + 6 * i), T(958), farmer_actor)
        k.walk(T(900 + 10 * i), [at(x, z), at(x1, z1)], speed=0.12)
        kids.append(k)
    return kids


def cows():
    """Background life: a few cows wandering and grazing on the grass round the farm (02-07)."""
    herd = (("CowA", (240.5, 236.5), [(243.5, 238.5), (238.5, 240.5)], 2.0),
            ("CowB", (247.0, 233.5), [(250.5, 236.0)], -1.0),
            ("CowC", (219.5, 229.5), [(216.0, 231.5), (220.5, 233.0)], 0.6),
            ("CowD", (209.5, 222.5), [(206.0, 225.0)], 2.6))

    def ground(x, y):
        # the median of five rays: a single ray can slip between faces and report a hole a few
        # blocks down (the cow dropped out of sight for a frame in 02: user 2026-11-21)
        hs = sorted(h for h in (g(x + dx, -y + dz) for dx, dz in ((0, 0), (0.6, 0), (-0.6, 0), (0, 0.6), (0, -0.6)))
                    if h is not None)
        return hs[len(hs) // 2]
    for i, (name, (x, z), stops, yaw) in enumerate(herd):
        with A.quiet():
            c = AN.cow(name, location=at(x, z), yaw=yaw)
        AN.amble(c, ground, 0, 960, (x, -z), [(sx, -sz) for sx, sz in stops], seed=10 + i)
        A.key_visible(c, [(0, 958)])


def memory_family(farmer_rig, kids):
    """Shot 22, the last and longest memory: father in the bare rows with the hoe; the younger
    one runs up along the row and he turns to him; the other stands at his side; a cow grazes
    just over the fence."""
    w0, w1 = MEMORIES["Family"]
    a = M.Actor(farmer_rig, pos=feet(*ROW), yaw=NORTH)
    a.look(0, T(2596, SEG2), feet(ROW[0], ROW[1] - 2.6, FEET))
    a.swing(T(2584, SEG2))
    a.face(T(2598, SEG2), -math.pi / 2 + 0.3)                     # turns to the child coming
    k1, k2 = [M.Actor(k.rig, pos=feet(*p), yaw=y) for k, p, y in
              zip(kids, ((229.5, 222.6), (238.3, 222.5)), (-math.pi / 2 - 0.1, math.pi / 2))]
    k1.walk(T(2578, SEG2), [feet(229.5, 222.6), feet(235.3, 222.6)], speed=0.21)     # running along his row
    k1.face(T(2612, SEG2), a)
    k1.look(0, 200, a)
    k2.face(0, a)
    k2.look(0, 200, a)
    a.look(T(2600, SEG2), 200, k1)
    M.bake([a, k1, k2], int(T(w1 + 2, SEG2)), frame0=SEG2)
    with A.quiet():
        c = AN.cow("CowMem", location=at(233.5, 226.5), yaw=1.9)
    AN.amble(c, lambda x, y: g(x, -y), w0 - 10, w1 + 4, (233.5, -226.5), [(232.0, -227.0)], seed=7)
    A.key_visible(c, [(w0 - 10, w1 + 4)])


# ------------------------------------------------------------------ cameras
def cameras():
    S = A.camera
    b = SET.b
    # 01: the crane comes down onto the village (Cam.Wide of the survey, from 18 blocks higher)
    S("Shot01", [(0, b(96, 58, 306), b(215, 16, 200)), (159, b(102, 36, 298), b(215, 13, 202))], lens=24)
    # 02: behind the poppy at the fence, 1.1 above the ground, tilted 5 deg down so that the
    # poppy sits low in the frame and the farmer shows over the fence; focus pulls to him at 0:12
    cpos = at(PX + 0.5, PZ - 2.6, 1.1)
    aim = cpos + Vector((0.0, -1.0, -math.tan(math.radians(5.0))))
    c = S("Shot02", [(160, cpos, aim)], lens=35)
    d_poppy = (Vector((PX + 0.5, -(PZ + 0.5), PY + 0.4)) - cpos).length
    d_farmer = (feet(*ROW) + Vector((0, 0, 1.4)) - cpos).length
    A.focus(c, [(160, d_poppy), (284, d_poppy), (300, d_farmer)], fstop=1.8)
    # 03: medium, three-quarter front from just over the wheat, a slow push in
    face = feet(ROW[0], ROW[1], FEET + 1.55)
    S("Shot03", [(319, feet(232.8, 219.4, FEET + 1.15), face),
                 (479, feet(233.4, 219.9, FEET + 1.15), face)], lens=40)
    # 04: wide from the side, the village behind him
    S("Shot04", [(480, at(253.0, 225.5, 2.4), feet(232.0, 219.0, FEET + 1.4)),
                 (638, at(252.0, 225.0, 2.4), feet(231.0, 219.0, FEET + 1.4))], lens=28)
    # 05: his eyes, a long lens on the crest; it follows the riders down a little
    eye = feet(ROW[0], ROW[1] - 0.45, FEET + 1.6)
    S("Shot05", [(639, eye, Vector((CX - 1, -(CZ + 3), CY + 1.5))),
                 (718, eye, Vector((CX - 7, -(CZ + 13), CY - 1.0)))], lens=120)
    # 06: low by the road, the lens follows the lead horse as it thunders past 2.5 blocks off
    lead = bpy.data.objects["Horse0.rig"]
    sc = bpy.context.scene
    mid = road_point(0.5, -0.9)
    cpos = at(mid[0], mid[1], 0.45)

    def track(f):
        sc.frame_set(f)
        h = lead.matrix_world.translation
        return cpos, Vector((h.x, h.y, cpos.z + 0.35))
    A.camera_path("Shot06", range(719, 799), track, lens=20)
    # 07: two-shot across the poppy and the fence
    S("Shot07", [(799, at(242.5, PZ + 0.6, 1.6), feet(GX + 0.8, GZ - 0.2, FEET + 1.3)),
                 (877, at(242.0, PZ + 0.6, 1.6), feet(GX + 0.8, GZ - 0.2, FEET + 1.3))], lens=40)
    # 08: just over the wheat, looking down at his feet: the hoe falls, the legs walk out
    S("Shot08", [(878, feet(GX + 2.6, GZ + 3.0, FEET + 2.1), feet(GX + 0.5, GZ + 1.4, FEET + 0.6))], lens=28)
    # 22: memories (each 1-2 s, darkness between them: shots/assemble.py)
    w = MEMORIES
    S("Shot22.Wheat", [(w["Wheat"][0], feet(243.0, 216.5, FEET + 1.2), feet(226.0, 215.5, FEET + 0.5)),
                       (w["Wheat"][1], feet(242.0, 216.3, FEET + 1.25), feet(226.0, 215.0, FEET + 0.6))], lens=35)
    pc = at(PX + 0.5, PZ - 1.2, 0.55)
    pp = Vector((PX + 0.5, -(PZ + 0.5), PY + 0.4))
    c = S("Shot22.Poppy", [(w["Poppy"][0], pc, pp), (w["Poppy"][1], pc + Vector((0, -0.2, 0)), pp)], lens=50)
    A.focus(c, [(w["Poppy"][0], (pp - pc).length), (w["Poppy"][1], (pp - pc).length - 0.2)], fstop=2.0)
    # the family, from over the south fence: the cow in the near left, father and the children
    S("Shot22.Family", [(w["Family"][0], at(240.8, 229.0, 2.9), feet(235.6, 222.6, FEET + 0.7)),
                        (w["Family"][1], at(240.0, 228.2, 2.8), feet(235.6, 222.6, FEET + 0.7))], lens=30)


# ------------------------------------------------------------------ sky and look per shot
def village(look="village", tick=1000):
    def prepare():
        SKY.apply(tick=tick, rain=0.0, render_distance=12, ground_mc_y=64.0 - FL, frame_start=0,
                  haze=L.LOOKS[look]["haze"])
        L.apply(look)
    return prepare


def build():
    A.setup()
    bpy.data.objects["Set.village"]                                # the set is in the .blend
    fa = farmer()
    sa, sb = soldiers(fa)
    farmer_led_off(fa)
    kids = children(fa)
    M.bake([fa, sa, sb] + kids, int(T(958)), frame0=F0)          # together: they look at each other
    for s in (sa, sb):
        A.key_visible(s.rig, [(799, 1200)])
    drop_hoe(fa.rig, 896)
    riders()
    cows()
    memory_family(fa.rig, kids)
    cameras()


PLAN = [dict(shot=n, cam=f"Shot{n:02d}", prepare=village()) for n in range(1, 9)] + [
    dict(shot=22, cam=f"Shot22.{k}", prepare=village("memory", 2000), range=r) for k, r in MEMORIES.items()]

if __name__ == "__main__":
    mode, shots = A.args()
    build()
    A.run(mode, shots, PLAN, "anim_village.blend")
