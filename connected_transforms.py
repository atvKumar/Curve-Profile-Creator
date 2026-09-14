"""Connected CPC part translation handling.

Ordinary Blender translation remains compatible with CPC's
endpoint-junction graph.  When Maintain Connected Parts is enabled, moving
any currently connected construction part with Blender G (or by changing its
Location) translates the complete connected CPC profile rigidly.

This module deliberately handles translation only.  CPC Part Rotation remains
the semantic rotation path, and Width/Height/Chord/Depth remain the semantic
shape-edit paths.
"""

from __future__ import annotations

import bpy
from bpy.app.handlers import persistent
from mathutils import Matrix, Vector

from . import junctions, library


_MATRIX_CACHE: dict[int, Matrix] = {}
_IN_HANDLER = False

_TRANSLATION_EPS = 1.0e-10
_LINEAR_EPS = 1.0e-8


def _object_key(obj) -> int:
    try:
        return int(obj.as_pointer())
    except Exception:
        return id(obj)


def _eligible(obj) -> bool:
    return bool(
        obj
        and isinstance(obj, bpy.types.Object)
        and obj.get("cpc_part")
        and not obj.get("cpc_preview")
    )


def _component_objects():
    """Return editable CPC parts when normal Blender data access is available.

    During extension registration Blender may expose ``bpy.data`` as
    ``_RestrictData``. Registration must not touch scene collections then.
    The cache is populated lazily on the first normal depsgraph update/load.
    """
    collections = getattr(bpy.data, "collections", None)
    if collections is None:
        return []
    coll = collections.get("CPC_ProfileParts")
    if not coll:
        return []
    return [obj for obj in coll.objects if _eligible(obj)]


def sync_object(obj):
    """Record an object's current world matrix as the next external-transform baseline."""
    if not _eligible(obj):
        return
    try:
        _MATRIX_CACHE[_object_key(obj)] = obj.matrix_world.copy()
    except Exception:
        pass


def sync_objects(objects):
    for obj in objects or ():
        sync_object(obj)


def prime_cache():
    """Rebuild the session-local transform cache from currently editable CPC parts."""
    _MATRIX_CACHE.clear()
    sync_objects(_component_objects())


def _linear_equal(a: Matrix, b: Matrix, eps=_LINEAR_EPS) -> bool:
    try:
        aa = a.to_3x3()
        bb = b.to_3x3()
        for r in range(3):
            for c in range(3):
                if abs(float(aa[r][c]) - float(bb[r][c])) > eps:
                    return False
        return True
    except Exception:
        return False


def _translation_delta(old: Matrix, new: Matrix):
    """Return a pure world-translation delta, or None for rotation/scale/shear changes."""
    if not _linear_equal(old, new):
        return None
    delta = new.translation - old.translation
    if delta.length_squared <= _TRANSLATION_EPS * _TRANSLATION_EPS:
        return None
    return delta


def _cached_matrix(obj):
    return _MATRIX_CACHE.get(_object_key(obj), obj.matrix_world.copy())


def _endpoint_world_from_matrix(obj, endpoint_index, matrix):
    local = library.curve_endpoint_local(obj, 1 if int(endpoint_index) else 0)
    return matrix @ local


def _old_connection_adjacency(parts, tolerance):
    """Build an undirected graph from endpoint junctions in the pre-transform state.

    Shared junction IDs express semantic connectivity. Cached endpoint positions
    still gate the edge so a manually detached stale junction does not pull
    geometry back unexpectedly.
    """
    tolerance = max(float(tolerance), 1.0e-6)
    adjacency = {obj: set() for obj in parts}
    members = junctions.members_map(parts)

    for _junction_id, endpoint_members in members.items():
        endpoint_members = list(endpoint_members)
        for index, (left, left_endpoint) in enumerate(endpoint_members):
            try:
                left_pos = _endpoint_world_from_matrix(
                    left,
                    left_endpoint,
                    _cached_matrix(left),
                )
            except Exception:
                continue
            for right, right_endpoint in endpoint_members[index + 1:]:
                if right == left:
                    continue
                try:
                    right_pos = _endpoint_world_from_matrix(
                        right,
                        right_endpoint,
                        _cached_matrix(right),
                    )
                except Exception:
                    continue
                if (left_pos - right_pos).length <= tolerance:
                    adjacency[left].add(right)
                    adjacency[right].add(left)

    # Hosted midpoint attachments participate in rigid connected translation in
    # both directions.  Cached matrices represent the pre-drag state, so stale
    # metadata from an intentionally detached branch does not reconnect it.
    by_component_id = {
        str(obj.get("cpc_component_id", "") or "").strip(): obj
        for obj in parts
        if str(obj.get("cpc_component_id", "") or "").strip()
    }
    for guest in parts:
        for guest_endpoint in (0, 1):
            record = junctions.hosted_attachment(guest, guest_endpoint)
            if not record:
                continue
            host = by_component_id.get(record["host_component_id"])
            if not host or host == guest:
                continue
            try:
                guest_pos = _endpoint_world_from_matrix(
                    guest, guest_endpoint, _cached_matrix(guest)
                )
                host_frame = junctions.host_frame_world(
                    host, record, matrix=_cached_matrix(host)
                )
            except Exception:
                continue
            if host_frame and (guest_pos - host_frame[0]).length <= tolerance:
                adjacency[guest].add(host)
                adjacency[host].add(guest)
    return adjacency


def _connected_set(root, adjacency):
    if root not in adjacency:
        return {root}
    seen = {root}
    stack = [root]
    while stack:
        obj = stack.pop()
        for neighbour in adjacency.get(obj, ()):
            if neighbour in seen:
                continue
            seen.add(neighbour)
            stack.append(neighbour)
    return seen


def _same_delta(a: Vector, b: Vector, eps=1.0e-8) -> bool:
    return (a - b).length <= eps


def _tag_redraw():
    try:
        wm = bpy.context.window_manager
    except Exception:
        wm = None
    if not wm:
        return
    for window in wm.windows:
        screen = getattr(window, "screen", None)
        if not screen:
            continue
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()


def _updated_original_object(update):
    id_data = getattr(update, "id", None)
    if not isinstance(id_data, bpy.types.Object):
        return None
    try:
        original = getattr(id_data, "original", None)
        if isinstance(original, bpy.types.Object):
            return original
    except Exception:
        pass
    return id_data


@persistent
def _depsgraph_update_post(scene, depsgraph):
    """Propagate external pure translations through the undirected connected profile."""
    global _IN_HANDLER
    if _IN_HANDLER:
        return

    parts = _component_objects()
    live_keys = {_object_key(obj) for obj in parts}
    for key in tuple(_MATRIX_CACHE):
        if key not in live_keys:
            _MATRIX_CACHE.pop(key, None)

    # First encounter establishes a baseline; it must never be interpreted as a move.
    for obj in parts:
        key = _object_key(obj)
        if key not in _MATRIX_CACHE:
            _MATRIX_CACHE[key] = obj.matrix_world.copy()

    updated_objects = []
    seen = set()
    try:
        for update in depsgraph.updates:
            obj = _updated_original_object(update)
            if not _eligible(obj):
                continue
            key = _object_key(obj)
            if key in seen:
                continue
            seen.add(key)
            updated_objects.append(obj)
    except Exception:
        updated_objects = []

    if not updated_objects:
        return

    # Classify all changed transforms against the same pre-update cache before
    # mutating that cache.  This is important for preserving pre-drag junctions.
    translations = {}
    other_transform_changes = set()
    for obj in updated_objects:
        key = _object_key(obj)
        old = _MATRIX_CACHE.get(key)
        if old is None:
            continue
        new = obj.matrix_world.copy()
        if _linear_equal(old, new):
            delta = _translation_delta(old, new)
            if delta is not None:
                translations[key] = (obj, delta)
        else:
            other_transform_changes.add(key)

    settings = getattr(scene, "cpc_settings", None)
    maintain = bool(getattr(settings, "maintain_connected_parts", True))
    tolerance = float(getattr(settings, "merge_tolerance", 0.0005))

    if not maintain or not translations:
        sync_objects(updated_objects)
        return

    adjacency = _old_connection_adjacency(parts, tolerance)
    by_key = {_object_key(obj): obj for obj in parts}
    processed = set()
    moved_any = False

    _IN_HANDLER = True
    try:
        for source_key, (source, source_delta) in tuple(translations.items()):
            if source_key in processed:
                continue

            connected = _connected_set(source, adjacency)
            connected_keys = {_object_key(obj) for obj in connected}
            processed.update(connected_keys)

            # If some object in this connected set simultaneously changed its
            # rotation/scale/shear, do not guess at a compound Blender transform.
            # CPC only promises automatic handling for pure translation.
            if connected_keys & other_transform_changes:
                sync_objects(connected)
                continue

            changed_here = {
                key: value
                for key, value in translations.items()
                if key in connected_keys
            }
            if not changed_here:
                continue

            deltas = [value[1] for value in changed_here.values()]
            if any(not _same_delta(source_delta, delta) for delta in deltas[1:]):
                # Multiple members were translated by different deltas in the
                # same depsgraph tick.  That is not a rigid profile move, so do
                # not solve or distort it automatically.
                sync_objects(connected)
                continue

            already_moved = set(changed_here)
            for obj in connected:
                key = _object_key(obj)
                if key in already_moved:
                    continue
                matrix = obj.matrix_world.copy()
                matrix.translation = matrix.translation + source_delta
                obj.matrix_world = matrix
                obj.update_tag()
                moved_any = True

            # All members now share the same rigid world translation baseline.
            sync_objects(connected)

        # Any updated object outside a processed connected set still needs a
        # fresh baseline for the next user transform.
        for obj in updated_objects:
            if _object_key(obj) not in processed:
                sync_object(obj)
    except Exception as exc:
        print(f"[Curve Profile Creator] connected transform warning: {exc}")
        sync_objects(parts)
    finally:
        _IN_HANDLER = False

    if moved_any:
        _tag_redraw()


@persistent
def _load_post(_dummy):
    prime_cache()


def register():
    if _depsgraph_update_post not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_depsgraph_update_post)
    if _load_post not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_load_post)

    # Blender extension registration may run under bpy.data _RestrictData,
    # where scene collections are intentionally hidden. Start empty here.
    # Missing baselines are established lazily by the depsgraph handler, while
    # load_post primes the cache once ordinary file data is available.
    _MATRIX_CACHE.clear()


def unregister():
    if _depsgraph_update_post in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_depsgraph_update_post)
    if _load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_load_post)
    _MATRIX_CACHE.clear()
