"""Cut the animatic under the track: renders/animatic/frames/f####.png (track frames 0..3753)
-> fades, darkness between the memory flashes, a slate for anything not rendered yet, the shot
number and track time burnt into the corner -> renders/animatic/animatic_v<N>.mp4 with
MemoryReboot_edit_2m36.wav.

    python shots/assemble.py [version] [--clean]      (--clean: without the burnt-in labels)
"""
import os
import shutil
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = r"C:\Dev\Projects\CinemaShort"
OUT = os.path.join(ROOT, "renders", "animatic")
FR = os.path.join(OUT, "frames")
TMP = os.path.join(OUT, "cut")
TRACK = os.path.join(ROOT, "MemoryReboot_edit_2m36.wav")
N = 3754
W, H = 960, 402
sys.path.insert(0, os.path.join(ROOT, "shots"))
SHOTS = {
    1: (0, 160), 2: (160, 319), 3: (319, 480), 4: (480, 639), 5: (639, 719), 6: (719, 799),
    7: (799, 878), 8: (878, 958), 9: (958, 1118), 10: (1118, 1278), 11: (1278, 1398),
    12: (1398, 1517), 13: (1517, 1597), 14: (1597, 1757), 15: (1757, 1877), 16: (1877, 1956),
    17: (1956, 2036), 18: (2036, 2116), 19: (2116, 2176), 20: (2176, 2236), 21: (2236, 2476),
    22: (2476, 2674), 23: (2674, 2794), 24: (2794, 2874), 25: (2874, 3034), 26: (3034, 3193),
    27: (3193, 3754),
}
MEMORIES = ((2484, 2518), (2528, 2566), (2578, 2664))      # shot 22: wheat, poppy, family; dark between


def ramp(f, a, b):
    return min(1.0, max(0.0, (f - a) / float(b - a)))


def gain(f):
    """Brightness multiplier per track frame (1 = as rendered, 0 = black)."""
    k = 1.0
    k *= ramp(f, 0, 36)                                        # 01: out of the black
    if SHOTS[22][0] <= f < SHOTS[22][1]:                       # 22: flashes 1-2 s, dark between
        k = 0.0
        for a, b in MEMORIES:
            if a <= f < b:
                k = min(ramp(f, a, a + 6), 1.0 - ramp(f, b - 8, b))
    if SHOTS[23][0] <= f < SHOTS[23][1]:                       # 23: everything goes dark
        k *= 1.0 - ramp(f, 2760, 2794)
    if f >= 3700:                                               # 27: fade to black
        k *= 1.0 - ramp(f, 3700, 3750)
    return k


def shot_of(f):
    return next(n for n, (a, b) in SHOTS.items() if a <= f < b)


def tc(f):
    s = f / 24.0
    return f"{int(s // 60)}:{s % 60:04.1f}"


def main(version=1, labels=True):
    os.makedirs(TMP, exist_ok=True)
    try:
        font = ImageFont.truetype("arial.ttf", 16)
        big = ImageFont.truetype("arial.ttf", 34)
    except OSError:
        font = big = ImageFont.load_default()
    missing = []
    black = Image.new("RGB", (W, H), (0, 0, 0))
    for f in range(N):
        src = os.path.join(FR, f"f{f:04d}.png")
        k = gain(f)
        n = shot_of(f)
        if k <= 0.0:
            im = black.copy()
        elif os.path.exists(src):
            im = Image.open(src).convert("RGB")
            if im.size != (W, H):
                im = im.resize((W, H))
            if k < 1.0:
                im = Image.eval(im, lambda v, k=k: int(v * k))
        else:
            missing.append(f)
            im = Image.new("RGB", (W, H), (40, 40, 40))
            d = ImageDraw.Draw(im)
            d.text((W // 2 - 120, H // 2 - 20), f"кадр {n:02d}: нет рендера", fill=(200, 200, 200), font=big)
        if labels:
            d = ImageDraw.Draw(im)
            t = f"{n:02d}   {tc(f)}"
            d.text((11, H - 25), t, fill=(0, 0, 0), font=font)
            d.text((10, H - 26), t, fill=(235, 235, 235), font=font)
        im.save(os.path.join(TMP, f"c{f:04d}.jpg"), quality=92)
    name = f"animatic_v{version}{'' if labels else '_clean'}.mp4"
    out = os.path.join(OUT, name)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-framerate", "24", "-i", os.path.join(TMP, "c%04d.jpg"),
           "-i", TRACK, "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
           "-c:a", "aac", "-b:a", "256k", "-shortest", out]
    subprocess.run(cmd, check=True)
    shutil.rmtree(TMP)
    print(out, "missing frames:", len(missing), (missing[0], missing[-1]) if missing else "")


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    main(int(a[0]) if a else 1, "--clean" not in sys.argv)
