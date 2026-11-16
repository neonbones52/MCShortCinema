"""Vanilla horse (Minecraft 26.2, read with javap) with iron horse armour, saddle and a rider.

AbstractEquineModel.createBodyMesh   body 10x10x22 (+0.05) at (0,11,5); head_parts (neck 4x12x7,
                                     head 6x5x7, mane, upper mouth, ears) at (0,4,-12) rot 30 deg;
                                     legs 4x11x4 at (+-4,14,7)/(+-4,14,-10); tail 3x14x4 rot 30 deg
LayerDefinitions                     HORSE scaled 1.1; HORSE_ARMOR = same mesh with deformation 0.1
EquineSaddleModel                    saddle 10x9x9 (+0.5) on the body, head harness, reins
AbstractEquineModel.setupAnim        legs: a = cos(pos*0.6662 + pi) * 0.8 * speed;
                                     front L/R = +a/-a, hind L/R = -a*0.5/+a*0.5 (times speed);
                                     head bob cos(pos*0.8)*0.15*speed when speed > 0.2; tail lifts 0.75*speed
HumanoidModel (riding)               legs xRot -1.4137, yRot +-pi/10, zRot +-0.0785; arms xRot -pi/5
"""
import math
import os

import bpy
from mathutils import Matrix, Vector

import mc_character as C

TEX = C.TEX
SCALE = 1.1

HORSE_BONES = {
    'root':   ((0, 24, 0), (0, 24, 6), None),
    'body':   ((0, 11, 5), (0, 11, -5), 'root'),
    'neck':   ((0, 4, -12), (0, -6, -12), 'root'),
    'tail':   ((0, 6, 7), (0, 6, 13), 'body'),
    'leg.LH': ((4, 14, 7), (4, 24, 7), 'root'),
    'leg.RH': ((-4, 14, 7), (-4, 24, 7), 'root'),
    'leg.LF': ((4, 14, -10), (4, 24, -10), 'root'),
    'leg.RF': ((-4, 14, -10), (-4, 24, -10), 'root'),
}
NECK_REST = math.radians(30)
TAIL_REST = math.radians(30)


def _horse_parts(name, png, d, body_infl, neck_infl, mat):
    """The equine mesh. d = deformation of the 'aload_0' parts (0 for the horse, 0.1 armour)."""
    S = (64, 64)
    P = []
    P.append((C.Part(name + ".body", png, S, 'body')
              .box((0, 32), (-5, -8, -17), (10, 10, 22), pivot=(0, 11, 5), inflate=body_infl), mat))
    neck = C.Part(name + ".neck", png, S, 'neck')
    neck.box((0, 35), (-2.05, -6, -2), (4, 12, 7), pivot=(0, 4, -12), inflate=neck_infl)
    neck.box((0, 13), (-3, -11, -2), (6, 5, 7), pivot=(0, 4, -12), inflate=d)
    neck.box((56, 36), (-1, -11, 5.01), (2, 16, 2), pivot=(0, 4, -12), inflate=d)
    neck.box((0, 25), (-2, -11, -7), (4, 5, 5), pivot=(0, 4, -12), inflate=d)
    neck.box((19, 16), (0.55, -13, 4), (2, 3, 1), pivot=(0, 4, -12), inflate=d - 0.001)
    neck.box((19, 16), (-2.55, -13, 4), (2, 3, 1), pivot=(0, 4, -12), inflate=d - 0.001)
    P.append((neck, mat))
    for bone, ox, piv, mirror in (('leg.LH', (-3, -1.01, -1), (4, 14, 7), True), ('leg.RH', (-1, -1.01, -1), (-4, 14, 7), False),
                                  ('leg.LF', (-3, -1.01, -1.9), (4, 14, -10), True), ('leg.RF', (-1, -1.01, -1.9), (-4, 14, -10), False)):
        P.append((C.Part(f"{name}.{bone}", png, S, bone).box((48, 21), ox, (4, 11, 4), pivot=piv, inflate=d, mirror=mirror), mat))
    P.append((C.Part(name + ".tail", png, S, 'tail').box((42, 36), (-1.5, 0, 0), (3, 14, 4), pivot=(0, 6, 7), inflate=d), mat))
    return P


def horse(name="Horse", coat="horse_brown", armor="iron", saddle=True, location=(0, 0, 0)):
    col = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(col)
    rig = C.make_rig(name + ".rig", col, HORSE_BONES)
    coat_png = os.path.join(TEX, "entity", "horse", coat + ".png")
    parts = _horse_parts(name, coat_png, 0.0, 0.05, 0.0, "horse." + coat)
    if armor:
        apng = os.path.join(TEX, "entity", "equipment", "horse_body", armor + ".png")
        # game: armour body/neck share the horse's own +0.05/+0 boxes -> coplanar; nudged out here
        for part, _m in _horse_parts(name + ".armor", apng, 0.1, 0.17, 0.12, "horse_armor." + armor):
            part.mat_kw = C.ARMOR_MAT
            parts.append((part, "horse_armor." + armor))
    if saddle:
        spng = os.path.join(TEX, "entity", "equipment", "horse_saddle", "saddle.png")
        S = (64, 64)
        parts.append((C.Part(name + ".saddle", spng, S, 'body')
                      .box((26, 0), (-5, -8, -9), (10, 9, 9), pivot=(0, 11, 5), inflate=0.5), "horse.saddle"))
        h = C.Part(name + ".harness", spng, S, 'neck')
        h.box((29, 5), (2, -9, -6), (1, 2, 2), pivot=(0, 4, -12))
        h.box((29, 5), (-3, -9, -6), (1, 2, 2), pivot=(0, 4, -12))
        rx = 3.25 if armor else 3.1        # reins: the armoured head's side is exactly at 3.1
        h.box((32, 2), (rx, -6, -8), (0, 3, 16), pivot=(0, 4, -12), rot=(-0.5235988, 0, 0))
        h.box((32, 2), (-rx, -6, -8), (0, 3, 16), pivot=(0, 4, -12), rot=(-0.5235988, 0, 0))
        h.box((1, 1), (-3, -11, -1.9), (6, 5, 6), pivot=(0, 4, -12), inflate=0.26)
        h.box((19, 0), (-2, -11, -4), (4, 5, 2), pivot=(0, 4, -12), inflate=0.2)
        parts.append((h, "horse.saddle"))
    for part, mname in parts:
        C.parent_to_bone(part.build(col, mname), rig, part.bone)
    rig.scale = (SCALE, SCALE, SCALE)
    rig.location = location
    pose(rig, 0.0, 0.0, 0.0)
    rig["mc_character"] = dict(kind="horse", coat=coat, armor=armor or "", saddle=saddle)
    return rig


def pose(rig, walk_pos, speed, age_ticks, frame=None, head_pitch=0.0):
    """AbstractEquineModel.setupAnim (no rearing / eating)."""
    a = math.cos(walk_pos * 0.6662 + math.pi) * 0.8 * speed
    bob = math.cos(walk_pos * 0.8) * 0.15 * speed if speed > 0.2 else 0.0
    C.set_bone_mc_rot(rig, 'neck', NECK_REST + head_pitch + bob, 0, 0, frame)
    C.set_bone_mc_rot(rig, 'leg.LF', a, 0, 0, frame)
    C.set_bone_mc_rot(rig, 'leg.RF', -a, 0, 0, frame)
    C.set_bone_mc_rot(rig, 'leg.LH', -a * 0.5 * speed, 0, 0, frame)
    C.set_bone_mc_rot(rig, 'leg.RH', a * 0.5 * speed, 0, 0, frame)
    C.set_bone_mc_rot(rig, 'tail', TAIL_REST + speed * 0.75, math.cos(age_ticks * 0.7) * 0.0 , 0, frame)


SADDLE_SEAT = (0, 2.0, 1.0)      # model px on the horse where the rider's origin goes (tuned by eye)


def mount(rider, horse_rig, seat_drop_px=12.0):
    """Sit a villager on the horse: riding pose + parented so it follows the horse."""
    C.set_bone_mc_rot(rider, 'leg.R', -1.4137167, math.pi / 10, 0.07853982)
    C.set_bone_mc_rot(rider, 'leg.L', -1.4137167, -math.pi / 10, -0.07853982)
    C.set_bone_mc_rot(rider, 'arm.R', -math.pi / 5, 0, 0)
    C.set_bone_mc_rot(rider, 'arm.L', -math.pi / 5, 0, 0)
    rider.parent = horse_rig
    rider.matrix_parent_inverse = Matrix.Identity(4)
    seat = C.m2b(SADDLE_SEAT)
    rider.location = seat - Vector((0, 0, seat_drop_px / 16.0))
    rider.rotation_euler = (0, 0, 0)
    rider.scale = (1 / SCALE, 1 / SCALE, 1 / SCALE)
    return rider


def gallop(rig, path, frame0, speed_bpt=0.45, fps=24.0, riders=()):
    """Key a gallop along a polyline `path` (Blender points on the ground), game speed in
    blocks/tick. Limb animation follows WalkAnimationState: pos += speed each tick."""
    pts = [Vector(p) for p in path]
    segs = [(a, b, (b - a).length) for a, b in zip(pts, pts[1:])]
    total = sum(s[2] for s in segs)
    ticks = int(total / speed_bpt)
    walk_speed, walk_pos = 0.0, 0.0
    prev_q = None
    for t in range(ticks + 1):
        dist = min(total, t * speed_bpt)
        acc = 0.0
        for a, b, L in segs:
            if acc + L >= dist:
                p = a + (b - a) * ((dist - acc) / L)
                direction = (b - a).normalized()
                break
            acc += L
        f = frame0 + t * fps / 20.0
        target = min(1.0, speed_bpt * 4.0)                # WalkAnimationState: min(dist*4, 1)
        walk_speed += (target - walk_speed) * 0.4
        walk_pos += walk_speed
        rig.location = p
        rig.rotation_mode = 'QUATERNION'
        q = Vector((0, -1, 0)).rotation_difference(Vector((direction.x, direction.y, 0)).normalized())
        if prev_q is not None and q.dot(prev_q) < 0:
            q.negate()
        prev_q = q.copy()
        rig.rotation_quaternion = q
        rig.keyframe_insert("location", frame=f)
        rig.keyframe_insert("rotation_quaternion", frame=f)
        pose(rig, walk_pos, walk_speed, t, frame=f)
    return ticks
