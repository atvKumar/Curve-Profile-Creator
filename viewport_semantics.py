"""Semantic viewport-edit fields for Curve Profile Creator.

This module maps a selected CPC construction object to the *authoritative*
parameter owner/property.  Basic parts edit their own RNA properties;
Architectural Component children expose the packed controller parameters rather
than pretending child geometry is an independent semantic definition.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import architectural_components, architectural_recipes, primitives


@dataclass(frozen=True)
class SemanticField:
    field_id: str
    label: str
    owner: object
    prop_name: str
    editable: bool = True
    kind: str = "LENGTH"

    @property
    def value(self) -> float:
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


def _field(field_id, label, owner, prop, *, editable=True):
    return SemanticField(field_id, label, owner, prop, editable=editable)


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


def fields_for(obj):
    if not obj or obj.type != 'CURVE' or not obj.get("cpc_part") or not obj.get("cpc_parametric"):
        return []
    controller = architectural_components.controller_for(obj) if obj.get("cpc_arch_instance_id") else None
    return _architectural_fields(obj, controller) if controller else _basic_fields(obj)


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


def apply_value(obj, field_id, value):
    field = field_by_id(obj, field_id)
    if field is None:
        raise ValueError("Viewport dimension is no longer available")
    if not field.editable:
        raise ValueError(f"{field.label} is derived and cannot be edited directly")
    value = float(value)
    if field.kind == "LENGTH" and value <= 0.0:
        raise ValueError(f"{field.label} must be greater than zero")
    setattr(field.owner, field.prop_name, value)
    return field


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
