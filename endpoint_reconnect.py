"""Pure deterministic planning for explicit CPC endpoint reconnection."""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class EndpointRecord:
    object_key: str
    endpoint_index: int
    position: tuple[float, float, float]
    junction_id: str = ""
    sequence: int = 0


@dataclass(frozen=True)
class ReconnectCluster:
    members: tuple[EndpointRecord, ...]
    keep_id: str
    merged_ids: tuple[str, ...]
    needs_new_id: bool


def _distance_sq(left, right):
    return sum((float(a) - float(b)) ** 2 for a, b in zip(left, right))


def plan_reconnections(records, tolerance):
    tolerance = float(tolerance)
    if not math.isfinite(tolerance) or tolerance <= 0.0:
        raise ValueError("Reconnect tolerance must be greater than zero")
    ordered = tuple(
        sorted(
            records,
            key=lambda item: (
                int(item.sequence),
                str(item.object_key),
                int(item.endpoint_index),
            ),
        )
    )
    parent = list(range(len(ordered)))

    def find(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left, right):
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    limit = tolerance * tolerance
    for left in range(len(ordered)):
        for right in range(left + 1, len(ordered)):
            if _distance_sq(ordered[left].position, ordered[right].position) <= limit:
                union(left, right)

    grouped = {}
    for index, item in enumerate(ordered):
        grouped.setdefault(find(index), []).append(item)

    result = []
    for members in grouped.values():
        if len(members) < 2 or len({item.object_key for item in members}) < 2:
            continue
        ids = tuple(
            dict.fromkeys(
                item.junction_id for item in members if item.junction_id
            )
        )
        result.append(
            ReconnectCluster(
                members=tuple(members),
                keep_id=ids[0] if ids else "",
                merged_ids=ids[1:],
                needs_new_id=not ids,
            )
        )
    return tuple(result)
