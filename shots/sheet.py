"""Contact sheet of the animatic stills: one row per shot, its stills left to right, with the shot
number and the track time.  python shots/sheet.py <first shot> <last shot> [out name]
-> renders/animatic/sheet_<first>-<last>.png
"""
import glob
import os
import re
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = r"C:\Dev\Projects\CinemaShort"
ST = os.path.join(ROOT, "renders", "animatic", "stills")
W = 480                                                  # thumbnail width


def tc(f):
    s = f / 24.0
    return f"{int(s // 60)}:{s % 60:04.1f}"


def main(a, b, name=None):
    rows = {}
    for p in sorted(glob.glob(os.path.join(ST, "s*_f*.png"))):
        m = re.match(r"s(\d+)_f(\d+)\.png", os.path.basename(p))
        n, f = int(m.group(1)), int(m.group(2))
        if a <= n <= b:
            rows.setdefault(n, []).append((f, p))
    cols = max(len(v) for v in rows.values())
    h = round(W * 804 / 1920)
    pad, lab = 6, 40
    sheet = Image.new("RGB", (lab + cols * (W + pad) + pad, len(rows) * (h + pad + 18) + pad), (24, 24, 24))
    d = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("arial.ttf", 18)
        small = ImageFont.truetype("arial.ttf", 13)
    except OSError:
        font = small = ImageFont.load_default()
    for r, n in enumerate(sorted(rows)):
        y = pad + r * (h + pad + 18)
        d.text((6, y + h // 2 - 10), f"{n:02d}", fill=(240, 240, 240), font=font)
        for c, (f, p) in enumerate(sorted(rows[n])):
            x = lab + pad + c * (W + pad)
            sheet.paste(Image.open(p).convert("RGB").resize((W, h)), (x, y))
            d.text((x + 2, y + h + 2), f"{tc(f)}  (f{f})", fill=(170, 170, 170), font=small)
    out = os.path.join(ROOT, "renders", "animatic", name or f"sheet_{a:02d}-{b:02d}.png")
    sheet.save(out)
    print(out)


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]), sys.argv[3] if len(sys.argv) > 3 else None)
