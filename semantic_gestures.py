"""Blender-independent math for CPC semantic Rotation and Size gestures."""

from __future__ import annotations

import math


FINE_FACTOR = 0.1
SIZE_SNAP = 0.1
MIN_FACTOR = 0.001


def _finite(value, label):
    try:
        result = float(value)
    except Exception as exc:
        raise ValueError(f"{label} must be numeric") from exc
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite")
    return result


def rotation_delta(raw_delta, *, shift=False, ctrl=False, snap_radians=0.0):
    value = _finite(raw_delta, "Rotation delta")
    fine = FINE_FACTOR if shift else 1.0
    value *= fine
    if ctrl:
        step = _finite(snap_radians, "Rotation snap") * fine
        if step <= 0.0:
            raise ValueError("Rotation snap must be greater than zero")
        value = round(value / step) * step
    return value


def rotation_target(start_rotation, *, delta=0.0, typed_degrees=None):
    """Resolve one component Rotation gesture value.

    Pointer motion is relative to the captured start value. Typed Rotation is
    an absolute degree value, matching the viewport semantic field contract.
    """
    start = _finite(start_rotation, "Rotation start")
    if typed_degrees is not None:
        return parse_angle_degrees(typed_degrees)
    return start + _finite(delta, "Rotation delta")


def resize_factor(raw_factor, *, shift=False, ctrl=False):
    raw = _finite(raw_factor, "Resize factor")
    fine = FINE_FACTOR if shift else 1.0
    value = 1.0 + (raw - 1.0) * fine
    if ctrl:
        step = SIZE_SNAP * fine
        value = round(value / step) * step
    return max(value, MIN_FACTOR)


def parse_angle_degrees(text):
    return math.radians(_finite(str(text).strip(), "Rotation"))


def parse_positive_factor(text):
    value = _finite(str(text).strip(), "Size")
    if value <= 0.0:
        raise ValueError("Size must be greater than zero")
    return value
