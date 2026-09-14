"""Normalized profile-space transform helpers for CPC 0.4.0+ recipes.

CPC stores evaluated component transforms relative to one reusable Profile Frame.
Blender ``mathutils.Matrix`` remains authoritative for composition; persisted
records use JSON-safe row-major numeric lists. Semantic ``cpc_part_rotation`` is
stored separately by the recipe and is never inferred from these matrices.
"""

from __future__ import annotations

import copy
import json
from typing import Iterable, Mapping

from mathutils import Matrix, Vector


PROFILE_TRANSFORM_SCHEMA = 1
PROFILE_FRAME_POLICY = "START_ORIGIN_WORLD_BASIS"


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
