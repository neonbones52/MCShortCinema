"""Render the whole animatic (every location script in background Blender, one after another) and
cut it under the track.   python shots/render_all.py [version] [shot ...]   (shots: only those)
Log: renders/animatic/render_log.txt
"""
import os
import subprocess
import sys
import time

ROOT = r"C:\Dev\Projects\CinemaShort"
BLENDER = r"D:\Apps\Blender\blender.exe"
JOBS = (("village", "anim_village"), ("drill", "anim_drill"), ("hq", "anim_hq"), ("front", "anim_front"),
        ("front", "anim_finale"))
LOG = os.path.join(ROOT, "renders", "animatic", "render_log.txt")


def log(msg):
    line = time.strftime("%H:%M:%S ") + msg
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


OWN = {"anim_village": (1, 2, 3, 4, 5, 6, 7, 8, 22), "anim_drill": (9, 10, 11, 12, 13), "anim_hq": (14, 15),
       "anim_front": (16, 17, 18, 19, 20), "anim_finale": (21, 23, 24, 25, 26, 27)}


def main(version=1, shots=()):
    t0 = time.time()
    for blend, script in JOBS:
        mine = [n for n in OWN[script] if not shots or n in shots]
        if not mine:
            continue
        t = time.time()
        p = subprocess.run([BLENDER, "-b", os.path.join(ROOT, "blender", "sets", blend + ".blend"), "--python",
                            os.path.join(ROOT, "shots", script + ".py"), "--", "render"] + [str(n) for n in mine],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        done = [l for l in p.stdout.splitlines() if l.startswith("SHOT")]
        errs = [l for l in (p.stdout + p.stderr).splitlines() if "Error" in l or "Traceback" in l]
        log(f"{script}: {time.time() - t:.0f} s, exit {p.returncode}; " + "; ".join(done) + (" ERR " + " | ".join(errs[:5]) if errs else ""))
    subprocess.run([sys.executable, os.path.join(ROOT, "shots", "assemble.py"), str(version)], check=True)
    log(f"done in {(time.time() - t0) / 60:.1f} min")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 1, [int(x) for x in sys.argv[2:]])
