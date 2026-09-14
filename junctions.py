"""Endpoint junctions and hosted midpoint attachments for Curve Profile Creator.

CPC keeps two deliberately small semantic connection types:

* endpoint junctions — endpoint <-> endpoint, symmetric;
* hosted attachments — one CPC endpoint is attached to an interior point of
  another CPC part (currently Midpoint / Arc Midpoint / Curve Midpoint).

Hosted attachments are asymmetric for semantic shape editing: the host drives
its attached branch.  For ordinary connected Blender translation they still
participate in the undirected connected set, so moving either member with G
moves the complete connected construction rigidly.
"""

from __future__ import annotations

import uuid
import bpy
from mathutils import Vector


_START_KEY = "cpc_start_junction_id"
_END_KEY = "cpc_end_junction_id"
_HOST_COMPONENT_KEYS = (
    "cpc_start_host_component_id",
    "cpc_end_host_component_id",
)
_HOST_KIND_KEYS = (
    "cpc_start_host_kind",
    "cpc_end_host_kind",
)
_HOST_FRACTION_KEYS = (
    "cpc_start_host_fraction",
    "cpc_end_host_fraction",
)


def _key(endpoint_index):
    return _END_KEY if int(endpoint_index) else _START_KEY


def _endpoint(endpoint_index):
    return 1 if int(endpoint_index) else 0


def _component_id(obj):
    return str(obj.get("cpc_component_id", "") or "").strip() if obj else ""


def endpoint_id(obj, endpoint_index) -> str:
    if not obj:
        return ""
    return str(obj.get(_key(endpoint_index), "") or "").strip()


def set_endpoint_id(obj, endpoint_index, junction_id):
    if not obj:
        return
    junction_id = str(junction_id or "").strip()
    key = _key(endpoint_index)
    if junction_id:
        obj[key] = junction_id
    else:
        obj.pop(key, None)


def clear_endpoint(obj, endpoint_index):
    set_endpoint_id(obj, endpoint_index, "")


def hosted_attachment(obj, endpoint_index):
    """Return hosted-attachment metadata for one endpoint, or None."""
    if not obj:
        return None
    endpoint_index = _endpoint(endpoint_index)
    host_component_id = str(obj.get(_HOST_COMPONENT_KEYS[endpoint_index], "") or "").strip()
    if not host_component_id:
        return None
    kind = str(obj.get(_HOST_KIND_KEYS[endpoint_index], "MIDPOINT") or "MIDPOINT").strip().upper()
    try:
        fraction = float(obj.get(_HOST_FRACTION_KEYS[endpoint_index], 0.5))
    except Exception:
        fraction = 0.5
    return {
        "host_component_id": host_component_id,
        "kind": kind or "MIDPOINT",
        "fraction": min(max(fraction, 0.0), 1.0),
    }


def clear_hosted_attachment(obj, endpoint_index):
    if not obj:
        return
    endpoint_index = _endpoint(endpoint_index)
    obj.pop(_HOST_COMPONENT_KEYS[endpoint_index], None)
    obj.pop(_HOST_KIND_KEYS[endpoint_index], None)
    obj.pop(_HOST_FRACTION_KEYS[endpoint_index], None)


def set_hosted_attachment(guest, guest_endpoint, host, *, kind="MIDPOINT", fraction=0.5):
    """Attach one CPC endpoint to an interior semantic point of another CPC part."""
    if not guest or not host or guest == host:
        return False
    host_component_id = _component_id(host)
    if not host_component_id:
        return False
    guest_endpoint = _endpoint(guest_endpoint)
    # One endpoint owns one semantic connection type.
    clear_endpoint(guest, guest_endpoint)
    clear_hosted_attachment(guest, guest_endpoint)
    guest[_HOST_COMPONENT_KEYS[guest_endpoint]] = host_component_id
    guest[_HOST_KIND_KEYS[guest_endpoint]] = str(kind or "MIDPOINT").upper()
    guest[_HOST_FRACTION_KEYS[guest_endpoint]] = min(max(float(fraction), 0.0), 1.0)
    return True


def set_hosted_record(guest, guest_endpoint, record):
    """Restore a hosted attachment from serialized metadata without resolving its host yet."""
    if not guest or not isinstance(record, dict):
        return False
    host_component_id = str(record.get("host_component_id", "") or "").strip()
    if not host_component_id:
        return False
    guest_endpoint = _endpoint(guest_endpoint)
    clear_endpoint(guest, guest_endpoint)
    clear_hosted_attachment(guest, guest_endpoint)
    guest[_HOST_COMPONENT_KEYS[guest_endpoint]] = host_component_id
    guest[_HOST_KIND_KEYS[guest_endpoint]] = str(record.get("kind", "MIDPOINT") or "MIDPOINT").upper()
    guest[_HOST_FRACTION_KEYS[guest_endpoint]] = min(max(float(record.get("fraction", 0.5)), 0.0), 1.0)
    return True


def clear_object(obj):
    clear_endpoint(obj, 0)
    clear_endpoint(obj, 1)
    clear_hosted_attachment(obj, 0)
    clear_hosted_attachment(obj, 1)


def new_id() -> str:
    return f"junction-{uuid.uuid4()}"


def component_objects():
    collections = getattr(bpy.data, "collections", None)
    if collections is None:
        return []
    coll = collections.get("CPC_ProfileParts")
    if not coll:
        return []
    return [
        obj for obj in coll.objects
        if obj.get("cpc_part") and not obj.get("cpc_preview")
    ]


def members_map(objects=None):
    result = {}
    for obj in objects if objects is not None else component_objects():
        for endpoint in (0, 1):
            junction_id = endpoint_id(obj, endpoint)
            if junction_id:
                result.setdefault(junction_id, []).append((obj, endpoint))
    return result


def hosted_children(host, objects=None):
    """Return (guest, guest_endpoint, metadata) entries hosted by ``host``."""
    host_id = _component_id(host)
    if not host_id:
        return []
    result = []
    for guest in objects if objects is not None else component_objects():
        if guest == host:
            continue
        for endpoint in (0, 1):
            record = hosted_attachment(guest, endpoint)
            if record and record["host_component_id"] == host_id:
                result.append((guest, endpoint, record))
    return result


def merge_ids(keep_id, drop_id, objects=None):
    keep_id = str(keep_id or "").strip()
    drop_id = str(drop_id or "").strip()
    if not keep_id or not drop_id or keep_id == drop_id:
        return keep_id or drop_id
    for obj in objects if objects is not None else component_objects():
        for endpoint in (0, 1):
            if endpoint_id(obj, endpoint) == drop_id:
                set_endpoint_id(obj, endpoint, keep_id)
    return keep_id


def connect_endpoints(a, endpoint_a, b, endpoint_b, *, objects=None):
    """Make two CPC endpoints members of the same semantic junction."""
    if not a or not b or a == b and int(endpoint_a) == int(endpoint_b):
        return ""
    endpoint_a = _endpoint(endpoint_a)
    endpoint_b = _endpoint(endpoint_b)
    # Endpoint-to-endpoint connection supersedes any hosted relation at those endpoints.
    clear_hosted_attachment(a, endpoint_a)
    clear_hosted_attachment(b, endpoint_b)
    a_id = endpoint_id(a, endpoint_a)
    b_id = endpoint_id(b, endpoint_b)
    if a_id and b_id:
        junction_id = merge_ids(a_id, b_id, objects=objects)
    else:
        junction_id = a_id or b_id or new_id()
    set_endpoint_id(a, endpoint_a, junction_id)
    set_endpoint_id(b, endpoint_b, junction_id)
    return junction_id


def connect_chain(parts):
    """Connect construction-order End -> Start endpoints for an open recipe chain."""
    parts = list(parts or ())
    for left, right in zip(parts, parts[1:]):
        connect_endpoints(left, 1, right, 0, objects=parts)



def _bezier_point(p0, p1, p2, p3, u):
    v = 1.0 - u
    return (v ** 3) * p0 + 3.0 * (v ** 2) * u * p1 + 3.0 * v * (u ** 2) * p2 + (u ** 3) * p3


def curve_frame_local(obj, fraction=0.5, samples_per_segment=32):
    """Approximate an arc-length-fraction point and forward tangent on a CPC curve."""
    if not obj or obj.type != 'CURVE' or not obj.data.splines:
        return None
    spline = obj.data.splines[0]
    fraction = min(max(float(fraction), 0.0), 1.0)
    samples = []

    if spline.type == 'BEZIER' and len(spline.bezier_points) >= 2:
        points = spline.bezier_points
        steps = max(int(samples_per_segment), 8)
        for index in range(len(points) - 1):
            a = points[index]
            b = points[index + 1]
            p0, p1, p2, p3 = a.co.copy(), a.handle_right.copy(), b.handle_left.copy(), b.co.copy()
            for step in range(steps + 1):
                if index and step == 0:
                    continue
                u = step / float(steps)
                samples.append(_bezier_point(p0, p1, p2, p3, u))
    elif spline.points:
        samples = [Vector(point.co[:3]) for point in spline.points]

    if not samples:
        return None
    if len(samples) == 1:
        return samples[0].copy(), Vector((1.0, 0.0, 0.0))

    lengths = []
    total = 0.0
    for a, b in zip(samples, samples[1:]):
        seg = (b - a).length
        lengths.append(seg)
        total += seg
    if total <= 1.0e-12:
        return samples[0].copy(), Vector((1.0, 0.0, 0.0))

    target = total * fraction
    accum = 0.0
    for index, seg in enumerate(lengths):
        if accum + seg >= target or index == len(lengths) - 1:
            factor = 0.0 if seg <= 1.0e-12 else min(max((target - accum) / seg, 0.0), 1.0)
            position = samples[index].lerp(samples[index + 1], factor)
            tangent = samples[index + 1] - samples[index]
            if tangent.length <= 1.0e-10:
                tangent = Vector((1.0, 0.0, 0.0))
            else:
                tangent.normalize()
            return position, tangent
        accum += seg
    tangent = samples[-1] - samples[-2]
    if tangent.length <= 1.0e-10:
        tangent = Vector((1.0, 0.0, 0.0))
    else:
        tangent.normalize()
    return samples[-1].copy(), tangent


def curve_frame_world(obj, fraction=0.5, *, matrix=None):
    frame = curve_frame_local(obj, fraction)
    if frame is None:
        return None
    local_position, local_tangent = frame
    matrix = matrix.copy() if matrix is not None else obj.matrix_world.copy()
    position = matrix @ local_position
    tangent = matrix.to_3x3() @ local_tangent
    tangent.z = 0.0
    if tangent.length <= 1.0e-10:
        tangent = Vector((1.0, 0.0, 0.0))
    else:
        tangent.normalize()
    return position, tangent


def host_frame_world(host, attachment_record, *, matrix=None):
    if not host or not attachment_record:
        return None
    kind = str(attachment_record.get("kind", "MIDPOINT") or "MIDPOINT").upper()
    fraction = float(attachment_record.get("fraction", 0.5))
    # Hosted attachments intentionally target semantic midpoint frames. Keeping
    # the fraction in the schema makes future arbitrary point-on-curve support
    # possible without changing the topology record again.
    if kind in {"MIDPOINT", "ARC_MIDPOINT", "CURVE_MIDPOINT"}:
        return curve_frame_world(host, fraction, matrix=matrix)
    return curve_frame_world(host, fraction, matrix=matrix)


def connected_objects(root, *, objects=None, tolerance=0.0005, instance_id=""):
    """Return the coincident topology-connected object set containing ``root``.

    Endpoint junctions and hosted midpoint attachments both participate. Hosted
    relations are traversed in both directions for rigid connected translation;
    semantic shape editing remains host-driven in ``primitives``.
    """
    if not root:
        return []
    from . import library

    objects = list(objects if objects is not None else component_objects())
    instance_id = str(instance_id or "")
    if instance_id:
        objects = [
            obj for obj in objects
            if str(obj.get("cpc_arch_instance_id", "") or "") == instance_id
        ]
    if root not in objects:
        objects.append(root)

    members = members_map(objects)
    by_id = {_component_id(obj): obj for obj in objects if _component_id(obj)}
    hosted_by_host = {}
    for guest in objects:
        for endpoint in (0, 1):
            record = hosted_attachment(guest, endpoint)
            if record:
                hosted_by_host.setdefault(record["host_component_id"], []).append((guest, endpoint, record))

    tolerance = max(float(tolerance), 1.0e-6)
    seen = {root}
    stack = [root]
    while stack:
        obj = stack.pop()
        obj_id = _component_id(obj)

        # Symmetric endpoint junctions.
        for endpoint in (0, 1):
            junction_id = endpoint_id(obj, endpoint)
            if not junction_id:
                continue
            try:
                pos = library.object_endpoint_world(obj, endpoint)
            except Exception:
                continue
            for other, other_endpoint in members.get(junction_id, ()):
                if other in seen:
                    continue
                try:
                    other_pos = library.object_endpoint_world(other, other_endpoint)
                except Exception:
                    continue
                if (other_pos - pos).length > tolerance:
                    continue
                seen.add(other)
                stack.append(other)

        # Host -> guest midpoint attachments.
        for guest, guest_endpoint, record in hosted_by_host.get(obj_id, ()):
            if guest in seen:
                continue
            try:
                host_frame = host_frame_world(obj, record)
                guest_pos = library.object_endpoint_world(guest, guest_endpoint)
            except Exception:
                continue
            if not host_frame or (guest_pos - host_frame[0]).length > tolerance:
                continue
            seen.add(guest)
            stack.append(guest)

        # Guest -> host, for rigid connected traversal only.
        for guest_endpoint in (0, 1):
            record = hosted_attachment(obj, guest_endpoint)
            if not record:
                continue
            host = by_id.get(record["host_component_id"])
            if not host or host in seen:
                continue
            try:
                host_frame = host_frame_world(host, record)
                guest_pos = library.object_endpoint_world(obj, guest_endpoint)
            except Exception:
                continue
            if not host_frame or (guest_pos - host_frame[0]).length > tolerance:
                continue
            seen.add(host)
            stack.append(host)
    return list(seen)
