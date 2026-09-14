"""Uniform semantic placement-parameter vocabulary for CPC.

This module is intentionally Blender-independent.  Basic primitives and
Packed Architectural/Constructed Components declare which public semantic dimensions may be
edited during placement.  The modal operator consumes these descriptors
instead of special-casing recipe names and hotkeys.
"""

from dataclasses import dataclass
from typing import Mapping, Sequence


@dataclass(frozen=True)
class PlacementParameter:
    hotkey: str
    field: str
    label: str
    semantic: str
    chord_field: str = ""


HOTKEY_ORDER = ("L", "W", "H", "D", "F")


def _ordered(items: Sequence[PlacementParameter]):
    rank = {key: i for i, key in enumerate(HOTKEY_ORDER)}
    return tuple(sorted(items, key=lambda item: rank.get(item.hotkey, 999)))


def basic_parameters(primitive_id: str, *, arc_mode="ARC_DEPTH", shape_mode="CIRCLE"):
    primitive_id = str(primitive_id or "").upper()
    arc_mode = str(arc_mode or "ARC_DEPTH").upper()
    shape_mode = str(shape_mode or "CIRCLE").upper()

    if primitive_id == "LINE":
        return (PlacementParameter("L", "width", "Length", "LENGTH"),)

    if primitive_id in {"OVOLO", "CAVETTO", "TORUS"}:
        if arc_mode == "ARC_DEPTH":
            return (
                PlacementParameter("W", "width", "Chord", "WIDTH_OR_CHORD"),
                PlacementParameter("D", "arc_depth", "Arc Depth", "ARC_DEPTH"),
            )
        items = [PlacementParameter("W", "width", "Width", "WIDTH_OR_CHORD")]
        if shape_mode == "ELLIPSE":
            items.append(PlacementParameter("H", "height", "Height", "HEIGHT_OR_RISE"))
        return _ordered(items)

    if primitive_id in {"CYMA_RECTA", "CYMA_REVERSA"}:
        items = [
            PlacementParameter("W", "width", "Width", "WIDTH_OR_CHORD"),
            PlacementParameter("H", "height", "Height", "HEIGHT_OR_RISE"),
        ]
        if arc_mode == "ARC_DEPTH":
            items.append(PlacementParameter("D", "arc_depth", "Primary Arc Depth", "ARC_DEPTH"))
        return _ordered(items)

    return ()


def architectural_parameters(component_id: str, values: Mapping | None = None):
    component_id = str(component_id or "").upper()
    values = dict(values or {})
    arc_mode = str(values.get("arc_construction_mode", "ARC_DEPTH") or "ARC_DEPTH").upper()

    fillet = PlacementParameter("F", "fillet_a", "Fillet", "MEMBER_SIZE")

    if component_id in {"OVOLO_FILLETS", "CAVETTO_FILLETS"}:
        if arc_mode == "ARC_DEPTH":
            return (
                PlacementParameter("W", "width", "Chord", "WIDTH_OR_CHORD"),
                PlacementParameter("D", "arc_depth", "Arc Depth", "ARC_DEPTH"),
                fillet,
            )
        return (
            PlacementParameter("W", "width", "Width", "WIDTH_OR_CHORD"),
            PlacementParameter("H", "height", "Height", "HEIGHT_OR_RISE"),
            fillet,
        )

    if component_id in {"CYMA_RECTA_FILLETS", "CYMA_REVERSA_FILLETS"}:
        items = [
            PlacementParameter("W", "width", "Width", "WIDTH_OR_CHORD"),
            PlacementParameter("H", "height", "Height", "HEIGHT_OR_RISE"),
            fillet,
        ]
        if arc_mode == "ARC_DEPTH":
            items.append(PlacementParameter("D", "arc_depth", "Primary Arc Depth", "ARC_DEPTH"))
        return _ordered(items)

    if component_id in {"FASCIA_OVOLO_FILLET", "FASCIA_CAVETTO_FILLET"}:
        items = [
            PlacementParameter("W", "width", "Chord" if arc_mode == "ARC_DEPTH" else "Curve Width", "WIDTH_OR_CHORD"),
            PlacementParameter("H", "fascia", "Fascia", "HEIGHT_OR_RISE"),
            PlacementParameter("F", "fillet_a", "Fillet", "MEMBER_SIZE"),
        ]
        if arc_mode == "ARC_DEPTH":
            items.append(PlacementParameter("D", "arc_depth", "Arc Depth", "ARC_DEPTH"))
        return _ordered(items)

    if component_id == "NOSE_COVE":
        if arc_mode == "ARC_DEPTH":
            # Repeated D cycles between the two independent depth members.
            return _ordered((
                PlacementParameter("W", "width", "Nose Chord", "WIDTH_OR_CHORD"),
                PlacementParameter("D", "arc_depth", "Nose Arc Depth", "ARC_DEPTH", "width"),
                PlacementParameter("D", "secondary_arc_depth", "Cove Arc Depth", "ARC_DEPTH", "secondary_width"),
                PlacementParameter("F", "secondary_width", "Cove Chord", "MEMBER_SIZE"),
            ))
        return (
            PlacementParameter("W", "width", "Nose Width", "WIDTH_OR_CHORD"),
            PlacementParameter("H", "secondary_height", "Cove Height", "HEIGHT_OR_RISE"),
            PlacementParameter("F", "secondary_width", "Cove Width", "MEMBER_SIZE"),
        )

    if component_id == "SIMPLE_SCOTIA":
        if arc_mode == "ARC_DEPTH":
            return (
                PlacementParameter("W", "width", "Chord", "WIDTH_OR_CHORD"),
                PlacementParameter("D", "arc_depth", "Arc Depth", "ARC_DEPTH"),
            )
        return (
            PlacementParameter("W", "width", "Width", "WIDTH_OR_CHORD"),
            PlacementParameter("H", "height", "Height", "HEIGHT_OR_RISE"),
        )

    if component_id == "CLASSICAL_SCOTIA":
        # Projection + Height uniquely derive the two circular quarter-radii.
        # Fullness mode preserves the same endpoints/tangent framework.
        return (
            PlacementParameter("W", "width", "Projection", "WIDTH_OR_CHORD"),
            PlacementParameter("H", "height", "Height", "HEIGHT_OR_RISE"),
        )

    if component_id == "CHAMFER":
        return (
            PlacementParameter("W", "width", "Run", "WIDTH_OR_CHORD"),
            PlacementParameter("H", "height", "Rise", "HEIGHT_OR_RISE"),
            PlacementParameter("F", "fillet_a", "Fillet", "MEMBER_SIZE"),
        )

    if component_id == "V_GROOVE":
        return (
            PlacementParameter("W", "width", "Width", "WIDTH_OR_CHORD"),
            PlacementParameter("H", "height", "Depth", "HEIGHT_OR_RISE"),
        )

    if component_id == "REBATE":
        return (
            PlacementParameter("W", "width", "Width", "WIDTH_OR_CHORD"),
            PlacementParameter("H", "height", "Depth", "HEIGHT_OR_RISE"),
        )

    if component_id == "SINGLE_STEP":
        return (
            PlacementParameter("W", "tread1", "Tread", "WIDTH_OR_CHORD"),
            PlacementParameter("H", "rise1", "Rise", "HEIGHT_OR_RISE"),
        )

    if component_id == "DOUBLE_STEP":
        return (
            PlacementParameter("W", "tread1", "Tread", "WIDTH_OR_CHORD"),
            PlacementParameter("H", "rise1", "Rise", "HEIGHT_OR_RISE"),
        )

    return ()


def by_hotkey_all(parameters, hotkey: str):
    hotkey = str(hotkey or "").upper()
    return tuple(item for item in parameters if item.hotkey == hotkey)


def by_hotkey(parameters, hotkey: str):
    matches = by_hotkey_all(parameters, hotkey)
    return matches[0] if matches else None


def _merged_labels(labels):
    labels = [str(label).strip() for label in labels if str(label).strip()]
    if len(labels) < 2:
        return labels[0] if labels else ""
    words = [label.split() for label in labels]
    suffix = []
    while all(parts for parts in words):
        candidate = words[0][-1]
        if not all(parts[-1] == candidate for parts in words):
            break
        suffix.insert(0, candidate)
        for parts in words:
            parts.pop()
    prefixes = [" ".join(parts).strip() for parts in words]
    if suffix and all(prefixes):
        return f"{'/'.join(prefixes)} {' '.join(suffix)}"
    return "/".join(labels)


def shortcut_text(parameters):
    groups = []
    seen = set()
    for item in parameters:
        if item.hotkey in seen:
            continue
        seen.add(item.hotkey)
        matches = by_hotkey_all(parameters, item.hotkey)
        groups.append(f"{item.hotkey} {_merged_labels([match.label for match in matches])}")
    return " • ".join(groups)
