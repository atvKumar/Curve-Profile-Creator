"""Pure recipe definitions for CPC packed components.

This module has no Blender dependency. Architectural Components use semantic
recipes over the primitive registry, while Constructed Shapes delegate their
line-heavy canonical point chains to :mod:`constructed_shapes`. Named roles do
not automatically become new geometry kernels.
"""

from dataclasses import dataclass
import math
from typing import Dict, List, Tuple

from . import compound_geometry, constructed_shapes, primitive_geometry


@dataclass(frozen=True)
class RecipePart:
    primitive_id: str
    role: str
    parameters: Dict[str, float | str]
    turn: float = 0.0  # deliberate tangent break relative to aligned predecessor


@dataclass(frozen=True)
class LaidOutPart:
    part: RecipePart
    geometry: primitive_geometry.PrimitiveGeometry
    translation: Tuple[float, float]
    rotation: float


ARCHITECTURAL_COMPONENT_ITEMS = (
    ('OVOLO_FILLETS', "Ovolo + Fillets", "Convex ovolo bounded by architectural fillets"),
    ('CAVETTO_FILLETS', "Cavetto + Fillets", "Concave cove bounded by architectural fillets"),
    ('CYMA_RECTA_FILLETS', "Cyma Recta + Fillets", "Crowning ogee bounded by fillets"),
    ('CYMA_REVERSA_FILLETS', "Cyma Reversa + Fillets", "Reverse ogee bounded by fillets"),
    ('FASCIA_OVOLO_FILLET', "Fascia + Ovolo + Fillet", "Flat fascia flowing into an ovolo and terminating fillet"),
    ('FASCIA_CAVETTO_FILLET', "Fascia + Cavetto + Fillet", "Flat fascia flowing into a cavetto and terminating fillet"),
    ('NOSE_COVE', "Nose + Cove", "Half-round nose joined to a concave cove"),
    ('SIMPLE_SCOTIA', "Simple Scotia", "Practical deep concave scotia using the CPC cavetto kernel"),
    ('CLASSICAL_SCOTIA', "Classical Scotia", "Two tangent quarter-circle hollows of unequal radius"),
)

ARCHITECTURAL_LABELS = {item[0]: item[1] for item in ARCHITECTURAL_COMPONENT_ITEMS}
ALL_COMPONENT_LABELS = dict(ARCHITECTURAL_LABELS)
ALL_COMPONENT_LABELS.update(constructed_shapes.CONSTRUCTED_LABELS)

DEFAULT_PARAMETERS = {
    "width": 0.030,
    "height": 0.030,
    "fullness": 1.0,
    "arc_construction_mode": "ARC_DEPTH",
    "arc_depth": 0.0062132034,
    "secondary_arc_depth": 0.0041421356,
    "bias": 0.5,
    "concave_fullness": 1.0,
    "convex_fullness": 1.0,
    "fillet_a": 0.005,
    "fillet_b": 0.005,
    "equal_fillets": True,
    "fascia": 0.020,
    "secondary_width": 0.020,
    "secondary_height": 0.020,
    "secondary_fullness": 1.0,
    "tread1": 0.020,
    "rise1": 0.015,
    "tread2": 0.020,
    "rise2": 0.015,
    "equal_steps": True,
}


def display_name(component_id: str) -> str:
    return ALL_COMPONENT_LABELS.get(component_id, component_id.replace('_', ' ').title())


def component_group(component_id: str) -> str:
    return "CONSTRUCTED" if str(component_id or "").upper() in constructed_shapes.CONSTRUCTED_IDS else "ARCHITECTURAL"


def _positive(value, fallback=0.001):
    try:
        return max(abs(float(value)), 1.0e-6)
    except Exception:
        return fallback


def _factor(value, low=0.2, high=1.8, fallback=1.0):
    try:
        return min(high, max(low, float(value)))
    except Exception:
        return fallback


def normalize_parameters(component_id: str, values=None) -> Dict[str, float | bool | str]:
    values = dict(values or {})
    has_width = "width" in values and values.get("width") is not None
    has_arc_depth = "arc_depth" in values and values.get("arc_depth") is not None
    has_secondary_arc_depth = "secondary_arc_depth" in values and values.get("secondary_arc_depth") is not None
    p = dict(DEFAULT_PARAMETERS)
    p.update(values)

    for key in (
        "width", "height", "arc_depth", "secondary_arc_depth", "fillet_a", "fillet_b", "fascia",
        "secondary_width", "secondary_height", "tread1", "rise1", "tread2", "rise2",
    ):
        p[key] = _positive(p.get(key), DEFAULT_PARAMETERS[key])

    if not has_arc_depth:
        if component_id == 'NOSE_COVE':
            p["arc_depth"] = primitive_geometry.default_torus_arc_depth(p["width"])
        else:
            p["arc_depth"] = primitive_geometry.default_arc_depth(p["width"])
    if not has_secondary_arc_depth:
        p["secondary_arc_depth"] = primitive_geometry.default_arc_depth(p["secondary_width"])

    p["arc_construction_mode"] = (
        "FULLNESS" if str(p.get("arc_construction_mode", "ARC_DEPTH")).upper() == "FULLNESS" else "ARC_DEPTH"
    )
    p["fullness"] = _factor(p.get("fullness"))
    p["secondary_fullness"] = _factor(p.get("secondary_fullness"))
    p["concave_fullness"] = _factor(p.get("concave_fullness"))
    p["convex_fullness"] = _factor(p.get("convex_fullness"))
    try:
        p["bias"] = min(0.85, max(0.15, float(p.get("bias", 0.5))))
    except Exception:
        p["bias"] = 0.5

    cyma_orientation = None
    if component_id == 'CYMA_RECTA_FILLETS':
        cyma_orientation = "RECTA"
    elif component_id == 'CYMA_REVERSA_FILLETS':
        cyma_orientation = "REVERSA"
    if cyma_orientation and p["arc_construction_mode"] == "ARC_DEPTH":
        if not has_arc_depth:
            p["arc_depth"] = compound_geometry.cyma_primary_depth(
                p["width"], p["height"], p["bias"], orientation=cyma_orientation
            )
        solution = compound_geometry.solve_cyma_from_primary_depth(
            p["width"], p["height"], p["arc_depth"], orientation=cyma_orientation
        )
        p["arc_depth"] = solution.first.sagitta
        p["bias"] = solution.bias

    if component_id == 'CLASSICAL_SCOTIA':
        # Classical Scotia exposes total Height and the lower run-out beyond
        # the upper endpoint.  Height/3 is the exact 2:1 lower:upper radius
        # form and is the canonical default when no projection was supplied.
        if not has_width:
            p["width"] = p["height"] / 3.0
        # Keep projection below Height so both quarter-circle radii stay
        # positive even when a typed value overshoots during placement.
        p["width"] = min(p["width"], p["height"] * 0.95)
        p["fullness"] = _factor(p.get("fullness"))
        p["secondary_fullness"] = _factor(p.get("secondary_fullness"))

    p["equal_fillets"] = bool(p.get("equal_fillets", True))
    p["equal_steps"] = bool(p.get("equal_steps", True))
    if p["equal_fillets"]:
        p["fillet_b"] = p["fillet_a"]
    if p["equal_steps"]:
        p["tread2"] = p["tread1"]
        p["rise2"] = p["rise1"]
    return p


def build_recipe(component_id: str, values=None) -> List[RecipePart]:
    p = normalize_parameters(component_id, values)

    def line(length, role):
        return RecipePart("LINE", role, {"width": length, "height": length})

    def quarter(primitive_id, role):
        return RecipePart(
            primitive_id,
            role,
            {
                "width": p["width"],
                "height": p["height"],
                "shape_mode": "ELLIPSE",
                "fullness": p["fullness"],
                "arc_construction_mode": p["arc_construction_mode"],
                "arc_depth": p["arc_depth"],
            },
        )

    def cyma(primitive_id, role):
        return RecipePart(
            primitive_id,
            role,
            {
                "width": p["width"],
                "height": p["height"],
                "bias": p["bias"],
                "concave_fullness": p["concave_fullness"],
                "convex_fullness": p["convex_fullness"],
                "arc_construction_mode": p["arc_construction_mode"],
                "arc_depth": p["arc_depth"],
            },
        )

    if component_id == 'OVOLO_FILLETS':
        return [line(p["fillet_a"], "fillet"), quarter("OVOLO", "ovolo"), line(p["fillet_b"], "fillet")]
    if component_id == 'CAVETTO_FILLETS':
        return [line(p["fillet_a"], "fillet"), quarter("CAVETTO", "cavetto"), line(p["fillet_b"], "fillet")]
    if component_id == 'CYMA_RECTA_FILLETS':
        return [line(p["fillet_a"], "fillet"), cyma("CYMA_RECTA", "cyma_recta"), line(p["fillet_b"], "fillet")]
    if component_id == 'CYMA_REVERSA_FILLETS':
        return [line(p["fillet_a"], "fillet"), cyma("CYMA_REVERSA", "cyma_reversa"), line(p["fillet_b"], "fillet")]
    if component_id == 'FASCIA_OVOLO_FILLET':
        return [line(p["fascia"], "fascia"), quarter("OVOLO", "ovolo"), line(p["fillet_a"], "fillet")]
    if component_id == 'FASCIA_CAVETTO_FILLET':
        return [line(p["fascia"], "fascia"), quarter("CAVETTO", "cavetto"), line(p["fillet_a"], "fillet")]
    if component_id == 'NOSE_COVE':
        return [
            RecipePart("TORUS", "nose", {
                "width": p["width"], "height": p["width"] * 0.5,
                "shape_mode": "CIRCLE", "fullness": p["fullness"],
                "arc_construction_mode": p["arc_construction_mode"],
                "arc_depth": p["arc_depth"],
            }),
            RecipePart("CAVETTO", "cove", {
                "width": p["secondary_width"], "height": p["secondary_height"],
                "shape_mode": "ELLIPSE", "fullness": p["secondary_fullness"],
                "arc_construction_mode": p["arc_construction_mode"],
                "arc_depth": p["secondary_arc_depth"],
            }),
        ]
    if component_id == 'SIMPLE_SCOTIA':
        return [RecipePart("CAVETTO", "simple_scotia", {
            "width": p["width"], "height": p["height"],
            "shape_mode": "ELLIPSE", "fullness": p["fullness"],
            "arc_construction_mode": p["arc_construction_mode"],
            "arc_depth": p["arc_depth"],
        })]
    if component_id == 'CLASSICAL_SCOTIA':
        return [RecipePart("CLASSICAL_SCOTIA", "classical_scotia", {
            "width": p["width"],
            "height": p["height"],
            "shape_mode": "CIRCLE",
            "arc_construction_mode": p["arc_construction_mode"],
            # Generic child RNA names are reused internally; packed UI exposes
            # these semantically as Upper / Lower Fullness.
            "concave_fullness": p["fullness"],
            "convex_fullness": p["secondary_fullness"],
        })]
    if component_id in constructed_shapes.CONSTRUCTED_IDS:
        return [
            RecipePart("LINE", role, {"width": length, "height": length})
            for _start, _end, role, length, _angle in constructed_shapes.line_metrics(component_id, p)
        ]
    raise ValueError(f"Unknown CPC Architectural Component: {component_id}")


def _rotate(point, angle):
    c = math.cos(angle)
    s = math.sin(angle)
    return (c * point[0] - s * point[1], s * point[0] + c * point[1])


def _transform_point(point, translation, rotation):
    r = _rotate(point, rotation)
    return (r[0] + translation[0], r[1] + translation[1])


def _angle(vector):
    return math.atan2(vector[1], vector[0])


def _geometry_from_part(part: RecipePart):
    p = part.parameters
    return primitive_geometry.generate(
        part.primitive_id,
        width=float(p.get("width", 0.05)),
        height=float(p.get("height", 0.025)),
        shape_mode=str(p.get("shape_mode", "CIRCLE")),
        bias=float(p.get("bias", 0.5)),
        fullness=float(p.get("fullness", 1.0)),
        concave_fullness=float(p.get("concave_fullness", 1.0)),
        convex_fullness=float(p.get("convex_fullness", 1.0)),
        arc_construction_mode=str(p.get("arc_construction_mode", "FULLNESS")),
        arc_depth=float(p.get("arc_depth", primitive_geometry.default_arc_depth(float(p.get("width", 0.05))))),
    )


def layout_recipe(component_id: str, values=None) -> List[LaidOutPart]:
    """Lay out a packed component in its canonical local 2D frame.

    Architectural recipes retain tangent-relative composition. Constructed
    Shapes use canonical local point chains instead: each LINE translation,
    length and rotation is derived from its endpoints, never authored as a
    +/-90 or 180 degree constant.
    """
    component_id = str(component_id or "").upper()
    normalized = normalize_parameters(component_id, values)

    if component_id in constructed_shapes.CONSTRUCTED_IDS:
        laid_out: List[LaidOutPart] = []
        for start, _end, role, length, angle in constructed_shapes.line_metrics(component_id, normalized):
            part = RecipePart("LINE", role, {"width": length, "height": length})
            geom = _geometry_from_part(part)
            laid_out.append(LaidOutPart(part, geom, start, angle))
        return laid_out

    recipe = build_recipe(component_id, normalized)
    laid_out: List[LaidOutPart] = []

    for index, part in enumerate(recipe):
        geom = _geometry_from_part(part)
        if index == 0:
            translation = (0.0, 0.0)
            rotation = 0.0
        else:
            prev = laid_out[-1]
            prev_seg = prev.geometry.segments[-1]
            prev_end = _transform_point(prev_seg.p1, prev.translation, prev.rotation)
            prev_tangent = _rotate(prev.geometry.end_tangent, prev.rotation)
            start_tangent = geom.start_tangent
            rotation = _angle(prev_tangent) - _angle(start_tangent) + part.turn
            start_point = geom.segments[0].p0
            rotated_start = _rotate(start_point, rotation)
            translation = (prev_end[0] - rotated_start[0], prev_end[1] - rotated_start[1])
        laid_out.append(LaidOutPart(part, geom, translation, rotation))
    return laid_out


def bounds_and_endpoints(component_id: str, values=None):
    layout = layout_recipe(component_id, values)
    if not layout:
        return None
    points = []
    for item in layout:
        for segment in item.geometry.segments:
            points.extend([
                _transform_point(segment.p0, item.translation, item.rotation),
                _transform_point(segment.h0, item.translation, item.rotation),
                _transform_point(segment.h1, item.translation, item.rotation),
                _transform_point(segment.p1, item.translation, item.rotation),
            ])
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    first = layout[0]
    last = layout[-1]
    start = _transform_point(first.geometry.segments[0].p0, first.translation, first.rotation)
    end = _transform_point(last.geometry.segments[-1].p1, last.translation, last.rotation)
    start_tangent = _rotate(first.geometry.start_tangent, first.rotation)
    end_tangent = _rotate(last.geometry.end_tangent, last.rotation)
    return {
        "min": (min(xs), min(ys)),
        "max": (max(xs), max(ys)),
        "start": start,
        "end": end,
        "start_tangent": start_tangent,
        "end_tangent": end_tangent,
    }
