"""Semantic viewport-edit fields for Curve Profile Creator.

This module maps a selected CPC construction object to the *authoritative*
parameter owner/property.  Basic parts edit their own RNA properties;
Architectural Component children expose the packed controller parameters rather
than pretending child geometry is an independent semantic definition.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

from . import architectural_components, architectural_recipes, primitives


@dataclass(frozen=True)
class SemanticField:
    field_id: str
    label: str
    owner: object | None
    prop_name: str
    editable: bool = True
    kind: str = "LENGTH"
    value_override: float | None = None

    @property
    def value(self) -> float:
        if self.value_override is not None:
            return float(self.value_override)
        return float(getattr(self.owner, self.prop_name))


_ARC_PACKED = {
    'OVOLO_FILLETS', 'CAVETTO_FILLETS',
    'FASCIA_OVOLO_FILLET', 'FASCIA_CAVETTO_FILLET',
    'SIMPLE_SCOTIA',
}
_FILLET_COMPONENTS = {
    'OVOLO_FILLETS', 'CAVETTO_FILLETS',
    'CYMA_RECTA_FILLETS', 'CYMA_REVERSA_FILLETS',
}
_CYMA_PACKED = {'CYMA_RECTA_FILLETS', 'CYMA_REVERSA_FILLETS'}
_FASCIA_PACKED = {'FASCIA_OVOLO_FILLET', 'FASCIA_CAVETTO_FILLET'}


def _field(field_id, label, owner, prop, *, editable=True, kind="LENGTH", value_override=None):
    return SemanticField(
        field_id,
        label,
        owner,
        prop,
        editable=editable,
        kind=kind,
        value_override=value_override,
    )


def _basic_fields(obj):
    primitive_id = str(obj.get("cpc_primitive_id", "LINE"))
    fields = []

    if primitive_id == 'LINE':
        fields.append(_field("length", "Length", obj, "cpc_param_width"))
        return fields

    if primitive_id in {'OVOLO', 'CAVETTO', 'TORUS'}:
        mode = str(getattr(obj, "cpc_param_arc_construction_mode", "FULLNESS"))
        if mode == 'ARC_DEPTH':
            fields.extend([
                _field("chord", "Chord", obj, "cpc_param_width"),
                _field("depth", "Arc Depth", obj, "cpc_param_arc_depth"),
                _field("radius", "Radius", obj, "cpc_param_arc_radius", editable=False),
            ])
        else:
            fields.append(_field("width", "Width", obj, "cpc_param_width"))
            if str(getattr(obj, "cpc_param_shape_mode", "CIRCLE")) == 'ELLIPSE':
                fields.append(_field("height", "Height", obj, "cpc_param_height"))
        return fields

    if primitive_id in {'CYMA_RECTA', 'CYMA_REVERSA'}:
        fields.extend([
            _field("width", "Width", obj, "cpc_param_width"),
            _field("height", "Height", obj, "cpc_param_height"),
        ])
        if str(getattr(obj, "cpc_param_arc_construction_mode", "FULLNESS")) == 'ARC_DEPTH':
            fields.append(_field("depth", "Primary Arc Depth", obj, "cpc_param_arc_depth"))
        return fields

    if primitive_id == 'CLASSICAL_SCOTIA':
        return [
            _field("width", "Projection", obj, "cpc_param_width"),
            _field("height", "Height", obj, "cpc_param_height"),
        ]
    return fields


def _architectural_fields(selected, controller):
    component_id = str(controller.get("cpc_arch_component_id", ""))
    fields = []

    if component_id in _ARC_PACKED:
        mode = str(getattr(controller, "cpc_arch_arc_construction_mode", "ARC_DEPTH"))
        if mode == 'ARC_DEPTH':
            fields.extend([
                _field("arch_chord", "Chord", controller, "cpc_arch_width"),
                _field("arch_depth", "Arc Depth", controller, "cpc_arch_arc_depth"),
                _field("arch_radius", "Radius", controller, "cpc_arch_arc_radius", editable=False),
            ])
        else:
            fields.extend([
                _field("arch_width", "Width", controller, "cpc_arch_width"),
                _field("arch_height", "Height", controller, "cpc_arch_height"),
            ])

    if component_id in _CYMA_PACKED:
        fields.extend([
            _field("arch_width", "Width", controller, "cpc_arch_width"),
            _field("arch_height", "Height", controller, "cpc_arch_height"),
        ])
        if str(getattr(controller, "cpc_arch_arc_construction_mode", "FULLNESS")) == 'ARC_DEPTH':
            fields.append(_field("arch_depth", "Primary Arc Depth", controller, "cpc_arch_arc_depth"))

    if component_id in _FILLET_COMPONENTS:
        if bool(getattr(controller, "cpc_arch_equal_fillets", True)):
            fields.append(_field("fillet", "Fillet", controller, "cpc_arch_fillet_a"))
        else:
            fields.extend([
                _field("fillet_a", "Start Fillet", controller, "cpc_arch_fillet_a"),
                _field("fillet_b", "End Fillet", controller, "cpc_arch_fillet_b"),
            ])

    if component_id in _FASCIA_PACKED:
        fields.extend([
            _field("fascia", "Fascia", controller, "cpc_arch_fascia"),
            _field("fillet", "End Fillet", controller, "cpc_arch_fillet_a"),
        ])

    if component_id == 'NOSE_COVE':
        mode = str(getattr(controller, "cpc_arch_arc_construction_mode", "FULLNESS"))
        if mode == 'ARC_DEPTH':
            fields.extend([
                _field("nose_chord", "Nose Chord", controller, "cpc_arch_width"),
                _field("nose_depth", "Nose Arc Depth", controller, "cpc_arch_arc_depth"),
                _field("nose_radius", "Nose Radius", controller, "cpc_arch_arc_radius", editable=False),
                _field("cove_chord", "Cove Chord", controller, "cpc_arch_secondary_width"),
                _field("cove_depth", "Cove Arc Depth", controller, "cpc_arch_secondary_arc_depth"),
                _field("cove_radius", "Cove Radius", controller, "cpc_arch_secondary_arc_radius", editable=False),
            ])
        else:
            fields.extend([
                _field("nose_width", "Nose Width", controller, "cpc_arch_width"),
                _field("cove_width", "Cove Width", controller, "cpc_arch_secondary_width"),
                _field("cove_height", "Cove Height", controller, "cpc_arch_secondary_height"),
            ])

    if component_id == 'CLASSICAL_SCOTIA':
        fields.extend([
            _field("arch_width", "Projection", controller, "cpc_arch_width"),
            _field("arch_height", "Height", controller, "cpc_arch_height"),
        ])

    if component_id == 'CHAMFER':
        fields.extend([
            _field("arch_width", "Run", controller, "cpc_arch_width"),
            _field("arch_height", "Rise", controller, "cpc_arch_height"),
            _field("fillet_a", "Fillet", controller, "cpc_arch_fillet_a"),
        ])

    if component_id in {'V_GROOVE', 'REBATE'}:
        fields.extend([
            _field("arch_width", "Width", controller, "cpc_arch_width"),
            _field("arch_height", "Depth", controller, "cpc_arch_height"),
        ])

    if component_id == 'SINGLE_STEP':
        fields.extend([
            _field("tread1", "Tread", controller, "cpc_arch_tread1"),
            _field("rise1", "Rise", controller, "cpc_arch_rise1"),
        ])

    if component_id == 'DOUBLE_STEP':
        fields.extend([
            _field("tread1", "Tread 1", controller, "cpc_arch_tread1"),
            _field("rise1", "Rise 1", controller, "cpc_arch_rise1"),
        ])
        if not bool(getattr(controller, "cpc_arch_equal_steps", True)):
            fields.extend([
                _field("tread2", "Tread 2", controller, "cpc_arch_tread2"),
                _field("rise2", "Rise 2", controller, "cpc_arch_rise2"),
            ])

    # Avoid accidental duplicates when a component belongs to several families.
    seen = set()
    unique = []
    for item in fields:
        if item.field_id in seen:
            continue
        seen.add(item.field_id)
        unique.append(item)
    return unique


def target_kind(obj):
    if not obj or getattr(obj, "type", "") != "CURVE" or obj.get("cpc_preview"):
        return ""
    if obj.get("cpc_part") and obj.get("cpc_parametric"):
        return "COMPONENT"
    if obj.get("cpc_profile") and not obj.get("cpc_part"):
        return "PROFILE"
    return ""


def fields_for(obj):
    kind = target_kind(obj)
    if kind == "PROFILE":
        from . import profile_transforms

        state = profile_transforms.profile_placement_state(obj)
        return [
            _field(
                "profile_rotation",
                "Rotation",
                obj,
                "",
                kind="ANGLE",
                value_override=state["rotation"],
            ),
            _field(
                "profile_uniform_scale",
                "Uniform Scale",
                obj,
                "",
                kind="FACTOR",
                value_override=state["uniform_scale"],
            ),
        ]
    if kind != "COMPONENT":
        return []
    controller = architectural_components.controller_for(obj) if obj.get("cpc_arch_instance_id") else None
    dimensions = _architectural_fields(obj, controller) if controller else _basic_fields(obj)
    return [
        _field("part_rotation", "Rotation", obj, "cpc_part_rotation", kind="ANGLE"),
        _field("part_size", "Size", None, "", kind="RESIZE_ACTION", value_override=1.0),
        *dimensions,
    ]


def format_field_value(context, field, *, value=None):
    shown = field.value if value is None else float(value)
    if field.kind == "ANGLE":
        return f"{math.degrees(shown):.2f}°"
    if field.kind in {"FACTOR", "RESIZE_ACTION"}:
        return f"{shown:.3f}×"
    from . import interaction_units

    return interaction_units.format_length(context, shown)


def resolve_scrub_value(
    field_kind,
    start_value,
    total_dx,
    *,
    shift=False,
    ctrl=False,
    rotation_snap_radians=0.0,
):
    from . import semantic_gestures

    kind = str(field_kind or "")
    start = float(start_value)
    dx = float(total_dx)
    if kind == "LENGTH":
        sensitivity = 0.01 * (0.1 if shift else 1.0)
        return max(start * math.exp(dx * sensitivity), 1.0e-6)
    if kind == "ANGLE":
        return start + semantic_gestures.rotation_delta(
            dx * 0.005,
            shift=shift,
            ctrl=ctrl,
            snap_radians=rotation_snap_radians,
        )
    if kind in {"FACTOR", "RESIZE_ACTION"}:
        gesture_factor = semantic_gestures.resize_factor(
            math.exp(dx * 0.005),
            shift=shift,
            ctrl=ctrl,
        )
        return start * gesture_factor if kind == "FACTOR" else gesture_factor
    raise ValueError(f"Unsupported semantic field kind: {kind}")


def capture_uniform_resize_state(obj):
    """Capture authoritative CPC construction dimensions for one S/Size gesture."""
    if not obj or obj.type != 'CURVE' or not obj.get("cpc_part") or not obj.get("cpc_parametric"):
        return None

    controller = architectural_components.controller_for(obj) if obj.get("cpc_arch_instance_id") else None
    if controller:
        return {
            "kind": "PACKED",
            "controller": controller,
            "component_id": str(controller.get("cpc_arch_component_id", "") or ""),
            "params": architectural_components.controller_parameters(controller),
        }

    return {
        "kind": "BASIC",
        "object": obj,
        "width": float(obj.cpc_param_width),
        "height": float(obj.cpc_param_height),
        "arc_depth": float(obj.cpc_param_arc_depth),
        "shape_mode": str(obj.cpc_param_shape_mode),
        "bias": float(obj.cpc_param_bias),
        "fullness": float(obj.cpc_param_fullness),
        "concave_fullness": float(obj.cpc_param_concave_fullness),
        "convex_fullness": float(obj.cpc_param_convex_fullness),
        "arc_construction_mode": str(obj.cpc_param_arc_construction_mode),
    }


def uniform_resize_scope(obj):
    """Objects whose raw Blender scale belongs to the same semantic component."""
    if not obj:
        return []
    controller = architectural_components.controller_for(obj) if obj.get("cpc_arch_instance_id") else None
    if controller:
        return architectural_components.instance_parts(controller)
    return [obj]


def apply_uniform_resize_state(obj, state, factor, context=None, *, preserve_anchor=True, propagate_connected=True):
    """Regenerate CPC construction geometry from captured dimensions × factor.

    Dimensionless semantics (Bias, Fullness, flips, Rotation Offset and
    construction mode) come from the captured state and are not scaled.
    """
    if not state:
        return False
    try:
        factor = float(factor)
    except Exception:
        return False
    if factor <= 0.0:
        return False

    if state.get("kind") == "PACKED":
        controller = state.get("controller")
        if not controller:
            return False
        component_id = str(state.get("component_id", "") or "")
        params = architectural_recipes.scale_length_parameters(
            component_id,
            state.get("params", {}),
            factor,
        )
        if not architectural_components.apply_parameters(controller, params, context):
            return False
        for part in architectural_components.instance_parts(controller):
            part["cpc_scale"] = 1.0
        return True

    target = state.get("object") or obj
    if not target or target.type != 'CURVE' or not target.get("cpc_parametric"):
        return False

    width = max(float(state["width"]) * factor, 1.0e-6)
    height = max(float(state["height"]) * factor, 1.0e-6)
    arc_depth = max(float(state["arc_depth"]) * factor, 1.0e-6)

    target["_cpc_param_initializing"] = True
    try:
        target.cpc_param_width = width
        target.cpc_param_height = height
        target.cpc_param_arc_depth = arc_depth
        target.cpc_param_shape_mode = str(state["shape_mode"])
        target.cpc_param_bias = float(state["bias"])
        target.cpc_param_fullness = float(state["fullness"])
        target.cpc_param_concave_fullness = float(state["concave_fullness"])
        target.cpc_param_convex_fullness = float(state["convex_fullness"])
        target.cpc_param_arc_construction_mode = str(state["arc_construction_mode"])
    finally:
        target["_cpc_param_initializing"] = False

    settings = None
    if context is not None and getattr(context, "scene", None) is not None:
        settings = getattr(context.scene, "cpc_settings", None)
    maintain = bool(getattr(settings, "maintain_connected_parts", True)) if propagate_connected else False
    tolerance = float(getattr(settings, "merge_tolerance", 0.0005))

    primitives.update_object_geometry(
        target,
        width=width,
        height=height,
        shape_mode=str(state["shape_mode"]),
        bias=float(state["bias"]),
        fullness=float(state["fullness"]),
        concave_fullness=float(state["concave_fullness"]),
        convex_fullness=float(state["convex_fullness"]),
        arc_construction_mode=str(state["arc_construction_mode"]),
        arc_depth=arc_depth,
        preserve_anchor=bool(preserve_anchor),
        propagate_connected=maintain,
        connection_tolerance=tolerance,
    )
    target["cpc_scale"] = 1.0
    return True


def field_by_id(obj, field_id):
    for field in fields_for(obj):
        if field.field_id == str(field_id):
            return field
    return None


def apply_value(obj, field_id, value, context=None):
    field = field_by_id(obj, field_id)
    if field is None:
        raise ValueError("Viewport semantic field is no longer available")
    if not field.editable:
        raise ValueError(f"{field.label} is derived and cannot be edited directly")
    value = float(value)
    if field.kind == "LENGTH" and value <= 0.0:
        raise ValueError(f"{field.label} must be greater than zero")
    if field.kind == "RESIZE_ACTION":
        raise ValueError(f"{field.label} requires a captured resize gesture")
    if field.field_id.startswith("profile_"):
        if field.kind == "FACTOR" and value <= 0.0:
            raise ValueError(f"{field.label} must be greater than zero")
        settings = getattr(getattr(context, "scene", None), "cpc_settings", None)
        if settings is None:
            raise ValueError(f"{field.label} requires a profile placement context")
        from . import properties

        change = "rotation" if field.field_id == "profile_rotation" else "uniform_scale"
        properties.set_profile_placement_state(settings, context, obj, **{change: value})
        return field
    setattr(field.owner, field.prop_name, value)
    return field


def _raw_scale(obj):
    try:
        values = tuple(float(value) for value in obj.scale)
    except Exception as exc:
        raise ValueError("Object Scale must contain three numeric values") from exc
    if len(values) != 3 or any(not math.isfinite(value) for value in values):
        raise ValueError("Object Scale must contain three finite values")
    return values


def _set_neutral_scale(objects):
    for item in objects:
        item.scale = (1.0, 1.0, 1.0)


def _profile_settings(context):
    settings = getattr(getattr(context, "scene", None), "cpc_settings", None)
    if settings is None:
        raise ValueError("Profile semantic editing requires a scene context")
    return settings


def capture_edit_state(obj, field_id):
    field = field_by_id(obj, field_id)
    if field is None:
        raise ValueError("Viewport semantic field is no longer available")

    if field.field_id == "part_size":
        scope = uniform_resize_scope(obj)
        if not scope:
            raise ValueError("Component Size has no editable objects")
        for item in scope:
            if any(abs(value - 1.0) > 1.0e-6 for value in _raw_scale(item)):
                raise ValueError("Component Size requires neutral Object Scale")
        resize_state = capture_uniform_resize_state(obj)
        if not resize_state:
            raise ValueError("Component Size state is no longer available")
        return {
            "kind": "COMPONENT_SIZE",
            "field_id": field.field_id,
            "resize_state": resize_state,
            "value": 1.0,
        }

    if field.field_id == "part_rotation":
        return {
            "kind": "COMPONENT_ROTATION",
            "field_id": field.field_id,
            "value": field.value,
        }

    if field.kind == "LENGTH":
        return {
            "kind": "DIRECT_VALUE",
            "field_id": field.field_id,
            "value": field.value,
        }

    if field.field_id in {"profile_rotation", "profile_uniform_scale"}:
        from . import profile_transforms

        original_placement = dict(profile_transforms.profile_placement_state(obj))
        original_scale = _raw_scale(obj)
        baseline = profile_transforms.capture_profile_resize_state(
            original_placement,
            original_scale,
        )
        return {
            "kind": "PROFILE",
            "field_id": field.field_id,
            "original_placement": original_placement,
            "original_scale": original_scale,
            "baseline": baseline,
            "value": float(
                baseline[
                    "rotation"
                    if field.field_id == "profile_rotation"
                    else "uniform_scale"
                ]
            ),
        }

    raise ValueError(f"Unsupported semantic edit field: {field.field_id}")


def apply_edit_value(obj, field_id, value, state, context=None):
    if not state or state.get("field_id") != str(field_id):
        raise ValueError("Semantic edit state does not match the active field")

    kind = state.get("kind")
    if kind == "COMPONENT_SIZE":
        applied = apply_uniform_resize_state(
            obj,
            state.get("resize_state"),
            value,
            context,
        )
        if applied:
            _set_neutral_scale(uniform_resize_scope(obj))
        return bool(applied)

    if kind in {"COMPONENT_ROTATION", "DIRECT_VALUE"}:
        apply_value(obj, field_id, value, context)
        return True

    if kind == "PROFILE":
        from . import profile_transforms, properties

        resolved = profile_transforms.resolve_profile_semantic_field(
            state["baseline"],
            field_id,
            value,
        )
        previous_scale = _raw_scale(obj)
        _set_neutral_scale([obj])
        try:
            properties.set_profile_placement_state(
                _profile_settings(context),
                context,
                obj,
                state=resolved,
            )
        except Exception:
            obj.scale = previous_scale
            raise
        return True

    raise ValueError("Unsupported semantic edit state")


def restore_edit_state(obj, field_id, state, context=None):
    if not state or state.get("field_id") != str(field_id):
        raise ValueError("Semantic edit state does not match the active field")

    kind = state.get("kind")
    if kind == "COMPONENT_SIZE":
        restored = apply_uniform_resize_state(
            obj,
            state.get("resize_state"),
            1.0,
            context,
        )
        if restored:
            _set_neutral_scale(uniform_resize_scope(obj))
        return bool(restored)

    if kind in {"COMPONENT_ROTATION", "DIRECT_VALUE"}:
        apply_value(obj, field_id, state["value"], context)
        return True

    if kind == "PROFILE":
        from . import properties

        properties.set_profile_placement_state(
            _profile_settings(context),
            context,
            obj,
            state=state["original_placement"],
        )
        obj.scale = tuple(state["original_scale"])
        return True

    raise ValueError("Unsupported semantic edit state")


def shortcut_fields(obj, key):
    key = str(key or "").upper()
    fields = fields_for(obj)
    preferred = {
        'L': ("length",),
        'W': ("chord", "arch_chord", "width", "arch_width", "nose_chord", "nose_width", "tread1"),
        'H': ("height", "arch_height", "fascia", "cove_height", "rise1"),
        'D': ("depth", "arch_depth", "nose_depth", "cove_depth"),
        'F': ("fillet", "fillet_a", "cove_chord", "cove_width"),
    }.get(key, ())
    result = []
    for field_id in preferred:
        for field in fields:
            if field.field_id == field_id and field.editable:
                result.append(field)
                break
    return tuple(result)


def shortcut_field(obj, key):
    matches = shortcut_fields(obj, key)
    return matches[0] if matches else None
