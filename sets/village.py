"""Location 1: the plains village and the hero's field (shots 01-08), 384 x 384 blocks.

Not superflat: rolling plains from layered noise, a ridge in the north-east that the road
climbs over (the riders appear on its crest, shot 05), a pond. The village is built from the
game's own plains-village pieces read from the 26.2 jar (tools/mc_vanilla.py) and set down the
way the game does it: each house on its own level by its entrance jigsaw, the ground eased
towards it all around (the game's "beard"), streets following the ground. The hero's farm (his
house, a fenced wheat field, the poppy) stands at the east end, below the ridge.

Axes: X = east, Y = up, Z = south. In Blender (OBJ, forward -Z, up Y): x = X, y = -Z, z = Y.
    C:\\Games\\MCBuilder\\venv\\Scripts\\python sets\\village.py     -> assets/sets/village.schem,
                                                                     village_map.png, village_marks.json
    python tools\\build_set.py village                               -> assets/sets/obj/village.obj
"""
import json
import math
import os
import random
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import schem  # noqa: E402  (puts MCBuilder on sys.path)
import mcvox as R  # noqa: E402
import mc_vanilla as V  # noqa: E402
from mcvox import blk, ctx, burp, h3, put  # noqa: E402

W, H, D = 384, 60, 384
BASE = 14.0
SEED = 2026
HOUSES = "village/plains/houses/"
rng = random.Random(SEED)
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
HMf = BASE + 3.0 * (vnoise2(70, 1) * 2 - 1) + 1.5 * (vnoise2(26, 2) * 2 - 1) + 0.5 * (vnoise2(10, 3) * 2 - 1)
# the ridge: its axis runs NW-SE, the road crosses it at the crest
CREST = (300, 126)
_dx, _dz = XX - CREST[0], ZZ - CREST[1]
HMf += 13.0 * np.exp(-((_dx * 0.8 + _dz * 0.6) / 75.0) ** 2 - ((_dx * 0.6 - _dz * 0.8) / 30.0) ** 2)
# the pond: a bowl below the local level
POND = (92, 268)
_r = np.hypot(XX - POND[0], ZZ - POND[1])
_lvl = float(HMf[_r < 16].mean())
WATER = int(round(_lvl)) - 1
HMf = HMf * (1 - sm(1.6 - _r / 12.0)) + (_lvl - 4.5 * np.clip(1 - (_r / 13.0) ** 2, 0, 1) + 0.6) * sm(1.6 - _r / 12.0)

# ================================================================ roads (centre lines)
MAIN, CROSS = 1, 2
MEET = (145, 210)                                 # origin of the meeting point (10 x 10)
ROUTES = [
    (MAIN, [(0, 236), (60, 225), (100, 220), (144, 214)]),
    (MAIN, [(155, 215), (205, 207), (236, 200), (268, 172), (298, 128), (330, 88), (383, 36)]),
    (CROSS, [(150, 209), (150, 160), (153, 138)]),
    (CROSS, [(149, 220), (149, 276), (146, 292)]),
]
road = np.zeros((W, D), np.uint8)
for code, pts in ROUTES:
    for (x0, z0), (x1, z1) in zip(pts, pts[1:]):
        lx, lz = x1 - x0, z1 - z0
        t = np.clip(((XX - x0) * lx + (ZZ - z0) * lz) / float(lx * lx + lz * lz), 0, 1)
        road[np.hypot(XX - (x0 + t * lx), ZZ - (z0 + t * lz)) <= 1.35] = code
VILLAGE_X = (66, 212)                             # between these the main road is a village street

# ================================================================ where everything stands
PADS = []          # dict(rect=(x0, x1, z0, z1), level, kind, ...)


def rect_gap(a, b):
    return max(a[0] - b[1], b[0] - a[1], a[2] - b[3], b[2] - a[3])


def add_pad(rect, kind, **kw):
    x0, x1, z0, z1 = rect
    level = int(round(float(HMf[x0:x1 + 1, z0:z1 + 1].mean())))
    for p in PADS:
        if rect_gap(rect, p["rect"]) < 1:
            print("OVERLAP", kind, kw.get("name", ""), rect, "with", p["kind"], p.get("name", ""), p["rect"])
    PADS.append(dict(rect=rect, level=level, kind=kind, **kw))
    return PADS[-1]


def add_house(name, cell, extend):
    p = V.piece(HOUSES + name)
    origin, k = V.entrance_origin(p, cell, 0, extend)
    return add_pad(V.footprint(p, origin, k), "house", name=name, cell=cell, extend=extend)


def road_span(code, fixed, axis):
    """Extent of the road across column x (axis 'x') or row z (axis 'z') near the village."""
    line = road[fixed, :] if axis == "x" else road[:, fixed]
    idx = np.nonzero(line == code)[0]
    return int(idx.min()), int(idx.max())


def row(code, side, start, names, gap=3):
    """Houses side by side along a street, entrances on it. side N/S: along the main road from
    x = start eastwards; side W/E: along the cross street from z = start southwards."""
    cur = start
    for name in names:
        p = V.piece(HOUSES + name)
        sz, ez = p.size[2], p.entrance["pos"][2]
        span = range(cur, cur + sz)
        if side == "N":
            add_house(name, (cur + ez, min(road_span(code, x, "x")[0] for x in span) - 1), "north")
        elif side == "S":
            add_house(name, (cur + sz - 1 - ez, max(road_span(code, x, "x")[1] for x in span) + 1), "south")
        elif side == "W":
            add_house(name, (min(road_span(code, z, "z")[0] for z in span) - 1, cur + sz - 1 - ez), "west")
        else:
            add_house(name, (max(road_span(code, z, "z")[1] for z in span) + 1, cur + ez), "east")
        cur += sz + gap


add_pad((MEET[0], MEET[0] + 9, MEET[1], MEET[1] + 9), "meeting")
row(MAIN, "N", 84, ["plains_small_house_2", "plains_butcher_shop_1", "plains_medium_house_2", "plains_library_2"], 4)
row(MAIN, "S", 86, ["plains_animal_pen_2", "plains_small_house_4", "plains_weaponsmith_1", "plains_small_house_7"], 4)
row(MAIN, "N", 160, ["plains_temple_3", "plains_small_house_6", "plains_large_farm_1", "plains_small_house_3"], 4)
row(MAIN, "S", 160, ["plains_tool_smith_1", "plains_big_house_1", "plains_stable_1"], 4)
row(CROSS, "W", 166, ["plains_cartographer_1", "plains_small_house_5", "plains_shepherds_house_1"], 4)
row(CROSS, "E", 166, ["plains_fletcher_house_1", "plains_small_house_8", "plains_masons_house_1"], 4)
row(CROSS, "W", 229, ["plains_armorer_house_1", "plains_small_house_1", "plains_animal_pen_3"], 4)
row(CROSS, "E", 229, ["plains_tannery_1", "plains_medium_house_1"], 4)

# the hero's farm: his house on the south side of the road, the wheat field east of it
HERO_HOUSE = "plains_small_house_3"
_p = V.piece(HOUSES + HERO_HOUSE)
_hx = 214
HERO = add_house(HERO_HOUSE, (_hx + _p.size[2] - 1 - _p.entrance["pos"][2],
                              max(road_span(MAIN, x, "x")[1] for x in range(_hx, _hx + _p.size[2])) + 1), "south")
FIELD = (226, 250, 209, 223)                      # farmland x0, x1, z0, z1
FPAD = add_pad((FIELD[0] - 2, FIELD[1] + 2, FIELD[2] - 2, FIELD[3] + 2), "field")

# ================================================================ ease the ground towards the pads
num, den, wmax = np.zeros((W, D)), np.zeros((W, D)), np.zeros((W, D))
for p in PADS:
    x0, x1, z0, z1 = p["rect"]
    d = np.hypot(np.maximum(np.maximum(x0 - XX, XX - x1), 0), np.maximum(np.maximum(z0 - ZZ, ZZ - z1), 0))
    w = 1.0 - sm(d / 9.0)
    num += w * p["level"]
    den += w
    wmax = np.maximum(wmax, w)
HMf = HMf * (1 - wmax) + np.where(den > 0, num / np.maximum(den, 1e-9), 0.0) * wmax
# streets: no single-block bumps under the path
near = road > 0
for _ in range(2):
    near = near | np.roll(near, 1, 0) | np.roll(near, -1, 0) | np.roll(near, 1, 1) | np.roll(near, -1, 1)
blur = HMf.copy()
for _ in range(3):
    blur = (blur + np.roll(blur, 1, 0) + np.roll(blur, -1, 0) + np.roll(blur, 1, 1) + np.roll(blur, -1, 1)) / 5.0
HMf = np.where(near, blur, HMf)
HM = np.rint(HMf).astype(int)
for p in PADS:
    x0, x1, z0, z1 = p["rect"]
    HM[x0:x1 + 1, z0:z1 + 1] = p["level"]

# ================================================================ terrain into the world
DIRT, GRASS_B = ctx("dirt"), ctx("grass_block", snowy="false")
low = np.minimum.reduce([HM, np.roll(HM, 1, 0), np.roll(HM, -1, 0), np.roll(HM, 1, 1), np.roll(HM, -1, 1)])
bottom = np.clip(np.minimum(HM - 3, low - 1), 0, None)
wet = (HM < WATER) & (_r < 22)
G = R.grid
for x in range(W):
    for z in range(D):
        h = HM[x, z]
        G[x, bottom[x, z]:h, z] = DIRT
        G[x, h, z] = GRASS_B
for x, z in zip(*np.nonzero(wet)):
    h = HM[x, z]
    put(x, h, z, ctx(burp(x, 0, z, "dirt", [("gravel", .25), ("clay", .18)], 71, 2.4)))
    for y in range(h + 1, WATER + 1):
        put(x, y, z, ctx("water", level="0"))

# ================================================================ roads
for x, z in zip(*np.nonzero(road)):
    if wet[x, z]:
        continue
    street = road[x, z] == CROSS or VILLAGE_X[0] <= x <= VILLAGE_X[1]
    put(x, HM[x, z], z, "dirt_path" if street else
        burp(x, 0, z, "dirt_path", [("coarse_dirt", .22), ("gravel", .10)], 43, 2.0))


# ================================================================ trees, lamps, yard things
def oak(x, y, z, height=None):
    """The game's plain oak: trunk 4-6, two 5x5 leaf layers with ragged corners, a 3x3 and a plus."""
    height = height or rng.choice((4, 5, 5, 6))
    for dy in range(height):
        put(x, y + dy, z, ctx("oak_log", axis="y"))
    for dy, rad in ((height - 3, 2), (height - 2, 2), (height - 1, 1), (height, 1)):
        for dx in range(-rad, rad + 1):
            for dz in range(-rad, rad + 1):
                corner = abs(dx) == rad and abs(dz) == rad
                if corner and (rad == 1 and dy == height or rng.random() < 0.6):
                    continue
                if R.get(x + dx, y + dy, z + dz) == 0:
                    put(x + dx, y + dy, z + dz, ctx("oak_leaves"))


LAMP = V.piece("village/plains/plains_lamp_1")
HAY = lambda: blk("hay_block", axis=rng.choice("xyz"))


def decorate(spots):
    for pool, (x, y, z) in spots:
        if pool.endswith("decor"):
            r = rng.random()
            if r < 0.45:
                V.place(LAMP, (x - 1, y + 1, z - 1), 0)
            elif r < 0.60 and R.get(x, y + 1, z) == 0:
                put(x, y + 1, z, HAY())
        elif pool.endswith("trees") and R.get(x, y + 1, z) == 0:
            oak(x, y + 1, z)


# ================================================================ the village
MARKS = {}
decorate(V.place(V.piece("village/plains/town_centers/plains_meeting_point_1"),
                 (MEET[0], PADS[0]["level"], MEET[1]), 0, carve_from=1))
STEP = {"north": (0, 1), "south": (0, -1), "west": (1, 0), "east": (-1, 0)}    # from the entrance to the street
for p in PADS:
    if p["kind"] != "house":
        continue
    piece = V.piece(HOUSES + p["name"])
    decorate(V.place_by_entrance(piece, p["cell"], p["level"], p["extend"]))
    dx, dz = STEP[p["extend"]]
    x, z = p["cell"][0] + dx, p["cell"][1] + dz
    for _ in range(8):                            # the path from the door to the street
        if not (0 <= x < W and 0 <= z < D) or road[x, z]:
            break
        put(x, HM[x, z], z, "dirt_path")
        road[x, z] = 9
        x, z = x + dx, z + dz

# ================================================================ the hero's farm
FL = FPAD["level"]
fx0, fx1, fz0, fz1 = FIELD
WATER_ROWS = (fz0 + 3, fz0 + 11)
BARE = (fz1 - 1, fz1)                             # the two rows he is still tilling (shot 03)
for x in range(fx0, fx1 + 1):
    for z in range(fz0, fz1 + 1):
        if z in WATER_ROWS:
            put(x, FL, z, blk("water", level="0"))
            continue
        put(x, FL, z, blk("farmland", moisture="7"))
        if z in BARE and x > fx0 + 5:
            continue
        put(x, FL + 1, z, blk("wheat", age="7" if h3(x, 0, z, 3) > .12 else str(4 + int(h3(x, 1, z, 4) * 3))))
GATE = (fx0 + 6, fz0 - 1)                         # in the north fence, towards the road
for x in range(fx0 - 1, fx1 + 2):
    for z in (fz0 - 1, fz1 + 1):
        put(x, FL + 1, z, "oak_fence")
for z in range(fz0 - 1, fz1 + 2):
    for x in (fx0 - 1, fx1 + 1):
        put(x, FL + 1, z, "oak_fence")
put(GATE[0], FL + 1, GATE[1], blk("oak_fence_gate", facing="north", in_wall="false", open="true", powered="false"))
x, z = GATE[0], GATE[1] - 1                        # footpath from the gate to the road
while not road[x, z] and z > 0:
    put(x, HM[x, z], z, burp(x, 0, z, "dirt_path", [("coarse_dirt", .3)], 47, 1.6))
    road[x, z] = 9
    z -= 1
hx0, hx1, hz0, hz1 = HERO["rect"]
yard = [(hx1 + 2, hz1 - 1, HAY()), (hx1 + 3, hz1 - 1, HAY()), (hx1 + 2, hz1 - 2, HAY()),
        (hx1 + 2, hz1 - 4, blk("composter", level="4")), (hx1 + 2, hz0 + 1, blk("barrel", facing="up", open="false"))]
for x, z, b in yard:
    put(x, HM[x, z] + 1, z, b)
put(hx1 + 2, HM[hx1 + 2, hz1 - 1] + 2, hz1 - 1, HAY())
POPPY = (fx0 + 10, fz0 - 2)                        # the poppy of shot 02: outside the north fence, wheat behind it
put(POPPY[0], HM[POPPY] + 1, POPPY[1], "poppy")
road[POPPY] = 9                                    # keep the grass tufts off it
for dx, dz in ((-1, 0), (1, 0), (0, -1), (-1, -1), (1, -1)):
    road[POPPY[0] + dx, POPPY[1] + dz] = 9

# ================================================================ meadow: grass, flowers, trees
built = np.zeros((W, D), bool)
for p in PADS:
    x0, x1, z0, z1 = p["rect"]
    built[x0:x1 + 1, z0:z1 + 1] = True
FLOWERS = ("dandelion", "poppy", "azure_bluet", "oxeye_daisy", "cornflower", "red_tulip", "orange_tulip",
           "white_tulip", "pink_tulip")
patch, kindmap = vnoise2(13, 21), vnoise2(44, 22)
grass_id = GRASS_B
for x in range(W):
    for z in range(D):
        y = HM[x, z]
        if built[x, z] or road[x, z] or G[x, y, z] != grass_id or G[x, y + 1, z] != 0:
            continue
        r = h3(x, 5, z, 91)
        if patch[x, z] > 0.80 and r < 0.22:
            put(x, y + 1, z, ctx(FLOWERS[int(kindmap[x, z] * len(FLOWERS)) % len(FLOWERS)]))
        elif r < 0.24:
            put(x, y + 1, z, ctx("short_grass"))
        elif r < 0.255:
            put(x, y + 1, z, ctx("tall_grass", half="lower"))
            put(x, y + 2, z, ctx("tall_grass", half="upper"))
trees = 0
while trees < 26:
    x, z = rng.randrange(8, W - 8), rng.randrange(8, D - 8)
    if built[x - 5:x + 6, z - 5:z + 6].any() or road[x - 4:x + 5, z - 4:z + 5].any() or wet[x, z]:
        continue
    if FIELD[0] - 30 < x < FIELD[1] + 40 and FIELD[2] - 60 < z < FIELD[3] + 12:
        continue                                   # keep the view from the field to the crest open
    built[x - 3:x + 4, z - 3:z + 4] = True
    put(x, HM[x, z], z, DIRT)
    put(x, HM[x, z] + 1, z, 0)
    oak(x, HM[x, z] + 1, z)
    trees += 1
for x, z in zip(*np.nonzero((HM == WATER) & (_r < 24))):       # sugar cane on the shore
    if any(wet[x + dx, z + dz] for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1))) and h3(x, 2, z, 17) < 0.2:
        put(x, HM[x, z], z, DIRT)
        for dy in range(1, 2 + int(h3(x, 3, z, 18) * 3)):
            put(x, HM[x, z] + dy, z, ctx("sugar_cane", age="0"))

# ================================================================ marks for the shot scripts
door = HERO["cell"]
MARKS.update(size=[W, H, D], water_level=WATER,
             hero_door=[door[0], int(HM[door]), door[1]], hero_house=list(HERO["rect"]), hero_house_level=HERO["level"],
             field=list(FIELD), field_level=FL, field_gate=[GATE[0], FL, GATE[1]], field_bare_rows=list(BARE),
             poppy=[POPPY[0], int(HM[POPPY]) + 1, POPPY[1]],
             crest=[CREST[0], int(HM[CREST]), CREST[1]], meeting=[MEET[0] + 5, PADS[0]["level"], MEET[1] + 5],
             road_main=[[x, int(HM[min(x, W - 1), z]), z] for _, pts in ROUTES[:2] for x, z in pts],
             houses=[dict(name=p["name"], rect=list(p["rect"]), level=p["level"], door=list(p["cell"]))
                     for p in PADS if p["kind"] == "house"])


def preview(path):
    """Top-down map, one pixel per block, shaded by height."""
    from PIL import Image
    col = {"grass_block": (104, 150, 62), "dirt_path": (160, 132, 82), "coarse_dirt": (120, 88, 60),
           "gravel": (130, 126, 124), "water": (58, 96, 190), "farmland": (92, 60, 36), "wheat": (214, 180, 72),
           "oak_leaves": (52, 104, 40), "oak_log": (104, 82, 50), "cobblestone": (126, 126, 126),
           "oak_planks": (168, 136, 84), "hay_block": (200, 168, 40), "short_grass": (112, 160, 66),
           "tall_grass": (112, 160, 66), "oak_fence": (150, 120, 74), "dirt": (134, 96, 66)}
    img = np.zeros((D, W, 3), np.uint8)
    top = (G != 0).shape[1] - 1 - np.argmax((G != 0)[:, ::-1, :], axis=1)
    for x in range(W):
        for z in range(D):
            n = R.VARIANTS[G[x, top[x, z], z]]["name"]
            c = col.get(n) or ((226, 70, 60) if n in FLOWERS or n == "poppy" else
                               (190, 150, 110) if "stairs" in n or "slab" in n or "planks" in n else (150, 150, 150))
            k = 0.72 + 0.022 * (HM[x, z] - BASE)
            img[z, x] = np.clip(np.array(c) * k, 0, 255)
    Image.fromarray(img).resize((W * 2, D * 2), Image.NEAREST).save(path)


if __name__ == "__main__":
    out = os.path.join(os.path.dirname(HERE), "assets", "sets")
    print("ground", int(HM.min()), "..", int(HM.max()), "water", WATER, "pads", len(PADS),
          "levels", sorted(set(p["level"] for p in PADS)))
    schem.export_schem(os.path.join(out, "village.schem"))
    with open(os.path.join(out, "village_marks.json"), "w", encoding="utf-8") as fh:
        json.dump(MARKS, fh, indent=1)
    preview(os.path.join(out, "village_map.png"))
    print("marks:", {k: MARKS[k] for k in ("hero_door", "field", "poppy", "crest", "meeting")})
