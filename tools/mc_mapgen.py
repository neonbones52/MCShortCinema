"""A filled Minecraft map, drawn the way the game draws it (26.2, read with javap), of a landmass
of our own (the HQ wall map, shot 14). Plain Python (numpy, Pillow):

    python tools/mc_mapgen.py [cols rows] [seed]   -> assets/maps/hq_<col>_<row>.png (128 x 128 each)
                                                      + renders/tests/hq/map_preview_v1.png

Scale level 4 ("1:16"): one map pixel = 16 x 16 blocks, one map = 2048 x 2048 blocks; a wall of
cols x rows maps in item frames covers cols*2048 x rows*2048 blocks, maps side by side as the
game aligns them.

MapItem.update, for every map pixel (k east, l south; l runs from -1 so that row 0 has a row to
the north to compare with, and the previous height is reset to 0 at the top of every column):
  * for each of the 16 x 16 block columns: from the WORLD_SURFACE heightmap go down to the first
    block whose map colour is not NONE (grass tufts and flowers count: PLANT); if it is a fluid,
    count the blocks down to the first non-fluid one (depth); add y / 256 to the mean height;
  * the pixel's colour is the most frequent colour (ties: the first one met, x outer, z inner);
  * WATER: d = (sum of depths // 256) * 0.1 + ((k + l) & 1) * 0.2; d < 0.5 HIGH, d > 0.9 LOW,
    else NORMAL; any other colour: d = (mean - mean of the pixel to the north) * 4 / (4 + 4)
    + (((k + l) & 1) - 0.5) * 0.4; d > 0.6 HIGH, d < -0.6 LOW, else NORMAL;
  * shade: colour * {LOW 180, NORMAL 220, HIGH 255} / 255 (MapColor.Brightness).
The landmass is not the game's generator (that would need a world made in the game): it is
noise shaped like an overworld with plains, forests, a coast, rivers, lakes and stony hills.
"""
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "maps")
PREVIEW = os.path.join(ROOT, "renders", "tests", "hq")
SCALE = 4
S = 1 << SCALE                                    # 16 blocks per pixel
SEA = 63                                          # water surface block y = 62

# MapColor (26.2 static init): id -> RGB
COLORS = {"NONE": (0, 0x000000), "GRASS": (1, 0x7FB238), "SAND": (2, 0xF7E9A3), "PLANT": (7, 0x007C00),
          "SNOW": (8, 0xFFFFFF), "CLAY": (9, 0xA4A8B8), "DIRT": (10, 0x976D4D), "STONE": (11, 0x707070),
          "WATER": (12, 0x4040FF), "WOOD": (13, 0x8F7748), "PODZOL": (34, 0x815631)}
BRIGHT = {"LOW": 180, "NORMAL": 220, "HIGH": 255}
ORDER = list(COLORS)                              # index into this = colour code in the arrays


def fbm(w, h, scale, seed, octaves=4, x0=0, z0=0):
    """Fractal value noise on a w x h block grid, roughly -1..1, features ~scale blocks."""
    rng = np.random.default_rng(seed)
    out = np.zeros((w, h), np.float32)
    amp, tot, sc = 1.0, 0.0, float(scale)
    for _ in range(octaves):
        gw, gh = int((w + x0 % sc) / sc) + 3, int((h + z0 % sc) / sc) + 3
        g = rng.random((gw, gh), dtype=np.float32) * 2 - 1
        xs = (np.arange(w, dtype=np.float32) + (x0 % sc)) / sc
        zs = (np.arange(h, dtype=np.float32) + (z0 % sc)) / sc
        ix, iz = xs.astype(int), zs.astype(int)
        tx, tz = xs - ix, zs - iz
        tx = (tx * tx * (3 - 2 * tx))[:, None]
        tz = (tz * tz * (3 - 2 * tz))[None, :]
        a, b = g[np.ix_(ix, iz)], g[np.ix_(ix + 1, iz)]
        c, d = g[np.ix_(ix, iz + 1)], g[np.ix_(ix + 1, iz + 1)]
        out += amp * ((a * (1 - tx) + b * tx) * (1 - tz) + (c * (1 - tx) + d * tx) * tz)
        tot += amp
        amp *= 0.5
        sc /= 2.0
    return out / tot


def world(w, h, seed):
    """Block columns of the landmass (x east, z south): surface y, map colour code, water depth."""
    def code(name):
        return ORDER.index(name)

    yy, xx = np.meshgrid(np.arange(h, dtype=np.float32), np.arange(w, dtype=np.float32))
    # continents: an ocean along the west and south-west, a bay, a few islands
    cont = fbm(w, h, 1400, seed + 1, 5) * 1.3 + (xx / w - 0.30) * 1.1 + (0.25 - yy / h) * 0.35
    hills = fbm(w, h, 420, seed + 2, 5)
    small = fbm(w, h, 60, seed + 3, 3)
    ridges = 1 - np.abs(fbm(w, h, 700, seed + 4, 4)) * 2.2
    river = np.abs(fbm(w, h, 900, seed + 5, 4))
    lakes = fbm(w, h, 260, seed + 6, 3)
    land = cont > 0
    hgt = SEA + 1 + np.clip(cont, 0, None) * 26 + hills * 9 + small * 2.0
    mount = np.clip((ridges - 0.72) * 3.0, 0, 1) * np.clip(cont * 3, 0, 1)
    hgt += mount * 38
    ocean_floor = SEA - 3 + cont * 34 + small * 2
    hgt = np.where(land, hgt, np.minimum(ocean_floor, SEA - 1))
    # rivers and lakes cut down to the sea
    riv = land & (river < 0.018) & (hgt < SEA + 30)
    lake = land & (lakes > 0.42) & (hgt < SEA + 12)
    bed = np.where(riv, SEA - 2 - (0.018 - river) * 150, SEA - 2 - (lakes - 0.42) * 30)
    wet = ~land | riv | lake
    hgt = np.where(riv | lake, np.minimum(hgt, bed), hgt)
    surf = np.rint(hgt).astype(np.int16)
    depth = np.where(wet, np.clip(SEA - 1 - surf, 1, None) + 1, 0).astype(np.int16)  # water blocks + floor
    col = np.full((w, h), code("GRASS"), np.uint8)
    beach = land & ~riv & ~lake & (surf <= SEA + 1) & (cont < 0.06)
    col[beach] = code("SAND")
    stony = land & (mount > 0.35) & (surf > SEA + 28)
    col[stony] = code("STONE")
    col[land & (surf > SEA + 66)] = code("SNOW")
    # forests: canopy columns are leaves 4..7 above the ground; plains: tufts (PLANT) and few trees
    forest = fbm(w, h, 500, seed + 7, 4) + small * 0.15
    rnd = np.random.default_rng(seed + 8).random((w, h), dtype=np.float32)
    grassy = land & ~beach & ~stony & ~wet & (col == code("GRASS"))
    canopy_p = np.clip((forest - 0.08) * 4.0, 0, 0.88)
    canopy = grassy & (rnd < canopy_p)
    tuft = grassy & ~canopy & (rnd > 0.70)
    col[canopy | tuft] = code("PLANT")
    top = surf.copy()
    top[canopy] += (4 + (rnd[canopy] * 40).astype(np.int16) % 4)
    top[tuft] += 1
    col[wet] = code("WATER")
    top[wet] = SEA - 1
    return top, col, depth, surf


def draw(top, col, depth):
    """MapItem.update over a block grid whose first S rows (z) lie north of the map. Returns the
    pixels (colour code, brightness name) as an RGB array, height x width = rows x cols of pixels."""
    w, h = top.shape
    pw, ph = w // S, h // S                       # ph includes the extra row to the north
    t = top.reshape(pw, S, ph, S).transpose(0, 2, 1, 3).reshape(pw, ph, S * S).astype(np.float64)
    c = col.reshape(pw, S, ph, S).transpose(0, 2, 1, 3).reshape(pw, ph, S * S)
    dp = depth.reshape(pw, S, ph, S).transpose(0, 2, 1, 3).reshape(pw, ph, S * S)
    mean = t.sum(-1) / (S * S)                     # y / (s*s) summed: the game's d3
    counts = np.stack([(c == i).sum(-1) for i in range(len(ORDER))], -1)
    big = S * S + 1
    first = np.stack([np.where((c == i).any(-1), (c == i).argmax(-1), big) for i in range(len(ORDER))], -1)
    # most frequent; ties -> met first (x outer, z inner = index i * 16 + j in the s*s order)
    key = counts * big * 2 - first
    key[counts == 0] = -10 ** 9
    best = key.argmax(-1)
    water_depth = dp.sum(-1) // (S * S)
    k = np.arange(pw)[:, None]
    l = np.arange(ph)[None, :] - 1                 # pixel row -1 is the strip to the north
    checker = ((k + l) & 1).astype(np.float64)
    prev = np.concatenate([np.zeros((pw, 1)), mean[:, :-1]], 1)
    d_land = (mean - prev) * 4.0 / (SCALE + 4) + (checker - 0.5) * 0.4
    d_water = water_depth * 0.1 + checker * 0.2
    is_water = best == ORDER.index("WATER")
    bright = np.where(is_water, np.where(d_water < 0.5, 255, np.where(d_water > 0.9, 180, 220)),
                      np.where(d_land > 0.6, 255, np.where(d_land < -0.6, 180, 220)))
    rgb_table = np.array([[(v >> 16) & 255, (v >> 8) & 255, v & 255] for _, v in COLORS.values()])
    rgb = rgb_table[best] * bright[..., None] // 255
    return rgb[:, 1:].transpose(1, 0, 2).astype(np.uint8)       # drop the north strip; rows = z


def main(cols=1, rows=1, seed=1916):
    from PIL import Image
    w, h = cols * 128 * S, rows * 128 * S
    top, col, depth, _surf = world(w, h + S, seed)              # + the strip north of the map
    img = draw(top, col, depth)
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(PREVIEW, exist_ok=True)
    for i in range(cols):
        for j in range(rows):
            tile = img[j * 128:(j + 1) * 128, i * 128:(i + 1) * 128]
            Image.fromarray(tile).save(os.path.join(OUT, f"hq_{i}_{j}.png"))
    Image.fromarray(img).resize((img.shape[1] * 4, img.shape[0] * 4), Image.NEAREST).save(
        os.path.join(PREVIEW, "map_preview_v1.png"))
    used = {ORDER[i]: int(n) for i, n in enumerate(np.bincount(col.ravel(), minlength=len(ORDER))) if n}
    print("maps", cols, "x", rows, "blocks", w, "x", h, "columns by colour", used)


if __name__ == "__main__":
    a = [int(v) for v in sys.argv[1:]]
    main(*(a[:2] or [1, 1]), *(a[2:3] or []))
