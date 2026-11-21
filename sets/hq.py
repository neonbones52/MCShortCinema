"""Location 3: the HQ (shots 14-15, night, interior by lanterns), 96 x 96 blocks.

A command building on a small patch of plains, built like the player-made builds of the fort:
stone-brick footing, spruce log posts and plank infill, a gabled spruce roof. Inside, one hall
(15 x 19, 5 blocks to the beams) laid out for the staging approved in tests/test_motion.py:
  * north wall: the map in an item frame at chest height (tools/mc_map.py, placed in Blender),
    Steve's wall banners either side (tools/mc_banner.py), bookshelves, a cartography table and
    a lectern; the officer stands left of the map;
  * benches (oak slabs) in three rows on both sides of an aisle, 24 seats: the whole squad (16);
  * the aisle: a red carpet from the double door in the south wall to the map, Steve walks it;
  * lanterns hanging from the ceiling beams, glass windows in the side walls (night outside).
The door is left open (doors in the game open at once, without a swing; shot 15 can switch it).

Axes: X = east, Y = up, Z = south. In Blender (OBJ, forward -Z, up Y): x = X, y = -Z, z = Y.
    C:\\Games\\MCBuilder\\venv\\Scripts\\python sets\\hq.py      -> assets/sets/hq.schem, hq_marks.json
    python tools\\build_set.py hq                               -> assets/sets/obj/hq.obj
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import schem  # noqa: E402  (puts MCBuilder on sys.path)
import mcvox as R  # noqa: E402
from mcvox import blk, ctx, burp, h3, put, stairs, slab  # noqa: E402

W, H, D = 96, 40, 96
BASE = 14.0
R.new_world(W, H, D)
XX, ZZ = np.meshgrid(np.arange(W), np.arange(D), indexing="ij")


def vnoise2(scale, seed):
    g = np.random.default_rng(seed).random((int(W / scale) + 3, int(D / scale) + 3))
    xs, zs = np.arange(W) / scale, np.arange(D) / scale
    ix, iz = xs.astype(int), zs.astype(int)
    tx, tz = xs - ix, zs - iz
    tx, tz = (tx * tx * (3 - 2 * tx))[:, None], (tz * tz * (3 - 2 * tz))[None, :]
    a, b = g[np.ix_(ix, iz)], g[np.ix_(ix + 1, iz)]
    c, d = g[np.ix_(ix, iz + 1)], g[np.ix_(ix + 1, iz + 1)]
    return (a * (1 - tx) + b * tx) * (1 - tz) + (c * (1 - tx) + d * tx) * tz


def sm(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3 - 2 * t)


# ================================================================ ground
HMf = BASE + 2.0 * (vnoise2(40, 41) * 2 - 1) + 0.6 * (vnoise2(12, 42) * 2 - 1)
BX, BZ = 40, 38                                   # building origin; outer walls x BX..BX+16, z BZ..BZ+20
BW, BD = 17, 21
pad = (BX - 3, BX + BW + 2, BZ - 3, BZ + BD + 6)
L = int(round(float(HMf[pad[0]:pad[1] + 1, pad[2]:pad[3] + 1].mean())))
d = np.hypot(np.maximum(np.maximum(pad[0] - XX, XX - pad[1]), 0), np.maximum(np.maximum(pad[2] - ZZ, ZZ - pad[3]), 0))
w = 1.0 - sm(d / 10.0)
HM = np.rint(HMf * (1 - w) + L * w).astype(int)
HM[pad[0]:pad[1] + 1, pad[2]:pad[3] + 1] = L
DIRT, GRASS_B = ctx("dirt"), ctx("grass_block", snowy="false")
G = R.grid
for x in range(W):
    for z in range(D):
        G[x, max(HM[x, z] - 4, 0):HM[x, z], z] = DIRT
        G[x, HM[x, z], z] = GRASS_B

# ================================================================ the building
F = L + 1                                         # floor level: feet stand at y = F (floor blocks at L)
TOP = F + 5                                       # beams; clear height 5
x0, x1, z0, z1 = BX, BX + BW - 1, BZ, BZ + BD - 1
cx = BX + BW // 2                                 # the aisle / door centre column (x = cx)


def wall_block(x, y, z):
    corner = x in (x0, x1) and z in (z0, z1)
    post = corner or (z in (z0, z1) and (x - x0) % 4 == 0) or (x in (x0, x1) and (z - z0) % 4 == 0)
    if y < F + 1:
        return burp(x, y, z, "stone_bricks", [("mossy_stone_bricks", .08), ("cracked_stone_bricks", .1)], 81, 1.6)
    if post:
        return blk("spruce_log", axis="y")
    if y == TOP:
        return blk("stripped_spruce_log", axis="x" if z in (z0, z1) else "z")
    return "spruce_planks"


for x in range(x0, x1 + 1):
    for z in range(z0, z1 + 1):
        edge = x in (x0, x1) or z in (z0, z1)
        put(x, L, z, burp(x, 0, z, "stone_bricks", [("cracked_stone_bricks", .1)], 82, 1.6) if edge
            else "spruce_planks")                 # floor
        for y in range(F, TOP + 1):
            put(x, y, z, wall_block(x, y, z) if edge else 0)
        put(x, TOP + 1, z, "spruce_planks")       # ceiling
# ceiling beams across the hall every 4 blocks (lanterns hang from them)
BEAMS_Z = list(range(z0 + 4, z1, 4))
for z in BEAMS_Z:
    for x in range(x0 + 1, x1):
        put(x, TOP, z, blk("stripped_spruce_log", axis="x"))
# windows in the side walls: 2 high, between the posts
WINDOWS = []
for z in range(z0 + 2, z1 - 1, 4):
    for x in (x0, x1):
        for y in (F + 1, F + 2):
            put(x, y, z, "glass_pane")
            put(x, y, z + 1, "glass_pane")
        WINDOWS.append([x, F + 1, z])
# the double door in the south wall (open), a step outside
DOOR = (cx - 1, cx)
for x, hinge in zip(DOOR, ("left", "right")):
    for half, y in (("lower", F), ("upper", F + 1)):
        put(x, y, z1, blk("spruce_door", facing="north", half=half, hinge=hinge, open="true", powered="false"))
    put(x, F + 2, z1, "spruce_planks")
# gabled roof, ridge along z
for i in range(BW // 2 + 2):
    y = TOP + 2 + i
    for z in range(z0 - 1, z1 + 2):
        for x, facing in ((x0 - 1 + i, "east"), (x1 + 1 - i, "west")):
            if x0 - 1 + i <= x1 + 1 - i:
                put(x, y, z, stairs("spruce_planks", facing) if x0 - 1 + i < x1 + 1 - i else slab("spruce_planks"))
    for x in range(x0 + i, x1 - i + 1):          # gable ends
        if x0 - 1 + i < x < x1 + 1 - i:
            for z in (z0, z1):
                put(x, y, z, "spruce_planks")

# ================================================================ inside
# north wall: map in the middle (Blender), banners either side (Blender), shelves, table, lectern
MAP_BLOCK = [cx, F + 1, z0 + 1]                   # the frame hangs in this block on the north wall
for x in (x0 + 1, x0 + 2, x1 - 2, x1 - 1):
    for y in (F, F + 1, F + 2):
        put(x, y, z0 + 1, "bookshelf")
put(cx - 3, F, z0 + 1, "cartography_table")
put(cx + 3, F, z0 + 2, blk("lectern", facing="south", has_book="true", powered="false"))
for x in (x0 + 1, x1 - 1):
    put(x, F, z1 - 1, blk("barrel", facing="up", open="false"))
    put(x, F, z1 - 2, blk("chest", facing="east" if x == x0 + 1 else "west", type="single", waterlogged="false"))
# the aisle: red carpet from the door to the map
for z in range(z0 + 3, z1):
    put(cx - 1, F, z, "red_carpet")
    put(cx, F, z, "red_carpet")
# benches: oak slabs, three rows each side of the aisle, facing north (the map)
ROWS_Z = (z0 + 6, z0 + 10, z0 + 14)
SEATS = []
for z in ROWS_Z:
    for xa, xb in ((x0 + 2, cx - 3), (cx + 2, x1 - 2)):
        for x in range(xa, xb + 1):
            put(x, F, z, slab("oak_planks"))
        n = 4
        span = xb + 1 - xa
        for i in range(n):
            SEATS.append([xa + (i + 0.5) * span / n, F + 0.5, z + 0.5])
# lanterns hanging from the beams (and the lamp light positions for Blender)
LANTERNS = []
for z in BEAMS_Z:
    for x in (x0 + 4, x1 - 4):
        put(x, TOP - 1, z, blk("lantern", hanging="true", waterlogged="false"))
        LANTERNS.append([x + 0.5, TOP - 1 + 0.35, z + 0.5])
for x in (cx - 2, cx + 2):                        # two by the map, on fence posts
    put(x, F, z0 + 2, "spruce_fence")
    put(x, F + 1, z0 + 2, blk("lantern", hanging="false", waterlogged="false"))
    LANTERNS.append([x + 0.5, F + 1 + 0.3, z0 + 2 + 0.5])
# outside: lanterns by the door, a path south
for x in (cx - 3, cx + 2):
    put(x, F, z1 + 1, "spruce_fence")
    put(x, F + 1, z1 + 1, blk("lantern", hanging="false", waterlogged="false"))
    LANTERNS.append([x + 0.5, F + 1 + 0.3, z1 + 1 + 0.5])
for z in range(z1 + 1, D):
    for x in (cx - 1, cx):
        put(x, HM[x, z], z, burp(x, 0, z, "dirt_path", [("coarse_dirt", .25), ("gravel", .1)], 83, 1.5))

# grass tufts outside
for x in range(W):
    for z in range(D):
        if pad[0] <= x <= pad[1] and pad[2] <= z <= pad[3]:
            continue
        if G[x, HM[x, z] + 1, z] == 0 and G[x, HM[x, z], z] == GRASS_B and h3(x, 5, z, 91) < 0.22:
            put(x, HM[x, z] + 1, z, ctx("short_grass"))

MARKS = dict(
    size=[W, H, D], floor=F, hall=[x0 + 1, x1 - 1, z0 + 1, z1 - 1], ceiling=TOP,
    map_block=MAP_BLOCK, map_facing="south", officer=[cx - 0.45, F, z0 + 2.7],
    banners=[[cx - 3, F + 2, z0 + 1], [cx + 3, F + 2, z0 + 1]], banner_facing="south",
    door=[cx - 1, F, z1], aisle=[[cx, F, z1 + 2], [cx, F, z0 + 4]],
    seats=SEATS, seat_facing="north", lanterns=LANTERNS, windows=WINDOWS)


if __name__ == "__main__":
    out = os.path.join(os.path.dirname(HERE), "assets", "sets")
    print("level", L, "floor", F, "seats", len(SEATS), "lanterns", len(LANTERNS))
    schem.export_schem(os.path.join(out, "hq.schem"))
    with open(os.path.join(out, "hq_marks.json"), "w", encoding="utf-8") as fh:
        json.dump(MARKS, fh, indent=1, default=float)
