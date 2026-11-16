"""Pipeline test set: a corner of a plains farm with the block types that usually break
in a Minecraft -> Blender export: crops, farmland, water, fences + gate, door, glass pane,
stairs/slabs, leaves, flowers, short grass, lantern, torch, campfire, hay, composter, path.
Axes: X = east, Y = up, Z = south.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import schem  # noqa: E402  (puts MCBuilder on sys.path)
import mcvox as R  # noqa: E402
from mcvox import blk, ctx, burp, h3, put, stairs, slab  # noqa: E402

W, H, D = 26, 14, 24
R.new_world(W, H, D)
G = 1                                                   # ground level (dirt below)

for x in range(W):
    for z in range(D):
        put(x, 0, z, ctx("dirt"))
        put(x, G, z, ctx(burp(x, 0, z, "grass_block", [("coarse_dirt", .04)], 13)))  # snowy set in schem.py

# ---- field: 9x9 farmland, water channel in the middle row, ripe wheat
FX0, FZ0 = 3, 7
for x in range(FX0, FX0 + 9):
    for z in range(FZ0, FZ0 + 9):
        if z == FZ0 + 4:
            put(x, G, z, blk("water", level="0"))
        else:
            put(x, G, z, blk("farmland", moisture="7"))
            age = "7" if h3(x, 0, z, 3) > .15 else str(int(h3(x, 1, z, 4) * 6))
            put(x, G + 1, z, blk("wheat", age=age))
# fence around the field with a gate on the north side
for x in range(FX0 - 1, FX0 + 10):
    for z in (FZ0 - 1, FZ0 + 9):
        put(x, G + 1, z, "oak_fence")
for z in range(FZ0 - 1, FZ0 + 10):
    for x in (FX0 - 1, FX0 + 9):
        put(x, G + 1, z, "oak_fence")
put(FX0 + 4, G + 1, FZ0 - 1, blk("oak_fence_gate", facing="north", in_wall="false", open="false", powered="false"))
put(FX0 - 1, G + 2, FZ0 - 1, blk("lantern", hanging="false", waterlogged="false"))
put(FX0 + 9, G + 2, FZ0 + 9, blk("lantern", hanging="false", waterlogged="false"))

# ---- path from the gate to the hut
for z in range(1, FZ0 - 1):
    for x in (FX0 + 4, FX0 + 5):
        put(x, G, z, burp(x, 0, z, "dirt_path", [("gravel", .15)], 51, 1.4))

# ---- small hut (east side)
X0, X1, Z0, Z1 = 16, 22, 6, 11
for x in range(X0, X1 + 1):
    for z in range(Z0, Z1 + 1):
        edge = x in (X0, X1) or z in (Z0, Z1)
        put(x, G + 1, z, burp(x, 1, z, "cobblestone", [("mossy_cobblestone", .25)], 7) if edge else "oak_planks")
        if not edge:
            continue
        corner = x in (X0, X1) and z in (Z0, Z1)
        for y in range(G + 2, G + 5):
            put(x, y, z, blk("oak_log", axis="y") if corner else "oak_planks")
put(X0, G + 2, 9, blk("oak_door", facing="west", half="lower", hinge="left", open="false", powered="false"))
put(X0, G + 3, 9, blk("oak_door", facing="west", half="upper", hinge="left", open="false", powered="false"))
put(X0, G + 3, 7, "glass_pane"); put(X1, G + 3, 8, "glass_pane"); put(19, G + 3, Z1, "glass_pane")
put(X0, G + 4, 8, blk("wall_torch", facing="west"))
half = (Z1 + 1 - (Z0 - 1)) // 2
for x in range(X0 - 1, X1 + 2):
    for k in range(half):
        put(x, G + 5 + k, Z0 - 1 + k, stairs("spruce_planks", "south"))
        put(x, G + 5 + k, Z1 + 1 - k, stairs("spruce_planks", "north"))
    if (Z1 - Z0) % 2 == 0:
        put(x, G + 5 + half, Z0 - 1 + half, slab("spruce_planks"))
for x in (X0, X1):
    for z in range(Z0, Z1 + 1):
        k = min(z - (Z0 - 1), Z1 + 1 - z)
        for y in range(G + 5, G + 5 + k - 1):
            put(x, y, z, "oak_planks")

# ---- yard props
put(15, G + 1, 14, blk("hay_block", axis="y")); put(16, G + 1, 14, blk("hay_block", axis="x"))
put(15, G + 2, 14, blk("hay_block", axis="z"))
put(17, G + 1, 14, blk("composter", level="3"))
put(20, G + 1, 16, blk("campfire", lit="true", signal_fire="false", facing="north", waterlogged="false"))
for (x, z, ax) in ((18, 16, "z"), (22, 16, "z"), (20, 18, "x")):
    put(x, G + 1, z, blk("oak_log", axis=ax))

# ---- oak tree (north-west) and flowers / grass tufts
tx, tz = 2, 2
for y in range(G + 1, G + 6):
    put(tx, y, tz, ctx("oak_log", axis="y"))
for y in range(G + 4, G + 8):
    r = 2 if y < G + 6 else 1
    for dx in range(-r, r + 1):
        for dz in range(-r, r + 1):
            if (dx or dz or y > G + 5) and 0 <= tx + dx < W and 0 <= tz + dz < D and abs(dx) + abs(dz) <= r + 1:
                if R.get(tx + dx, y, tz + dz) == 0:
                    put(tx + dx, y, tz + dz, ctx("oak_leaves"))
for i in range(160):
    x, z = int(h3(i, 1, 0, 61) * W), int(h3(i, 2, 0, 62) * D)
    if R.name_at(x, G, z) == "grass_block" and R.get(x, G + 1, z) == 0:
        put(x, G + 1, z, ctx("poppy" if h3(i, 3, 0, 63) > .85 else "short_grass"))
put(FX0 + 3, G + 1, FZ0 - 2, "poppy")                   # the poppy by the gate

if __name__ == "__main__":
    out = os.path.join(os.path.dirname(HERE), "assets", "sets", "test_farm.schem")
    schem.export_schem(out)
