"""Read entity model geometry out of `javap -c -p -constants` output.

Minecraft 26.x ships unobfuscated, so a model class's createBodyLayer() is a readable
sequence of CubeListBuilder / PartPose calls. This prints them as calls with their literal
arguments, e.g.  addOrReplaceChild('head', ...)  texOffs(0, 0)  addBox(-4, -10, -4, 8, 10, 8)
Usage: python tools/javap_model.py <javap_output.txt> [method_name ...]
"""
import re
import sys

LIT = [
    (re.compile(r"\b(fconst|iconst)_(m?\d)\b"), lambda m: float(m.group(2).replace("m", "-"))),
    (re.compile(r"\b(bipush|sipush)\s+(-?\d+)"), lambda m: float(m.group(2))),
    (re.compile(r"\bldc(?:_w)?\s+#\d+\s+//\s+float\s+(-?[\d.Ee+-]+)f"), lambda m: float(m.group(1))),
    (re.compile(r"\bldc(?:_w)?\s+#\d+\s+//\s+int\s+(-?\d+)"), lambda m: float(m.group(1))),
    (re.compile(r"\bldc(?:_w)?\s+#\d+\s+//\s+String\s+(.*)$"), lambda m: m.group(1).strip()),
    (re.compile(r"\bgetstatic\s+#\d+\s+//\s+Field\s+(\S+)"), lambda m: "@" + m.group(1).split("/")[-1]),
]
CALL = re.compile(r"invoke(static|virtual|special)\s+#\d+\s+//\s+Method\s+(\S+?):\(([^)]*)\)")


def n_args(desc):
    return len(re.findall(r"\[*(?:L[^;]+;|[ZBCSIFJD])", desc))


def run(path, methods=None):
    cur, stack = None, []
    for line in open(path, encoding="utf-8", errors="ignore"):
        mm = re.match(r"\s*(?:public|private|protected|static|\s)*.*\s(\w+)\((.*)\);\s*$", line)
        if mm and not line.strip()[0].isdigit():
            cur = mm.group(1)
            stack = []
            if not methods or cur in methods:
                print(f"\n== {cur}")
            continue
        if methods and cur not in methods:
            continue
        for rx, fn in LIT:
            m = rx.search(line)
            if m:
                stack.append(fn(m))
                break
        c = CALL.search(line)
        if c:
            name = c.group(2).split(".")[-1]
            k = n_args(c.group(3))
            args = stack[-k:] if k else []
            del stack[len(stack) - len(args):]
            if name in ("create", "<init>") and not args:
                continue
            fmt = ", ".join(f"{a:g}" if isinstance(a, float) else str(a) for a in args)
            print(f"  {name}({fmt})")


if __name__ == "__main__":
    run(sys.argv[1], set(sys.argv[2:]) or None)
