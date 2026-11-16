"""Vanilla-accurate Minecraft villager characters for Blender (run inside Blender).

Geometry follows the game's own models (VillagerModel / ZombieVillagerModel, humanoid
armor, ElytraModel): boxes in model pixels, MC box-UV layout, rigid parts on a simple rig.

Model space (as in the game): x = entity's left(+)/right(-), y = DOWN, z = back(+)/front(-),
ground at y = 24. Blender: 1 block = 1 m, character faces -Y.
"""
import math
import os

import bmesh
import bpy
from mathutils import Matrix, Vector

PX = 1.0 / 16.0
ROOT = r"C:\Dev\Projects\CinemaShort"
TEX = os.path.join(ROOT, "assets", "mc", "textures")
CHARS = os.path.join(ROOT, "assets", "characters")


def m2b(p):
    """model-space point (px) -> Blender metres"""
    return Vector((p[0] * PX, p[2] * PX, (24.0 - p[1]) * PX))


def rot_model(xr=0.0, yr=0.0, zr=0.0):
    """MC PartPose rotation (radians, model space): R = Rz * Ry * Rx"""
    return (Matrix.Rotation(zr, 3, 'Z') @ Matrix.Rotation(yr, 3, 'Y') @ Matrix.Rotation(xr, 3, 'X'))


# ------------------------------------------------------------------ materials / images
def image(path):
    path = os.path.normpath(path)
    for im in bpy.data.images:
        if os.path.normpath(bpy.path.abspath(im.filepath)) == path:
            return im
    im = bpy.data.images.load(path)
    im.alpha_mode = 'STRAIGHT'
    return im


def material(name, path, rough=0.9, spec=0.15, metallic=0.0):
    mat = bpy.data.materials.get(name)
    if mat:
        return mat
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    tex = nt.nodes.new('ShaderNodeTexImage')
    tex.image = image(path)
    tex.interpolation = 'Closest'
    tex.location = (-400, 200)
    nt.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
    nt.links.new(tex.outputs['Alpha'], bsdf.inputs['Alpha'])
    bsdf.inputs['Roughness'].default_value = rough
    bsdf.inputs['Metallic'].default_value = metallic
    for key in ('Specular IOR Level', 'Specular'):
        if key in bsdf.inputs:
            bsdf.inputs[key].default_value = spec
            break
    mat.use_backface_culling = False
    for attr, val in (('surface_render_method', 'DITHERED'), ('use_transparent_shadow', True)):
        try:
            setattr(mat, attr, val)                 # transparent pixels must not cast shadows
        except (AttributeError, TypeError):
            pass
    mat["mc_texture"] = path
    return mat


# ------------------------------------------------------------------ box with MC UVs
def add_box(bm, uvl, tex_wh, uv, origin, size, pivot=(0, 0, 0), inflate=0.0, mirror=False,
            rot=(0, 0, 0), uvsize=None, faces=None):
    """Add one MC cube to bmesh. origin/size in px relative to pivot (model space)."""
    tw, th = tex_wh
    u, v = uv
    W, H, D = uvsize or size
    x0, y0, z0 = origin
    x1, y1, z1 = x0 + size[0], y0 + size[1], z0 + size[2]
    x0 -= inflate; y0 -= inflate; z0 -= inflate
    x1 += inflate; y1 += inflate; z1 += inflate
    if mirror:
        x0, x1 = x1, x0                       # as the game does: swap, so the texture mirrors
    R = rot_model(*rot)
    pv = Vector(pivot)

    def P(x, y, z):
        return m2b(pv + R @ Vector((x, y, z)))

    def UV(px, py):
        return (px / tw, 1.0 - py / th)

    f4, f5, f6, f7 = u, u + D, u + D + W, u + D + W + W
    f8, f9 = u + D + W + D, u + D + W + D + W
    f10, f11, f12 = v, v + D, v + D + H
    c = {
        'v0': (x0, y0, z0), 'v1': (x1, y0, z0), 'v2': (x1, y1, z0), 'v3': (x0, y1, z0),
        'v4': (x0, y0, z1), 'v5': (x1, y0, z1), 'v6': (x1, y1, z1), 'v7': (x0, y1, z1),
    }
    # (vertices, (u0, v0, u1, v1)) ; polygon remap: [0]->(u1,v0) [1]->(u0,v0) [2]->(u0,v1) [3]->(u1,v1)
    polys = {
        'top':    (('v5', 'v4', 'v0', 'v1'), (f5, f10, f6, f11)),
        'bottom': (('v2', 'v3', 'v7', 'v6'), (f6, f11, f7, f10)),
        'west':   (('v0', 'v4', 'v7', 'v3'), (f4, f11, f5, f12)),
        'front':  (('v1', 'v0', 'v3', 'v2'), (f5, f11, f6, f12)),
        'east':   (('v5', 'v1', 'v2', 'v6'), (f6, f11, f8, f12)),
        'back':   (('v4', 'v5', 'v6', 'v7'), (f8, f11, f9, f12)),
    }
    made = []
    for key, (vs, (u0, v0, u1, v1)) in polys.items():
        if faces and key not in faces:
            continue
        verts = [bm.verts.new(P(*c[k])) for k in vs]
        f = bm.faces.new(verts)
        uvs = [(u1, v0), (u0, v0), (u0, v1), (u1, v1)]
        for loop, (a, b) in zip(f.loops, uvs):
            loop[uvl].uv = UV(a, b)
        made.append(f)
    return made


class Part:
    """Collects boxes that share a texture and a bone into one mesh object."""

    def __init__(self, name, tex_path, tex_wh, bone, mat_kw=None):
        self.name, self.tex_path, self.tex_wh, self.bone = name, tex_path, tex_wh, bone
        self.bm = bmesh.new()
        self.uvl = self.bm.loops.layers.uv.new("UVMap")
        self.mat_kw = mat_kw or {}

    def box(self, uv, origin, size, **kw):
        add_box(self.bm, self.uvl, self.tex_wh, uv, origin, size, **kw)
        return self

    def build(self, collection, mat_name):
        me = bpy.data.meshes.new(self.name)
        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces)
        self.bm.to_mesh(me)
        self.bm.free()
        me.materials.append(material(mat_name, self.tex_path, **self.mat_kw))
        ob = bpy.data.objects.new(self.name, me)
        collection.objects.link(ob)
        return ob


# ------------------------------------------------------------------ item sprite (extruded)
def item_mesh(name, png, collection, thickness_px=1.0, grip=(8, 8)):
    """Extruded 16x16 item like the game's 'generated' item models. 1 m = 16 px.
    Sprite lies in the XZ plane; origin at the `grip` pixel (x, y from the image's top-left)."""
    from math import floor
    im = image(png)
    w, h = im.size
    px = list(im.pixels)

    def opaque(x, y):
        if x < 0 or y < 0 or x >= w or y >= h:
            return False
        return px[((h - 1 - y) * w + x) * 4 + 3] > 0.1

    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    s = PX * 16.0 / w
    t = thickness_px * PX * 16.0 / w / 2.0

    def quad(pts, uvs):
        f = bm.faces.new([bm.verts.new(p) for p in pts])
        for loop, uvv in zip(f.loops, uvs):
            loop[uvl].uv = uvv

    for y in range(h):
        for x in range(w):
            if not opaque(x, y):
                continue
            X0, X1 = (x - w / 2) * s, (x + 1 - w / 2) * s
            Z1, Z0 = (h / 2 - y) * s, (h / 2 - y - 1) * s
            cu, cv = (x + 0.5) / w, 1.0 - (y + 0.5) / h
            uv4 = [(cu, cv)] * 4
            quad([(X0, -t, Z0), (X1, -t, Z0), (X1, -t, Z1), (X0, -t, Z1)],
                 [(x / w, 1 - (y + 1) / h), ((x + 1) / w, 1 - (y + 1) / h), ((x + 1) / w, 1 - y / h), (x / w, 1 - y / h)])
            quad([(X1, t, Z0), (X0, t, Z0), (X0, t, Z1), (X1, t, Z1)],
                 [((x + 1) / w, 1 - (y + 1) / h), (x / w, 1 - (y + 1) / h), (x / w, 1 - y / h), ((x + 1) / w, 1 - y / h)])
            if not opaque(x - 1, y):
                quad([(X0, t, Z0), (X0, -t, Z0), (X0, -t, Z1), (X0, t, Z1)], uv4)
            if not opaque(x + 1, y):
                quad([(X1, -t, Z0), (X1, t, Z0), (X1, t, Z1), (X1, -t, Z1)], uv4)
            if not opaque(x, y - 1):
                quad([(X0, -t, Z1), (X1, -t, Z1), (X1, t, Z1), (X0, t, Z1)], uv4)
            if not opaque(x, y + 1):
                quad([(X0, t, Z0), (X1, t, Z0), (X1, -t, Z0), (X0, -t, Z0)], uv4)
    gx, gy = (grip[0] + 0.5 - w / 2) * s, (h / 2 - grip[1] - 0.5) * s
    bmesh.ops.translate(bm, vec=Vector((-gx, 0, -gy)), verts=bm.verts)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(material("item." + os.path.basename(png)[:-4], png, rough=0.6, spec=0.3))
    ob = bpy.data.objects.new(name, me)
    collection.objects.link(ob)
    return ob


# ------------------------------------------------------------------ rig
BONES = {  # name: (head_model_px, tail_model_px, parent)
    'root':   ((0, 24, 0), (0, 24, 6), None),
    'body':   ((0, 12, 0), (0, 0, 0), 'root'),
    'head':   ((0, 0, 0), (0, -10, 0), 'body'),
    'arm.R':  ((-5, 2, 0), (-5, 12, 0), 'body'),
    'arm.L':  ((5, 2, 0), (5, 12, 0), 'body'),
    'hand.R': ((-6, 12, 0), (-6, 15, 0), 'arm.R'),
    'leg.R':  ((-2, 12, 0), (-2, 24, 0), 'root'),
    'leg.L':  ((2, 12, 0), (2, 24, 0), 'root'),
    'wing.R': ((-5, 0, 3), (-5, 10, 3), 'body'),
    'wing.L': ((5, 0, 3), (5, 10, 3), 'body'),
}


def make_rig(name, collection, bones=None):
    bones = bones or BONES
    arm = bpy.data.armatures.new(name)
    ob = bpy.data.objects.new(name, arm)
    collection.objects.link(ob)
    ob.show_in_front = True
    view_layer = bpy.context.view_layer
    prev = view_layer.objects.active
    view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode='EDIT')
    for bname, (h, t, parent) in bones.items():
        eb = arm.edit_bones.new(bname)
        eb.head, eb.tail = m2b(h), m2b(t)
        if bname == 'root':
            eb.tail = m2b(h) + Vector((0, 0.4, 0))
        eb.roll = 0.0
        if parent:
            eb.parent = arm.edit_bones[parent]
    bpy.ops.object.mode_set(mode='OBJECT')
    view_layer.objects.active = prev
    return ob


M_AX = Matrix(((1, 0, 0), (0, 0, 1), (0, -1, 0)))     # model axes -> Blender axes (rotation part of m2b)

# ElytraAnimationState targets (radians, model space, left wing; the right wing mirrors y and z)
WING_STAND = (0.2617994, 0.0, -0.2617994)
WING_GLIDE = (0.34906584, 0.0, -1.5707964)
WING_CROUCH = (0.6981317, 0.08726646, -0.7853982)


def mc_rot_arm(xr, yr, zr):
    """A game PartPose rotation expressed in Blender armature space."""
    return M_AX @ rot_model(xr, yr, zr) @ M_AX.inverted()


def set_bone_mc_rot(rig, bone, xr=0.0, yr=0.0, zr=0.0, frame=None):
    """Pose a bone with a rotation given the game's way (about its head), optionally keyed."""
    pb, b = rig.pose.bones[bone], rig.data.bones[bone]
    rest = b.matrix_local.to_3x3()
    pb.rotation_mode = 'QUATERNION'
    q = (rest.inverted() @ mc_rot_arm(xr, yr, zr) @ rest).to_quaternion()
    if q.dot(pb.rotation_quaternion) < 0:      # keep sign continuous with the previous key
        q.negate()
    pb.rotation_quaternion = q
    if frame is not None:
        pb.keyframe_insert("rotation_quaternion", frame=frame)


def set_wing_pose(rig, xr, yr, zr, frame=None):
    set_bone_mc_rot(rig, 'wing.L', xr, yr, zr, frame)
    set_bone_mc_rot(rig, 'wing.R', xr, -yr, -zr, frame)


def parent_to_bone(ob, rig, bone):
    ob.parent = rig
    ob.parent_type = 'BONE'
    ob.parent_bone = bone
    b = rig.data.bones[bone]
    tail_m = rig.matrix_world @ b.matrix_local @ Matrix.Translation((0, b.length, 0))
    ob.matrix_parent_inverse = tail_m.inverted()


# ------------------------------------------------------------------ the character
# Armor inflations differ from the game's by hundredths of a pixel (helmet 1.05, chest 1.1,
# chest arms 1.02, boots 1.04, leggings 0.6/0.65) so that no two visible faces of different
# parts share a plane: a renderer shows shared planes as flicker (z-fighting).
ARMOR_MAT = dict(rough=0.42, spec=0.5, metallic=0.0)
ITEM_GRIP = {  # pixel the fist closes on (x, y from the sprite's top-left)
    'iron_hoe': (4, 12), 'iron_sword': (4, 12), 'stick': (5, 11), 'paper': (8, 8),
    'firework_rocket': (8, 10), 'crossbow_standby': (8, 8), 'crossbow_firework': (8, 8),
}
LEG_L_EXTRA = 0.01   # px


def leg_piece(side, inflate=0.0, gap=None, pivot_x=None):
    """(origin, size) for a 4x12x4 box on one leg (pass uvsize=(4, 12, 4)).
    In the game the left and right pieces overlap at the centre (inflated armor; player legs at
    +-1.9) and their coplanar front/back faces flicker (z-fighting) in a renderer. The left piece
    is made LEG_L_EXTRA deeper and longer instead, so the planes differ while the inner faces
    stay where the game has them: each layer's inner side still covers the layer below it when
    the legs swing apart (trimming the inner side, as before 2026-11-16, let the skin show
    through between the legs in a walk). gap / pivot_x are ignored (old signature)."""
    e = LEG_L_EXTRA if side == 'L' else 0.0
    return (-2.0, -e, -2.0 - e), (4.0, 12.0 + 2 * e, 4.0 + 2 * e)


ITEM_HANDLE = {  # direction from the grip along the handle, in sprite pixels (right, up)
    'iron_hoe': (6, 8), 'iron_sword': (8, 8), 'stick': (6, 8),
}


def villager(name="Villager", skin="plains_farmer", helmet=None, chest=None, legs=None, boots=None,
             elytra=False, hat=True, item_r=None, location=(0, 0, 0)):
    """Build a villager. helmet/chest/legs/boots: 'iron', 'chainmail', 'diamond', 'netherite'...
    Profession hat is hidden under a helmet, as in the game."""
    col = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(col)
    rig = make_rig(name + ".rig", col)
    skin_png = os.path.join(CHARS, skin + ".png")
    S = (64, 64)
    mskin = "skin." + skin
    parts = []

    head = Part(name + ".head", skin_png, S, 'head')
    head.box((0, 0), (-4, -10, -4), (8, 10, 8))
    head.box((24, 0), (-1, -1, -6), (2, 4, 2), pivot=(0, -2, 0))                     # nose
    if hat and not helmet:
        head.box((32, 0), (-4, -10, -4), (8, 10, 8), inflate=0.51)                    # hat layer
        head.box((30, 47), (-8, -8, -6), (16, 16, 1), rot=(-math.pi / 2, 0, 0))      # hat rim
    parts.append((head, mskin))

    body = Part(name + ".body", skin_png, S, 'body')
    body.box((16, 20), (-4, 0, -3), (8, 12, 6))
    if not legs:
        # robe; with leggings on it is left off so the armor covers the clothes, as on a player
        body.box((0, 38), (-4, 0, -3), (8, 20, 6), inflate=0.5)
    parts.append((body, mskin))
    parts.append((Part(name + ".arm.R", skin_png, S, 'arm.R').box((44, 22), (-3, -2, -2), (4, 12, 4), pivot=(-5, 2, 0)), mskin))
    parts.append((Part(name + ".arm.L", skin_png, S, 'arm.L').box((44, 22), (-1, -2, -2), (4, 12, 4), pivot=(5, 2, 0), mirror=True), mskin))
    parts.append((Part(name + ".leg.R", skin_png, S, 'leg.R').box((0, 22), (-2, 0, -2), (4, 12, 4), pivot=(-2, 12, 0)), mskin))
    parts.append((Part(name + ".leg.L", skin_png, S, 'leg.L').box((0, 22), (-2, 0, -2), (4, 12, 4), pivot=(2, 12, 0), mirror=True), mskin))

    A = (64, 32)

    def armor_png(mat, layer='humanoid'):
        return os.path.join(TEX, "entity", "equipment", layer, mat + ".png")

    if helmet:
        p = Part(name + ".helmet", armor_png(helmet), A, 'head', ARMOR_MAT)
        # 1.05 (game: 1.0): its bottom must not share the plane y=-1 with the chestplate top
        p.box((0, 0), (-4, -10, -4), (8, 8, 8), inflate=1.05)
        parts.append((p, "armor." + helmet))
    if chest:
        p = Part(name + ".chest", armor_png(chest), A, 'body', ARMOR_MAT)
        # 1.1 (game: 1.0): at 1.0 its front/back (z=+-4) coincide with the head's faces and its
        # top (y=-1) with the helmet's bottom -> flicker at the head corners
        p.box((16, 16), (-4, 0, -3), (8, 12, 6), inflate=1.1, uvsize=(8, 12, 4))
        parts.append((p, "armor." + chest))
        parts.append((Part(name + ".chest.arm.R", armor_png(chest), A, 'arm.R', ARMOR_MAT)
                      .box((40, 16), (-3, -2, -2), (4, 12, 4), pivot=(-5, 2, 0), inflate=1.02), "armor." + chest))
        parts.append((Part(name + ".chest.arm.L", armor_png(chest), A, 'arm.L', ARMOR_MAT)
                      .box((40, 16), (-1, -2, -2), (4, 12, 4), pivot=(5, 2, 0), inflate=1.02, mirror=True), "armor." + chest))
    if legs:
        lp = armor_png(legs, 'humanoid_leggings')
        # The two leg pieces overlap at the centre line (x -0.5..0.5) and, at the game's 0.5,
        # their inner faces sit exactly on the other leg's skin: that flickers. Slightly larger
        # (0.6 / 0.65), and leg_piece keeps the left and right pieces' planes apart.
        parts.append((Part(name + ".legs.body", lp, A, 'body', ARMOR_MAT)
                      .box((16, 16), (-4, 0, -3), (8, 12, 6), inflate=0.6, uvsize=(8, 12, 4)), "armor_legs." + legs))
        parts.append((Part(name + ".legs.R", lp, A, 'leg.R', ARMOR_MAT)
                      .box((0, 16), *leg_piece('R', 0.65), pivot=(-2, 12, 0), inflate=0.65, uvsize=(4, 12, 4)), "armor_legs." + legs))
        parts.append((Part(name + ".legs.L", lp, A, 'leg.L', ARMOR_MAT)
                      .box((0, 16), *leg_piece('L', 0.65), pivot=(2, 12, 0), inflate=0.65, uvsize=(4, 12, 4), mirror=True), "armor_legs." + legs))
    if boots:
        parts.append((Part(name + ".boot.R", armor_png(boots), A, 'leg.R', ARMOR_MAT)
                      .box((0, 16), *leg_piece('R', 1.04, gap=0.1), pivot=(-2, 12, 0), inflate=1.04, uvsize=(4, 12, 4)), "armor." + boots))
        parts.append((Part(name + ".boot.L", armor_png(boots), A, 'leg.L', ARMOR_MAT)
                      .box((0, 16), *leg_piece('L', 1.04, gap=0.1), pivot=(2, 12, 0), inflate=1.04, uvsize=(4, 12, 4), mirror=True), "armor." + boots))
    if elytra:
        ep = os.path.join(TEX, "entity", "equipment", "wings", "elytra.png")
        # built unrotated; the pose (closed / gliding / crouching) is set on the wing bones
        parts.append((Part(name + ".wing.L", ep, A, 'wing.L', dict(rough=0.7, spec=0.2))
                      .box((22, 0), (-10, 0, 0), (10, 20, 2), pivot=(5, 0, 3), inflate=1.0), "elytra"))
        parts.append((Part(name + ".wing.R", ep, A, 'wing.R', dict(rough=0.7, spec=0.2))
                      .box((22, 0), (0, 0, 0), (10, 20, 2), pivot=(-5, 0, 3), inflate=1.0, mirror=True), "elytra"))

    for part, mname in parts:
        ob = part.build(col, mname)
        parent_to_bone(ob, rig, part.bone)

    if item_r:
        attach_item(name, rig, col, item_r)

    if elytra:
        set_wing_pose(rig, *WING_STAND)
    rig.location = location
    rig["mc_character"] = dict(skin=skin, helmet=helmet or "", chest=chest or "", legs=legs or "",
                               boots=boots or "", elytra=elytra, item_r=item_r or "")
    return rig


def attach_item(name, rig, col, item_r):
    """Item in the right fist (rest pose), parented to hand.R. Villager and player share the
    right arm's centre line (x = -6 px), so the same placement serves both."""
    grip = ITEM_GRIP.get(item_r, (8, 8))
    it = item_mesh(name + ".item.R", os.path.join(TEX, "item", item_r + ".png"), col, grip=grip)
    # held like a tool: grip in the fist, sprite in the side plane, pointing forward.
    # The sprite is turned 180 deg about its own handle so the head faces away from the body.
    hx, hy = ITEM_HANDLE.get(item_r, (6, 8))
    handle = Vector((hx, 0, hy)).normalized()
    saved = rig.matrix_world.copy()
    rig.matrix_world = Matrix.Identity(4)
    bpy.context.view_layer.update()
    it.matrix_world = (Matrix.Translation(m2b((-6, 11, -0.5)))
                       @ Matrix.Rotation(math.radians(40), 4, 'X')
                       @ Matrix.Rotation(math.radians(-90), 4, 'Z')
                       @ Matrix.Rotation(math.pi, 4, handle)
                       @ Matrix.Scale(0.85, 4))
    bpy.context.view_layer.update()
    mw = it.matrix_world.copy()
    parent_to_bone(it, rig, 'hand.R')
    it.matrix_world = mw
    rig.matrix_world = saved
    bpy.context.view_layer.update()
    return it


# ------------------------------------------------------------------ player (Steve / Alex skins)
# From net.minecraft.client.model.player.PlayerModel.createMesh + HumanoidModel (26.2, javap):
# head 8x8x8, body 8x12x4, arms 4x12x4 (wide) / 3x12x4 (slim) at (+-5, 2), legs at (+-1.9, 12);
# a second skin layer (hat 0.5, jacket/sleeves/pants 0.25) and own left-limb textures.
# AvatarRenderer.scale: the whole model is drawn at 0.9375 (1.875 blocks tall).
# Armor (LayerDefinitions + HumanoidModel.createBaseArmorMesh): outer 1.0 (helmet, chestplate,
# boots), inner 0.5 (leggings), and on the legs extend(-0.1): leggings 0.4, boots 0.9.
PLAYER_SCALE = 0.9375
PLAYER_BONES = dict(BONES)
PLAYER_BONES.update({
    'leg.R':  ((-1.9, 12, 0), (-1.9, 24, 0), 'root'),
    'leg.L':  ((1.9, 12, 0), (1.9, 24, 0), 'root'),
    'wing.R': ((-5, 0, 2), (-5, 10, 2), 'body'),      # WingsLayer: translate(0, 0, 0.125)
    'wing.L': ((5, 0, 2), (5, 10, 2), 'body'),
})


def _has_pixels(png, x0, y0, w, h):
    im = image(png)
    W, H = im.size
    px = im.pixels[:]
    return any(px[((H - 1 - y) * W + x) * 4 + 3] > 0.01
               for y in range(y0, y0 + h) for x in range(x0, x0 + w))


def player(name="Steve", skin=os.path.join(TEX, "entity", "player", "wide", "steve.png"), slim=False,
           helmet=None, chest=None, legs=None, boots=None, elytra=False, item_r=None,
           location=(0, 0, 0)):
    """Build a player-model character (default Steve, wide arms) with optional armor.
    Inflations differ from the game's by hundredths of a pixel so that no two visible faces
    share a plane (game value in brackets): sleeves 0.26 (0.25), pants 0.27 (0.25), helmet 1.05
    (1.0), chestplate arms 1.02 (1.0), leggings body 0.6 (0.5); left-leg boxes are 0.01 deeper
    than the right ones (leg_piece), so the pieces overlapping at the centre never share a plane."""
    col = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(col)
    rig = make_rig(name + ".rig", col, PLAYER_BONES)
    S = (64, 64)
    mskin = "skin." + os.path.splitext(os.path.basename(skin))[0] + (".slim" if slim else ".wide")
    aw = 3 if slim else 4                    # arm width
    parts = []

    def P(pname, bone, tex=skin, wh=S, kw=None):
        return Part(name + "." + pname, tex, wh, bone, kw)

    def overlay(uv, w, h):                   # build a second-layer box only if it has pixels
        return _has_pixels(skin, uv[0], uv[1], w, h)

    parts.append((P("head", 'head').box((0, 0), (-4, -8, -4), (8, 8, 8)), mskin))
    if overlay((32, 0), 32, 16):
        parts.append((P("hat", 'head').box((32, 0), (-4, -8, -4), (8, 8, 8), inflate=0.5), mskin))
    parts.append((P("body", 'body').box((16, 16), (-4, 0, -2), (8, 12, 4)), mskin))
    if overlay((16, 32), 24, 16):
        parts.append((P("jacket", 'body').box((16, 32), (-4, 0, -2), (8, 12, 4), inflate=0.25), mskin))
    # arms: right (40,16) / sleeve (40,32), left (32,48) / sleeve (48,48); slim arms are 3 wide
    rx = -2 if slim else -3
    parts.append((P("arm.R", 'arm.R').box((40, 16), (rx, -2, -2), (aw, 12, 4), pivot=(-5, 2, 0)), mskin))
    parts.append((P("arm.L", 'arm.L').box((32, 48), (-1, -2, -2), (aw, 12, 4), pivot=(5, 2, 0)), mskin))
    if overlay((40, 32), 16, 16):
        parts.append((P("sleeve.R", 'arm.R').box((40, 32), (rx, -2, -2), (aw, 12, 4), pivot=(-5, 2, 0), inflate=0.26), mskin))
    if overlay((48, 48), 16, 16):
        parts.append((P("sleeve.L", 'arm.L').box((48, 48), (-1, -2, -2), (aw, 12, 4), pivot=(5, 2, 0), inflate=0.26), mskin))
    # legs at +-1.9 overlap by 0.2 px at the centre: leg_piece keeps their planes apart
    for side, uv, puv, px in (('R', (0, 16), (0, 32), -1.9), ('L', (16, 48), (0, 48), 1.9)):
        parts.append((P("leg." + side, 'leg.' + side)
                      .box(uv, *leg_piece(side, 0.0, gap=0.02, pivot_x=1.9), pivot=(px, 12, 0), uvsize=(4, 12, 4)), mskin))
        if overlay(puv, 16, 16):
            parts.append((P("pants." + side, 'leg.' + side)
                          .box(puv, *leg_piece(side, 0.27, gap=0.04, pivot_x=1.9), pivot=(px, 12, 0),
                               inflate=0.27, uvsize=(4, 12, 4)), mskin))

    A = (64, 32)

    def armor_png(mat, layer='humanoid'):
        return os.path.join(TEX, "entity", "equipment", layer, mat + ".png")

    if helmet:
        parts.append((P("helmet", 'head', armor_png(helmet), A, ARMOR_MAT)
                      .box((0, 0), (-4, -8, -4), (8, 8, 8), inflate=1.05), "armor." + helmet))
    if chest:
        cp = armor_png(chest)
        parts.append((P("chest", 'body', cp, A, ARMOR_MAT).box((16, 16), (-4, 0, -2), (8, 12, 4), inflate=1.0), "armor." + chest))
        parts.append((P("chest.arm.R", 'arm.R', cp, A, ARMOR_MAT)
                      .box((40, 16), (-3, -2, -2), (4, 12, 4), pivot=(-5, 2, 0), inflate=1.02), "armor." + chest))
        parts.append((P("chest.arm.L", 'arm.L', cp, A, ARMOR_MAT)
                      .box((40, 16), (-1, -2, -2), (4, 12, 4), pivot=(5, 2, 0), inflate=1.02, mirror=True), "armor." + chest))
    if legs:
        lp = armor_png(legs, 'humanoid_leggings')
        parts.append((P("legs.body", 'body', lp, A, ARMOR_MAT)
                      .box((16, 16), (-4, 0, -2), (8, 12, 4), inflate=0.6), "armor_legs." + legs))
        for side, px in (('R', -1.9), ('L', 1.9)):
            parts.append((P("legs." + side, 'leg.' + side, lp, A, ARMOR_MAT)
                          .box((0, 16), *leg_piece(side, 0.4, gap=0.06, pivot_x=1.9), pivot=(px, 12, 0),
                               inflate=0.4, uvsize=(4, 12, 4), mirror=(side == 'L')), "armor_legs." + legs))
    if boots:
        for side, px in (('R', -1.9), ('L', 1.9)):
            parts.append((P("boot." + side, 'leg.' + side, armor_png(boots), A, ARMOR_MAT)
                          .box((0, 16), *leg_piece(side, 0.9, gap=0.1, pivot_x=1.9), pivot=(px, 12, 0),
                               inflate=0.9, uvsize=(4, 12, 4), mirror=(side == 'L')), "armor." + boots))
    if elytra:
        ep = os.path.join(TEX, "entity", "equipment", "wings", "elytra.png")
        parts.append((P("wing.L", 'wing.L', ep, A, dict(rough=0.7, spec=0.2))
                      .box((22, 0), (-10, 0, 0), (10, 20, 2), pivot=(5, 0, 2), inflate=1.0), "elytra"))
        parts.append((P("wing.R", 'wing.R', ep, A, dict(rough=0.7, spec=0.2))
                      .box((22, 0), (0, 0, 0), (10, 20, 2), pivot=(-5, 0, 2), inflate=1.0, mirror=True), "elytra"))

    for part, mname in parts:
        parent_to_bone(part.build(col, mname), rig, part.bone)
    if item_r:
        attach_item(name, rig, col, item_r)
    if elytra:
        set_wing_pose(rig, *WING_STAND)
    rig.scale = (PLAYER_SCALE,) * 3
    rig.location = location
    rig["mc_character"] = dict(kind="player", skin=skin, slim=slim, helmet=helmet or "", chest=chest or "",
                               legs=legs or "", boots=boots or "", elytra=elytra, item_r=item_r or "")
    return rig


# ------------------------------------------------------------------ baby villager (26.x model)
# From net.minecraft.client.model.npc.BabyVillagerModel.createBodyModel (26.2, read with javap):
# 1 block tall, own texture layout (villager_baby.png + baby/<type>.png), arms crossed at -60 deg.
BABY_BONES = {
    'root':  ((0, 24, 0), (0, 24, 6), None),
    'body':  ((0, 21, 0), (0, 16, 0), 'root'),
    'head':  ((0, 16, 0), (0, 8, 0), 'body'),
    'arms':  ((0, 17.5, 0), (0, 20, -3), 'body'),
    'leg.R': ((-1, 21.5, 0), (-1, 24, 0), 'root'),
    'leg.L': ((1, 21.5, 0), (1, 24, 0), 'root'),
}


def baby_villager(name="Child", skin="baby_plains", hat=False, location=(0, 0, 0)):
    col = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(col)
    rig = make_rig(name + ".rig", col, BABY_BONES)
    png = os.path.join(CHARS, skin + ".png")
    S, m = (64, 64), "skin." + skin
    a60 = -1.0472
    parts = [
        (Part(name + ".head", png, S, 'head')
         .box((0, 0), (-4, -8, -3.5), (8, 8, 7), pivot=(0, 16, 0))
         .box((23, 0), (-1, 0, -0.5), (2, 2, 1), pivot=(0, 14, -4)), m),               # nose
        (Part(name + ".body", png, S, 'body')
         .box((0, 15), (-2, -2.75, -1.5), (4, 5, 3), pivot=(0, 18.75, 0))
         .box((16, 21), (-2.5, -8, -1.5), (4, 6, 3), pivot=(0.5, 24, 0), inflate=0.2), m),  # jacket
        (Part(name + ".arms", png, S, 'arms')
         .box((36, 15), (-1, -2.4925, -1.8401), (2, 4, 2), pivot=(-3, 18.9025, -0.9599), rot=(a60, 0, 0))
         .box((16, 15), (5, -2.4925, -1.8401), (2, 4, 2), pivot=(-3, 18.9025, -0.9599), rot=(a60, 0, 0))
         .box((24, 17), (-2, -0.9924, -0.9825), (4, 2, 2), pivot=(0, 18.4024, -1.8175), rot=(a60, 0, 0)), m),
        (Part(name + ".leg.R", png, S, 'leg.R').box((8, 23), (-1, -0.5, -1), (2, 3, 2), pivot=(-1, 21.5, 0)), m),
        (Part(name + ".leg.L", png, S, 'leg.L').box((0, 23), (-1, -0.5, -1), (2, 3, 2), pivot=(1, 21.5, 0)), m),
    ]
    if hat:
        parts.append((Part(name + ".hat", png, S, 'head')
                      .box((0, 30), (-4, -4, -3.5), (8, 8, 7), pivot=(0, 12, 0), inflate=0.3)
                      .box((0, 45), (-7, -0.5, -6), (14, 1, 12), pivot=(0, 11.5, 0)), m))
    for part, mname in parts:
        parent_to_bone(part.build(col, mname), rig, part.bone)
    rig.location = location
    rig["mc_character"] = dict(kind="baby_villager", skin=skin)
    return rig


# ------------------------------------------------------------------ checks
INTERIOR_OK = {('arm', 'body'), ('arms', 'body'), ('body', 'head'), ('body', 'leg'), ('leg', 'leg'),
               ('wing', 'wing'), ('arm', 'wing'), ('leg', 'wing')}
# Wings are checked in the rest pose, where they hang straight down and share planes with each
# other and with the backs of the arms/legs; they are always posed (stand/glide/crouch) apart.


def coplanar_report(rig):
    """Pairs of axis-aligned faces of different parts that share a plane and overlap (rest pose).
    Contacts between bare body parts (arm/body, head/body, leg/body, leg/leg) are hidden inside
    the model, as in the game, and are skipped. Returns a list of (part_a, part_b, axis, px)."""
    from itertools import combinations
    saved = rig.data.pose_position
    rig.data.pose_position = 'REST'
    bpy.context.view_layer.update()
    inv = rig.matrix_world.inverted()

    def faces(ob):
        M = inv @ ob.matrix_world
        res = []
        for p in ob.data.polygons:
            vs = [M @ ob.data.vertices[i].co for i in p.vertices]
            n = (M.to_3x3() @ p.normal).normalized()
            ax = max(range(3), key=lambda i: abs(n[i]))
            if abs(n[ax]) > 0.999:
                lo = [min(v[i] for v in vs) for i in range(3)]
                hi = [max(v[i] for v in vs) for i in range(3)]
                res.append((ax, lo, hi))
        return res

    obs = [o for o in rig.children if o.type == 'MESH' and '.item.' not in o.name]
    F = {o.name: faces(o) for o in obs}
    kind = lambda o: o.name.split('.')[1]
    hits = set()
    for a, b in combinations(obs, 2):
        if tuple(sorted((kind(a), kind(b)))) in INTERIOR_OK:
            continue
        for ax, lo_a, hi_a in F[a.name]:
            for bx, lo_b, hi_b in F[b.name]:
                if ax != bx or abs(lo_a[ax] - lo_b[ax]) > 1e-5:
                    continue
                if all(min(hi_a[i], hi_b[i]) - max(lo_a[i], lo_b[i]) > 1e-5 for i in range(3) if i != ax):
                    hits.add((a.name, b.name, 'xyz'[ax], round(lo_a[ax] * 16, 2)))
    rig.data.pose_position = saved
    bpy.context.view_layer.update()
    return sorted(hits)
