"""Compose villager skins from the 26.2 layered textures (base + biome type + profession).

Adds the hand (rows 34-38) under the sleeve so the skin works on separate
zombie-villager-style arms (4x12x4 at uv 44,22).
Run from the project root: python tools/make_skins.py
"""
import os
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENT = os.path.join(ROOT, "assets", "mc", "textures", "entity", "villager")
OUT = os.path.join(ROOT, "assets", "characters")


def compose(vtype="plains", profession=None):
    base = Image.open(os.path.join(ENT, "villager.png")).convert("RGBA")
    img = base.copy()
    img.alpha_composite(Image.open(os.path.join(ENT, "type", vtype + ".png")).convert("RGBA"))
    if profession:
        img.alpha_composite(Image.open(os.path.join(ENT, "profession", profession + ".png")).convert("RGBA"))
    # hand: copy the bare arm skin (rows 30-34 of the base arm) into rows 34-38 under the sleeve
    hand = base.crop((44, 30, 60, 34))
    img.paste(hand, (44, 34))
    # bottom face of the arm (52..56, 22..26) is the palm: skin, not sleeve
    img.paste(base.crop((48, 30, 52, 34)), (52, 22))
    return img


def compose_baby(vtype="plains"):
    """26.x baby villagers have their own model and textures: villager_baby.png + baby/<type>.png
    (no profession layer)."""
    img = Image.open(os.path.join(ENT, "villager_baby.png")).convert("RGBA")
    img.alpha_composite(Image.open(os.path.join(ENT, "baby", vtype + ".png")).convert("RGBA"))
    return img


if __name__ == "__main__":
    compose_baby("plains").save(os.path.join(OUT, "baby_plains.png"))
    print("saved", os.path.join(OUT, "baby_plains.png"))
    os.makedirs(OUT, exist_ok=True)
    for name, vt, prof in [("plains_farmer", "plains", "farmer"), ("plains_plain", "plains", None),
                           ("plains_armorer", "plains", "armorer"), ("plains_weaponsmith", "plains", "weaponsmith")]:
        p = os.path.join(OUT, name + ".png")
        compose(vt, prof).save(p)
        print("saved", p)
