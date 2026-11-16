"""Write the current mcvox world to a Sponge Schematic v3 (.schem), which Mineways opens directly.

Run with the MCBuilder venv (it has nbtlib):
    C:\\Games\\MCBuilder\\venv\\Scripts\\python sets\\<set>.py
Each set script builds its world with mcvox and calls export_schem().
"""
import gzip
import os
import sys

MCB = r"C:\Games\MCBuilder"
if MCB not in sys.path:
    sys.path.insert(0, MCB)

import numpy as np
import nbtlib
from nbtlib.tag import ByteArray, Compound, Int, IntArray, List, Short

import mcvox as R


def _state(var):
    name, props = var["name"], dict(var["props"])
    if name.endswith("_leaves"):                       # otherwise they decay / render as decaying
        props.update(persistent="true", distance="1", waterlogged=props.get("waterlogged", "false"))
    if name in ("grass_block", "podzol", "mycelium"):
        props.setdefault("snowy", "false")
    if name == "water" and not props:
        props = {"level": "0"}
    s = "minecraft:" + name
    if props:
        s += "[" + ",".join(f"{k}={v}" for k, v in sorted(props.items())) + "]"
    return s


def _varints(values):
    out = bytearray()
    for v in values:
        v = int(v)
        while True:
            b = v & 0x7F
            v >>= 7
            if v:
                out.append(b | 0x80)
            else:
                out.append(b)
                break
    return out


def export_schem(path, include_context=True):
    """Write R.grid (x, y, z) to `path`. include_context=False drops ctx blocks (terrain etc.)."""
    R.connect()
    grid = R.grid.copy()
    if not include_context:
        isctx = np.array([v["ctx"] for v in R.VARIANTS])
        grid[isctx[grid]] = 0
    W, H, D = grid.shape
    states = [_state(v) for v in R.VARIANTS]
    palette, remap = {}, np.zeros(len(states), np.int64)
    for i, s in enumerate(states):
        remap[i] = palette.setdefault(s, len(palette))
    # Sponge order: index = x + z * Width + y * Width * Length
    flat = remap[grid.transpose(1, 2, 0).reshape(-1)]
    data = _varints(flat)
    schem = Compound({
        "Version": Int(3),
        "DataVersion": Int(R.DATA_VERSION),
        "Width": Short(W), "Height": Short(H), "Length": Short(D),
        "Offset": IntArray([0, 0, 0]),
        "Blocks": Compound({
            "Palette": Compound({k: Int(v) for k, v in palette.items()}),
            "Data": ByteArray(np.frombuffer(bytes(data), dtype=np.int8)),
            "BlockEntities": List[Compound]([]),
        }),
    })
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    nbtlib.File({"Schematic": schem}, gzipped=True).save(path)
    print(f"schem: {W}x{H}x{D}, {len(palette)} block states, {int((grid != 0).sum())} blocks -> {path}")
