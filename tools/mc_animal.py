"""Vanilla cow (Minecraft 26.2, read with javap) for the village background and the memory.

CowModel.createBaseCowModel (64x64, cow_temperate.png = the plains cow):
    head   texOffs(0,0) box(-4,-4,-6, 8,8,6); muzzle texOffs(1,33) box(-3,1,-7, 6,3,1);
           horns texOffs(22,0) box(-5,-5,-5, 1,3,1) and box(4,-5,-5, 1,3,1); pose offset (0,4,-8)
    body   texOffs(18,4) box(-6,-10,-7, 12,18,10); udder texOffs(52,0) box(-2,2,-8, 4,6,1);
           pose offset (0,5,2) rotated xRot = pi/2
    legs   texOffs(0,16) box(-2,0,-2, 4,12,4) at (-4,12,7) / (4,12,7) / (-4,12,-5) / (4,12,-5),
           the right legs mirrored
QuadrupedModel.setupAnim: head xRot/yRot = the look; legs xRot = cos(pos*0.6662 [+pi]) * 1.4 * speed
    (right hind and left front in phase, the other pair opposite).
"""
import math
import os

import bpy
from mathutils import Quaternion, Vector

import mc_character as C

TEX = os.path.join(C.TEX, "entity", "cow")
COW_BONES = {
    'root':   ((0, 24, 0), (0, 24, 6), None),
    'body':   ((0, 5, 2), (0, 5, -6), 'root'),
    'head':   ((0, 4, -8), (0, 4, -14), 'root'),
    'leg.RH': ((-4, 12, 7), (-4, 24, 7), 'root'),
    'leg.LH': ((4, 12, 7), (4, 24, 7), 'root'),
    'leg.RF': ((-4, 12, -5), (-4, 24, -5), 'root'),
    'leg.LF': ((4, 12, -5), (4, 24, -5), 'root'),
}


def cow(name="Cow", variant="temperate", location=(0, 0, 0), yaw=0.0):
    col = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(col)
    rig = C.make_rig(name + ".rig", col, COW_BONES)
    png = os.path.join(TEX, f"cow_{variant}.png")
    S, m = (64, 64), f"cow.{variant}"
    head = C.Part(name + ".head", png, S, 'head')
    head.box((0, 0), (-4, -4, -6), (8, 8, 6), pivot=(0, 4, -8))
    head.box((1, 33), (-3, 1, -7), (6, 3, 1), pivot=(0, 4, -8))
    head.box((22, 0), (-5, -5, -5), (1, 3, 1), pivot=(0, 4, -8))
    head.box((22, 0), (4, -5, -5), (1, 3, 1), pivot=(0, 4, -8))
    body = C.Part(name + ".body", png, S, 'body')
    body.box((18, 4), (-6, -10, -7), (12, 18, 10), pivot=(0, 5, 2), rot=(math.pi / 2, 0, 0))
    body.box((52, 0), (-2, 2, -8), (4, 6, 1), pivot=(0, 5, 2), rot=(math.pi / 2, 0, 0))
    parts = [head, body]
    for bone, piv in (('leg.RH', (-4, 12, 7)), ('leg.LH', (4, 12, 7)), ('leg.RF', (-4, 12, -5)), ('leg.LF', (4, 12, -5))):
        parts.append(C.Part(f"{name}.{bone}", png, S, bone).box((0, 16), (-2, 0, -2), (4, 12, 4), pivot=piv,
                                                                 mirror=bone.startswith("leg.R")))
    for p in parts:
        C.parent_to_bone(p.build(col, m), rig, p.bone)
    rig.location = location
    rig.rotation_mode = 'QUATERNION'
    rig.rotation_quaternion = Quaternion((0, 0, 1), yaw)
    rig["mc_character"] = dict(kind="cow", variant=variant)
    return rig


def pose(rig, walk_pos, speed, head_pitch=0.0, head_yaw=0.0, frame=None):
    a = math.cos(walk_pos * 0.6662) * 1.4 * speed
    C.set_bone_mc_rot(rig, 'head', head_pitch, head_yaw, 0, frame)
    C.set_bone_mc_rot(rig, 'leg.RH', a, 0, 0, frame)
    C.set_bone_mc_rot(rig, 'leg.LH', -a, 0, 0, frame)
    C.set_bone_mc_rot(rig, 'leg.RF', -a, 0, 0, frame)
    C.set_bone_mc_rot(rig, 'leg.LF', a, 0, 0, frame)


def amble(rig, ground, frame0, frame1, start, stops, seed=1, speed=0.08, fps=24.0):
    """Background life: stand, look about (head down to the grass now and then), walk a few
    blocks to the next stop, as a cow's random stroll does. stops: [(x, y)] Blender xy; ground(x, y)
    gives the z of the feet. Keys every game tick."""
    import random
    rng = random.Random(seed)
    pos = Vector((start[0], start[1], ground(*start)))
    yaw = rig.rotation_quaternion.to_euler().z
    route = list(stops)
    walk_pos, wspeed = 0.0, 0.0
    target, wait = None, rng.randrange(20, 80)
    hp, hy, want_p, want_y = 0.0, 0.0, 0.0, 0.0
    t, prev_q = 0, None
    while True:
        f = frame0 + t * fps / 20.0
        if f > frame1:
            break
        moving = False
        if target is None:
            wait -= 1
            if wait <= 0 and route:
                target = Vector(route.pop(0))
            if t % 40 == 0:
                want_p = rng.choice((0.0, 0.2, 0.9, 0.9))                 # down to the grass, or up
                want_y = rng.uniform(-0.6, 0.6)
        else:
            d = target - pos.xy
            if d.length < speed:
                target, wait = None, rng.randrange(60, 160)
            else:
                pos.xy += d.normalized() * speed
                z = ground(pos.x, pos.y)
                if z is not None and abs(z - pos.z) <= 1.05:     # a block step at most, as in the game
                    pos.z = z
                yaw += ((math.atan2(d.y, d.x) + math.pi / 2) - yaw + math.pi) % (2 * math.pi) - math.pi
                moving, want_p, want_y = True, 0.1, 0.0
        wspeed += (min((speed if moving else 0.0) * 4.0, 1.0) - wspeed) * 0.4
        walk_pos += wspeed
        hp += max(-0.17, min(0.17, want_p - hp))
        hy += max(-0.17, min(0.17, want_y - hy))
        q = Quaternion((0, 0, 1), yaw)
        if prev_q is not None and q.dot(prev_q) < 0:
            q.negate()
        prev_q = q.copy()
        rig.location, rig.rotation_quaternion = pos, q
        rig.keyframe_insert("location", frame=f)
        rig.keyframe_insert("rotation_quaternion", frame=f)
        pose(rig, walk_pos, wspeed, hp, hy, frame=f)
        t += 1
