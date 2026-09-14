import bpy
from mathutils import Vector


def display_name(name):
    return str(name or "").replace("_", " ").strip().title()


def ensure_builder_collection(scene):
    coll = bpy.data.collections.get("CPC_ProfileParts")
    if coll is None:
        coll = bpy.data.collections.new("CPC_ProfileParts")
        scene.collection.children.link(coll)
    return coll


def ensure_profile_collection(scene):
    coll = bpy.data.collections.get("CPC_Profiles")
    if coll is None:
        coll = bpy.data.collections.new("CPC_Profiles")
        scene.collection.children.link(coll)
    return coll


def ensure_sweep_collection(scene):
    coll = bpy.data.collections.get("CPC_Sweeps")
    if coll is None:
        coll = bpy.data.collections.new("CPC_Sweeps")
        scene.collection.children.link(coll)
    return coll


def relink_object(obj, collection):
    for coll in list(obj.users_collection):
        coll.objects.unlink(obj)
    if collection.objects.get(obj.name) is None:
        collection.objects.link(obj)


def curve_endpoint_local(obj, endpoint_index):
    if not obj or obj.type != 'CURVE' or not obj.data.splines:
        return Vector((0.0, 0.0, 0.0))
    spline = obj.data.splines[0]
    if spline.type == 'BEZIER' and spline.bezier_points:
        bp = spline.bezier_points[0 if endpoint_index == 0 else -1]
        return bp.co.copy()
    if spline.points:
        p = spline.points[0 if endpoint_index == 0 else -1]
        return Vector(p.co[:3])
    return Vector((0.0, 0.0, 0.0))


def curve_endpoint_interior_dir_local(obj, endpoint_index):
    """Direction from the chosen endpoint toward the interior of the spline."""
    if not obj or obj.type != 'CURVE' or not obj.data.splines:
        return Vector((1.0, 0.0, 0.0))
    spline = obj.data.splines[0]
    if spline.type == 'BEZIER' and len(spline.bezier_points) >= 2:
        if endpoint_index == 0:
            bp = spline.bezier_points[0]
            vec = bp.handle_right - bp.co
            if vec.length < 1e-8:
                vec = spline.bezier_points[1].co - bp.co
        else:
            bp = spline.bezier_points[-1]
            vec = bp.handle_left - bp.co
            if vec.length < 1e-8:
                vec = spline.bezier_points[-2].co - bp.co
        return vec.normalized() if vec.length else Vector((1.0, 0.0, 0.0))
    if len(spline.points) >= 2:
        if endpoint_index == 0:
            vec = Vector(spline.points[1].co[:3]) - Vector(spline.points[0].co[:3])
        else:
            vec = Vector(spline.points[-2].co[:3]) - Vector(spline.points[-1].co[:3])
        return vec.normalized() if vec.length else Vector((1.0, 0.0, 0.0))
    return Vector((1.0, 0.0, 0.0))


def object_endpoint_world(obj, endpoint_index):
    return obj.matrix_world @ curve_endpoint_local(obj, endpoint_index)


def object_endpoint_outward_world(obj, endpoint_index):
    local = curve_endpoint_interior_dir_local(obj, endpoint_index)
    world = obj.matrix_world.to_3x3() @ local
    if world.length < 1e-8:
        return Vector((1.0, 0.0, 0.0))
    return -world.normalized()
