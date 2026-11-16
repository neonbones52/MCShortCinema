"""Photosensitive-epilepsy check of rendered frames (WCAG 2.x, success criterion 2.3.1).

    python tools/flash_check.py renders/shots/25 [--fps 24] [--report out.txt]

Definitions used (WCAG 2.x "general flash and red flash thresholds"):
  general flash   a pair of opposing changes in relative luminance of >= 0.10 where the darker
                  state is below 0.80, over a combined area >= 25 % of any 10-degree visual field
                  (341 x 256 px at 1024 x 768, scaled here by frame width: 640 x 480 at 1920)
  red flash       a pair of opposing transitions involving saturated red: R/(R+G+B) >= 0.8 and the
                  change in max(0, R-G-B) * 320 > 20 (linear R, G, B), same area rule
  limit           no more than 3 flashes of either kind in any one-second period
Method: frames are reduced to 8x8-pixel cells; each cell's luminance series is split into
transitions with a zig-zag (hysteresis 0.10), each transition ends at its extreme; per frame the
area of cells ending a rising / falling transition (within a 2-frame tolerance) is summed in
sliding 10-degree windows; >= 25 % makes an area event; alternating events pair into flashes.
Also reported: the largest frame-to-frame change of mean luminance (global flicker).
"""
import argparse
import glob
import os

import numpy as np
from PIL import Image

CELL = 8


def srgb_to_lin(a):
    return np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)


def load(paths):
    lum, red = [], []
    for p in paths:
        im = np.asarray(Image.open(p).convert('RGB'), dtype=np.float32) / 255.0
        h, w = (im.shape[0] // CELL) * CELL, (im.shape[1] // CELL) * CELL
        lin = srgb_to_lin(im[:h, :w])
        cells = lin.reshape(h // CELL, CELL, w // CELL, CELL, 3).mean(axis=(1, 3))
        R, G, B = cells[..., 0], cells[..., 1], cells[..., 2]
        lum.append(0.2126 * R + 0.7152 * G + 0.0722 * B)
        sat = R / np.maximum(R + G + B, 1e-6) >= 0.8
        red.append(np.where(sat, np.maximum(0.0, R - G - B) * 320.0, 0.0))
    return np.stack(lum), np.stack(red), w


def transitions(series, step, dark_limit=None):
    """Zig-zag over each cell's series. Returns (T, H, W) int8: +1 / -1 where a rising / falling
    transition of amplitude >= step ends (at its extreme), 0 elsewhere."""
    T = series.shape[0]
    flat = series.reshape(T, -1)
    out = np.zeros_like(flat, dtype=np.int8)
    for c in range(flat.shape[1]):
        s = flat[:, c]
        if s.max() - s.min() < step:
            continue
        pivot, ext, ext_t, direction = s[0], s[0], 0, 0
        for t in range(1, T):
            v = s[t]
            if direction >= 0 and v > ext:
                ext, ext_t = v, t
                if direction == 0 and ext - pivot >= step:
                    direction = 1
            elif direction <= 0 and v < ext:
                ext, ext_t = v, t
                if direction == 0 and pivot - ext >= step:
                    direction = -1
            if direction == 1 and ext - v >= step:          # turned down: the rise ended at ext
                if dark_limit is None or min(pivot, ext) < dark_limit:
                    out[ext_t, c] = 1
                pivot, ext, ext_t, direction = ext, v, t, -1
            elif direction == -1 and v - ext >= step:       # turned up: the fall ended at ext
                if dark_limit is None or min(pivot, ext) < dark_limit:
                    out[ext_t, c] = -1
                pivot, ext, ext_t, direction = ext, v, t, 1
        if direction != 0 and abs(ext - pivot) >= step and (dark_limit is None or min(pivot, ext) < dark_limit):
            out[ext_t, c] = direction                       # last, unfinished run
    return out.reshape(series.shape)


def window_events(tr, win_h, win_w, area=0.25, tol=2, stride=4):
    """(T, nwin) int8 events: +1 / -1 when >= area of a window ends a rise / fall within tol frames."""
    T, H, W = tr.shape
    events = []
    ys = list(range(0, max(1, H - win_h + 1), stride)) or [0]
    xs = list(range(0, max(1, W - win_w + 1), stride)) or [0]
    need = area * min(win_h, H) * min(win_w, W)
    for sign in (1, -1):
        m = (tr == sign).astype(np.int32)
        # widen in time by the tolerance (a flash front can take a couple of frames)
        acc = m.copy()
        for k in range(1, tol):
            acc[k:] |= m[:-k]
        sat = acc.cumsum(1).cumsum(2)
        sat = np.pad(sat, ((0, 0), (1, 0), (1, 0)))
        ev = np.zeros((T, len(ys) * len(xs)), dtype=bool)
        i = 0
        for y in ys:
            for x in xs:
                y1, x1 = min(H, y + win_h), min(W, x + win_w)
                s = sat[:, y1, x1] - sat[:, y, x1] - sat[:, y1, x] + sat[:, y, x]
                ev[:, i] = s >= need
                i += 1
        events.append(ev)
    return np.where(events[0], 1, 0) - np.where(events[1] & ~events[0], 1, 0)


def flashes_per_second(ev, fps):
    """Max flashes in any 1-s period over all windows (and the frame where it peaks).
    Same-sign events in a row are one transition; a flash is a pair of opposing transitions,
    so flashes in a period = alternating transitions in it // 2 (a 3 Hz strobe = 3)."""
    T, N = ev.shape
    best, at = 0, 0
    for n in range(N):
        seq = ev[:, n]
        times, last = [], 0
        for t in range(T):
            s = seq[t]
            if s != 0 and s != last:
                times.append(t)
                last = s
        times = np.array(times)
        for t in times:
            c = int(((times > t - fps) & (times <= t)).sum()) // 2
            if c > best:
                best, at = c, int(t)
    return best, at


def check(folder, fps=24, pattern="*.png"):
    paths = sorted(glob.glob(os.path.join(folder, pattern)))
    if not paths:
        raise SystemExit(f"no frames in {folder}")
    lum, red, width = load(paths)
    scale = width / 1024.0
    win_w = max(1, round(341 * scale / CELL))
    win_h = max(1, round(256 * scale / CELL))
    g = transitions(lum, 0.10, dark_limit=0.80)
    r = transitions(red, 20.0)
    g_best, g_at = flashes_per_second(window_events(g, win_h, win_w), fps)
    r_best, r_at = flashes_per_second(window_events(r, win_h, win_w), fps)
    mean = lum.reshape(len(paths), -1).mean(1)
    flick = float(np.abs(np.diff(mean)).max()) if len(mean) > 1 else 0.0
    ok = g_best <= 3 and r_best <= 3
    lines = [
        f"frames: {len(paths)} ({os.path.basename(paths[0])} .. {os.path.basename(paths[-1])}), {fps} fps",
        f"10-degree window: {win_w * CELL} x {win_h * CELL} px, area threshold 25 %",
        f"general flashes: max {g_best} in one second (at {os.path.basename(paths[g_at])})",
        f"red flashes:     max {r_best} in one second (at {os.path.basename(paths[r_at])})",
        f"global flicker:  largest frame-to-frame change of mean luminance {flick:.3f}",
        f"mean luminance:  {mean.min():.3f} .. {mean.max():.3f}",
        "RESULT: " + ("PASS (<= 3 flashes per second)" if ok else "FAIL (more than 3 flashes per second)"),
    ]
    return ok, "\n".join(lines)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--fps", type=float, default=24)
    ap.add_argument("--pattern", default="*.png")
    ap.add_argument("--report")
    a = ap.parse_args()
    ok, text = check(a.folder, a.fps, a.pattern)
    print(text)
    if a.report:
        with open(a.report, "w", encoding="utf-8") as f:
            f.write(text + "\n")
    raise SystemExit(0 if ok else 1)
