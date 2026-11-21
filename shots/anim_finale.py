"""Animatic, the finale on the front (black sky, endless barrage): shots 21, 23-27.

    blender -b blender/sets/front.blend --python shots/anim_finale.py -- stills|render|save [shot ...]

Built on the approved finale stand (tests/test_front_finale.py: the field of the fallen in
Alex's rear, the hero kneeling, the barrage ahead going up), with the barrage over the whole
end of the film (frames 2236-3754). Animatic shortcut: the burst lamps are folded into the one
shadowed key light (mc_salvo.key_light with share 1.0), no coloured glints, so a frame renders
in about a second.

21  slow motion: the hero tumbles through the air, close, silent bursts behind
23  wide: he falls out of the sky onto the plain, the impact (the picture darkens: assemble.py)
24  his eyes: black, then the eyes open, blurred, onto the field and the barrage
25  from behind his head: on his knees, looking back where he flew from, the barrage ahead
26  slow pan across the fallen, ending on him
27  one shot (27+28): the dolly back from the nape, the field opens up; at the end he keels over
"""
import math
import os
import sys

import bpy
from mathutils import Euler, Matrix, Quaternion, Vector

sys.path.insert(0, r"C:\Dev\Projects\CinemaShort\shots")
import importlib
import anim as A
importlib.reload(A)
import mc_character as C
import mc_fallen as FL
import mc_look as L
import mc_set as SET

ROOT = A.ROOT


def stand():
    """The finale stand's functions (sky, hero, fallen, barrage) without running it."""
    path = os.path.join(ROOT, "tests", "test_front_finale.py")
    src = open(path, encoding="utf-8").read().split("\nargs = sys.argv")[0]
    ns = {"__name__": "finale_stand", "__file__": path}
    exec(compile(src, path, "exec"), ns)
    ns["FRAMES"] = (2236, A.TRACK_FRAMES)
    ns["KEY_SHARE"] = 1.0
    ns["AMBIENT"] = A.FINALE_AMBIENT
    return ns


def g(x, z):
    return SET.ground(x, z, "front")


# ------------------------------------------------------------------ the hero's fall (21, 23)
CENTER = Vector((0.0, 0.0, 1.05))          # mid-body in rig space: he turns about this, not his heels


def falling_hero(ns):
    """Shots 21 and 23. Returns the rig and the path of his mid-body per frame (for the camera)."""
    HX, HY, HZ = ns["HX"], ns["HY"], ns["HZ"]
    with A.quiet():
        rig = C.villager("HeroFall", skin="plains_farmer", helmet="iron", legs="iron", boots="iron", elytra=True)
    gy = g(HX + 0.5, HZ + 0.5)
    rig.rotation_mode = 'QUATERNION'
    prev = None
    centers = {}

    def key(f, center, q):
        nonlocal prev
        if prev is not None and q.dot(prev) < 0:
            q.negate()
        prev = q.copy()
        rig.rotation_quaternion = q
        rig.location = center - q @ CENTER
        rig.keyframe_insert("location", frame=f)
        rig.keyframe_insert("rotation_quaternion", frame=f)
        centers[f] = center.copy()

    def limbs(f, speed):
        """Limp limbs swaying in the air stream (slowly in the slow motion)."""
        w = f * speed
        C.set_bone_mc_rot(rig, "arm.R", -0.9 + 0.7 * math.sin(w), 0, 0.9 + 0.3 * math.sin(w * 0.7), frame=f)
        C.set_bone_mc_rot(rig, "arm.L", -0.5 + 0.6 * math.sin(w + 1.7), 0, -1.0 - 0.3 * math.sin(w * 0.8), frame=f)
        C.set_bone_mc_rot(rig, "leg.R", 0.3 * math.sin(w + 0.6), 0, 0.15, frame=f)
        C.set_bone_mc_rot(rig, "leg.L", -0.35 * math.sin(w + 0.9), 0, -0.2, frame=f)
        C.set_bone_mc_rot(rig, "head", 0.5 * math.sin(w * 0.6), 0.3 * math.sin(w * 0.4), 0, frame=f)
        C.set_wing_pose(rig, 0.3 + 0.15 * math.sin(w * 0.9), 0.05, -1.1 + 0.4 * math.sin(w * 0.5), frame=f)

    def tumble(t, rate):
        """Head over heels about his own middle, with a slow roll on top."""
        return (Quaternion((0, 0, 1), -math.pi / 2) @ Quaternion((1, 0, 0), rate * t)
                @ Quaternion((0, 1, 0), 0.35 * math.sin(t * 0.9)))

    # 21: slow motion, high over Alex's rear, drifting down and turning over (a turn in ~10 s)
    p0, p1 = Vector((HX - 34, -(HZ + 0.5), gy + 38)), Vector((HX - 24, -(HZ + 1.5), gy + 31))
    for f in range(2236, 2477):
        key(f, p0.lerp(p1, (f - 2236) / 240.0), tumble((f - 2236) / 24.0, 2 * math.pi / 10.0))
        if f % 2 == 0:
            limbs(f, 0.035)
    # 23: real speed now: down out of the sky onto the plain, lands at frame 2742
    q0 = Vector((HX - 26, -(HZ + 0.5), gy + 28))
    land_f = 2742
    for f in range(2674, land_f + 1):
        u = (f - 2674) / (land_f - 2674)
        c = Vector((q0.x + (HX + 0.5 - q0.x) * u, q0.y, gy + 1.0 + (q0.z - gy - 1.0) * (1 - u * u)))
        key(f, c, tumble((f - 2674) / 24.0 + 1.3, 2 * math.pi / 1.6))
        limbs(f, 0.25)
    # lies face down where he will come to
    FL.apply_pose(rig, FL.POSES["prone_reach"])
    for pb in rig.pose.bones:
        pb.keyframe_insert("rotation_quaternion", frame=land_f + 2)
    FL.lay(rig, FL.POSES["prone_reach"], -math.pi / 2, "front", HX + 0.5, HZ + 0.5)
    for f in (land_f + 2, 2800):
        rig.keyframe_insert("location", frame=f)
        rig.keyframe_insert("rotation_quaternion", frame=f)
    A.key_visible(rig, [(2236, 2476), (2674, 2794)])
    return rig, centers


def _bone_quats(rig, names):
    return {n: rig.pose.bones[n].rotation_quaternion.copy() for n in names if n in rig.pose.bones}


def keel_over(rig, ns):
    """Shot 27's end, alive: he breathes on his knees all through 25-27; at 2:31.2 he slumps
    (head drops, shoulders go forward), at 2:31.9 he topples onto his side with gravity, an arm
    flops after him, and he settles with a small bounce, like the others around him."""
    HX, HZ = ns["HX"], ns["HZ"]
    rig.rotation_mode = 'QUATERNION'
    names = ("head", "body", "arm.R", "arm.L", "leg.R", "leg.L", "wing.L", "wing.R")
    K = dict(FL.KNEEL["bones"])
    loc0, q0 = rig.location.copy(), rig.rotation_quaternion.copy()
    kneel = _bone_quats(rig, names)
    slump_rot = dict(K)
    slump_rot.update({"body": (0.48, 0.0, 0.06), "head": (0.65, 0.05, 0.1), "arm.R": (0.02, 0, 0.04),
                      "arm.L": (0.05, 0, -0.03)})
    for n, r in slump_rot.items():
        C.set_bone_mc_rot(rig, n, *r)
    slump = _bone_quats(rig, names)
    FL.apply_pose(rig, FL.POSES["side_flat"])
    FL.lay(rig, FL.POSES["side_flat"], -math.pi / 2, "front", HX + 0.5, HZ + 0.5)
    loc1, q1 = rig.location.copy(), rig.rotation_quaternion.copy()
    if q1.dot(q0) < 0:
        q1.negate()
    lie = _bone_quats(rig, names)
    for d in (slump, lie):
        for n in d:
            if d[n].dot(kneel[n]) < 0:
                d[n].negate()

    def put(f, loc, q, bones):
        rig.location, rig.rotation_quaternion = loc, q
        rig.keyframe_insert("location", frame=f)
        rig.keyframe_insert("rotation_quaternion", frame=f)
        for n, bq in bones.items():
            rig.pose.bones[n].rotation_quaternion = bq
            rig.pose.bones[n].keyframe_insert("rotation_quaternion", frame=f)

    def mix(a, b, u):
        return {n: a[n].slerp(b[n], u) for n in a}

    s0, s1, t1, settle = 3628, 3646, 3666, 3678
    # breathing: a slow rise and fall of the shoulders (body pitch) and the head
    for f in range(2874, s0, 6):
        w = 2 * math.pi * (f - 2874) / 100.0
        bones = dict(kneel)
        for n, amp, ph in (("body", 0.03, 0.0), ("head", 0.025, 0.6)):
            r = K[n]
            C.set_bone_mc_rot(rig, n, r[0] + amp * math.sin(w + ph), r[1], r[2])
            q = rig.pose.bones[n].rotation_quaternion.copy()
            if q.dot(kneel[n]) < 0:
                q.negate()
            bones[n] = q
        put(f, loc0, q0, bones)
    put(s0, loc0, q0, kneel)
    for f in range(s0 + 1, s1 + 1):                     # the slump: ease in and out
        put(f, loc0, q0, mix(kneel, slump, A.smooth((f - s0) / (s1 - s0))))
    for f in range(s1 + 1, settle + 1):                 # the topple with gravity, then a small bounce
        if f <= t1:
            u = (f - s1) / (t1 - s1)
            k = u * u
            lag = max(0.0, (f - s1 - 3) / (t1 - s1 - 3)) ** 2
            lift = 0.0
        else:
            v = (f - t1) / (settle - t1)
            k = 1.0 - 0.06 * math.sin(math.pi * v)      # the body rocks back a little
            lag = 1.0 + 0.18 * math.sin(math.pi * min(1.0, v * 1.4)) * (1 - v)   # the arm flops past and back
            lift = 0.03 * math.sin(math.pi * v)
        q = q0.slerp(q1, k)
        loc = loc0.lerp(loc1, k) + Vector((0, 0, lift))
        bones = mix(slump, lie, k)
        if lag <= 1.0:
            bones["arm.R"] = slump["arm.R"].slerp(lie["arm.R"], lag)
        else:
            bones["arm.R"] = lie["arm.R"].slerp(slump["arm.R"], lag - 1.0)
        bones["head"] = slump["head"].slerp(lie["head"], min(1.0, lag))
        put(f, loc, q, bones)
    put(A.TRACK_FRAMES, loc1, q1, lie)
    A.key_visible(rig, [(2874, A.TRACK_FRAMES)])


# ------------------------------------------------------------------ cameras
def cameras(ns, head, fall_rig):
    HX, HY, HZ = ns["HX"], ns["HY"], ns["HZ"]
    sc = bpy.context.scene
    # 21: close beside him as he turns over in the air, the bursts behind
    pts = fall_rig[1]                                     # his mid-body, not the rig origin at the feet
    A.camera_path("Shot21", range(2236, 2476), lambda f: (pts[f] + Vector((3.8, 1.3, 0.6)), pts[f]), lens=35)
    # 23: wide on the plain, he comes down out of the sky
    gy = g(HX + 0.5, HZ + 0.5)
    A.camera("Shot23", [(2674, Vector((HX + 16, -(HZ + 22), gy + 3.0)), Vector((HX - 10, -(HZ + 0.5), gy + 12))),
                        (2793, Vector((HX + 15, -(HZ + 21), gy + 2.8)), Vector((HX - 1, -(HZ + 0.5), gy + 1.0)))], lens=28)
    # 24: his eyes, lying in the mud: the lids part, the field and the barrage swim into focus
    eye = Vector((HX + 0.2, -(HZ + 0.5), gy + 0.32))
    look = eye + Vector((-10.0, 0.4, 1.3))
    c = A.camera("Shot24", [(2794, eye, look), (2873, eye + Vector((0, 0, 0.05)), look + Vector((0, 0, 0.6)))], lens=24)
    A.focus(c, [(2794, 0.25), (2836, 0.6), (2866, 14.0)], fstop=1.4)
    lids(c)
    # 25: from behind his head, a little to the right, the barrage ahead; a slow push in
    west = Vector((-1, 0, 0))
    A.camera("Shot25", [(2874, head - west * 3.0 + Vector((0, -0.7, 0.35)), head + west * 30 + Vector((0, 0, 1.2))),
                        (3033, head - west * 2.4 + Vector((0, -0.6, 0.3)), head + west * 30 + Vector((0, 0, 1.2)))],
             lens=35)
    # 26: slow pan across the fallen from the north, ending on him
    cp = Vector((HX + 13, -(HZ - 13), g(HX + 13, HZ - 13) + 1.5))
    A.camera("Shot26", [(3034, cp, Vector((HX + 30, -(HZ - 2), gy - 1.0))),
                        (3192, cp + Vector((-1.5, 0, 0)), Vector((HX + 0.5, -(HZ + 0.5), gy + 0.6)))], lens=32)
    # 27: the approved dolly, stretched over the merged shot (23.4 s): straight back along the
    # view axis, the nape dead centre, pitch -3 deg
    p = ns["PITCH"]
    look_v = Vector((-math.cos(p), 0.0, math.sin(p)))
    d0, d1 = ns["DOLLY"][0], 36.0

    def dolly(f):
        t = A.smooth((f - 3193) / (3753 - 3193))
        d = d0 + (d1 - d0) * t
        pos = head - look_v * d
        return pos, pos + look_v
    A.camera_path("Shot27", range(3193, 3754), dolly, lens=ns["LENS"])


def lids(cam):
    """Two black planes in front of the lens: closed, a flutter, then open (shot 24)."""
    mat = bpy.data.materials.get("Lid.Black") or bpy.data.materials.new("Lid.Black")
    mat.diffuse_color = (0, 0, 0, 1)
    mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (0, 0, 0, 1)
    bsdf.inputs["Roughness"].default_value = 1.0
    keys = ((2794, 0.0), (2812, 0.0), (2820, 0.35), (2828, 0.08), (2840, 0.6), (2846, 0.45), (2862, 1.0))
    for side in (1, -1):
        me = bpy.data.meshes.new(f"Lid{side}")
        me.from_pydata([(-1, 0, 0), (1, 0, 0), (1, side * 0.8, 0), (-1, side * 0.8, 0)], [], [(0, 1, 2, 3)])
        ob = bpy.data.objects.new(f"Shot24.Lid{'Up' if side > 0 else 'Down'}", me)
        ob.data.materials.append(mat)
        A.collection("Shots").objects.link(ob)
        ob.parent = cam
        for f, open_ in keys:
            ob.location = (0, side * (0.01 + 0.2 * open_ * 1.0), -0.1)
            ob.keyframe_insert("location", frame=f)
        A.key_visible(ob, [(2794, 2874)])


def finale_sky(ns):
    def prepare():
        ns["sky"]()
        A.apply_look("finale")
    return prepare


def build():
    A.setup()
    A.remove_collections(["Alex", "Hero"])
    ns = stand()
    bpy.context.scene.frame_set(2236)
    hero, head = ns["hero"]()
    ns["fallen"]()
    fall = falling_hero(ns)
    cameras(ns, head, fall)
    keel_over(hero, ns)
    bpy.context.scene.camera = bpy.data.objects["Shot27"]
    ns["sky"]()
    ns["barrage"]()
    # animatic: only the key light remains (the burst lamps gave it their light)
    for ob in list(bpy.data.collections["FX"].objects):
        if ob.type == 'LIGHT' and ob.name != "Barrage.Key":
            bpy.data.objects.remove(ob, do_unlink=True)
    return ns


NS = None


def plan():
    prep = (lambda: (NS["sky"](), A.apply_look("finale")))
    return [dict(shot=n, cam=f"Shot{n:02d}", prepare=prep) for n in (21, 23, 24, 25, 26, 27)]


if __name__ == "__main__":
    mode, shots = A.args()
    NS = build()
    A.run(mode, shots, plan(), "anim_finale.blend")
