"""Pure local-point recipes for CPC Constructed Shapes.

Constructed Shapes are geometric assemblies rather than new mathematical
primitives.  Every child line is derived from canonical local 2D points.  The
line length and orientation therefore come from the endpoint vector instead of
hard-coded +/-90 or 180 degree rotation constants.
"""

from __future__ import annotations

import math
from typing import Mapping, Tuple

Point2 = Tuple[float, float]


CONSTRUCTED_SHAPE_ITEMS = (
    ('CHAMFER', "Chamfer", "Diagonal splay between two equal horizontal fillets"),
    ('V_GROOVE', "V-Groove", "Two straight flanks meeting at a centered groove depth"),
    ('REBATE', "Rebate / Notch", "Three-line rectangular recess defined by Width and Depth"),
    ('SINGLE_STEP', "Single Step", "One tread and one rise"),
    ('DOUBLE_STEP', "Double Step", "Two independently editable treads and rises"),
)

CONSTRUCTED_IDS = frozenset(item[0] for item in CONSTRUCTED_SHAPE_ITEMS)
CONSTRUCTED_LABELS = {item[0]: item[1] for item in CONSTRUCTED_SHAPE_ITEMS}


def _positive(value, fallback=0.001):
    try:
        return max(abs(float(value)), 1.0e-6)
    except Exception:
        return fallback


def local_path(shape_id: str, values: Mapping) -> tuple[tuple[Point2, ...], tuple[str, ...]]:
    """Return canonical local points and one role per connecting line.

    ``points[i] -> points[i+1]`` defines child line ``roles[i]``.  There are no
    authored child angles in this representation; consumers derive angle with
    ``atan2(dy, dx)`` and length with ``hypot(dx, dy)``.
    """
    shape_id = str(shape_id or '').upper()
    width = _positive(values.get('width', 0.030), 0.030)
    height = _positive(values.get('height', 0.020), 0.020)
    fillet = _positive(values.get('fillet_a', 0.005), 0.005)

    if shape_id == 'CHAMFER':
        # Keep the packed component's overall Start/End at the same locations
        # as the former one-line chamfer: (0, 0) -> (Run, Rise).  The two
        # horizontal fillets extend from the diagonal toward the same local
        # -X side. Traversal therefore runs +X on the first fillet and -X on
        # the last; both orientations are derived from these points, never
        # authored as 0/180 degree child rotations.
        return (
            (0.0, 0.0),
            (fillet, 0.0),
            (fillet + width, height),
            (width, height),
        ), ('fillet', 'chamfer', 'fillet')

    if shape_id == 'V_GROOVE':
        return (
            (0.0, 0.0),
            (width * 0.5, -height),
            (width, 0.0),
        ), ('groove_flank', 'groove_flank')

    if shape_id == 'REBATE':
        return (
            (0.0, 0.0),
            (0.0, -height),
            (width, -height),
            (width, 0.0),
        ), ('recess_side', 'recess_floor', 'recess_side')

    tread1 = _positive(values.get('tread1', 0.020), 0.020)
    rise1 = _positive(values.get('rise1', 0.015), 0.015)
    tread2 = _positive(values.get('tread2', tread1), tread1)
    rise2 = _positive(values.get('rise2', rise1), rise1)

    if shape_id == 'SINGLE_STEP':
        return (
            (0.0, 0.0),
            (tread1, 0.0),
            (tread1, rise1),
        ), ('step_tread', 'step_rise')

    if shape_id == 'DOUBLE_STEP':
        return (
            (0.0, 0.0),
            (tread1, 0.0),
            (tread1, rise1),
            (tread1 + tread2, rise1),
            (tread1 + tread2, rise1 + rise2),
        ), ('step_tread', 'step_rise', 'step_tread', 'step_rise')

    raise ValueError(f"Unknown CPC Constructed Shape: {shape_id}")


def line_metrics(shape_id: str, values: Mapping):
    """Return (start, end, role, length, angle) for each child line."""
    points, roles = local_path(shape_id, values)
    result = []
    for start, end, role in zip(points, points[1:], roles):
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        length = math.hypot(dx, dy)
        if length <= 1.0e-12:
            raise ValueError(f"Constructed Shape {shape_id} contains a zero-length line")
        result.append((start, end, role, length, math.atan2(dy, dx)))
    return tuple(result)


def wrapped_angle_delta(value: float) -> float:
    """Normalize an angular delta to [-pi, pi] without defining recipe angles."""
    return math.atan2(math.sin(float(value)), math.cos(float(value)))


def relative_turn_delta(old_angles, new_angles, index: int, anchor_index: int) -> float:
    """Delta that remains after connected propagation carries upstream rotation.

    ``old_angles`` and ``new_angles`` are derived from endpoint vectors.  This
    function contains no authored line orientation; it only compares two
    point-derived layouts.
    """
    old_angles = tuple(float(v) for v in old_angles)
    new_angles = tuple(float(v) for v in new_angles)
    if len(old_angles) != len(new_angles) or not new_angles:
        raise ValueError("Constructed turn comparison requires equal non-empty layouts")
    index = int(index)
    anchor_index = 1 if int(anchor_index) else 0

    if anchor_index == 0:
        if index == 0:
            return wrapped_angle_delta(new_angles[0] - old_angles[0])
        old_turn = old_angles[index] - old_angles[index - 1]
        new_turn = new_angles[index] - new_angles[index - 1]
        return wrapped_angle_delta(new_turn - old_turn)

    last = len(new_angles) - 1
    if index == last:
        return wrapped_angle_delta(new_angles[last] - old_angles[last])
    old_turn = old_angles[index] - old_angles[index + 1]
    new_turn = new_angles[index] - new_angles[index + 1]
    return wrapped_angle_delta(new_turn - old_turn)
