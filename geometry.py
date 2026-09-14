import os
import bpy
import bmesh
from mathutils import Vector


def set_curve_fill_both(curve):
    """Set full/two-sided curve fill across Blender API versions.

    Blender 5.x accepts ``BOTH`` while Blender 4.x used ``FULL``.  Do not use
    RNA enum introspection here: Blender 5.2 can expose legacy enum metadata
    even though the runtime setter only accepts the new identifiers.  The
    setter itself is therefore the compatibility test.
    """
    try:
        curve.fill_mode = 'BOTH'
        return 'BOTH'
    except (TypeError, ValueError):
        pass

    try:
        curve.fill_mode = 'FULL'
        return 'FULL'
    except (TypeError, ValueError):
        # A future Blender version may rename the enum again.  Fill mode is not
        # essential to constructing the profile/path datablock, so preserve
        # Blender's default instead of aborting the modelling operation.
        return curve.fill_mode


def remove_cpc_smooth_by_angle(obj):
    """Remove only Smooth by Angle modifiers that CPC previously created."""
    if not obj:
        return 0
    removed = 0
    for mod in list(obj.modifiers):
        try:
            owned = bool(mod.get("cpc_smooth_by_angle"))
        except Exception:
            owned = False
        if owned:
            obj.modifiers.remove(mod)
            removed += 1
    return removed


def _set_nodes_modifier_input(modifier, socket_name, value):
    """Set a Geometry Nodes modifier input by interface socket name."""
    group = getattr(modifier, "node_group", None)
    interface = getattr(group, "interface", None) if group else None
    items = getattr(interface, "items_tree", None) if interface else None
    if not items:
        return False
    for item in items:
        if getattr(item, "item_type", None) != 'SOCKET':
            continue
        if getattr(item, "in_out", None) != 'INPUT':
            continue
        if getattr(item, "name", "") != socket_name:
            continue
        identifier = getattr(item, "identifier", "")
        if not identifier:
            continue
        try:
            modifier[identifier] = value
            return True
        except Exception:
            return False
    return False


def update_cpc_smooth_angle(obj, angle):
    """Update the Angle input on an existing CPC-owned Smooth by Angle modifier."""
    if not obj:
        return False
    for mod in obj.modifiers:
        try:
            owned = bool(mod.get("cpc_smooth_by_angle"))
        except Exception:
            owned = False
        if not owned:
            continue
        changed = _set_nodes_modifier_input(mod, "Angle", float(angle))
        if not changed:
            for identifier in ("Input_1", "Socket_1"):
                try:
                    mod[identifier] = float(angle)
                    changed = True
                    break
                except Exception:
                    pass
        try:
            mod["cpc_smooth_angle"] = float(angle)
        except Exception:
            pass
        if changed:
            obj.update_tag()
        return changed
    return False


def _find_loaded_smooth_by_angle_group():
    """Return an already loaded Smooth by Angle geometry node group, if any."""
    exact = bpy.data.node_groups.get("Smooth by Angle")
    if exact and getattr(exact, "bl_idname", "") == 'GeometryNodeTree':
        return exact
    for group in bpy.data.node_groups:
        if getattr(group, "bl_idname", "") != 'GeometryNodeTree':
            continue
        if group.name.lower().startswith("smooth by angle"):
            return group
    return None


def _smooth_by_angle_library_candidates():
    """Yield installed Blender Essentials blend files that may contain Smooth by Angle.

    Blender 5.x consolidated Geometry Nodes Essentials into
    ``datafiles/assets/nodes/geometry_nodes_essentials.blend``. Blender 4.x used
    the older per-asset ``geometry_nodes/smooth_by_angle.blend`` layout. Try
    LOCAL and SYSTEM resource roots so portable/system installs are both covered.
    """
    relpaths = (
        os.path.join("datafiles", "assets", "nodes", "geometry_nodes_essentials.blend"),
        os.path.join("datafiles", "assets", "geometry_nodes", "smooth_by_angle.blend"),
    )
    seen = set()
    for resource_type in ('LOCAL', 'SYSTEM'):
        try:
            root = bpy.utils.resource_path(resource_type)
        except Exception:
            root = ""
        if not root:
            continue
        for relpath in relpaths:
            path = os.path.normpath(os.path.join(root, relpath))
            key = os.path.normcase(path)
            if key in seen:
                continue
            seen.add(key)
            yield path


def _load_smooth_by_angle_group_direct():
    """Load Blender's bundled Smooth by Angle node group directly from Essentials."""
    group = _find_loaded_smooth_by_angle_group()
    if group is not None:
        return group, "already loaded"

    errors = []
    for filepath in _smooth_by_angle_library_candidates():
        if not os.path.isfile(filepath):
            continue
        try:
            # Direct library loading avoids depending on Asset Browser/operator
            # context. Only the requested node group is appended below.
            with bpy.data.libraries.load(filepath, link=False) as (data_from, data_to):
                available = list(getattr(data_from, "node_groups", ()))
                name = next((n for n in available if n == "Smooth by Angle"), None)
                if name is None:
                    name = next((n for n in available if n.lower().startswith("smooth by angle")), None)
                if name is None:
                    errors.append(f"not found in {filepath}")
                    continue
                data_to.node_groups = [name]
            group = _find_loaded_smooth_by_angle_group()
            if group is not None:
                return group, filepath
        except Exception as exc:
            errors.append(f"{filepath}: {exc}")

    return None, "; ".join(errors) if errors else "Essentials library file not found"


def _add_smooth_by_angle_via_operator(context, obj):
    """Fallback to Blender's asset operator using both 5.x and legacy IDs."""
    identifiers = (
        r"nodes\geometry_nodes_essentials.blend\NodeTree\Smooth by Angle",
        r"geometry_nodes\smooth_by_angle.blend\NodeTree\Smooth by Angle",
    )
    errors = []
    for identifier in identifiers:
        before = {mod.as_pointer() for mod in obj.modifiers}
        try:
            op = bpy.ops.object.modifier_add_node_group
            rna = op.get_rna_type()
            props = rna.properties
            kwargs = {
                "asset_library_type": 'ESSENTIALS',
                "asset_library_identifier": "",
                "relative_asset_identifier": identifier,
            }
            if "use_selected_objects" in props:
                kwargs["use_selected_objects"] = False

            override = {
                "object": obj,
                "active_object": obj,
                "selected_objects": [obj],
                "selected_editable_objects": [obj],
            }
            with context.temp_override(**override):
                result = op(**kwargs)
            if 'FINISHED' not in result:
                errors.append(f"{identifier}: {result}")
                continue
            created = [mod for mod in obj.modifiers if mod.as_pointer() not in before]
            candidate = next((m for m in created if m.type == 'NODES'), None)
            if candidate is not None:
                return candidate, identifier
        except Exception as exc:
            errors.append(f"{identifier}: {exc}")
    return None, "; ".join(errors)


def ensure_smooth_by_angle(context, obj, angle, enabled=True):
    """Add Blender's bundled Smooth by Angle Geometry Nodes modifier robustly.

    Blender 5.x changed the Essentials asset layout, and operator-based asset
    insertion can also depend on UI/asset-library state. CPC therefore prefers
    a direct load of Blender's bundled node group, then creates a normal NODES
    modifier. The asset operator remains a compatibility fallback.
    """
    if not obj:
        return False, "No sweep object"

    if not enabled:
        remove_cpc_smooth_by_angle(obj)
        return True, "Disabled"

    # Avoid stacking CPC-owned copies when Apply Profile is used repeatedly.
    existing = None
    for mod in obj.modifiers:
        try:
            if mod.get("cpc_smooth_by_angle"):
                existing = mod
                break
        except Exception:
            pass
    if existing is not None:
        update_cpc_smooth_angle(obj, angle)
        return True, existing.name

    # Preferred path: load/reuse Blender's bundled node group directly. This is
    # independent of the current editor context and of asynchronous asset-index
    # state, which makes it considerably more reliable from an extension.
    group, source = _load_smooth_by_angle_group_direct()
    candidate = None
    if group is not None:
        try:
            candidate = obj.modifiers.new(name="Smooth by Angle", type='NODES')
            candidate.node_group = group
        except Exception as exc:
            candidate = None
            source = f"direct modifier creation failed: {exc}"

    # Compatibility fallback for installations where the bundled file layout is
    # different from the known Blender 4.x/5.x layouts.
    if candidate is None:
        candidate, op_message = _add_smooth_by_angle_via_operator(context, obj)
        if candidate is None:
            return False, f"{source}; operator fallback: {op_message}"
        source = op_message

    try:
        candidate["cpc_smooth_by_angle"] = True
        candidate["cpc_smooth_angle"] = float(angle)
    except Exception:
        pass

    # Prefer named interface lookup. Retain known legacy identifiers as a final
    # fallback because older Smooth by Angle assets used Input_1/Socket_1.
    changed = _set_nodes_modifier_input(candidate, "Angle", float(angle))
    if not changed:
        for identifier in ("Input_1", "Socket_1"):
            try:
                candidate[identifier] = float(angle)
                changed = True
                break
            except Exception:
                pass

    try:
        candidate.show_viewport = True
        candidate.show_render = True
    except Exception:
        pass
    try:
        if candidate.node_group:
            candidate.node_group.interface_update(context)
    except Exception:
        pass
    obj.update_tag()
    try:
        context.view_layer.update()
    except Exception:
        pass
    return True, f"{candidate.name} ({source})"


def cubic_bezier(p0, p1, p2, p3, t):
    u = 1.0 - t
    return (u ** 3) * p0 + 3.0 * (u ** 2) * t * p1 + 3.0 * u * (t ** 2) * p2 + (t ** 3) * p3


def sample_curve_object_world(obj, resolution=12):
    """Return one world-space point-list per spline in a Curve object."""
    if not obj or obj.type != 'CURVE':
        return []
    result = []
    mw = obj.matrix_world

    for spline in obj.data.splines:
        pts = []
        if spline.type == 'BEZIER':
            bps = spline.bezier_points
            count = len(bps)
            if count < 2:
                continue
            span_count = count if spline.use_cyclic_u else count - 1
            for i in range(span_count):
                a = bps[i]
                b = bps[(i + 1) % count]
                for step in range(resolution):
                    if i > 0 and step == 0:
                        continue
                    t = step / float(resolution)
                    co = cubic_bezier(a.co, a.handle_right, b.handle_left, b.co, t)
                    pts.append(mw @ co)
            pts.append(mw @ bps[0 if spline.use_cyclic_u else -1].co)
        elif spline.type in {'POLY', 'NURBS'}:
            pts = [mw @ Vector(p.co[:3]) for p in spline.points]
            if spline.use_cyclic_u and pts and (pts[0] - pts[-1]).length > 1e-9:
                pts.append(pts[0].copy())
        if len(pts) >= 2:
            result.append(pts)
    return result



def bezier_splines_world(obj):
    """Return preservable world-space Bézier spline point specs for ``obj``.

    The committed-profile Bézier path deliberately accepts only open Bézier
    splines with at least two points.  Unsupported/mixed legacy geometry is
    reported to the caller so Commit can use the proven sampled fallback
    rather than silently changing topology.
    """
    if not obj or obj.type != 'CURVE':
        return None, "not a Curve object"
    if not obj.data.splines:
        return None, "contains no splines"

    mw = obj.matrix_world
    result = []
    for index, spline in enumerate(obj.data.splines):
        if spline.type != 'BEZIER':
            return None, f"spline {index + 1} is {spline.type}, not Bézier"
        if spline.use_cyclic_u:
            return None, f"spline {index + 1} is cyclic"
        if len(spline.bezier_points) < 2:
            return None, f"spline {index + 1} has fewer than two points"

        points = []
        for point_index, bp in enumerate(spline.bezier_points):
            left_type = str(bp.handle_left_type)
            right_type = str(bp.handle_right_type)
            # CPC's canonical primitives use explicit FREE/VECTOR semantics.
            # Automatic/aligned legacy handles can be recalculated by Blender
            # when neighboring topology changes, so use sampled fallback rather
            # than claim an exact preservation we cannot guarantee.
            if left_type not in {'FREE', 'VECTOR'} or right_type not in {'FREE', 'VECTOR'}:
                return None, (
                    f"spline {index + 1} point {point_index + 1} uses "
                    f"{left_type}/{right_type} handles"
                )
            points.append({
                "co": mw @ bp.co,
                "handle_left": mw @ bp.handle_left,
                "handle_right": mw @ bp.handle_right,
                "handle_left_type": left_type,
                "handle_right_type": right_type,
                "radius": float(bp.radius),
                "tilt": float(bp.tilt),
                "weight_softbody": float(bp.weight_softbody),
            })
        result.append(points)

    return result, ""


def _reverse_bezier_points(points):
    """Reverse a Bézier point sequence while preserving each side's handles."""
    reversed_points = []
    for point in reversed(points):
        reversed_points.append({
            "co": point["co"].copy(),
            "handle_left": point["handle_right"].copy(),
            "handle_right": point["handle_left"].copy(),
            "handle_left_type": point["handle_right_type"],
            "handle_right_type": point["handle_left_type"],
            "radius": point.get("radius", 1.0),
            "tilt": point.get("tilt", 0.0),
            "weight_softbody": point.get("weight_softbody", 0.0),
        })
    return reversed_points


def _merge_bezier_junction(left, right):
    """Merge touching endpoints without losing either segment's handle vector.

    A tiny positional mismatch can exist because older/custom parts may only be
    within merge tolerance.  The shared committed point is placed at the
    midpoint and each retained handle is translated by the same endpoint delta,
    preserving its tangent vector and local cubic construction.
    """
    co = (left["co"] + right["co"]) * 0.5
    left_delta = co - left["co"]
    right_delta = co - right["co"]
    return {
        "co": co,
        "handle_left": left["handle_left"] + left_delta,
        "handle_right": right["handle_right"] + right_delta,
        "handle_left_type": left["handle_left_type"],
        "handle_right_type": right["handle_right_type"],
        "radius": (float(left.get("radius", 1.0)) + float(right.get("radius", 1.0))) * 0.5,
        "tilt": (float(left.get("tilt", 0.0)) + float(right.get("tilt", 0.0))) * 0.5,
        "weight_softbody": (
            float(left.get("weight_softbody", 0.0)) + float(right.get("weight_softbody", 0.0))
        ) * 0.5,
    }


def stitch_bezier_splines(splines, tolerance):
    """Stitch open Bézier splines by touching endpoints.

    Each input spline may be reversed.  At a join, the two coincident endpoint
    records become one Blender Bézier point: the incoming left handle is kept
    from the preceding spline and the outgoing right handle from the following
    spline.  This is the key operation that lets CPC preserve straight/curve
    side semantics at architectural component junctions.
    """
    pending = [list(points) for points in splines if len(points) >= 2]
    chains = []

    while pending:
        chain = pending.pop(0)
        changed = True
        while changed and pending:
            changed = False
            best = None
            for idx, seg in enumerate(pending):
                tests = (
                    ((chain[-1]["co"] - seg[0]["co"]).length, 'APPEND', False),
                    ((chain[-1]["co"] - seg[-1]["co"]).length, 'APPEND', True),
                    ((chain[0]["co"] - seg[-1]["co"]).length, 'PREPEND', False),
                    ((chain[0]["co"] - seg[0]["co"]).length, 'PREPEND', True),
                )
                local_best = min(tests, key=lambda item: item[0])
                if best is None or local_best[0] < best[0]:
                    best = (local_best[0], idx, local_best[1], local_best[2])

            if best and best[0] <= tolerance:
                _dist, idx, mode, reverse = best
                seg = pending.pop(idx)
                if reverse:
                    seg = _reverse_bezier_points(seg)

                if mode == 'APPEND':
                    chain[-1] = _merge_bezier_junction(chain[-1], seg[0])
                    chain.extend(seg[1:])
                else:
                    merged = _merge_bezier_junction(seg[-1], chain[0])
                    chain = seg[:-1] + [merged] + chain[1:]
                changed = True

        chains.append(chain)

    return chains


def _dedupe_adjacent(points, eps=1e-9):
    if not points:
        return []
    result = [points[0]]
    for p in points[1:]:
        if (p - result[-1]).length > eps:
            result.append(p)
    return result


def stitch_segments(segments, tolerance):
    """Stitch sampled line segments by nearest touching endpoints.

    Returns a list of continuous chains. Each input segment can be reversed.
    """
    pending = [list(seg) for seg in segments if len(seg) >= 2]
    chains = []

    while pending:
        chain = pending.pop(0)
        changed = True
        while changed and pending:
            changed = False
            best = None
            for idx, seg in enumerate(pending):
                tests = (
                    ((chain[-1] - seg[0]).length, 'APPEND', False),
                    ((chain[-1] - seg[-1]).length, 'APPEND', True),
                    ((chain[0] - seg[-1]).length, 'PREPEND', False),
                    ((chain[0] - seg[0]).length, 'PREPEND', True),
                )
                local_best = min(tests, key=lambda x: x[0])
                if best is None or local_best[0] < best[0]:
                    best = (local_best[0], idx, local_best[1], local_best[2])

            if best and best[0] <= tolerance:
                _dist, idx, mode, reverse = best
                seg = pending.pop(idx)
                if reverse:
                    seg.reverse()
                if mode == 'APPEND':
                    chain.extend(seg[1:])
                else:
                    chain = seg[:-1] + chain
                changed = True

        chains.append(_dedupe_adjacent(chain))

    return chains


def create_profile_curve(name, chains, anchor_world, collection):
    curve = bpy.data.curves.new(name=f"{name}_Curve", type='CURVE')
    curve.dimensions = '2D'
    curve.resolution_u = 12
    curve.render_resolution_u = 24
    set_curve_fill_both(curve)

    for chain in chains:
        if len(chain) < 2:
            continue
        spline = curve.splines.new('POLY')
        spline.points.add(len(chain) - 1)
        for p, world_co in zip(spline.points, chain):
            local = world_co - anchor_world
            p.co = (local.x, local.y, 0.0, 1.0)

    obj = bpy.data.objects.new(name, curve)
    obj.location = (0.0, 0.0, 0.0)
    obj["cpc_profile"] = True
    obj["cpc_anchor_world"] = tuple(anchor_world)
    collection.objects.link(obj)
    return obj



def create_profile_curve_bezier(name, chains, anchor_world, collection):
    """Create a committed 2D profile while retaining Bézier points/handles."""
    curve = bpy.data.curves.new(name=f"{name}_Curve", type='CURVE')
    curve.dimensions = '2D'
    curve.resolution_u = 12
    curve.render_resolution_u = 24
    set_curve_fill_both(curve)

    for chain in chains:
        if len(chain) < 2:
            continue
        spline = curve.splines.new('BEZIER')
        spline.bezier_points.add(len(chain) - 1)

        # Write coordinates/handles first.  Final handle types are assigned in a
        # second pass, matching CPC's primitive writer and avoiding transient
        # AUTO/VECTOR recalculation while the geometry is incomplete.
        for bp, spec in zip(spline.bezier_points, chain):
            co = spec["co"] - anchor_world
            hl = spec["handle_left"] - anchor_world
            hr = spec["handle_right"] - anchor_world
            bp.co = (co.x, co.y, 0.0)
            bp.handle_left = (hl.x, hl.y, 0.0)
            bp.handle_right = (hr.x, hr.y, 0.0)
            bp.radius = float(spec.get("radius", 1.0))
            bp.tilt = float(spec.get("tilt", 0.0))
            bp.weight_softbody = float(spec.get("weight_softbody", 0.0))

        for bp, spec in zip(spline.bezier_points, chain):
            bp.handle_left_type = spec["handle_left_type"]
            bp.handle_right_type = spec["handle_right_type"]

    obj = bpy.data.objects.new(name, curve)
    obj.location = (0.0, 0.0, 0.0)
    obj["cpc_profile"] = True
    obj["cpc_anchor_world"] = tuple(anchor_world)
    collection.objects.link(obj)
    return obj


def selected_edge_paths_world(mesh_obj):
    """Extract ordered world-space paths from selected edit-mode mesh edges.

    Branches are split into maximal non-branching chains. Closed loops become
    cyclic paths with the first point repeated at the end.
    """
    if not mesh_obj or mesh_obj.type != 'MESH' or mesh_obj.mode != 'EDIT':
        return []

    bm = bmesh.from_edit_mesh(mesh_obj.data)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    selected = [e for e in bm.edges if e.select and not e.hide]
    if not selected:
        return []

    selected_set = set(selected)
    adjacency = {}
    for edge in selected:
        for vert in edge.verts:
            adjacency.setdefault(vert, []).append(edge)

    unvisited = set(selected)
    paths = []

    def other_vert(edge, vert):
        return edge.verts[1] if edge.verts[0] == vert else edge.verts[0]

    def walk(start_vert, start_edge):
        verts = [start_vert]
        current_vert = start_vert
        current_edge = start_edge
        while current_edge in unvisited:
            unvisited.remove(current_edge)
            next_vert = other_vert(current_edge, current_vert)
            verts.append(next_vert)
            candidates = [e for e in adjacency.get(next_vert, []) if e in unvisited]
            if len(adjacency.get(next_vert, [])) != 2 or not candidates:
                break
            current_vert = next_vert
            current_edge = candidates[0]
        return verts

    # Start at endpoints and branch vertices first.
    for vert, edges in list(adjacency.items()):
        if len(edges) == 2:
            continue
        for edge in edges:
            if edge in unvisited:
                paths.append(walk(vert, edge))

    # Any remaining edges belong to closed loops.
    while unvisited:
        start_edge = next(iter(unvisited))
        start_vert = start_edge.verts[0]
        verts = [start_vert]
        current_vert = start_vert
        current_edge = start_edge
        while current_edge in unvisited:
            unvisited.remove(current_edge)
            next_vert = other_vert(current_edge, current_vert)
            verts.append(next_vert)
            candidates = [e for e in adjacency.get(next_vert, []) if e in unvisited]
            if not candidates:
                break
            current_vert = next_vert
            current_edge = candidates[0]
        if verts[-1] != verts[0]:
            # For a valid degree-2 loop the final vertex should be the start.
            # Add it when the final vertex is topologically connected back.
            if any(other_vert(e, verts[-1]) == verts[0] for e in adjacency.get(verts[-1], [])):
                verts.append(verts[0])
        paths.append(verts)

    mw = mesh_obj.matrix_world
    world_paths = []
    for verts in paths:
        coords = [mw @ v.co for v in verts]
        coords = _dedupe_adjacent(coords)
        if len(coords) >= 2:
            world_paths.append(coords)
    return world_paths


def _horizontal_planar_z(world_paths, tolerance=1.0e-5):
    points = [co for path in world_paths for co in path]
    if not points:
        return None
    zs = [co.z for co in points]
    z_min, z_max = min(zs), max(zs)
    if (z_max - z_min) <= tolerance:
        return sum(zs) / len(zs)
    return None


def _add_vector_bezier_spline(curve, coords, cyclic=False):
    """Create exact straight path segments with visible VECTOR handles."""
    if len(coords) < 2:
        return None
    spline = curve.splines.new('BEZIER')
    spline.bezier_points.add(len(coords) - 1)
    for bp, co in zip(spline.bezier_points, coords):
        bp.co = co
    # Set handle types after coordinates so Blender owns the exact vector
    # construction at corners/endpoints.
    for bp in spline.bezier_points:
        bp.handle_left_type = 'VECTOR'
        bp.handle_right_type = 'VECTOR'
    spline.use_cyclic_u = cyclic
    return spline


def create_sweep_path(
    name,
    world_paths,
    profile_obj,
    collection,
    resolution=4,
    twist_mode='MINIMUM',
    fill_caps=False,
    path_mode='AUTO',
    planar_tolerance=1.0e-5,
):
    curve = bpy.data.curves.new(name=f"{name}_Curve", type='CURVE')
    curve.resolution_u = resolution
    curve.render_resolution_u = max(resolution, 8)
    curve.bevel_mode = 'OBJECT'
    curve.bevel_object = profile_obj
    set_curve_fill_both(curve)
    curve.use_fill_caps = fill_caps

    detected_z = _horizontal_planar_z(world_paths, planar_tolerance)
    use_2d = path_mode == '2D' or (path_mode == 'AUTO' and detected_z is not None)

    if use_2d:
        # 2D curves are constrained to local XY.  Keep the selected ceiling
        # elevation in the object's Z transform rather than losing it when Z
        # is clamped, matching the production workflow users were doing by
        # hand after converting the path to 2D.
        points = [co for path in world_paths for co in path]
        plane_z = detected_z if detected_z is not None else (sum(co.z for co in points) / len(points))
        curve.dimensions = '2D'
    else:
        plane_z = 0.0
        curve.dimensions = '3D'
        curve.twist_mode = twist_mode

    for source_coords in world_paths:
        coords = list(source_coords)
        cyclic = len(coords) >= 3 and (coords[0] - coords[-1]).length < 1e-7
        if cyclic:
            coords = coords[:-1]
        if len(coords) < 2:
            continue

        if use_2d:
            local_coords = [Vector((co.x, co.y, 0.0)) for co in coords]
        else:
            local_coords = [Vector((co.x, co.y, co.z)) for co in coords]
        _add_vector_bezier_spline(curve, local_coords, cyclic=cyclic)

    obj = bpy.data.objects.new(name, curve)
    if use_2d:
        obj.location.z = plane_z
    obj["cpc_sweep"] = True
    obj["cpc_profile_name"] = profile_obj.name
    obj["cpc_path_mode"] = '2D' if use_2d else '3D'
    collection.objects.link(obj)
    return obj

