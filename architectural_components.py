"""Blender integration for CPC packed Architectural and Constructed components."""

import json
import uuid
import bpy
from mathutils import Matrix, Vector

from . import architectural_recipes, constructed_shapes, junctions, library, primitives


def scene_parameters(settings, component_id=None):
    if component_id is None:
        component_id = (
            settings.constructed_shape
            if str(getattr(settings, "construction_kind", "BASIC")) == "CONSTRUCTED"
            else settings.arch_component
        )
    return architectural_recipes.normalize_parameters(component_id, {
        "width": settings.arch_width,
        "height": settings.arch_height,
        "fullness": settings.arch_fullness,
        "arc_construction_mode": settings.arch_arc_construction_mode,
        "arc_depth": settings.arch_arc_depth,
        "secondary_arc_depth": settings.arch_secondary_arc_depth,
        "bias": settings.arch_bias,
        "concave_fullness": settings.arch_concave_fullness,
        "convex_fullness": settings.arch_convex_fullness,
        "fillet_a": settings.arch_fillet_a,
        "fillet_b": settings.arch_fillet_b,
        "equal_fillets": settings.arch_equal_fillets,
        "fascia": settings.arch_fascia,
        "secondary_width": settings.arch_secondary_width,
        "secondary_height": settings.arch_secondary_height,
        "secondary_fullness": settings.arch_secondary_fullness,
        "tread1": settings.arch_tread1,
        "rise1": settings.arch_rise1,
        "tread2": settings.arch_tread2,
        "rise2": settings.arch_rise2,
        "equal_steps": settings.arch_equal_steps,
    })


def _matrix_2d(tx, ty, angle):
    return Matrix.Translation((tx, ty, 0.0)) @ Matrix.Rotation(angle, 4, 'Z')


def _create_proxy_curve(component_id, params):
    info = architectural_recipes.bounds_and_endpoints(component_id, params)
    if not info:
        raise ValueError("Architectural Component produced no layout")
    start = Vector((info["start"][0], info["start"][1], 0.0))
    end = Vector((info["end"][0], info["end"][1], 0.0))
    start_tan = Vector((info["start_tangent"][0], info["start_tangent"][1], 0.0))
    end_tan = Vector((info["end_tangent"][0], info["end_tangent"][1], 0.0))
    chord = max((end - start).length, 0.01)
    handle = chord / 3.0

    curve = bpy.data.curves.new(name="CPC_ArchitecturalProxy_Curve", type='CURVE')
    curve.dimensions = '2D'
    spline = curve.splines.new('BEZIER')
    spline.bezier_points.add(1)
    a, b = spline.bezier_points
    a.co = start
    a.handle_left = start - start_tan.normalized() * handle if start_tan.length else start
    a.handle_right = start + start_tan.normalized() * handle if start_tan.length else start
    b.co = end
    b.handle_left = end - end_tan.normalized() * handle if end_tan.length else end
    b.handle_right = end + end_tan.normalized() * handle if end_tan.length else end
    for bp in (a, b):
        bp.handle_left_type = 'FREE'
        bp.handle_right_type = 'FREE'
    return bpy.data.objects.new("CPC_ArchitecturalProxy", curve)


def refresh_preview(proxy, parts, component_id, params):
    """Regenerate an Architectural Component placement preview in place.

    Used by Arc Depth interaction so the complete packed recipe
    can change while the placement modal retains its target/rotation state.
    Returns the refreshed local matrices in construction order.
    """
    layout = architectural_recipes.layout_recipe(component_id, params)
    if len(parts or ()) != len(layout):
        raise ValueError("Architectural preview part count changed unexpectedly")

    local_matrices = []
    for obj, item in zip(parts, layout):
        p = item.part.parameters
        obj["_cpc_param_initializing"] = True
        try:
            obj.cpc_param_width = float(p.get("width", 0.05))
            obj.cpc_param_height = float(p.get("height", 0.025))
            obj.cpc_param_shape_mode = str(p.get("shape_mode", "CIRCLE"))
            obj.cpc_param_bias = float(p.get("bias", 0.5))
            obj.cpc_param_fullness = float(p.get("fullness", 1.0))
            obj.cpc_param_concave_fullness = float(p.get("concave_fullness", 1.0))
            obj.cpc_param_convex_fullness = float(p.get("convex_fullness", 1.0))
            obj.cpc_param_arc_construction_mode = str(p.get("arc_construction_mode", "FULLNESS"))
            obj.cpc_param_arc_depth = float(p.get("arc_depth", 0.01))
        finally:
            obj["_cpc_param_initializing"] = False

        primitives.update_object_geometry(
            obj,
            width=float(p.get("width", 0.05)),
            height=float(p.get("height", 0.025)),
            shape_mode=str(p.get("shape_mode", "CIRCLE")),
            bias=float(p.get("bias", 0.5)),
            fullness=float(p.get("fullness", 1.0)),
            concave_fullness=float(p.get("concave_fullness", 1.0)),
            convex_fullness=float(p.get("convex_fullness", 1.0)),
            arc_construction_mode=str(p.get("arc_construction_mode", "FULLNESS")),
            arc_depth=float(p.get("arc_depth", 0.01)),
            preserve_anchor=False,
            propagate_connected=False,
        )
        obj["cpc_role"] = item.part.role
        local_m = _matrix_2d(item.translation[0], item.translation[1], item.rotation)
        obj.matrix_world = local_m
        local_matrices.append(local_m)

    new_proxy = _create_proxy_curve(component_id, params)
    old_data = proxy.data
    proxy.data = new_proxy.data
    bpy.data.objects.remove(new_proxy, do_unlink=True)
    if old_data and old_data.users == 0 and old_data.name in bpy.data.curves:
        bpy.data.curves.remove(old_data)
    return local_matrices


def create_preview(context, component_id, params):
    layout = architectural_recipes.layout_recipe(component_id, params)
    coll = library.ensure_builder_collection(context.scene)
    instance_id = f"arch-{uuid.uuid4()}"
    parts = []
    local_matrices = []
    label = architectural_recipes.display_name(component_id)

    for index, item in enumerate(layout):
        p = item.part.parameters
        obj = primitives.create_object(
            item.part.primitive_id,
            float(p.get("width", 0.05)),
            float(p.get("height", 0.025)),
            shape_mode=str(p.get("shape_mode", "CIRCLE")),
            bias=float(p.get("bias", 0.5)),
            fullness=float(p.get("fullness", 1.0)),
            concave_fullness=float(p.get("concave_fullness", 1.0)),
            convex_fullness=float(p.get("convex_fullness", 1.0)),
            arc_construction_mode=str(p.get("arc_construction_mode", "FULLNESS")),
            arc_depth=float(p.get("arc_depth", 0.01)),
        )
        library.relink_object(obj, coll)
        obj.name = f"CPC_{label.replace(' ', '_').replace('/', '_')}_{index + 1:02d}"
        obj["cpc_part"] = True
        obj["cpc_preview"] = True
        obj["cpc_role"] = item.part.role
        obj["cpc_arch_component"] = True
        obj["cpc_arch_component_id"] = component_id
        obj["cpc_arch_component_name"] = label
        obj["cpc_component_group"] = architectural_recipes.component_group(component_id)
        obj["cpc_arch_instance_id"] = instance_id
        obj["cpc_arch_part_index"] = index
        obj["cpc_arch_controller"] = (index == 0)
        obj.show_in_front = True
        local_m = _matrix_2d(item.translation[0], item.translation[1], item.rotation)
        obj.matrix_world = local_m
        parts.append(obj)
        local_matrices.append(local_m)

    proxy = _create_proxy_curve(component_id, params)
    return proxy, parts, local_matrices, instance_id


def controller_for(obj):
    if not obj or not obj.get("cpc_arch_instance_id"):
        return None
    instance_id = str(obj.get("cpc_arch_instance_id", ""))
    coll = bpy.data.collections.get("CPC_ProfileParts")
    if not coll:
        return obj if obj.get("cpc_arch_controller") else None
    fallback = None
    for candidate in coll.objects:
        if str(candidate.get("cpc_arch_instance_id", "")) != instance_id:
            continue
        fallback = fallback or candidate
        if candidate.get("cpc_arch_controller"):
            return candidate
    return fallback


def instance_parts(obj_or_instance):
    instance_id = obj_or_instance if isinstance(obj_or_instance, str) else str(obj_or_instance.get("cpc_arch_instance_id", ""))
    if not instance_id:
        return []
    coll = bpy.data.collections.get("CPC_ProfileParts")
    if not coll:
        return []
    return sorted(
        [obj for obj in coll.objects if str(obj.get("cpc_arch_instance_id", "")) == instance_id and obj.get("cpc_part")],
        key=lambda obj: int(obj.get("cpc_arch_part_index", 0)),
    )


def _params_from_controller(controller):
    return architectural_recipes.normalize_parameters(str(controller.get("cpc_arch_component_id", "")), {
        "width": controller.cpc_arch_width,
        "height": controller.cpc_arch_height,
        "fullness": controller.cpc_arch_fullness,
        "arc_construction_mode": controller.cpc_arch_arc_construction_mode,
        "arc_depth": controller.cpc_arch_arc_depth,
        "bias": controller.cpc_arch_bias,
        "concave_fullness": controller.cpc_arch_concave_fullness,
        "convex_fullness": controller.cpc_arch_convex_fullness,
        "fillet_a": controller.cpc_arch_fillet_a,
        "fillet_b": controller.cpc_arch_fillet_b,
        "equal_fillets": controller.cpc_arch_equal_fillets,
        "fascia": controller.cpc_arch_fascia,
        "secondary_width": controller.cpc_arch_secondary_width,
        "secondary_arc_depth": controller.cpc_arch_secondary_arc_depth,
        "secondary_height": controller.cpc_arch_secondary_height,
        "secondary_fullness": controller.cpc_arch_secondary_fullness,
        "tread1": controller.cpc_arch_tread1,
        "rise1": controller.cpc_arch_rise1,
        "tread2": controller.cpc_arch_tread2,
        "rise2": controller.cpc_arch_rise2,
        "equal_steps": controller.cpc_arch_equal_steps,
    })


def _set_controller_rna(controller, params):
    controller["_cpc_arch_initializing"] = True
    try:
        controller.cpc_arch_width = float(params["width"])
        controller.cpc_arch_height = float(params["height"])
        controller.cpc_arch_fullness = float(params["fullness"])
        controller.cpc_arch_arc_construction_mode = str(params.get("arc_construction_mode", "ARC_DEPTH"))
        controller.cpc_arch_arc_depth = float(params.get("arc_depth", 0.0062132034))
        controller.cpc_arch_bias = float(params["bias"])
        controller.cpc_arch_concave_fullness = float(params["concave_fullness"])
        controller.cpc_arch_convex_fullness = float(params["convex_fullness"])
        controller.cpc_arch_fillet_a = float(params["fillet_a"])
        controller.cpc_arch_fillet_b = float(params["fillet_b"])
        controller.cpc_arch_equal_fillets = bool(params["equal_fillets"])
        controller.cpc_arch_fascia = float(params["fascia"])
        controller.cpc_arch_secondary_width = float(params["secondary_width"])
        controller.cpc_arch_secondary_arc_depth = float(params.get("secondary_arc_depth", 0.0041421356))
        controller.cpc_arch_secondary_height = float(params["secondary_height"])
        controller.cpc_arch_secondary_fullness = float(params["secondary_fullness"])
        controller.cpc_arch_tread1 = float(params["tread1"])
        controller.cpc_arch_rise1 = float(params["rise1"])
        controller.cpc_arch_tread2 = float(params["tread2"])
        controller.cpc_arch_rise2 = float(params["rise2"])
        controller.cpc_arch_equal_steps = bool(params["equal_steps"])
    finally:
        controller["_cpc_arch_initializing"] = False


def initialise_instance(parts, component_id, params, anchor_index=0):
    if not parts:
        return
    params = architectural_recipes.normalize_parameters(component_id, params)
    controller = parts[0]
    controller["cpc_arch_controller"] = True
    controller["cpc_arch_anchor_index"] = 1 if int(anchor_index) else 0
    controller["cpc_arch_parameters"] = json.dumps(params, sort_keys=True)
    group = architectural_recipes.component_group(component_id)
    for obj in parts:
        obj["cpc_component_group"] = group
        obj["_cpc_part_transform_initializing"] = True
        try:
            obj.cpc_part_rotation = 0.0
            obj["cpc_part_rotation_applied"] = 0.0
            obj["cpc_part_rotation_saved"] = 0.0
        finally:
            obj["_cpc_part_transform_initializing"] = False
    _set_controller_rna(controller, params)


def restore_loaded_instances(objects):
    """Restore packed-controller RNA state for the current 0.4.0+ contract."""
    seen = set()
    for obj in objects:
        instance_id = str(obj.get("cpc_arch_instance_id", ""))
        if not instance_id or instance_id in seen:
            continue
        seen.add(instance_id)
        parts = instance_parts(instance_id)
        if not parts:
            continue
        controller = next((p for p in parts if p.get("cpc_arch_controller")), parts[0])
        component_id = str(controller.get("cpc_arch_component_id", ""))
        if not component_id:
            continue
        raw = controller.get("cpc_arch_parameters", "")
        try:
            params = json.loads(raw) if raw else {}
        except Exception:
            params = {}
        normalized = architectural_recipes.normalize_parameters(component_id, params)
        controller["cpc_arch_parameters"] = json.dumps(normalized, sort_keys=True)
        group = architectural_recipes.component_group(component_id)
        for part in parts:
            part["cpc_component_group"] = group
            part["_cpc_part_transform_initializing"] = True
            try:
                offset = float(part.get("cpc_part_rotation_saved", getattr(part, "cpc_part_rotation", 0.0)))
                part.cpc_part_rotation = offset
                part["cpc_part_rotation_applied"] = offset
            finally:
                part["_cpc_part_transform_initializing"] = False
        _set_controller_rna(controller, normalized)


def _recipe_turn_delta(old_layout, new_layout, index, anchor_index):
    old_angles = tuple(item.rotation for item in old_layout)
    new_angles = tuple(item.rotation for item in new_layout)
    return constructed_shapes.relative_turn_delta(old_angles, new_angles, index, anchor_index)


def _rotate_recipe_line(obj, angle, anchor_index, *, tolerance, maintain, instance_id):
    """Apply a recipe-derived base rotation without changing user Rotation Offset."""
    if abs(angle) <= 1.0e-12:
        return
    snapshot = primitives._junction_snapshot()
    pivot = library.object_endpoint_world(obj, anchor_index).copy()
    delta = (
        Matrix.Translation(pivot)
        @ Matrix.Rotation(angle, 4, 'Z')
        @ Matrix.Translation(-pivot)
    )
    obj.matrix_world = delta @ obj.matrix_world
    try:
        from . import connected_transforms
        connected_transforms.sync_object(obj)
    except Exception:
        pass
    obj.update_tag()
    primitives._propagate_from_endpoint(
        obj,
        1 - anchor_index,
        snapshot,
        tolerance=tolerance,
        include_external=maintain,
        internal_instance_id=instance_id,
    )


def _update_constructed_geometry(parts, old_layout, new_layout, *, anchor_index, tolerance, maintain, instance_id):
    """Regenerate canonical local-point line chains while preserving user offsets."""
    indices = range(len(parts)) if anchor_index == 0 else range(len(parts) - 1, -1, -1)
    for index in indices:
        obj = parts[index]
        item = new_layout[index]
        p = item.part.parameters

        # Length follows the new endpoint distance.  The chosen group end remains
        # fixed and existing junction propagation carries the opposite side.
        snapshot = primitives._junction_snapshot()
        primitives.update_object_geometry(
            obj,
            width=float(p.get("width", 0.05)),
            height=float(p.get("height", 0.05)),
            shape_mode="CIRCLE",
            bias=0.5,
            fullness=1.0,
            concave_fullness=1.0,
            convex_fullness=1.0,
            arc_construction_mode="FULLNESS",
            arc_depth=0.01,
            preserve_anchor=True,
            propagate_connected=False,
            anchor_index_override=anchor_index,
        )
        primitives._propagate_from_endpoint(
            obj,
            1 - anchor_index,
            snapshot,
            tolerance=tolerance,
            include_external=maintain,
            internal_instance_id=instance_id,
        )

        # Base angle comes only from canonical local points. User
        # cpc_part_rotation is deliberately untouched and remains an additive
        # semantic offset on top of this regenerated base orientation.
        delta_turn = _recipe_turn_delta(old_layout, new_layout, index, anchor_index)
        _rotate_recipe_line(
            obj, delta_turn, anchor_index,
            tolerance=tolerance, maintain=maintain, instance_id=instance_id,
        )


def update_instance(controller, context=None):
    controller = controller_for(controller) or controller
    if not controller or not controller.get("cpc_arch_controller"):
        return
    if controller.get("_cpc_arch_initializing") or controller.get("_cpc_arch_updating"):
        return
    component_id = str(controller.get("cpc_arch_component_id", ""))
    if not component_id:
        return
    parts = instance_parts(controller)
    params = _params_from_controller(controller)
    recipe = architectural_recipes.layout_recipe(component_id, params)
    if len(parts) != len(recipe):
        return

    try:
        previous_raw = controller.get("cpc_arch_parameters", "")
        previous_values = json.loads(previous_raw) if previous_raw else {}
        if not isinstance(previous_values, dict):
            previous_values = {}
    except Exception:
        previous_values = {}
    previous_params = architectural_recipes.normalize_parameters(component_id, previous_values or params)
    previous_recipe = architectural_recipes.layout_recipe(component_id, previous_params)
    if len(previous_recipe) != len(recipe):
        previous_recipe = recipe

    controller["_cpc_arch_updating"] = True
    try:
        _set_controller_rna(controller, params)

        settings = None
        if context is not None and getattr(context, "scene", None) is not None:
            settings = getattr(context.scene, "cpc_settings", None)
        maintain = bool(getattr(settings, "maintain_connected_parts", True))
        tolerance = float(getattr(settings, "merge_tolerance", 0.0005))
        instance_id = str(controller.get("cpc_arch_instance_id", "") or "")

        # If the user is editing a selected child, its Edit Anchor becomes the
        # local fixed point for the packed operation.  This lets a start fillet,
        # for example, grow away from an Ovolo while keeping their shared
        # junction fixed.  The packed recipe remains authoritative; this is an
        # interaction rebase, not an independent child-geometry override.
        focus_obj = None
        focus_anchor = 0
        focus_world_before = None
        if context is not None:
            selected = getattr(context, "object", None)
            if (
                selected in parts
                and str(selected.get("cpc_arch_instance_id", "") or "") == instance_id
            ):
                focus_obj = selected
                focus_anchor = 1 if int(selected.get("cpc_anchor_index", 0)) else 0
                focus_world_before = library.object_endpoint_world(focus_obj, focus_anchor).copy()

        group_anchor = 1 if int(controller.get("cpc_arch_anchor_index", 0)) else 0
        ordered_pairs = list(zip(parts, recipe))
        if group_anchor:
            ordered_pairs.reverse()

        # Synchronize child RNA values without firing their ordinary per-part
        # callbacks.  Child matrices/orientation overrides remain untouched.
        for obj, item in zip(parts, recipe):
            p = item.part.parameters
            obj["_cpc_param_initializing"] = True
            try:
                obj.cpc_param_width = float(p.get("width", 0.05))
                obj.cpc_param_height = float(p.get("height", 0.025))
                obj.cpc_param_shape_mode = str(p.get("shape_mode", "CIRCLE"))
                obj.cpc_param_bias = float(p.get("bias", 0.5))
                obj.cpc_param_fullness = float(p.get("fullness", 1.0))
                obj.cpc_param_concave_fullness = float(p.get("concave_fullness", 1.0))
                obj.cpc_param_convex_fullness = float(p.get("convex_fullness", 1.0))
                obj.cpc_param_arc_construction_mode = str(p.get("arc_construction_mode", "FULLNESS"))
                obj.cpc_param_arc_depth = float(p.get("arc_depth", 0.01))
            finally:
                obj["_cpc_param_initializing"] = False
            obj["cpc_role"] = item.part.role

        # Architectural recipes regenerate through their existing tangent/junction
        # path. Constructed Shapes additionally update recipe-derived LINE base
        # orientations from canonical local points; no +/-90/180 constants are
        # authoritative.
        if architectural_recipes.component_group(component_id) == "CONSTRUCTED":
            _update_constructed_geometry(
                parts, previous_recipe, recipe,
                anchor_index=group_anchor,
                tolerance=tolerance,
                maintain=maintain,
                instance_id=instance_id,
            )
        else:
            # Regenerate in construction direction. Endpoint-junction propagation
            # carries each dimensional change through the remaining recipe members
            # and, when Maintain Connected Parts is enabled, through external users.
            for obj, item in ordered_pairs:
                p = item.part.parameters
                snapshot = primitives._junction_snapshot()
                primitives.update_object_geometry(
                    obj,
                    width=float(p.get("width", 0.05)),
                    height=float(p.get("height", 0.025)),
                    shape_mode=str(p.get("shape_mode", "CIRCLE")),
                    bias=float(p.get("bias", 0.5)),
                    fullness=float(p.get("fullness", 1.0)),
                    concave_fullness=float(p.get("concave_fullness", 1.0)),
                    convex_fullness=float(p.get("convex_fullness", 1.0)),
                    arc_construction_mode=str(p.get("arc_construction_mode", "FULLNESS")),
                    arc_depth=float(p.get("arc_depth", 0.01)),
                    preserve_anchor=True,
                    propagate_connected=False,
                    anchor_index_override=group_anchor,
                )
                primitives._propagate_from_endpoint(
                    obj,
                    1 - group_anchor,
                    snapshot,
                    tolerance=tolerance,
                    include_external=maintain,
                    internal_instance_id=instance_id,
                )

        # Rebase the complete connected result so the selected child's chosen
        # Edit Anchor remains fixed even when that anchor is internal to the
        # Architectural Component rather than the group's historical end.
        if focus_obj is not None and focus_world_before is not None:
            focus_world_after = library.object_endpoint_world(focus_obj, focus_anchor).copy()
            delta = focus_world_before - focus_world_after
            if delta.length_squared > 1.0e-20:
                scope = junctions.connected_objects(
                    focus_obj,
                    tolerance=tolerance,
                    instance_id="" if maintain else instance_id,
                )
                for obj in scope:
                    matrix = obj.matrix_world.copy()
                    matrix.translation = matrix.translation + delta
                    obj.matrix_world = matrix
                    obj.update_tag()
                    try:
                        from . import connected_transforms
                        connected_transforms.sync_object(obj)
                    except Exception:
                        pass

        controller["cpc_arch_parameters"] = json.dumps(params, sort_keys=True)

        for obj in parts:
            obj.update_tag()
        if context is not None:
            try:
                context.view_layer.update()
            except Exception:
                pass
    finally:
        controller["_cpc_arch_updating"] = False

