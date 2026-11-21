"""Location 2: the training ground of Steve's empire (shots 09-13, overcast), 384 x 256 blocks.

Rolling plains (same noise family as the village, gentler). In the west the wooden fort from
MCBuilder (C:\\Games\\MCBuilder\\scenes\\fort.py: spruce palisade, field towers, two gatehouses,
barracks hall, granary, stable, forge, tents, well) set down unchanged on a levelled pad; its flag
cloth is left off (the empires' banners are still the user's open decision). In front of the
south gate the drill square (shots 09-10): the line of 16 recruits faces the fort. East of the
square the range (shots 11-13): the launch line, a field of haystacks to fall into, then a strip
of almost 300 blocks with marker posts on both sides and log gates 11 high: ground references
for the follow camera at 8-15 blocks (HANDOFF pitfall 20).

Axes: X = east, Y = up, Z = south. In Blender (OBJ, forward -Z, up Y): x = X, y = -Z, z = Y.
    C:\\Games\\MCBuilder\\venv\\Scripts\\python sets\\drill.py      -> assets/sets/drill.schem,
                                                                   drill_map.png, drill_marks.json
    python tools\\build_set.py drill                                -> assets/sets/obj/drill.obj
"""
import json
import os
import random
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import schem  # noqa: E402  (puts MCBuilder on sys.path)
import mcvox as R  # noqa: E402
from mcvox import blk, ctx, burp, h3, put  # noqa: E402

FORT_SCENE = os.path.join(schem.MCB, "scenes", "fort.py")
W, H, D = 384, 60, 256
BASE = 14.0
SEED = 2027
rng = random.Random(SEED)


# ================================================================ the fort, built by its own scene
def build_fort():
    """Run MCBuilder's fort scene in its own mcvox world (without its command line) and return
    its grid. Local y = 0 is its ground layer. Block ids stay valid: mcvox keeps one registry."""
    src = open(FORT_SCENE, encoding="utf-8").read()
    src = src[:src.index("\nR.cli(")]
    exec(compile(src, FORT_SCENE, "exec"), {"__name__": "fort", "__file__": FORT_SCENE})
    return R.grid.copy()


FORT = build_fort()
FW_, FH_, FD_ = FORT.shape                        # 60 x 24 x 60, palisade at local 10..49
R.new_world(W, H, D)
XX, ZZ = np.meshgrid(np.arange(W), np.arange(D), indexing="ij")


def vnoise2(scale, seed):
    """Smooth value noise over the whole map, 0..1, feature size ~ scale blocks."""
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


# ================================================================ natural ground
HMf = BASE + 2.5 * (vnoise2(80, 11) * 2 - 1) + 1.2 * (vnoise2(28, 12) * 2 - 1) + 0.4 * (vnoise2(10, 13) * 2 - 1)

# ================================================================ layout
FO = (40, 60)                                     # fort origin: palisade x 50..89, z 70..109
PAL = (FO[0] + 10, FO[0] + 49, FO[1] + 10, FO[1] + 49)
GATE_X = (FO[0] + 28, FO[0] + 31)                 # gates and the N-S road through the fort
SQUARE = (48, 96, 121, 143)                       # drill square x0, x1, z0, z1
LAUNCH_X = 100                                    # launch line (the square's east edge)
RANGE_Z = (120, 144)                              # the range strip, centre line z = 132
RANGE_C = 132
HAY_ZONE = (106, 160)                             # haystacks to fall into
GATES_X = (190, 235, 280, 325, 370)               # log gates over the range
POSTS_X = range(112, W - 2, 16)                   # marker posts on both sides
PADS = []


def add_pad(rect, kind, level=None):
    x0, x1, z0, z1 = rect
    if level is None:
        level = int(round(float(HMf[x0:x1 + 1, z0:z1 + 1].mean())))
    PADS.append(dict(rect=rect, level=level, kind=kind))
    return PADS[-1]


FPAD = add_pad((FO[0], FO[0] + FW_ - 1, FO[1], FO[1] + FD_ - 1), "fort")
L = FPAD["level"]
add_pad(SQUARE, "square", L)                      # the square continues the fort's ground
add_pad((SQUARE[1] + 1, LAUNCH_X + 2, SQUARE[2], SQUARE[3]), "launch", L)

# ease the ground towards the pads (the game's "beard"), as in the village
num, den, wmax = np.zeros((W, D)), np.zeros((W, D)), np.zeros((W, D))
for p in PADS:
    x0, x1, z0, z1 = p["rect"]
    d = np.hypot(np.maximum(np.maximum(x0 - XX, XX - x1), 0), np.maximum(np.maximum(z0 - ZZ, ZZ - z1), 0))
    w = 1.0 - sm(d / 14.0)
    num += w * p["level"]
    den += w
    wmax = np.maximum(wmax, w)
HMf = HMf * (1 - wmax) + np.where(den > 0, num / np.maximum(den, 1e-9), 0.0) * wmax
# the range: smoothed across (no single-block steps under the flight line), still following the land
rz = (ZZ >= RANGE_Z[0] - 4) & (ZZ <= RANGE_Z[1] + 4) & (XX > LAUNCH_X)
blur = HMf.copy()
for _ in range(6):
    blur = (blur + np.roll(blur, 1, 0) + np.roll(blur, -1, 0) + np.roll(blur, 1, 1) + np.roll(blur, -1, 1)) / 5.0
HMf = np.where(rz, blur, HMf)
HM = np.rint(HMf).astype(int)
for p in PADS:
    x0, x1, z0, z1 = p["rect"]
    HM[x0:x1 + 1, z0:z1 + 1] = p["level"]

# ================================================================ terrain into the world
DIRT, GRASS_B = ctx("dirt"), ctx("grass_block", snowy="false")
low = np.minimum.reduce([HM, np.roll(HM, 1, 0), np.roll(HM, -1, 0), np.roll(HM, 1, 1), np.roll(HM, -1, 1)])
bottom = np.clip(np.minimum(HM - 3, low - 1), 0, None)
G = R.grid
for x in range(W):
    for z in range(D):
        G[x, bottom[x, z]:HM[x, z], z] = DIRT
        G[x, HM[x, z], z] = GRASS_B

# ================================================================ the fort
used = np.zeros((W, D), bool)                     # columns with something built (no grass tufts, trees)
for lx, ly, lz in zip(*np.nonzero(FORT)):
    v = FORT[lx, ly, lz]
    name = R.VARIANTS[v]["name"]
    if name.endswith("_wool") and ly >= 8:        # the flag cloth: banners are not decided yet
        continue
    if name == "blue_wool":                       # one blue tent, the empire's colour is not decided
        v = blk("white_wool")
    x, y, z = FO[0] + lx, L + ly, FO[1] + lz
    put(x, y, z, int(v))
    if ly >= 1 or name not in ("grass_block", "coarse_dirt"):
        used[x, z] = True

# ================================================================ roads: north from the fort, south from the square
road = np.zeros((W, D), bool)
road[GATE_X[0]:GATE_X[1] + 1, 0:FO[1] + 1] = True
road[GATE_X[0]:GATE_X[1] + 1, SQUARE[3]:D] = True
for x, z in zip(*np.nonzero(road)):
    put(x, HM[x, z], z, burp(x, 0, z, "dirt_path", [("gravel", .22), ("coarse_dirt", .2)], 51, 1.5))
# fort road between the south gate and the square
for z in range(FO[1] + FD_, SQUARE[2]):
    for x in range(GATE_X[0], GATE_X[1] + 1):
        put(x, HM[x, z], z, burp(x, 0, z, "dirt_path", [("gravel", .22), ("coarse_dirt", .2)], 51, 1.5))
        road[x, z] = True

# ================================================================ the drill square (shots 09-10)
x0, x1, z0, z1 = SQUARE
for x in range(x0, LAUNCH_X + 1):
    for z in range(z0, z1 + 1):
        edge = x in (x0, x1) or z in (z0, z1)
        put(x, L, z, burp(x, 0, z, "coarse_dirt", [("dirt", .25), ("dirt_path", .12), ("gravel", .04)], 61, 1.7)
            if not edge else burp(x, 0, z, "dirt_path", [("coarse_dirt", .3)], 62, 1.4))
        used[x, z] = True
LINE_Z = 131                                      # the recruits stand on this row, facing north (the fort)
LINE = [(60 + 1.5 * i, LINE_Z) for i in range(16)]
SERGEANT = (57, LINE_Z - 2)
for x in (x0, x1):                                # corner posts with lanterns
    for z in (z0, z1):
        put(x, L + 1, z, "spruce_fence")
        put(x, L + 2, z, "spruce_fence")
        put(x, L + 3, z, blk("lantern", hanging="false", waterlogged="false"))
for z in range(z0 + 2, z1 - 1, 3):                # rocket racks along the west edge: barrels, a chest
    put(x0 + 1, L + 1, z, blk("barrel", facing="up", open="false"))
put(x0 + 1, L + 2, z0 + 5, blk("barrel", facing="up", open="false"))
for x in (x0 + 1,):
    put(x, L + 1, z1 - 2, blk("chest", facing="east", type="single", waterlogged="false"))

# ================================================================ the range (shots 11-13)
for z in range(RANGE_Z[0], RANGE_Z[1] + 1):       # the launch line: a strip of gravel
    put(LAUNCH_X, L, z, burp(LAUNCH_X, 0, z, "gravel", [("andesite", .3)], 63, 1.2))
for x in range(LAUNCH_X + 1, W):                  # a worn track down the middle of the range
    for z in range(RANGE_C - 1, RANGE_C + 2):
        if h3(x, 7, z, 64) < (0.9 if z == RANGE_C else 0.55):
            put(x, HM[x, z], z, burp(x, 0, z, "coarse_dirt", [("dirt_path", .4), ("gravel", .1)], 65, 1.6))
            used[x, z] = True


def stack(cx, cz, rows):
    """A haystack: rows of hay bales, each row a (w, d) footprint shrinking upwards."""
    top = HM[cx, cz]
    for i, (w, d) in enumerate(rows):
        for dx in range(w):
            for dz in range(d):
                x, z = cx - w // 2 + dx, cz - d // 2 + dz
                if i and h3(x, i, z, 66) < 0.12:
                    continue                      # a bale missing here and there
                put(x, HM[x, z] + 1 + i, z, blk("hay_block", axis="x" if (x + z + i) % 3 else "z"))
                used[x, z] = True
                top = max(top, HM[x, z] + 1 + i)
    return top


HAY = []
tries = 0
while len(HAY) < 14 and tries < 2000:
    tries += 1
    cx, cz = rng.randrange(HAY_ZONE[0], HAY_ZONE[1]), rng.randrange(RANGE_Z[0] + 1, RANGE_Z[1])
    if abs(cz - RANGE_C) < 3 or any(abs(cx - h[0]) < 7 and abs(cz - h[2]) < 6 for h in HAY):
        continue
    rows = rng.choice([[(4, 3), (2, 2)], [(3, 3), (3, 1)], [(5, 3), (3, 2), (1, 1)], [(3, 2)], [(4, 4), (2, 3)]])
    HAY.append([cx, stack(cx, cz, rows), cz])

for x in POSTS_X:                                 # marker posts on both sides: a target block on a fence post
    for z in (RANGE_Z[0] - 1, RANGE_Z[1] + 1):
        put(x, HM[x, z] + 1, z, "spruce_fence")
        put(x, HM[x, z] + 2, z, "spruce_fence")
        put(x, HM[x, z] + 3, z, blk("target", power="0"))
        used[x, z] = True

GATES = []
for gx in GATES_X:                                # log gates over the flight line
    zs = (RANGE_C - 7, RANGE_C + 7)
    base = max(HM[gx, z] for z in zs)
    top = base + 11
    for z in zs:
        for y in range(HM[gx, z] + 1, top + 1):
            put(gx, y, z, blk("spruce_log", axis="y"))
        used[gx, z] = True
    for z in range(zs[0], zs[1] + 1):
        put(gx, top + 1, z, blk("stripped_spruce_log", axis="z"))
    GATES.append([gx, top + 1, zs[0], zs[1]])

# ================================================================ meadow: grass, a few flowers, trees
FLOWERS = ("dandelion", "poppy", "azure_bluet", "oxeye_daisy", "cornflower")
patch, kindmap = vnoise2(15, 31), vnoise2(50, 32)
for x in range(W):
    for z in range(D):
        y = HM[x, z]
        if used[x, z] or road[x, z] or G[x, y, z] != GRASS_B or G[x, y + 1, z] != 0:
            continue
        r = h3(x, 5, z, 91)
        if patch[x, z] > 0.86 and r < 0.15:
            put(x, y + 1, z, ctx(FLOWERS[int(kindmap[x, z] * len(FLOWERS)) % len(FLOWERS)]))
        elif r < 0.26:
            put(x, y + 1, z, ctx("short_grass"))
        elif r < 0.27:
            put(x, y + 1, z, ctx("tall_grass", half="lower"))
            put(x, y + 2, z, ctx("tall_grass", half="upper"))


def oak(x, y, z):
    """The game's plain oak: trunk 4-6, two 5x5 leaf layers with ragged corners, a 3x3 and a plus."""
    height = rng.choice((4, 5, 5, 6))
    for dy in range(height):
        put(x, y + dy, z, ctx("oak_log", axis="y"))
    for dy, rad in ((height - 3, 2), (height - 2, 2), (height - 1, 1), (height, 1)):
        for dx in range(-rad, rad + 1):
            for dz in range(-rad, rad + 1):
                corner = abs(dx) == rad and abs(dz) == rad
                if corner and (rad == 1 and dy == height or rng.random() < 0.6):
                    continue
                if R.get(x + dx, y + dy, z + dz) in (0, R.VKEY.get(("short_grass", (), True), -1)):
                    put(x + dx, y + dy, z + dz, ctx("oak_leaves"))


busy = used | road
busy[FO[0] - 4:FO[0] + FW_ + 4, FO[1] - 4:FO[1] + FD_ + 4] = True
busy[LAUNCH_X:, RANGE_Z[0] - 10:RANGE_Z[1] + 11] = True          # keep the flight line open
busy[SQUARE[0] - 6:LAUNCH_X + 6, SQUARE[2] - 6:SQUARE[3] + 7] = True
trees = 0
while trees < 22:
    x, z = rng.randrange(6, W - 6), rng.randrange(6, D - 6)
    if busy[x - 4:x + 5, z - 4:z + 5].any():
        continue
    busy[x - 3:x + 4, z - 3:z + 4] = True
    put(x, HM[x, z], z, DIRT)
    put(x, HM[x, z] + 1, z, 0)
    oak(x, HM[x, z] + 1, z)
    trees += 1

# ================================================================ marks for the shot scripts
MARKS = dict(
    size=[W, H, D], level=L,
    fort=list(PAL), fort_origin=list(FO), gate_south=[GATE_X[0], L, PAL[3]], gate_north=[GATE_X[0], L, PAL[2]],
    square=list(SQUARE), line=[[x, L, z] for x, z in LINE], line_facing="north", sergeant=[SERGEANT[0], L, SERGEANT[1]],
    launch_x=LAUNCH_X, range_z=list(RANGE_Z), range_centre_z=RANGE_C,
    range_ground=[[x, int(HM[x, RANGE_C])] for x in range(LAUNCH_X, W, 8)],
    haystacks=HAY, gates=GATES, posts_x=list(POSTS_X))


def preview(path):
    """Top-down map, one pixel per block, shaded by height."""
    from PIL import Image
    col = {"grass_block": (104, 150, 62), "dirt_path": (160, 132, 82), "coarse_dirt": (120, 88, 60),
           "gravel": (130, 126, 124), "water": (58, 96, 190), "oak_leaves": (52, 104, 40), "oak_log": (104, 82, 50),
           "hay_block": (200, 168, 40), "short_grass": (112, 160, 66), "tall_grass": (112, 160, 66),
           "spruce_log": (80, 60, 40), "stripped_spruce_log": (140, 110, 70), "dirt": (134, 96, 66)}
    img = np.zeros((D, W, 3), np.uint8)
    top = (G != 0).shape[1] - 1 - np.argmax((G != 0)[:, ::-1, :], axis=1)
    for x in range(W):
        for z in range(D):
            n = R.VARIANTS[G[x, top[x, z], z]]["name"]
            c = col.get(n) or ((226, 70, 60) if n in FLOWERS else
                               (150, 115, 75) if "spruce" in n or "planks" in n or "stairs" in n or "slab" in n
                               else (150, 150, 150))
            k = 0.72 + 0.022 * (top[x, z] - BASE)
            img[z, x] = np.clip(np.array(c) * k, 0, 255)
    Image.fromarray(img).resize((W * 2, D * 2), Image.NEAREST).save(path)


if __name__ == "__main__":
    out = os.path.join(os.path.dirname(HERE), "assets", "sets")
    print("ground", int(HM.min()), "..", int(HM.max()), "level", L, "haystacks", len(HAY), "gates", GATES)
    schem.export_schem(os.path.join(out, "drill.schem"))
    with open(os.path.join(out, "drill_marks.json"), "w", encoding="utf-8") as fh:
        json.dump(MARKS, fh, indent=1, default=int)
    preview(os.path.join(out, "drill_map.png"))
