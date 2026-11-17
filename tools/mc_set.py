"""Locations in Blender: import the OBJ that tools/build_set.py made from a set script, fix the
materials, and convert set coordinates. Run inside Blender.

    import mc_set as SET
    ob = SET.load("village")                 # object "Set.village"
    marks = SET.marks("village")             # assets/sets/village_marks.json, written by the set script
    cam.location = SET.b(232, 16, 216)       # block coordinates (X east, Y up, Z south) -> Blender

Set axes: X = east, Y = up, Z = south; block (x, y, z) fills x..x+1, y..y+1, z..z+1.
Blender (OBJ import, forward -Z, up Y): x = X, y = -Z, z = Y. A character standing on the block
whose top block is at height h has its feet at z = h + 1 (path and farmland blocks are 1/16 lower).
"""
import json
import os

import bpy
from mathutils import Vector

ROOT = r"C:\Dev\Projects\CinemaShort"
SETS = os.path.join(ROOT, "assets", "sets")


def b(x, y, z):
    """Set (block) coordinates -> Blender world coordinates."""
    return Vector((x, -z, y))


def stand(x, z, top_y, center=True):
    """Blender position of the feet of someone standing on the block column (x, z) whose top
    block is at top_y."""
    o = 0.5 if center else 0.0
    return Vector((x + o, -(z + o), top_y + 1.0))


def ground(x, z, name="village", top=400.0):
    """Set Y of the walkable surface at set column (x, z): a ray straight down through the scene
    that only counts hits on "Set.<name>" (sky, cameras and actors are skipped). Grass and flowers
    count too, so a hit on a plant is up to a block above the ground under it. None off the set.
    Use it for camera heights: the land is not flat (HANDOFF pitfall 25)."""
    sc = bpy.context.scene
    dg = bpy.context.evaluated_depsgraph_get()
    target = bpy.data.objects["Set." + name]
    origin, down = Vector((x, -z, top)), Vector((0.0, 0.0, -1.0))
    for _ in range(64):
        hit, loc, _n, _i, ob, _m = sc.ray_cast(dg, origin, down)
        if not hit:
            return None
        if ob.original == target:
            return loc.z
        origin = loc + down * 1e-3
    return None


def marks(name):
    with open(os.path.join(SETS, name + "_marks.json"), encoding="utf-8") as fh:
        return json.load(fh)


def load(name, collection=None):
    """Import assets/sets/obj/<name>.obj as "Set.<name>" (replacing an earlier import) and run
    MCprep's material prep the safe way (HANDOFF pitfall 6: no animated textures, no texture
    swapping, no material sync, or MCprep substitutes its own old pack)."""
    old = bpy.data.objects.get("Set." + name)
    if old is not None:
        me = old.data
        bpy.data.objects.remove(old, do_unlink=True)
        if me.users == 0:
            bpy.data.meshes.remove(me)
    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=os.path.join(SETS, "obj", name + ".obj"), forward_axis='NEGATIVE_Z', up_axis='Y')
    new = [o for o in bpy.data.objects if o not in before]
    bpy.ops.object.select_all(action='DESELECT')
    for o in new:
        o.select_set(True)
    bpy.context.view_layer.objects.active = new[0]
    if len(new) > 1:
        bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = "Set." + name
    bpy.ops.mcprep.prep_materials(animateTextures=False, autoFindMissingTextures=False, improveUiSettings=False,
                                  syncMaterials=False, useExtraMaps=False)
    if collection is not None:
        for c in list(ob.users_collection):
            c.objects.unlink(ob)
        collection.objects.link(ob)
    ob.select_set(False)
    return ob
