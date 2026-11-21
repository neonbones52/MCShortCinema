"""The fallen of the finale (shots 25-28): dozens of the hero's comrades, each lying differently,
with torn wings; and the hero's kneeling pose. Run inside Blender (needs a set loaded for the
ground: mc_set).

    import mc_fallen as FL
    spots = FL.scatter(48, area=(x0, x1, z0, z1), avoid=[(x, z, r), ...], set_name="front", seed=7)
    rigs = FL.field(spots, set_name="front", seed=7)      # villagers posed, rested on the ground
    FL.kneel(hero_rig, set_name="front", block=(x, z))    # the hero on his knees

Decisions (HANDOFF, 2026-11-21): dozens of bodies, poses distinctly different from one another
(not just flat on the face); the comrades wear the recruits' kit (iron helmet, leggings, boots,
elytra) and their wings are torn: in the game a broken elytra changes only the item icon
(item/elytra_broken.png), the worn wings keep entity/equipment/wings/elytra.png, so the torn
look is our own texture in the spirit of that icon (holes with scorched rims, a ragged tip).
Poses are the game's way of posing (mc_character.set_bone_mc_rot, model space: x > 0 swings a
limb back, x < 0 forward; z > 0 lifts the right arm outwards, z < 0 the left; head x > 0 nods).
The rig is then laid down (rotation of the whole body) and lowered until its lowest vertex
touches the ground; spots are only taken where the ground under a body is flat, so nobody
floats over a step or sinks into a block.
"""
import math
import os
import random

import bpy
from mathutils import Euler, Matrix, Vector

import mc_character as C
import mc_set as SET

ROOT = r"C:\Dev\Projects\CinemaShort"
WINGS = os.path.join(ROOT, "assets", "mc", "textures", "entity", "equipment", "wings", "elytra.png")
OUT = os.path.join(ROOT, "assets", "characters")
SKINS = ("plains_farmer", "plains_plain", "plains_armorer", "plains_weaponsmith")
PI = math.pi

# name: dict(lay=(rx, ry) degrees of the whole body before the yaw: rx 90 face down, -90 on the back,
#            ry +-90 on a side), bones {bone: (x, y, z)} model radians, wings (x, y, z) model radians
POSES = {
    "prone_reach": dict(lay=(90, 0), bones={"arm.R": (-2.9, 0, 0.25), "arm.L": (0.2, 0, -0.35), "leg.R": (0.15, 0, 0.1),
                                            "leg.L": (-0.12, 0, -0.18), "head": (0.1, 1.25, 0)}, wings=(0.5, 0.1, -0.9)),
    "supine_spread": dict(lay=(-90, 0), bones={"arm.R": (0, 0, 1.45), "arm.L": (0.1, 0, -1.2), "leg.R": (0, 0, 0.28),
                                               "leg.L": (0, 0, -0.22), "head": (0.25, 0.7, 0)}, wings=(0.05, 0, -0.35)),
    "side_curled": dict(lay=(0, 90), bones={"arm.R": (-1.2, 0, 0.1), "arm.L": (-0.9, 0, -0.2), "leg.R": (-1.25, 0, 0),
                                            "leg.L": (-0.95, 0, 0.05), "head": (0.7, 0, 0), "body": (0.35, 0, 0)},
                        wings=C.WING_CROUCH),
    "side_reach": dict(lay=(0, -90), bones={"arm.R": (-0.35, 0, 0.2), "arm.L": (-1.7, 0, -0.1), "leg.R": (0.5, 0, 0),
                                            "leg.L": (-0.45, 0, 0), "head": (-0.35, 0.2, 0)}, wings=(0.4, 0.0, -0.6)),
    "prone_twisted": dict(lay=(88, 0), bones={"body": (0, 0.45, 0.12), "arm.R": (-0.45, 0, 0.3), "arm.L": (-2.3, 0, -0.2),
                                              "leg.R": (0.1, 0, 0.1), "leg.L": (0.05, 0, -0.55), "head": (0.0, -1.2, 0)},
                          wings=(0.35, 0.05, -1.3)),
    "sitting_slumped": dict(lay=(0, 0), bones={"leg.R": (-1.5, 0, 0.12), "leg.L": (-1.45, 0, -0.18), "body": (0.75, 0, 0),
                                               "head": (0.85, 0.25, 0), "arm.R": (-0.55, 0, 0.1), "arm.L": (-0.35, 0, -0.05)},
                            wings=C.WING_STAND),
    "supine_arm_up": dict(lay=(-90, 0), bones={"arm.R": (-1.35, 0, 0.1), "arm.L": (0.1, 0, -0.25), "leg.L": (-0.5, 0, -0.1),
                                               "leg.R": (0.05, 0, 0.15), "head": (0.1, -0.8, 0)}, wings=(0.05, 0, -0.5)),
    "prone_wings_out": dict(lay=(92, 0), bones={"arm.R": (-0.25, 0, 0.05), "arm.L": (-0.3, 0, -0.05),
                                                "head": (0.0, -1.3, 0)}, wings=C.WING_GLIDE),
    "side_arched": dict(lay=(25, 90), bones={"arm.R": (0.9, 0, 0.2), "arm.L": (0.6, 0, -0.3), "head": (-0.6, 0, 0),
                                             "leg.R": (0.3, 0, 0), "leg.L": (0.55, 0, 0)}, wings=(0.6, 0.1, -0.5)),
    "supine_knee_up": dict(lay=(-88, 0), bones={"leg.R": (-0.65, 0, 0.05), "arm.R": (0, 0, 0.5), "arm.L": (0, 0, -0.55),
                                                "head": (0.4, 0.3, 0)}, wings=(0.04, 0, -0.2)),
    "prone_crawl": dict(lay=(90, 0), bones={"arm.R": (-2.6, 0, 0.15), "arm.L": (0.35, 0, -0.1), "leg.R": (0.35, 0, 0.05),
                                            "leg.L": (-0.35, 0, -0.05), "head": (-0.55, 0, 0)}, wings=(0.45, 0.05, -0.7)),
    "facedown_kneeling": dict(lay=(55, 0), bones={"leg.R": (-1.1, 0, 0.05), "leg.L": (-1.05, 0, -0.08), "arm.R": (-0.2, 0, 0.6),
                                                  "arm.L": (-0.1, 0, -0.7), "head": (0.3, 0.9, 0)}, wings=(0.3, 0, -0.5)),
}
KNEEL = dict(lay=(0, 0), bones={"leg.R": (1.5, 0, 0.06), "leg.L": (1.5, 0, -0.06), "body": (0.12, 0, 0),
                                "head": (-0.25, 0, 0), "arm.R": (0.1, 0, 0.08), "arm.L": (0.15, 0, -0.06)},
             wings=C.WING_STAND)


# ------------------------------------------------------------------ torn wings
def torn_wings(variant=0):
    """A torn copy of the elytra texture (holes with scorched rims, a ragged tip), saved as
    assets/characters/elytra_torn_<variant>.png. The wing's pattern is on one face (x 34..46,
    y 2..22) and the material shows it from both sides, so cutting it there cuts the whole wing."""
    import numpy as np
    path = os.path.join(OUT, f"elytra_torn_{variant}.png")
    if not os.path.exists(path):
        src = bpy.data.images.load(WINGS)
        w, h = src.size
        px = np.array(src.pixels[:], np.float32).reshape(h, w, 4)[::-1].copy()     # rows top-down
        bpy.data.images.remove(src)
        rng = np.random.default_rng(100 + variant)
        yy, xx = np.mgrid[0:h, 0:w]
        wing = (xx >= 34) & (xx < 46) & (yy >= 2) & (yy < 22) & (px[..., 3] > 0)
        hole = np.zeros((h, w), bool)
        for _ in range(3 + variant):                                  # holes
            cx, cy, r = rng.uniform(35.5, 44.5), rng.uniform(5, 19), rng.uniform(0.9, 2.1)
            hole |= ((xx + 0.5 - cx) ** 2 + ((yy + 0.5 - cy) * 1.2) ** 2) < r * r
        for x in range(34, 46):                                       # ragged tip
            cut = int(rng.integers(0, 3 + variant))
            hole[22 - cut:22, x] = True
        for _ in range(2 + variant):                                  # bites out of the trailing edge
            cy, r = rng.uniform(8, 20), rng.uniform(1.0, 2.0)
            hole |= ((xx + 0.5 - 46) ** 2 + (yy + 0.5 - cy) ** 2) < r * r
        hole &= wing
        rim = np.zeros_like(hole)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            rim |= np.roll(np.roll(hole, dy, 0), dx, 1)
        rim &= wing & ~hole
        px[rim, :3] *= 0.45                                           # scorched
        px[hole, 3] = 0.0
        px[wing & ~hole & ~rim, :3] *= (0.85 + 0.15 * rng.random((wing & ~hole & ~rim).sum()))[:, None]
        os.makedirs(OUT, exist_ok=True)
        img = bpy.data.images.new(f"elytra_torn_{variant}_tmp", w, h, alpha=True)
        img.pixels[:] = px[::-1].ravel()
        img.filepath_raw, img.file_format = path, 'PNG'
        img.save()
        bpy.data.images.remove(img)
    return path


def tear_wings(rig, variant):
    mat = C.material(f"elytra.torn{variant}", torn_wings(variant), rough=0.75, spec=0.15)
    for ob in rig.children:
        if ".wing." in ob.name:
            ob.data.materials.clear()
            ob.data.materials.append(mat)


# ------------------------------------------------------------------ posing and resting on the ground
def apply_pose(rig, pose, jitter=0.0, rng=None):
    rng = rng or random.Random(0)
    for bone, (x, y, z) in pose["bones"].items():
        j = (lambda: rng.uniform(-jitter, jitter)) if jitter else (lambda: 0.0)
        C.set_bone_mc_rot(rig, bone, x + j(), y + j() * 0.5, z + j() * 0.5)
    if rig.pose.bones.get("wing.L") is not None:
        wx, wy, wz = pose["wings"]
        C.set_wing_pose(rig, wx, wy, wz)


def _mesh_children(rig):
    return [o for o in bpy.data.objects if o.type == 'MESH' and o.parent == rig]


def lowest_point(rig):
    """Lowest vertex of the body, wings left out: a body lies on its back or side and the wings
    under it give way (their tips may go into the ground, out of sight under the body)."""
    bpy.context.view_layer.update()
    zmin = None
    for ob in _mesh_children(rig):
        if ".wing." in ob.name:
            continue
        mw = ob.matrix_world
        for v in ob.data.vertices:
            z = (mw @ v.co).z
            zmin = z if zmin is None or z < zmin else zmin
    return zmin


def lay(rig, pose, yaw, set_name, x, z, sink=0.02):
    """Orient the posed body (lay angles, then the yaw) and lower it onto the ground at set column
    (x, z). Returns the ground height used."""
    rx, ry = pose["lay"]
    rot = Matrix.Rotation(yaw, 3, 'Z') @ Euler((math.radians(rx), math.radians(ry), 0), 'XYZ').to_matrix()
    rig.rotation_mode = 'QUATERNION'
    rig.rotation_quaternion = rot.to_quaternion()
    g = SET.ground(x, z, set_name)
    rig.location = Vector((x, -z, g + 3.0))
    low = lowest_point(rig)
    rig.location.z += g - low - sink
    return g


def flat_under(x, z, set_name, radius=1.2, tol=0.3):
    hs = [SET.ground(x + dx, z + dz, set_name) for dx, dz in
          ((0, 0), (radius, 0), (-radius, 0), (0, radius), (0, -radius), (0.8, 0.8), (-0.8, -0.8))]
    if any(h is None for h in hs):
        return False
    return max(hs) - min(hs) < tol


def scatter(n, area, set_name, avoid=(), seed=1, spacing=2.4, tries=4000):
    """n body spots (x, z) in area (x0, x1, z0, z1) on flat ground, at least `spacing` apart,
    clear of the circles in avoid [(x, z, r)]; a little clustering (people fall near each other)."""
    rng = random.Random(seed)
    x0, x1, z0, z1 = area
    spots = []
    for _ in range(tries):
        if len(spots) >= n:
            break
        if spots and rng.random() < 0.35:                 # next to someone already down
            bx, bz = rng.choice(spots)
            a, r = rng.uniform(0, 2 * PI), rng.uniform(spacing, spacing * 2.2)
            x, z = bx + math.cos(a) * r, bz + math.sin(a) * r
        else:
            x, z = rng.uniform(x0, x1), rng.uniform(z0, z1)
        if not (x0 <= x <= x1 and z0 <= z <= z1):
            continue
        if any(math.hypot(x - ax, z - az) < ar for ax, az, ar in avoid):
            continue
        if any(math.hypot(x - sx, z - sz) < spacing for sx, sz in spots):
            continue
        if not flat_under(x, z, set_name):
            continue
        spots.append((x, z))
    return spots


def field(spots, set_name, seed=1, name="Fallen"):
    """A body on every spot: the recruits' kit, a pose from the library (each used in turn, so the
    neighbours differ), jitter, a random yaw, torn wings (3 variants), now and then the helmet
    lost (the profession hat is then seen, as in the game)."""
    import contextlib
    import io
    rng = random.Random(seed)
    names = list(POSES)
    rng.shuffle(names)
    rigs = []
    for i, (x, z) in enumerate(spots):
        pose_name = names[i % len(names)]
        helmet = None if rng.random() < 0.22 else "iron"
        with contextlib.redirect_stdout(io.StringIO()):
            rig = C.villager(f"{name}{i:02d}", skin=SKINS[rng.randrange(len(SKINS))], helmet=helmet,
                             legs="iron", boots="iron", elytra=True)
        apply_pose(rig, POSES[pose_name], jitter=0.18, rng=rng)
        tear_wings(rig, rng.randrange(3))
        lay(rig, POSES[pose_name], rng.uniform(0, 2 * PI), set_name, x, z)
        rig["mc_fallen"] = pose_name
        rigs.append(rig)
    return rigs


def kneel(rig, set_name, x, z, yaw):
    """The hero on his knees (shots 25-27): legs folded back under him, a slight stoop, head up."""
    apply_pose(rig, KNEEL)
    return lay(rig, KNEEL, yaw, set_name, x, z, sink=0.0)
