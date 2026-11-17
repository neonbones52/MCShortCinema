"""Vanilla structure templates straight from the game jar, for mcvox sets: the plains village
houses, meeting points, lamps... (data/minecraft/structure/**.nbt). Run with the MCBuilder venv.

How the game puts a house down (JigsawPlacement, read from the 26.2 data):
  * every house has one jigsaw "building_entrance" on its west face (x = 0), looking west;
  * a street piece has its jigsaws one block above the path, so the entrance jigsaw ends up at
    street surface + 1: the house origin is  y = surface + 1 - jigsaw.y  (jigsaw.y = 0: the
    floor layer sits on top of the ground; 1: layer 0 replaces the surface layer; 2: a cellar);
  * the jigsaw block itself turns into its "final_state" (a door step, a fence gate, nothing);
  * air in the template carves, structure_void leaves the world alone.

    import mc_vanilla as V
    p = V.piece("village/plains/houses/plains_small_house_1")
    V.place_by_entrance(p, (x, z), surface_y, extend="north")
"""
import gzip
import io
import json
import os
import zipfile

import nbtlib

import mcvox as R
from mcvox import blk, put

JAR = json.load(open(os.path.join(R.HERE, "tex", "_version.json")))["jar"]
BASE = "data/minecraft/structure/"
FACING = ["north", "east", "south", "west"]            # clockwise seen from above (X east, Z south)
TURNS = {"east": 0, "south": 1, "west": 2, "north": 3}  # the house extends this way from its entrance
_zf = None
_cache = {}


def parse_state(s):
    """'minecraft:oak_stairs[facing=east,half=bottom]' -> ('oak_stairs', {...})"""
    s = str(s)
    name, _, rest = s.partition("[")
    props = dict(kv.split("=") for kv in rest.rstrip("]").split(",")) if rest else {}
    return name.split(":")[-1], props


class Piece:
    def __init__(self, path):
        global _zf
        if _zf is None:
            _zf = zipfile.ZipFile(JAR)
        f = nbtlib.File.parse(io.BytesIO(gzip.decompress(_zf.read(BASE + path + ".nbt"))))
        self.path = path
        self.size = tuple(int(v) for v in f["size"])
        pal = [(str(p["Name"]).split(":")[1], {str(k): str(v) for k, v in p.get("Properties", {}).items()})
               for p in f["palette"]]
        self.blocks, self.jigsaws = [], []
        for b in f["blocks"]:
            name, props = pal[int(b["state"])]
            pos = tuple(int(v) for v in b["pos"])
            if name == "jigsaw":
                t = b["nbt"]
                self.jigsaws.append(dict(pos=pos, name=str(t.get("name")).split(":")[-1],
                                         pool=str(t.get("pool")).split(":")[-1],
                                         final=parse_state(t.get("final_state"))))
                name, props = self.jigsaws[-1]["final"]
            self.blocks.append((pos, name, props))
        self.entrance = next((j for j in self.jigsaws if j["name"] == "building_entrance"), None)


def piece(path):
    if path not in _cache:
        _cache[path] = Piece(path)
    return _cache[path]


def rot_xz(x, z, k):
    """Rotate k quarter turns clockwise (Rotation.CLOCKWISE_90: (x, z) -> (-z, x))."""
    for _ in range(k % 4):
        x, z = -z, x
    return x, z


def rot_props(props, k):
    k %= 4
    if not k or not props:
        return props
    out = dict(props)
    if props.get("facing") in FACING:
        out["facing"] = FACING[(FACING.index(props["facing"]) + k) % 4]
    if k % 2 and props.get("axis") in ("x", "z"):
        out["axis"] = "z" if props["axis"] == "x" else "x"
    if "rotation" in props:
        out["rotation"] = str((int(props["rotation"]) + 4 * k) % 16)
    sides = [d for d in FACING if d in props]
    for d in sides:
        out[FACING[(FACING.index(d) + k) % 4]] = props[d]
    return out


def footprint(p, origin, k):
    """World (x0, x1, z0, z1) of the piece's bounding box."""
    sx, _, sz = p.size
    xs, zs = zip(*(rot_xz(x, z, k) for x in (0, sx - 1) for z in (0, sz - 1)))
    return origin[0] + min(xs), origin[0] + max(xs), origin[2] + min(zs), origin[2] + max(zs)


def entrance_origin(p, cell, surface_y, extend):
    """Origin and turns for a house whose entrance jigsaw stands on world cell (x, z), the
    street surface there being surface_y, the house extending `extend` from it."""
    k = TURNS[extend]
    ex, ey, ez = p.entrance["pos"]
    rx, rz = rot_xz(ex, ez, k)
    return (cell[0] - rx, surface_y + 1 - ey, cell[1] - rz), k


def place(p, origin, k=0, carve_from=0):
    """Put the piece into the mcvox world. Air below local y = carve_from does not carve (so a
    piece whose lower layers lie in the ground does not dig pits where it has no blocks).
    Returns the 'bottom' jigsaws as [(pool, (x, y, z))]: decor, trees, animals, villagers."""
    ox, oy, oz = origin
    for (x, y, z), name, props in p.blocks:
        if name == "structure_void":
            continue
        rx, rz = rot_xz(x, z, k)
        if name in ("air", "cave_air"):
            if y >= carve_from:
                put(ox + rx, oy + y, oz + rz, 0)
            continue
        put(ox + rx, oy + y, oz + rz, blk(name, **rot_props(props, k)))
    out = []
    for j in p.jigsaws:
        if j["name"] == "bottom":
            x, y, z = j["pos"]
            rx, rz = rot_xz(x, z, k)
            out.append((j["pool"], (ox + rx, oy + y, oz + rz)))
    return out


def place_by_entrance(p, cell, surface_y, extend):
    origin, k = entrance_origin(p, cell, surface_y, extend)
    return place(p, origin, k, carve_from=p.entrance["pos"][1])
