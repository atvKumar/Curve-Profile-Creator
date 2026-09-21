"""Normalized profile-space transform helpers for CPC 0.4.0+ recipes.

CPC stores evaluated component transforms relative to one reusable Profile Frame.
Blender ``mathutils.Matrix`` remains authoritative for composition; persisted
records use JSON-safe row-major numeric lists. Semantic ``cpc_part_rotation`` is
stored separately by the recipe and is never inferred from these matrices.
"""

from __future__ import annotations

import copy
import json
import math
from typing import Iterable, Mapping

from mathutils import Matrix, Vector


PROFILE_TRANSFORM_SCHEMA = 1
PROFILE_FRAME_POLICY = "START_ORIGIN_WORLD_BASIS"

# 0.4.4 complete-profile placement state.  This is deliberately separate from
# recipe matrix_profile transforms and semantic cpc_part_rotation.
PROFILE_PLACEMENT_SCHEMA = 1
PROFILE_PLACEMENT_KEY = "cpc_profile_placement_json"


def neutral_profile_placement() -> dict:
    return {
        "schema_version": PROFILE_PLACEMENT_SCHEMA,
        "offset_x": 0.0,
        "offset_y": 0.0,
        "rotation": 0.0,
        "flip_x": False,
        "flip_y": False,
        "uniform_scale": 1.0,
    }


def _finite_float(value, default: float) -> float:
    try:
        result = float(value)
    except Exception:
        return float(default)
    return result if math.isfinite(result) else float(default)


def normalize_profile_placement(value=None) -> dict:
    source = dict(value) if isinstance(value, Mapping) else {}
    state = neutral_profile_placement()
    state["offset_x"] = _finite_float(source.get("offset_x", 0.0), 0.0)
    state["offset_y"] = _finite_float(source.get("offset_y", 0.0), 0.0)
    state["rotation"] = _finite_float(source.get("rotation", 0.0), 0.0)
    state["flip_x"] = bool(source.get("flip_x", False))
    state["flip_y"] = bool(source.get("flip_y", False))
    state["uniform_scale"] = max(
        0.001,
        _finite_float(source.get("uniform_scale", 1.0), 1.0),
    )
    return state


def resolve_profile_placement(state=None, **changes) -> dict:
    """Resolve absolute complete-profile placement independent of interaction order.

    Each semantic channel is authoritative. Updating one channel never bakes the
    current visible geometry into another, so equivalent final values always
    produce the same placement matrix.
    """
    resolved = normalize_profile_placement(state)
    for key in ("offset_x", "offset_y", "rotation", "flip_x", "flip_y", "uniform_scale"):
        if key in changes:
            resolved[key] = changes[key]
    return normalize_profile_placement(resolved)


def profile_placement_to_json(state) -> str:
    return json.dumps(normalize_profile_placement(state), sort_keys=True, separators=(",", ":"))


def profile_placement_from_json(raw: str) -> dict:
    try:
        value = json.loads(str(raw or ""))
    except Exception as exc:
        raise ProfileTransformError("Invalid serialized profile placement state") from exc
    if not isinstance(value, Mapping):
        raise ProfileTransformError("Profile placement state must be a JSON object")
    return normalize_profile_placement(value)


def has_profile_placement_state(profile) -> bool:
    if profile is None:
        return False
    try:
        return bool(str(profile.get(PROFILE_PLACEMENT_KEY, "") or "").strip())
    except Exception:
        return False


def profile_placement_state(profile) -> dict:
    if profile is None:
        return neutral_profile_placement()
    try:
        raw = str(profile.get(PROFILE_PLACEMENT_KEY, "") or "").strip()
    except Exception:
        raw = ""
    if not raw:
        return neutral_profile_placement()
    try:
        return profile_placement_from_json(raw)
    except ProfileTransformError:
        return neutral_profile_placement()


def set_profile_placement_state(profile, state) -> dict:
    normalized = normalize_profile_placement(state)
    if profile is not None:
        profile[PROFILE_PLACEMENT_KEY] = profile_placement_to_json(normalized)
    return normalized


def build_profile_placement_matrix(state=None) -> Matrix:
    """Build one canonical local placement matrix for a complete CPC profile.

    Composition is intentionally fixed:
    canonical geometry -> uniform scale -> flip -> rotation -> local offset.
    """
    value = normalize_profile_placement(state)
    scale = Matrix.Diagonal((
        value["uniform_scale"],
        value["uniform_scale"],
        1.0,
        1.0,
    ))
    flip = Matrix.Diagonal((
        -1.0 if value["flip_x"] else 1.0,
        -1.0 if value["flip_y"] else 1.0,
        1.0,
        1.0,
    ))
    rotation = Matrix.Rotation(value["rotation"], 4, 'Z')
    offset = Matrix.Translation((value["offset_x"], value["offset_y"], 0.0))
    return offset @ rotation @ flip @ scale


def profile_placement_frame(profile, base_frame) -> Matrix:
    """Compose a recipe/world frame with the profile's canonical local placement."""
    return _matrix4(base_frame) @ build_profile_placement_matrix(profile_placement_state(profile))


class ProfileTransformError(ValueError):
    pass


def _matrix4(value) -> Matrix:
    if isinstance(value, Matrix):
        matrix = value.copy()
    else:
        try:
            rows = [tuple(float(item) for item in row) for row in value]
        except Exception as exc:
            raise ProfileTransformError("Matrix data must be numeric rows") from exc
        if len(rows) != 4 or any(len(row) != 4 for row in rows):
            raise ProfileTransformError("Profile transform must be a 4x4 matrix")
        matrix = Matrix(rows)
    if len(matrix) != 4 or any(len(row) != 4 for row in matrix):
        raise ProfileTransformError("Profile transform must be a 4x4 matrix")
    return matrix


def matrix_to_data(matrix) -> list[list[float]]:
    matrix = _matrix4(matrix)
    return [[float(matrix[row][col]) for col in range(4)] for row in range(4)]


def matrix_from_data(data) -> Matrix:
    return _matrix4(data)


def matrix_to_json(matrix) -> str:
    return json.dumps(matrix_to_data(matrix), separators=(",", ":"))


def matrix_from_json(raw: str) -> Matrix:
    try:
        data = json.loads(str(raw or ""))
    except Exception as exc:
        raise ProfileTransformError("Invalid serialized profile matrix") from exc
    return matrix_from_data(data)


def build_profile_frame(origin_world) -> Matrix:
    """Build the CPC profile frame: Start origin with world-axis basis."""
    try:
        origin = Vector(origin_world)
    except Exception as exc:
        raise ProfileTransformError("Profile origin must be vector-like") from exc
    if len(origin) < 3:
        origin = Vector((float(origin[0]), float(origin[1]), 0.0))
    else:
        origin = Vector((float(origin[0]), float(origin[1]), float(origin[2])))
    return Matrix.Translation(origin)


def world_to_profile_matrix(component_world, profile_frame) -> Matrix:
    world = _matrix4(component_world)
    frame = _matrix4(profile_frame)
    try:
        return frame.inverted() @ world
    except Exception as exc:
        raise ProfileTransformError("Profile frame is not invertible") from exc


def profile_to_world_matrix(component_profile, placement_frame) -> Matrix:
    return _matrix4(placement_frame) @ _matrix4(component_profile)


def normalize_recipe_records(records: Iterable[Mapping], profile_frame) -> list[dict]:
    """Deep-copy recipe records and replace temporary world matrices with profile-space matrices."""
    frame = _matrix4(profile_frame)
    normalized = []
    for source in records:
        record = copy.deepcopy(dict(source))
        matrix_data = record.pop("matrix_world", None)
        if matrix_data is not None:
            world = matrix_from_data(matrix_data)
            record["matrix_profile"] = matrix_to_data(world_to_profile_matrix(world, frame))
        normalized.append(record)
    return normalized


def recipe_record_world_matrix(record: Mapping, placement_frame) -> Matrix | None:
    """Resolve a 0.4.0+ recipe record under the supplied whole-profile placement frame."""
    matrix_data = record.get("matrix_profile")
    if matrix_data is None:
        return None
    if placement_frame is None:
        raise ProfileTransformError("Normalized recipe matrix requires a placement frame")
    return profile_to_world_matrix(matrix_from_data(matrix_data), placement_frame)


def matrix_max_abs_error(a, b) -> float:
    left = _matrix4(a)
    right = _matrix4(b)
    return max(abs(float(left[r][c]) - float(right[r][c])) for r in range(4) for c in range(4))
