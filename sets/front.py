"""Location 4: the front (shots 18-28, night), 448 x 320 blocks.

West to east (x): the open plain of Steve's side, where the waves fly in from (not superflat, a
few craters, the odd tree); no-man's land, churned and cratered, shattered trunks, a belt of
barbed wire (cobwebs on fence posts); Alex's three trench lines, zigzag (fire bays and
traverses), with a sandbag parapet (mud bricks), a fire step, duckboards and plank revetment,
joined by communication trenches; Alex's rear with tents and supplies, and in it the field of
the finale: the hero's spot 75 blocks behind the last line, looking west, back where he flew
from, over the trenches.
From the user's decisions (2026-11-21): at least 30 of Alex's soldiers (36 fire-step places);
the fallen lie in Alex's rear, behind the crossbowmen's backs (the waves crossed the lines and
were shot down over the rear); the hero watches the barrage go up ahead of him from the
trenches into the sky (air defence), bursting 64-80 blocks beyond them (mc_crossbow physics).

Axes: X = east, Y = up, Z = south. In Blender (OBJ, forward -Z, up Y): x = X, y = -Z, z = Y.
    C:\\Games\\MCBuilder\\venv\\Scripts\\python sets\\front.py   -> assets/sets/front.schem,
                                                                 front_map.png, front_marks.json
    python tools\\build_set.py front                             -> assets/sets/obj/front.obj
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

W, H, D = 448, 50, 320
BASE = 16.0
SEED = 2029
rng = random.Random(SEED)
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


# ================================================================ layout
LINES_X = (292, 306, 320)                         # Alex's trench lines (west edge of the fire bay)
Z_RANGE = (40, 280)                               # the trenches run north-south
COMMS_Z = range(64, 270, 48)                      # communication trenches between the lines
WIRE_X = LINES_X[0] - 14                          # barbed wire belt
HERO = (LINES_X[-1] + 75, 160)                    # finale: in Alex's rear, looks west over the trenches
NOMANS = (200, LINES_X[0] - 3)                    # churned ground
REAR = (LINES_X[-1] + 12, W - 6)

# ================================================================ ground
HMf = BASE + 2.6 * (vnoise2(90, 51) * 2 - 1) + 1.2 * (vnoise2(30, 52) * 2 - 1) + 0.4 * (vnoise2(9, 53) * 2 - 1)
# the trench belt follows the land, but smoothly (no single-block steps along a trench)
belt = (XX >= LINES_X[0] - 6) & (XX <= LINES_X[-1] + 12)
blur = HMf.copy()
for _ in range(10):
    blur = (blur + np.roll(blur, 1, 0) + np.roll(blur, -1, 0) + np.roll(blur, 1, 1) + np.roll(blur, -1, 1)) / 5.0
wb = sm(1.0 - np.maximum(np.maximum(LINES_X[0] - 6 - XX, XX - LINES_X[-1] - 12), 0) / 8.0)
HMf = HMf * (1 - wb) + blur * wb
# the finale's field: an almost level stretch around the hero (the camera dollies 30 blocks back
# east at head height and must not run into rising ground); 15 % of the relief is kept
_fd = np.hypot(np.maximum(np.abs(XX - HERO[0]) - 45, 0), np.maximum(np.abs(ZZ - HERO[1]) - 45, 0))
_fw = 0.85 * (1.0 - sm(_fd / 18.0))
_lvl = float(HMf[HERO[0] - 45:HERO[0] + 46, HERO[1] - 45:HERO[1] + 46].mean())
HMf = HMf * (1 - _fw) + _lvl * _fw
# craters: bowls with a rim, many in no-man's land, some on the plain
CRATERS = []
for n, (xa, xb), (r0, r1) in ((70, NOMANS, (2.0, 4.5)), (26, (40, NOMANS[0]), (1.5, 3.5)), (10, (REAR[0], REAR[1]), (1.5, 3.0))):
    for _ in range(n):
        cx, cz, r = rng.uniform(xa, xb), rng.uniform(20, D - 20), rng.uniform(r0, r1)
        if abs(cx - HERO[0]) < 6 and abs(cz - HERO[1]) < 6:
            continue                              # keep the hero's own patch whole
        CRATERS.append((cx, cz, r))
        dd = np.hypot(XX - cx, ZZ - cz) / r
        HMf -= np.where(dd < 1, (1 - dd ** 2) * r * 0.55, 0)
        HMf += np.where((dd >= 0.95) & (dd < 1.45), 0.45 * (1 - np.abs(dd - 1.2) / 0.25).clip(0, 1), 0)
HM = np.rint(HMf).astype(int)

DIRT, GRASS_B = ctx("dirt"), ctx("grass_block", snowy="false")
G = R.grid
churn = vnoise2(14, 54)
crater_d = np.full((W, D), 9.0)
for cx, cz, r in CRATERS:
    crater_d = np.minimum(crater_d, np.hypot(XX - cx, ZZ - cz) / r)
# how churned the ground is: fades in over 50 blocks from the plain, out over 20 behind the lines
churn_w = sm((XX - (NOMANS[0] - 35)) / 50.0) * (1 - sm((XX - (LINES_X[-1] + 6)) / 20.0))
churn_w = churn_w * (0.75 + 0.5 * vnoise2(40, 55))
nomans = churn_w > 0.5
for x in range(W):
    for z in range(D):
        h = HM[x, z]
        G[x, max(h - 4, 0):h, z] = DIRT
        if crater_d[x, z] < 1.15:
            top = burp(x, 0, z, "coarse_dirt", [("dirt", .25), ("gravel", .1), ("mud", .08)], 61, 3.0)
        elif churn[x, z] + 0.25 * h3(x, 1, z, 62) > 0.45 + (1 - min(churn_w[x, z], 1.0)) * 0.7:
            top = burp(x, 0, z, "coarse_dirt", [("dirt", .3), ("podzol", .12), ("mud", .04)], 63, 4.5)
        else:
            top = None
        G[x, h, z] = ctx(top) if top else GRASS_B

# ================================================================ trenches
SOLDIERS, TRENCH_FLOOR = [], {}
HM0 = HM.copy()                                   # the ground before digging: trench depths count from it


def trench_line(base):
    """A zigzag line: 10-block fire bays alternately 4 blocks forward and back, joined by
    traverses. Cross-section from the west: parapet (mud bricks on the lip), fire step (top
    G-1, two blocks wide: user 2026-11-21, the shooters stood pressed against the mud bricks), floor
    two blocks down (top G-2) with duckboards, plank revetment on the east wall."""
    cells = []
    for z in range(*Z_RANGE):
        off = 4 if (z // 10) % 2 else 0
        xb = base + off
        cells.append((xb, z, "bay"))
        if z % 10 == 0 and z > Z_RANGE[0]:        # traverse: carve across between the two bays
            for x in range(base, base + 7):
                cells.append((x, z, "trav"))
    for xb, z, kind in cells:
        g = int(round(float(np.mean(HM0[max(xb - 2, 0):xb + 5, z]))))
        cols = (xb, xb + 1, xb + 2) if kind == "bay" else (xb,)
        for i, x in enumerate(cols):
            step = kind == "bay" and i <= 1           # a 2-block fire step: the shooters stand off the parapet
            floor_top = g - 1 if step else g - 2
            for y in range(floor_top + 1, g + 2):
                put(x, y, z, 0)
            put(x, floor_top, z, burp(x, 0, z, "dirt", [("mud", .3), ("coarse_dirt", .3)], 65, 1.3))
            HM[x, z] = floor_top
            if not step:
                put(x, floor_top + 1, z, blk("spruce_trapdoor", facing="north", half="bottom", open="false",
                                             powered="false", waterlogged="false"))
                TRENCH_FLOOR[(x, z)] = floor_top
        if kind == "bay":
            for y in range(g - 2, g + 1):         # revetment on the east wall
                put(xb + 3, y, z, blk("spruce_log", axis="y") if z % 4 == 0 else "spruce_planks")
            if h3(xb, 3, z, 66) > 0.12:           # sandbags on the west lip, a gap here and there
                put(xb - 1, g + 1, z, "mud_bricks")
                if h3(xb, 4, z, 67) > 0.55:
                    put(xb - 1, g + 2, z, blk("mud_brick_slab", type="bottom", waterlogged="false"))
            put(xb + 4, g + 1, z, ctx("coarse_dirt"))   # parados: the spoil behind
    return cells


for base in LINES_X:
    trench_line(base)
    for z in range(Z_RANGE[0] + 9, Z_RANGE[1] - 9, 20):     # fire-step places, 12 per line
        off = 4 if (z // 10) % 2 else 0
        xb = base + off
        SOLDIERS.append([xb + 1.5, int(HM[xb + 1, z]) + 1, z + 0.5])   # the back block of the step (user 2026-11-21)
# communication trenches between the lines (east-west, 2 wide)
for z0 in COMMS_Z:
    for x in range(LINES_X[0] + 3, LINES_X[-1] + 3):
        for z in (z0, z0 + 1):
            if (x, z) in TRENCH_FLOOR:
                continue
            g = HM0[x, z]
            for y in range(g - 1, g + 2):
                put(x, y, z, 0)
            put(x, g - 2, z, burp(x, 0, z, "dirt", [("mud", .3)], 68, 1.3))
            put(x, g - 1, z, blk("spruce_trapdoor", facing="north", half="bottom", open="false",
                                 powered="false", waterlogged="false"))
            HM[x, z] = g - 2
            TRENCH_FLOOR[(x, z)] = g - 2

# ================================================================ no-man's land: wire, trunks
for z in range(Z_RANGE[0] - 10, Z_RANGE[1] + 10):
    x = WIRE_X + int(2 * np.sin(z * 0.21)) + (1 if h3(0, 5, z, 69) > 0.7 else 0)
    if z % 3 == 0:
        put(x, HM[x, z] + 1, z, "spruce_fence")
        put(x, HM[x, z] + 2, z, "spruce_fence")
    elif h3(x, 6, z, 70) > 0.25:
        put(x, HM[x, z] + 1, z, "cobweb")
        if h3(x, 7, z, 71) > 0.6:
            put(x, HM[x, z] + 2, z, "cobweb")
STUMPS = 0
while STUMPS < 14:
    x, z = rng.randrange(NOMANS[0], WIRE_X - 3), rng.randrange(20, D - 20)
    if (x, z) in TRENCH_FLOOR or crater_d[x, z] < 1.3:
        continue
    for dy in range(1, rng.choice((2, 3, 3, 4, 5))):
        put(x, HM[x, z] + dy, z, blk("stripped_oak_log" if h3(x, dy, z, 72) < 0.4 else "oak_log", axis="y"))
    STUMPS += 1

# ================================================================ Alex's rear: tents, barrels
TENTS = []
for i in range(6):
    cx, z0 = REAR[0] + 10 + (i % 3) * 22, 70 + (i // 3) * 120 + rng.randrange(0, 20)
    g = max(HM[x, z] for x in range(cx - 1, cx + 2) for z in range(z0, z0 + 5))
    for z in range(z0, z0 + 5):
        for x in (cx - 1, cx + 1):
            put(x, g + 1, z, "blue_wool")
        put(cx, g + 2, z, "blue_wool")
    TENTS.append([cx, g + 1, z0])
    for k in range(3):
        put(cx + 3, HM[cx + 3, z0 + k] + 1, z0 + k, blk("barrel", facing="up", open="false"))

# ================================================================ grass, flowers, trees on the living plain
FLOWERS = ("dandelion", "azure_bluet", "oxeye_daisy", "cornflower", "cornflower")   # no poppies: there is one, the symbol
for x in range(W):
    for z in range(D):
        y = HM[x, z]
        if G[x, y, z] != GRASS_B or G[x, y + 1, z] != 0:
            continue
        r = h3(x, 5, z, 91)
        p = 0.10 if nomans[x, z] else 0.24
        if abs(x - HERO[0]) < 55 and abs(z - HERO[1]) < 55:
            p = 0.05                              # the finale's field: trampled, the bodies must read
            if abs(z - HERO[1]) <= 1 and HERO[0] - 3 <= x <= HERO[0] + 36:
                p = 0.0                           # nothing between the dolly camera and the hero
        if r < p:
            put(x, y + 1, z, ctx("short_grass"))
        elif r < p + 0.004 and not nomans[x, z]:
            put(x, y + 1, z, ctx(FLOWERS[int(h3(x, 9, z, 92) * 5) % 5]))
        elif nomans[x, z] and r > 0.985:
            put(x, y + 1, z, ctx("dead_bush"))
# the poppy in the mud by the hero (shot 28): a step from where he falls, on his left
POPPY = (HERO[0] - 1, HERO[1] - 2)
put(POPPY[0], HM[POPPY], POPPY[1], ctx("coarse_dirt"))
put(POPPY[0], HM[POPPY] + 1, POPPY[1], "poppy")


def oak(x, y, z):
    height = rng.choice((4, 5, 5, 6))
    for dy in range(height):
        put(x, y + dy, z, ctx("oak_log", axis="y"))
    for dy, rad in ((height - 3, 2), (height - 2, 2), (height - 1, 1), (height, 1)):
        for dx in range(-rad, rad + 1):
            for dz in range(-rad, rad + 1):
                if abs(dx) == rad and abs(dz) == rad and (rad == 1 and dy == height or rng.random() < 0.6):
                    continue
                if R.get(x + dx, y + dy, z + dz) == 0:
                    put(x + dx, y + dy, z + dz, ctx("oak_leaves"))


trees = 0
while trees < 12:
    x, z = rng.randrange(8, NOMANS[0] - 30), rng.randrange(8, D - 8)
    if abs(z - HERO[1]) < 40 and x > 120:
        continue                                  # keep the finale's field of view open
    put(x, HM[x, z], z, DIRT)
    put(x, HM[x, z] + 1, z, 0)
    oak(x, HM[x, z] + 1, z)
    trees += 1

# ================================================================ marks
hero_y = int(HM[HERO])
MARKS = dict(
    size=[W, H, D], lines_x=list(LINES_X), trench_z=list(Z_RANGE), comms_z=list(COMMS_Z), wire_x=WIRE_X,
    hero=[HERO[0], hero_y, HERO[1]], hero_facing="west", poppy=[POPPY[0], int(HM[POPPY]) + 1, POPPY[1]],
    soldiers=SOLDIERS, soldier_facing="west", nomans_x=list(NOMANS), rear_x=list(REAR),
    craters=[[round(cx, 1), round(cz, 1), round(r, 2)] for cx, cz, r in CRATERS], tents=TENTS,
    alex_banners=[[LINES_X[-1] + 8, int(HM[LINES_X[-1] + 8, z]) + 1, z] for z in (70, 160, 250)],
    ground_x=[[x, int(HM[x, HERO[1]])] for x in range(0, W, 8)])


def preview(path):
    from PIL import Image
    col = {"grass_block": (96, 140, 58), "coarse_dirt": (110, 80, 56), "mud": (60, 56, 58), "podzol": (98, 70, 40),
           "gravel": (128, 124, 122), "dirt": (124, 90, 62), "mud_bricks": (140, 106, 80), "spruce_trapdoor": (100, 76, 46),
           "spruce_planks": (110, 82, 52), "spruce_log": (70, 52, 34), "blue_wool": (52, 64, 170), "cobweb": (220, 220, 220),
           "oak_leaves": (50, 100, 40), "short_grass": (96, 140, 58), "poppy": (220, 40, 40)}
    img = np.zeros((D, W, 3), np.uint8)
    top = (G != 0).shape[1] - 1 - np.argmax((G != 0)[:, ::-1, :], axis=1)
    for x in range(W):
        for z in range(D):
            n = R.VARIANTS[G[x, top[x, z], z]]["name"]
            c = col.get(n, (150, 150, 150))
            img[z, x] = np.clip(np.array(c) * (0.7 + 0.025 * (top[x, z] - BASE)), 0, 255)
    Image.fromarray(img).resize((W * 2, D * 2), Image.NEAREST).save(path)


if __name__ == "__main__":
    out = os.path.join(os.path.dirname(HERE), "assets", "sets")
    print("ground", int(HM.min()), "..", int(HM.max()), "craters", len(CRATERS), "soldier places", len(SOLDIERS),
          "hero", MARKS["hero"])
    schem.export_schem(os.path.join(out, "front.schem"))
    with open(os.path.join(out, "front_marks.json"), "w", encoding="utf-8") as fh:
        json.dump(MARKS, fh, indent=1, default=float)
    preview(os.path.join(out, "front_map.png"))
