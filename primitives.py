"""Blender writer and live editor for CPC mathematical profile primitives."""

import json
import math
import uuid
import bpy
from mathutils import Matrix, Vector

from . import primitive_geometry, junctions


PRIMITIVE_DEFAULT_ROLES = {
    "LINE": "fascia",
    "OVOLO": "ovolo",
    "CAVETTO": "cavetto",
    "TORUS": "torus",
    "CYMA_RECTA": "cyma_recta",
    "CYMA_REVERSA": "cyma_reversa",
    "CLASSICAL_SCOTIA": "classical_scotia",
}


def _v3(point):
    return Vector((point[0], point[1], 0.0))


def _spec_points(geometry):
    """Convert contiguous cubic segments to per-Bezier-point handle specs."""
    segments = geometry.segments
    if not segments:
        return []

    points = []
    first = segments[0]
    start_vec = _v3(first.h0) - _v3(first.p0)
    points.append({
        "co": _v3(first.p0),
        "left": _v3(first.p0) - start_vec,
        "right": _v3(first.h0),
        "left_type": 'VECTOR',
        "right_type": 'VECTOR' if geometry.straight else 'FREE',
    })

    for index in range(1, len(segments)):
        previous = segments[index - 1]
        current = segments[index]
        points.append({
            "co": _v3(previous.p1),
            "left": _v3(previous.h1),
            "right": _v3(current.h0),
            "left_type": 'FREE',
            "right_type": 'FREE',
        })

    last = segments[-1]
    end_vec = _v3(last.p1) - _v3(last.h1)
    points.append({
        "co": _v3(last.p1),
        "left": _v3(last.h1),
        "right": _v3(last.p1) + end_vec,
        "left_type": 'VECTOR' if geometry.straight else 'FREE',
        "right_type": 'VECTOR',
    })
    return points


def _curve_from_geometry(geometry):
    curve = bpy.data.curves.new(name=f"CPC_{geometry.primitive_id}_Curve", type='CURVE')
    curve.dimensions = '2D'
    curve.resolution_u = 12
    curve.render_resolution_u = 24

    spline = curve.splines.new('BEZIER')
    specs = _spec_points(geometry)
    spline.bezier_points.add(len(specs) - 1)

    for bp, spec in zip(spline.bezier_points, specs):
        bp.co = spec["co"]
        bp.handle_left = spec["left"]
        bp.handle_right = spec["right"]
    for bp, spec in zip(spline.bezier_points, specs):
        bp.handle_left_type = spec["left_type"]
        bp.handle_right_type = spec["right_type"]
    return curve


def _endpoint_local(obj, endpoint_index):
    if not obj or obj.type != 'CURVE' or not obj.data.splines:
        return Vector((0.0, 0.0, 0.0))
    spline = obj.data.splines[0]
    if spline.type == 'BEZIER' and spline.bezier_points:
        return spline.bezier_points[0 if endpoint_index == 0 else -1].co.copy()
    if spline.points:
        return Vector(spline.points[0 if endpoint_index == 0 else -1].co[:3])
    return Vector((0.0, 0.0, 0.0))


def ensure_component_id(obj):
    """Return a persistent semantic ID for a construction component."""
    if not obj:
        return ""
    component_id = str(obj.get("cpc_component_id", "")).strip()
    if not component_id:
        component_id = f"cpc-{uuid.uuid4()}"
        obj["cpc_component_id"] = component_id
    return component_id


def _write_metadata(obj, geometry):
    ensure_component_id(obj)
    obj["cpc_parametric"] = True
    obj["cpc_primitive_id"] = geometry.primitive_id
    obj["cpc_primitive_name"] = geometry.display_name
    if not str(obj.get("cpc_role", "") or "").strip():
        obj["cpc_role"] = PRIMITIVE_DEFAULT_ROLES.get(geometry.primitive_id, geometry.primitive_id.lower())
    obj["cpc_construction"] = geometry.construction
    obj["cpc_start_tangent"] = tuple(geometry.start_tangent)
    obj["cpc_end_tangent"] = tuple(geometry.end_tangent)
    obj["cpc_start_join"] = geometry.start_join
    obj["cpc_end_join"] = geometry.end_join
    obj["cpc_parameters"] = json.dumps(geometry.parameters, sort_keys=True)


def _initialise_edit_properties(
    obj, width, height, shape_mode, bias, fullness=1.0, concave_fullness=1.0, convex_fullness=1.0,
    arc_construction_mode="FULLNESS", arc_depth=None,
):
    """Set RNA edit properties without triggering a rebuild during creation."""
    if not hasattr(obj, "cpc_param_width"):
        return
    obj["_cpc_param_initializing"] = True
    try:
        obj.cpc_param_width = float(width)
        obj.cpc_param_height = float(height)
        obj.cpc_param_shape_mode = str(shape_mode)
        obj.cpc_param_bias = float(bias)
        if hasattr(obj, "cpc_param_fullness"):
            obj.cpc_param_fullness = float(fullness)
            obj.cpc_param_concave_fullness = float(concave_fullness)
            obj.cpc_param_convex_fullness = float(convex_fullness)
        if hasattr(obj, "cpc_param_arc_construction_mode"):
            obj.cpc_param_arc_construction_mode = str(arc_construction_mode or "FULLNESS")
            obj.cpc_param_arc_depth = float(
                arc_depth if arc_depth is not None else primitive_geometry.default_arc_depth(width)
            )
    finally:
        obj["_cpc_param_initializing"] = False




def _component_objects():
    """Return placed CPC construction components participating in endpoint junctions."""
    return junctions.component_objects()


def _endpoint_frame_world(obj, endpoint_index):
    """Return world endpoint position and outward tangent in the profile XY plane."""
    from . import library

    position = library.object_endpoint_world(obj, endpoint_index).copy()
    outward = library.object_endpoint_outward_world(obj, endpoint_index).copy()
    outward.z = 0.0
    if outward.length > 1.0e-10:
        outward.normalize()
    return position, outward


def _junction_snapshot(objects=None):
    """Capture endpoint and hosted-midpoint frames before a semantic edit."""
    objects = list(objects if objects is not None else _component_objects())
    snapshot = {}
    for obj in objects:
        component_id = ensure_component_id(obj)
        entry = {
            0: _endpoint_frame_world(obj, 0),
            1: _endpoint_frame_world(obj, 1),
        }
        midpoint_frame = junctions.curve_frame_world(obj, 0.5)
        if midpoint_frame is not None:
            entry["host_midpoint"] = midpoint_frame
        snapshot[component_id] = entry
    return snapshot


def _allowed_junction_member(root_obj, candidate, *, include_external=True, internal_instance_id=""):
    if include_external:
        return True
    internal_instance_id = str(internal_instance_id or "")
    if not internal_instance_id:
        return False
    return str(candidate.get("cpc_arch_instance_id", "") or "") == internal_instance_id


def _reachable_from_endpoint(
    root_obj,
    moving_endpoint,
    *,
    include_external=True,
    internal_instance_id="",
    tolerance=0.0005,
    snapshot=None,
):
    """Return parts that follow the selected moving side, including hosted branches."""
    objects = _component_objects()
    members = junctions.members_map(objects)
    snapshot = snapshot or _junction_snapshot(objects)
    tolerance = max(float(tolerance), 1.0e-6)
    root_id = ensure_component_id(root_obj)
    seen = {root_id}
    result = []
    endpoint_stack = [(root_obj, 1 if int(moving_endpoint) else 0)]
    host_stack = [root_obj]
    hosts_processed = set()

    while endpoint_stack or host_stack:
        if host_stack:
            host = host_stack.pop()
            host_id = ensure_component_id(host)
            if host_id not in hosts_processed:
                hosts_processed.add(host_id)
                old_host_frame = snapshot.get(host_id, {}).get("host_midpoint")
                if old_host_frame:
                    old_host_pos, _old_host_tangent = old_host_frame
                    for guest, guest_endpoint, record in junctions.hosted_children(host, objects):
                        guest_id = ensure_component_id(guest)
                        if guest_id in seen:
                            continue
                        if not _allowed_junction_member(
                            root_obj, guest, include_external=include_external,
                            internal_instance_id=internal_instance_id,
                        ):
                            continue
                        if abs(float(record.get("fraction", 0.5)) - 0.5) > 1.0e-9:
                            continue
                        guest_before = snapshot.get(guest_id, {}).get(guest_endpoint)
                        if not guest_before:
                            continue
                        old_guest_pos, _ = guest_before
                        if (old_guest_pos - old_host_pos).length > tolerance:
                            continue
                        seen.add(guest_id)
                        result.append(guest)
                        endpoint_stack.append((guest, 1 - int(guest_endpoint)))
                        host_stack.append(guest)

        if not endpoint_stack:
            continue

        driver, driver_endpoint = endpoint_stack.pop()
        junction_id = junctions.endpoint_id(driver, driver_endpoint)
        if not junction_id:
            continue
        driver_before = snapshot.get(ensure_component_id(driver), {}).get(driver_endpoint)
        if not driver_before:
            continue
        old_driver_pos, _old_driver_out = driver_before
        for candidate, candidate_endpoint in members.get(junction_id, ()):
            candidate_id = ensure_component_id(candidate)
            if candidate_id in seen:
                continue
            if not _allowed_junction_member(
                root_obj, candidate, include_external=include_external,
                internal_instance_id=internal_instance_id,
            ):
                continue
            candidate_before = snapshot.get(candidate_id, {}).get(candidate_endpoint)
            if not candidate_before:
                continue
            old_candidate_pos, _ = candidate_before
            if (old_candidate_pos - old_driver_pos).length > tolerance:
                continue
            seen.add(candidate_id)
            result.append(candidate)
            endpoint_stack.append((candidate, 1 - int(candidate_endpoint)))
            host_stack.append(candidate)
    return result


def _frame_delta_matrix(old_position, old_outward, new_position, new_outward):
    """Rigid 2D transform carrying an old endpoint frame onto its regenerated frame."""
    old_vec = Vector((old_outward.x, old_outward.y))
    new_vec = Vector((new_outward.x, new_outward.y))
    angle = 0.0
    if old_vec.length > 1.0e-10 and new_vec.length > 1.0e-10:
        old_angle = math.atan2(old_vec.y, old_vec.x)
        new_angle = math.atan2(new_vec.y, new_vec.x)
        angle = new_angle - old_angle
    return (
        Matrix.Translation(new_position)
        @ Matrix.Rotation(angle, 4, 'Z')
        @ Matrix.Translation(-old_position)
    )


def _propagate_from_endpoint(
    root_obj,
    moving_endpoint,
    snapshot,
    *,
    tolerance=0.0005,
    include_external=True,
    internal_instance_id="",
):
    """Propagate a semantic edit through endpoint junctions and hosted branches.

    Endpoint junctions remain symmetric along the user's moving side. Hosted
    attachments are intentionally host-driven for semantic shape editing: when
    a host moves or deforms, its midpoint-attached branch follows the host frame
    while preserving the branch's relative orientation.  This is not a general
    bidirectional constraint solver.
    """
    objects = _component_objects()
    members = junctions.members_map(objects)
    tolerance = max(float(tolerance), 1.0e-6)
    root_id = ensure_component_id(root_obj)
    visited = {root_id}
    endpoint_stack = [(root_obj, 1 if int(moving_endpoint) else 0)]
    host_stack = [root_obj]
    hosts_processed = set()

    def move_object(child, delta):
        child.matrix_world = delta @ child.matrix_world
        child.update_tag()
        try:
            from . import connected_transforms
            connected_transforms.sync_object(child)
        except Exception:
            pass

    while endpoint_stack or host_stack:
        # Any moved/deformed host may have midpoint-attached branches.  These
        # are processed independently of which endpoint side caused the host to
        # move because an interior attachment belongs to the host geometry.
        if host_stack:
            host = host_stack.pop()
            host_id = ensure_component_id(host)
            if host_id in hosts_processed:
                continue
            hosts_processed.add(host_id)
            old_host_frame = snapshot.get(host_id, {}).get("host_midpoint")
            new_host_frame = junctions.curve_frame_world(host, 0.5)
            if old_host_frame and new_host_frame:
                old_host_pos, old_host_tangent = old_host_frame
                new_host_pos, new_host_tangent = new_host_frame
                host_delta = _frame_delta_matrix(
                    old_host_pos, old_host_tangent, new_host_pos, new_host_tangent
                )
                for guest, guest_endpoint, record in junctions.hosted_children(host, objects):
                    guest_id = ensure_component_id(guest)
                    if guest_id in visited:
                        continue
                    if not _allowed_junction_member(
                        root_obj,
                        guest,
                        include_external=include_external,
                        internal_instance_id=internal_instance_id,
                    ):
                        continue
                    guest_before = snapshot.get(guest_id, {}).get(guest_endpoint)
                    if not guest_before:
                        continue
                    old_guest_pos, _old_guest_out = guest_before
                    # CPC supports midpoint-hosted attachments
                    # only. The stored fraction is future-facing schema data.
                    if abs(float(record.get("fraction", 0.5)) - 0.5) > 1.0e-9:
                        continue
                    if (old_guest_pos - old_host_pos).length > tolerance:
                        continue
                    visited.add(guest_id)
                    move_object(guest, host_delta)
                    endpoint_stack.append((guest, 1 - int(guest_endpoint)))
                    host_stack.append(guest)

        if not endpoint_stack:
            continue

        driver, driver_endpoint = endpoint_stack.pop()
        driver_id = ensure_component_id(driver)
        junction_id = junctions.endpoint_id(driver, driver_endpoint)
        if not junction_id:
            continue

        old_driver_frame = snapshot.get(driver_id, {}).get(driver_endpoint)
        if not old_driver_frame:
            continue
        old_driver_pos, old_driver_out = old_driver_frame
        new_driver_pos, new_driver_out = _endpoint_frame_world(driver, driver_endpoint)
        delta = _frame_delta_matrix(
            old_driver_pos,
            old_driver_out,
            new_driver_pos,
            new_driver_out,
        )

        for child, child_endpoint in members.get(junction_id, ()):
            child_id = ensure_component_id(child)
            if child_id in visited:
                continue
            if not _allowed_junction_member(
                root_obj,
                child,
                include_external=include_external,
                internal_instance_id=internal_instance_id,
            ):
                continue

            child_before = snapshot.get(child_id, {}).get(child_endpoint)
            if not child_before:
                continue
            old_child_pos, _old_child_out = child_before

            # Stale junction IDs do not pull manually detached geometry back.
            if (old_child_pos - old_driver_pos).length > tolerance:
                continue

            visited.add(child_id)
            move_object(child, delta)
            endpoint_stack.append((child, 1 - int(child_endpoint)))
            host_stack.append(child)


def connected_moving_side_count(root_obj, tolerance=0.0005):
    """Count parts on the side that will follow the selected Edit Anchor."""
    if not root_obj:
        return 0
    anchor_index = 1 if int(root_obj.get("cpc_anchor_index", 0)) else 0
    snapshot = _junction_snapshot()
    return len(_reachable_from_endpoint(
        root_obj,
        1 - anchor_index,
        include_external=True,
        tolerance=tolerance,
        snapshot=snapshot,
    ))


def update_part_rotation(obj, context=None):
    """Apply the universal CPC local part-rotation offset.

    Rotation is incremental around the part's chosen CPC Edit Anchor. Endpoint
    junctions propagate the opposite side, independent of original placement
    direction; this is deliberately not a general CAD constraint solver.
    """
    if not obj or not obj.get("cpc_part") or not obj.get("cpc_parametric") or obj.get("cpc_preview"):
        return
    if obj.get("_cpc_part_transform_initializing") or obj.get("_cpc_part_transform_updating"):
        return

    current = float(getattr(obj, "cpc_part_rotation", 0.0))
    applied = float(obj.get("cpc_part_rotation_applied", 0.0))
    delta_angle = current - applied
    if abs(delta_angle) <= 1.0e-12:
        obj["cpc_part_rotation_applied"] = current
        obj["cpc_part_rotation_saved"] = current
        return

    settings = None
    if context is not None and getattr(context, "scene", None) is not None:
        settings = getattr(context.scene, "cpc_settings", None)
    maintain = bool(getattr(settings, "maintain_connected_parts", True))
    tolerance = float(getattr(settings, "merge_tolerance", 0.0005))
    instance_id = str(obj.get("cpc_arch_instance_id", "") or "")
    should_propagate = maintain or bool(instance_id)
    snapshot = _junction_snapshot() if should_propagate else {}

    from . import library
    obj["_cpc_part_transform_updating"] = True
    try:
        anchor_index = 1 if int(obj.get("cpc_anchor_index", 0)) else 0
        pivot = library.object_endpoint_world(obj, anchor_index).copy()
        delta = (
            Matrix.Translation(pivot)
            @ Matrix.Rotation(delta_angle, 4, 'Z')
            @ Matrix.Translation(-pivot)
        )
        obj.matrix_world = delta @ obj.matrix_world
        try:
            from . import connected_transforms
            connected_transforms.sync_object(obj)
        except Exception:
            pass
        obj["cpc_part_rotation_applied"] = current
        obj["cpc_part_rotation_saved"] = current
        obj.update_tag()
        if snapshot:
            _propagate_from_endpoint(
                obj,
                1 - anchor_index,
                snapshot,
                tolerance=tolerance,
                include_external=maintain,
                internal_instance_id=instance_id,
            )
        if context is not None:
            try:
                context.view_layer.update()
            except Exception:
                pass
    finally:
        obj["_cpc_part_transform_updating"] = False


def update_object_geometry(
    obj,
    *,
    width,
    height,
    shape_mode='CIRCLE',
    bias=0.5,
    fullness=1.0,
    concave_fullness=1.0,
    convex_fullness=1.0,
    arc_construction_mode='FULLNESS',
    arc_depth=None,
    preserve_anchor=True,
    propagate_connected=False,
    connection_tolerance=0.0005,
    anchor_index_override=None,
):
    """Regenerate a placed parametric component while keeping its placed anchor fixed."""
    if not obj or obj.type != 'CURVE' or not obj.get("cpc_parametric"):
        return None

    connection_snapshot = _junction_snapshot() if propagate_connected else {}

    primitive_id = str(obj.get("cpc_primitive_id", "LINE"))
    if anchor_index_override is None:
        anchor_index = 1 if int(obj.get("cpc_anchor_index", 0)) else 0
    else:
        anchor_index = 1 if int(anchor_index_override) else 0
    anchor_world = None
    if preserve_anchor:
        anchor_world = obj.matrix_world @ _endpoint_local(obj, anchor_index)

    geometry = primitive_geometry.generate(
        primitive_id,
        width=float(width),
        height=float(height),
        shape_mode=str(shape_mode),
        bias=float(bias),
        fullness=float(fullness),
        concave_fullness=float(concave_fullness),
        convex_fullness=float(convex_fullness),
        arc_construction_mode=str(arc_construction_mode),
        arc_depth=float(
            arc_depth
            if arc_depth is not None
            else primitive_geometry.default_arc_depth_for_primitive(primitive_id, width)
        ),
    )

    old_curve = obj.data
    obj.data = _curve_from_geometry(geometry)
    _write_metadata(obj, geometry)

    if (
        primitive_id in {"CYMA_RECTA", "CYMA_REVERSA"}
        and geometry.parameters.get("arc_construction_mode") == "ARC_DEPTH"
        and hasattr(obj, "cpc_param_arc_depth")
    ):
        was_initializing = bool(obj.get("_cpc_param_initializing", False))
        obj["_cpc_param_initializing"] = True
        try:
            obj.cpc_param_arc_depth = float(geometry.parameters["arc_depth"])
            obj.cpc_param_bias = float(geometry.parameters["bias"])
        finally:
            obj["_cpc_param_initializing"] = was_initializing

    if anchor_world is not None:
        new_anchor_world = obj.matrix_world @ _endpoint_local(obj, anchor_index)
        delta = anchor_world - new_anchor_world
        if delta.length_squared > 1.0e-20:
            matrix = obj.matrix_world.copy()
            matrix.translation = matrix.translation + delta
            obj.matrix_world = matrix
            try:
                from . import connected_transforms
                connected_transforms.sync_object(obj)
            except Exception:
                pass

    if connection_snapshot:
        _propagate_from_endpoint(
            obj,
            1 - anchor_index,
            connection_snapshot,
            tolerance=connection_tolerance,
            include_external=True,
            internal_instance_id=str(obj.get("cpc_arch_instance_id", "") or ""),
        )

    if old_curve and old_curve.users == 0 and old_curve.name in bpy.data.curves:
        bpy.data.curves.remove(old_curve)
    return geometry


def create_object(
    primitive_id, width, height, shape_mode='CIRCLE', bias=0.5,
    fullness=1.0, concave_fullness=1.0, convex_fullness=1.0,
    arc_construction_mode='FULLNESS', arc_depth=None,
):
    semantic_arc_depth = (
        float(arc_depth)
        if arc_depth is not None
        else primitive_geometry.default_arc_depth_for_primitive(primitive_id, width)
    )
    geometry = primitive_geometry.generate(
        primitive_id,
        width=width,
        height=height,
        shape_mode=shape_mode,
        bias=bias,
        fullness=fullness,
        concave_fullness=concave_fullness,
        convex_fullness=convex_fullness,
        arc_construction_mode=arc_construction_mode,
        arc_depth=semantic_arc_depth,
    )

    curve = _curve_from_geometry(geometry)
    obj = bpy.data.objects.new(f"CPC_Part_{primitive_id}", curve)
    _write_metadata(obj, geometry)
    _initialise_edit_properties(
        obj,
        geometry.parameters.get("width", width),
        geometry.parameters.get("height", height),
        geometry.parameters.get("shape_mode", shape_mode),
        geometry.parameters.get("bias", bias),
        geometry.parameters.get("fullness", fullness),
        geometry.parameters.get("concave_fullness", concave_fullness),
        geometry.parameters.get("convex_fullness", convex_fullness),
        geometry.parameters.get("arc_construction_mode", arc_construction_mode),
        geometry.parameters.get("arc_depth", semantic_arc_depth),
    )
    return obj
