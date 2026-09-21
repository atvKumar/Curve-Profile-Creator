import json
import math
import uuid
import bpy
from bpy.types import Operator
from bpy.props import EnumProperty, IntProperty, StringProperty
from mathutils import Matrix, Vector, geometry as mu_geometry
from bpy_extras import view3d_utils

from . import architectural_components, architectural_recipes, compound_geometry, geometry, interaction_units, junctions, library, placement_parameters, primitives, profile_presets, profile_transforms, properties, primitive_geometry, user_profiles, viewport_overlay, viewport_semantics
from . import EXTENSION_VERSION


def _settings(context):
    return context.scene.cpc_settings


def _builder_parts(
    scene,
    include_preview=False,
    *,
    owner_profile_id=None,
    build_session_id=None,
):
    coll = bpy.data.collections.get("CPC_ProfileParts")
    if not coll:
        return []
    owner_profile_id = str(owner_profile_id or "").strip()
    build_session_id = str(build_session_id or "").strip()
    parts = []
    for obj in coll.objects:
        if not obj.get("cpc_part"):
            continue
        if not include_preview and obj.get("cpc_preview"):
            continue
        if owner_profile_id and str(obj.get("cpc_owner_profile_id", "")).strip() != owner_profile_id:
            continue
        if build_session_id and str(obj.get("cpc_build_session_id", "")).strip() != build_session_id:
            continue
        parts.append(obj)
    return sorted(parts, key=lambda o: int(o.get("cpc_seq", 0)))


def _active_builder_parts(scene, settings, include_preview=False):
    """Return only the parts belonging to the current construction/edit session."""
    editing_profile_id = str(getattr(settings, "editing_profile_id", "") or "").strip()
    if editing_profile_id:
        return _builder_parts(
            scene,
            include_preview=include_preview,
            owner_profile_id=editing_profile_id,
        )

    build_session_id = str(getattr(settings, "build_session_id", "") or "").strip()
    if build_session_id:
        return _builder_parts(
            scene,
            include_preview=include_preview,
            build_session_id=build_session_id,
        )

    return []


def _ensure_build_session(context):
    settings = _settings(context)
    if str(getattr(settings, "editing_profile_id", "") or "").strip():
        return ""
    session_id = str(getattr(settings, "build_session_id", "") or "").strip()
    if session_id:
        return session_id

    session_id = f"build-{uuid.uuid4()}"
    settings.build_session_id = session_id

    return session_id


def _next_seq(scene, settings):
    parts = _active_builder_parts(scene, settings, include_preview=True)
    return max((int(o.get("cpc_seq", 0)) for o in parts), default=0) + 1


def _angle_2d(v):
    return math.atan2(v.y, v.x)


def _placement_overlay_title(op):
    component_id = str(getattr(op, "_component_id", "") or "").strip()
    if component_id:
        return architectural_recipes.display_name(component_id)
    obj = getattr(op, "_obj", None)
    if obj:
        return str(obj.get("cpc_primitive_name", obj.get("cpc_primitive_id", "CPC Component")))
    return "CPC Component"


def _placement_overlay_owner(op):
    owner = str(getattr(op, "_overlay_owner", "") or "")
    if not owner:
        owner = f"{getattr(op, 'bl_idname', 'cpc.modal')}:{id(op)}"
        op._overlay_owner = owner
    return owner


def _placement_overlay_lines(op, context):
    lines = []
    dimension_mode = getattr(op, "_dimension_mode", None)
    if dimension_mode:
        try:
            descriptor = op._placement_parameter_descriptor(dimension_mode)
            label = descriptor.label if descriptor else "Dimension"
            value = op._get_placement_dimension(dimension_mode)
            lines.append(f"{label}  {viewport_overlay.format_length(context, value)}")
            if descriptor and descriptor.semantic == "ARC_DEPTH":
                radius = op._placement_arc_radius()
                if radius is not None:
                    lines.append(f"Radius  {viewport_overlay.format_length(context, radius)}")
            typed = str(getattr(op, "_dimension_numeric", "") or "")
            if typed:
                lines.append(f"Typed  {typed}")
        except Exception:
            pass
        try:
            siblings = placement_parameters.by_hotkey_all(op._placement_parameter_map(), dimension_mode)
            if len(siblings) > 1:
                lines.append(f"{dimension_mode} next member • Mouse adjust • Shift fine • Type exact value")
            else:
                lines.append("Mouse adjust • Shift fine • Type exact value • Enter accept • Esc cancel")
        except Exception:
            lines.append("Mouse adjust • Shift fine • Type exact value • Enter accept • Esc cancel")
        return lines

    if getattr(op, "_rotate_mode", False):
        try:
            delta = math.degrees(float(op._rotation_offset) - float(op._rotate_start_offset))
            lines.append(f"Rotation Δ  {delta:.2f}°")
            typed = str(getattr(op, "_rotate_numeric", "") or "")
            if typed:
                lines.append(f"Typed  {typed}°")
        except Exception:
            pass
        lines.append("Ctrl snap • Shift fine • Enter accept • Esc cancel")
        return lines

    lines.append(f"Scale  {float(getattr(op, '_scale', 1.0)):.3f}× • Auto Align {'On' if getattr(op, '_auto_align', True) else 'Off'}")
    try:
        params = op._placement_parameter_map()
        shortcuts = placement_parameters.shortcut_text(params)
        lines.append((shortcuts + " • " if shortcuts else "") + "R Rotate")
    except Exception:
        lines.append("R Rotate • Tab Swap End • X/Y Flip")
    return lines

def _sync_placement_overlay(op, context, event=None):
    if event is not None:
        op._overlay_mouse_region = (float(event.mouse_region_x), float(event.mouse_region_y))
    mouse_region = tuple(getattr(op, "_overlay_mouse_region", (24.0, 24.0)))

    if getattr(op, "_dimension_mode", None):
        mode = "Adjust"
        try:
            descriptor = op._placement_parameter_descriptor(op._dimension_mode)
            active_field = descriptor.label if descriptor else "Dimension"
        except Exception:
            active_field = "Dimension"
    elif getattr(op, "_rotate_mode", False):
        mode = "Rotate"
        active_field = "Rotation"
    else:
        mode = "Place"
        active_field = ""

    snap_world = None
    snap_kind = ""
    snap_label = ""
    snap_target = getattr(op, "_snap_target", None)
    if snap_target is not None:
        snap_world = tuple(snap_target)
        snap_kind = str(getattr(op, "_snap_kind", "") or "ORIGIN")
        snap_label = str(getattr(op, "_snap_label", "") or "Builder Origin")

    viewport_overlay.update_modal(
        owner=_placement_overlay_owner(op),
        title=_placement_overlay_title(op),
        mode=mode,
        active_field=active_field,
        mouse_region=mouse_region,
        snap_kind=snap_kind,
        snap_label=snap_label,
        snap_world=snap_world,
        anchor_label="End anchor" if int(getattr(op, "anchor_index", 0)) else "Start anchor",
        lines=_placement_overlay_lines(op, context),
    )


def _begin_placement_overlay(op, context, event):
    op._overlay_mouse_region = (float(event.mouse_region_x), float(event.mouse_region_y))
    viewport_overlay.begin_modal(
        _placement_overlay_owner(op),
        title=_placement_overlay_title(op),
        mode="Place",
        mouse_region=op._overlay_mouse_region,
        area_ptr=int(context.area.as_pointer()) if context.area else 0,
        region_ptr=int(context.region.as_pointer()) if context.region else 0,
    )
    _sync_placement_overlay(op, context, event)


def _clear_placement_overlay(op):
    viewport_overlay.clear_modal(_placement_overlay_owner(op))


def _ensure_component_id(obj):
    if not obj:
        return ""
    if obj.get("cpc_parametric"):
        return primitives.ensure_component_id(obj)
    component_id = str(obj.get("cpc_component_id", "")).strip()
    if not component_id:
        component_id = f"cpc-{uuid.uuid4()}"
        obj["cpc_component_id"] = component_id
    return component_id


def _set_part_edit_anchor(obj, anchor_index):
    """Switch the fixed semantic endpoint without changing world geometry.

    Part Rotation is rebased to zero because rotations around different pivots
    cannot be represented faithfully by one cumulative scalar offset. The
    current matrix remains authoritative and future rotation offsets begin from
    this new edit-anchor state.
    """
    if not obj:
        return
    new_anchor = 1 if int(anchor_index) else 0
    current_anchor = 1 if int(obj.get("cpc_anchor_index", 0)) else 0
    if new_anchor == current_anchor:
        return
    obj["cpc_anchor_index"] = new_anchor
    if hasattr(obj, "cpc_part_rotation"):
        obj["_cpc_part_transform_initializing"] = True
        try:
            obj.cpc_part_rotation = 0.0
            obj["cpc_part_rotation_applied"] = 0.0
            obj["cpc_part_rotation_saved"] = 0.0
        finally:
            obj["_cpc_part_transform_initializing"] = False


def _curve_midpoint_world(obj, samples_per_segment=24):
    """Return the actual half-arc-length point used by hosted midpoint snapping."""
    frame = junctions.curve_frame_world(obj, 0.5)
    return frame[0] if frame else None


def _component_recipe_snapshot(parts):
    """Serialize the semantic construction recipe used for later profile re-editing."""
    records = []
    for obj in parts:
        record = {
            "id": _ensure_component_id(obj),
            "name": obj.name,
            "sequence": int(obj.get("cpc_seq", 0)),
            "primitive_id": str(obj.get("cpc_primitive_id", "")),
            "anchor_index": int(obj.get("cpc_anchor_index", 0)),
            "part_rotation": float(getattr(obj, "cpc_part_rotation", 0.0)),
            "matrix_world": [list(row) for row in obj.matrix_world],
        }
        if obj.get("cpc_parameters"):
            try:
                record["parameters"] = json.loads(obj["cpc_parameters"])
            except Exception:
                record["parameters"] = str(obj["cpc_parameters"])
        role = str(obj.get("cpc_role", "") or "").strip()
        if role:
            record["role"] = role
        arch_instance_id = str(obj.get("cpc_arch_instance_id", "") or "").strip()
        if arch_instance_id:
            arch_record = {
                "component_id": str(obj.get("cpc_arch_component_id", "") or ""),
                "component_name": str(obj.get("cpc_arch_component_name", "") or ""),
                "component_group": str(obj.get("cpc_component_group", "") or ""),
                "instance_id": arch_instance_id,
                "part_index": int(obj.get("cpc_arch_part_index", 0)),
                "controller": bool(obj.get("cpc_arch_controller", False)),
            }
            if arch_record["controller"]:
                arch_record["anchor_index"] = int(obj.get("cpc_arch_anchor_index", 0))
                raw_arch = obj.get("cpc_arch_parameters", "")
                if raw_arch:
                    try:
                        arch_record["parameters"] = json.loads(raw_arch)
                    except Exception:
                        arch_record["parameters"] = str(raw_arch)
            record["architectural_component"] = arch_record
        start_junction = junctions.endpoint_id(obj, 0)
        end_junction = junctions.endpoint_id(obj, 1)
        if start_junction or end_junction:
            record["junctions"] = {
                "start": start_junction,
                "end": end_junction,
            }
        hosted = {}
        for endpoint, key in ((0, "start"), (1, "end")):
            attachment = junctions.hosted_attachment(obj, endpoint)
            if attachment:
                hosted[key] = dict(attachment)
        if hosted:
            record["hosted_attachments"] = hosted
        records.append(record)
    return records


def _ensure_profile_id(profile):
    if not profile:
        return ""
    profile_id = str(profile.get("cpc_profile_id", "")).strip()
    if not profile_id:
        profile_id = f"profile-{uuid.uuid4()}"
        profile["cpc_profile_id"] = profile_id
    return profile_id


def _profile_for_id(profile_id):
    profile_id = str(profile_id or "").strip()
    if not profile_id:
        return None
    for obj in bpy.data.objects:
        if obj.type == 'CURVE' and str(obj.get("cpc_profile_id", "")).strip() == profile_id:
            return obj
    return None


def _remove_part_object(obj):
    if not obj or obj.name not in bpy.data.objects:
        return
    data = obj.data if obj.type == 'CURVE' else None
    bpy.data.objects.remove(obj, do_unlink=True)
    if data and data.users == 0 and data.name in bpy.data.curves:
        bpy.data.curves.remove(data)


def _recipe_records(profile):
    if not profile:
        return []
    raw = profile.get("cpc_recipe_json", "")
    if not raw:
        return []
    try:
        records = json.loads(raw)
    except Exception:
        return []
    return records if isinstance(records, list) else []


def _recipe_profile_frame(profile):
    """Return the normalized frame required by the 0.4.0+ recipe contract."""
    if not profile:
        raise profile_transforms.ProfileTransformError("No CPC profile supplied")
    raw = str(profile.get("cpc_recipe_frame_json", "") or "").strip()
    if not raw:
        raise profile_transforms.ProfileTransformError("Profile has no normalized recipe frame")
    return profile_transforms.matrix_from_json(raw)


def _restore_recipe_parts(context, profile, *, placement_matrix=None):
    """Restore 0.4.0+ parametric construction parts from normalized recipe data."""
    records = _recipe_records(profile)
    if not records:
        return [], ["Profile has no usable construction recipe"]

    recipe_version = int(profile.get("cpc_recipe_version", 0))
    if recipe_version < profile_presets.MIN_PARAMETRIC_RECIPE_SCHEMA:
        return [], [f"CPC 0.4.3 supports recipe schema {profile_presets.MIN_PARAMETRIC_RECIPE_SCHEMA} or newer (0.4.0 baseline)"]

    try:
        placement = (
            placement_matrix.copy()
            if isinstance(placement_matrix, Matrix)
            else (
                profile_transforms.matrix_from_data(placement_matrix)
                if placement_matrix is not None
                else _recipe_profile_frame(profile)
            )
        )
    except Exception as exc:
        return [], [f"Could not read normalized profile frame: {exc}"]

    profile_id = _ensure_profile_id(profile)
    coll = library.ensure_builder_collection(context.scene)
    recipe_ids = {str(record.get("id", "")).strip() for record in records if record.get("id")}
    warnings = []

    for obj in list(_builder_parts(context.scene, include_preview=True, owner_profile_id=profile_id)):
        if str(obj.get("cpc_component_id", "")).strip() not in recipe_ids:
            _remove_part_object(obj)

    existing = {
        str(obj.get("cpc_component_id", "")).strip(): obj
        for obj in _builder_parts(context.scene, include_preview=True)
        if str(obj.get("cpc_component_id", "")).strip()
    }

    restored = []
    for record in sorted(records, key=lambda item: int(item.get("sequence", 0))):
        component_id = str(record.get("id", "")).strip() or f"cpc-{uuid.uuid4()}"
        primitive_id = str(record.get("primitive_id", "") or "").strip()
        if not primitive_id:
            warnings.append(f"Recipe record '{record.get('name', component_id)}' has no primitive_id")
            continue
        params = record.get("parameters", {})
        if not isinstance(params, dict):
            params = {}

        old = existing.get(component_id)
        if old is not None:
            _remove_part_object(old)

        try:
            obj = primitives.create_object(
                primitive_id,
                float(params.get("width", 0.05)),
                float(params.get("height", 0.025)),
                shape_mode=str(params.get("shape_mode", "CIRCLE")),
                bias=float(params.get("bias", 0.5)),
                fullness=float(params.get("fullness", 1.0)),
                concave_fullness=float(params.get("concave_fullness", 1.0)),
                convex_fullness=float(params.get("convex_fullness", 1.0)),
                arc_construction_mode=str(params.get("arc_construction_mode", "ARC_DEPTH")),
                arc_depth=float(params.get(
                    "arc_depth",
                    primitive_geometry.default_arc_depth_for_primitive(
                        primitive_id, float(params.get("width", 0.05))
                    ),
                )),
            )
        except Exception as exc:
            warnings.append(f"Could not restore {primitive_id}: {exc}")
            continue
        library.relink_object(obj, coll)

        obj.name = str(record.get("name", obj.name))
        obj["cpc_part"] = True
        obj["cpc_preview"] = False
        obj["cpc_component_id"] = component_id
        obj["cpc_owner_profile_id"] = profile_id
        obj.pop("cpc_build_session_id", None)

        role = str(record.get("role", "") or "").strip()
        if role:
            obj["cpc_role"] = role
        else:
            obj.pop("cpc_role", None)

        arch_record = record.get("architectural_component") if isinstance(record.get("architectural_component"), dict) else None
        if arch_record and arch_record.get("instance_id"):
            obj["cpc_arch_component"] = True
            obj["cpc_arch_component_id"] = str(arch_record.get("component_id", ""))
            obj["cpc_arch_component_name"] = str(arch_record.get("component_name", ""))
            saved_group = str(arch_record.get("component_group", "") or "")
            obj["cpc_component_group"] = saved_group or architectural_recipes.component_group(obj["cpc_arch_component_id"])
            obj["cpc_arch_instance_id"] = str(arch_record.get("instance_id"))
            obj["cpc_arch_part_index"] = int(arch_record.get("part_index", 0))
            obj["cpc_arch_controller"] = bool(arch_record.get("controller", False))
            if obj["cpc_arch_controller"]:
                obj["cpc_arch_anchor_index"] = 1 if int(arch_record.get("anchor_index", 0)) else 0
                arch_params = arch_record.get("parameters")
                if isinstance(arch_params, dict):
                    obj["cpc_arch_parameters"] = json.dumps(arch_params, sort_keys=True)
        else:
            for key in (
                "cpc_arch_component", "cpc_arch_component_id", "cpc_arch_component_name",
                "cpc_arch_instance_id", "cpc_arch_part_index", "cpc_arch_controller",
                "cpc_arch_anchor_index", "cpc_arch_parameters", "cpc_component_group",
            ):
                obj.pop(key, None)

        obj["cpc_seq"] = int(record.get("sequence", len(restored) + 1))
        obj["cpc_anchor_index"] = 1 if int(record.get("anchor_index", 0)) else 0
        rotation_offset = float(record.get("part_rotation", 0.0) or 0.0)
        obj["_cpc_part_transform_initializing"] = True
        try:
            obj.cpc_part_rotation = rotation_offset
            obj["cpc_part_rotation_applied"] = rotation_offset
            obj["cpc_part_rotation_saved"] = rotation_offset
        finally:
            obj["_cpc_part_transform_initializing"] = False

        junction_record = record.get("junctions") if isinstance(record.get("junctions"), dict) else {}
        junctions.set_endpoint_id(obj, 0, junction_record.get("start", ""))
        junctions.set_endpoint_id(obj, 1, junction_record.get("end", ""))
        junctions.clear_hosted_attachment(obj, 0)
        junctions.clear_hosted_attachment(obj, 1)
        hosted_record = record.get("hosted_attachments") if isinstance(record.get("hosted_attachments"), dict) else {}
        for endpoint, key in ((0, "start"), (1, "end")):
            attachment = hosted_record.get(key)
            if isinstance(attachment, dict):
                junctions.set_hosted_record(obj, endpoint, attachment)

        try:
            matrix = profile_transforms.recipe_record_world_matrix(record, placement)
            if matrix is None:
                raise profile_transforms.ProfileTransformError("recipe record has no matrix_profile")
            obj.matrix_world = matrix
        except Exception as exc:
            warnings.append(f"Could not restore transform for {obj.name}: {exc}")

        obj.hide_set(False)
        obj.hide_render = False
        obj.show_in_front = True
        restored.append(obj)

    architectural_components.restore_loaded_instances(restored)
    return restored, warnings


def _refresh_profile_dependents(context, profile):
    """Force bevel users to reevaluate after profile-data transforms."""
    if not profile or profile.type != 'CURVE':
        return
    profile.data.update_tag()
    profile.update_tag()
    for obj in bpy.data.objects:
        if obj.type != 'CURVE' or obj == profile:
            continue
        data = obj.data
        if getattr(data, "bevel_object", None) == profile:
            data.update_tag()
            obj.update_tag()
    try:
        context.view_layer.update()
    except Exception:
        pass
    wm = getattr(context, "window_manager", None)
    if wm:
        for window in wm.windows:
            screen = window.screen
            if screen:
                for area in screen.areas:
                    if area.type == 'VIEW_3D':
                        area.tag_redraw()


class CPC_OT_PlacePart(Operator):
    bl_idname = "cpc.place_part"
    bl_label = "Place Profile Part"
    bl_description = "Place a parametric architectural profile component with snapping, flipping, scaling and free rotation"
    bl_options = {'REGISTER', 'UNDO', 'BLOCKING'}

    anchor_index: IntProperty(default=0, min=0, max=1, options={'HIDDEN'})

    _obj = None
    _scale = 1.0
    _flip_x = False
    _flip_y = False
    _rotation_offset = 0.0
    _auto_align = True
    _snap_hit = None
    _snap_target = None
    _initial_part_name = ""
    _current_target = None
    _current_outward = None

    _rotate_mode = False
    _rotate_start_mouse_x = 0
    _rotate_last_mouse_x = 0
    _rotate_raw_delta = 0.0
    _rotate_start_offset = 0.0
    _rotate_numeric = ""
    _rotate_target = None
    _rotate_outward = None
    _hold_target_after_rotate = False
    _hold_mouse_region = None

    _dimension_mode = None
    _dimension_field = ""
    _dimension_start_mouse_x = 0
    _dimension_last_mouse_x = 0
    _dimension_raw_delta = 0.0
    _dimension_start_value = 0.0
    _dimension_target = None
    _dimension_outward = None

    @classmethod
    def poll(cls, context):
        return context.area and context.area.type == 'VIEW_3D' and context.scene is not None and context.mode == 'OBJECT'

    def _cleanup(self, context, remove=True):
        context.workspace.status_text_set(None)
        _clear_placement_overlay(self)
        if remove and self._obj and self._obj.name in bpy.data.objects:
            data = self._obj.data if self._obj.type == 'CURVE' else None
            bpy.data.objects.remove(self._obj, do_unlink=True)
            if data and data.users == 0 and data.name in bpy.data.curves:
                bpy.data.curves.remove(data)
        self._obj = None

    def _mouse_to_builder_plane(self, context, event):
        region = context.region
        rv3d = context.space_data.region_3d
        coord = Vector((event.mouse_region_x, event.mouse_region_y))
        ray_origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)
        ray_dir = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)
        plane_point = context.scene.cursor.location.copy()
        plane_normal = Vector((0.0, 0.0, 1.0))
        hit = mu_geometry.intersect_line_plane(
            ray_origin,
            ray_origin + ray_dir * 100000.0,
            plane_point,
            plane_normal,
            False,
        )
        if hit is None:
            return view3d_utils.region_2d_to_location_3d(region, rv3d, coord, plane_point)
        return hit

    def _nearest_snap(self, context, event):
        """Return the best CPC placement snap using semantic priority first.

        Candidate tuple:
            (priority, pixel_distance, world, outward, endpoint_hit, kind, label)

        Endpoint/origin targets are explicit construction anchors, tangent
        continuation comes next, and component midpoints are a lower-priority
        convenience. Endpoint snaps create endpoint junctions; midpoint snaps
        create persistent hosted attachments for Maintain Connected behavior.
        """
        region = context.region
        rv3d = context.space_data.region_3d
        mouse2d = Vector((event.mouse_region_x, event.mouse_region_y))
        max_px = float(_settings(context).snap_pixels)
        candidates = []

        def add_candidate(priority, world, outward, hit, kind, label):
            screen = view3d_utils.location_3d_to_region_2d(region, rv3d, world, default=None)
            if screen is None:
                return
            dist = (mouse2d - screen).length
            if dist <= max_px:
                candidates.append((int(priority), float(dist), world.copy(), outward.copy() if outward is not None else None, hit, kind, label))

        # Builder origin is an explicit anchor and therefore shares endpoint priority.
        origin = context.scene.cursor.location.copy()
        add_candidate(0, origin, None, None, "ORIGIN", "Builder Origin")

        try:
            free_target = self._mouse_to_builder_plane(context, event)
        except Exception:
            free_target = None

        for obj in _active_builder_parts(context.scene, _settings(context)):
            if obj == self._obj:
                continue
            start = library.object_endpoint_world(obj, 0)
            end = library.object_endpoint_world(obj, 1)

            for endpoint, world in ((0, start), (1, end)):
                outward = library.object_endpoint_outward_world(obj, endpoint)
                add_candidate(0, world, outward, (obj, endpoint), "ENDPOINT", f"Endpoint • {obj.name} • {'End' if endpoint else 'Start'}")

                # Tangent continuation is a semantic construction ray.  Project
                # the current builder-plane mouse point onto the outward ray and
                # only offer points in the continuation direction.
                if free_target is not None and outward is not None and outward.length > 1.0e-8:
                    tangent = outward.normalized()
                    along = (free_target - world).dot(tangent)
                    if along > 1.0e-6:
                        tangent_world = world + tangent * along
                        add_candidate(1, tangent_world, outward, None, "TANGENT", f"Tangent • {obj.name} • {'End' if endpoint else 'Start'}")

            midpoint = _curve_midpoint_world(obj)
            if midpoint is not None:
                primitive_id = str(obj.get("cpc_primitive_id", ""))
                if primitive_id == 'LINE':
                    midpoint_label = "Midpoint"
                elif primitive_id in {'OVOLO', 'CAVETTO', 'TORUS'}:
                    midpoint_label = "Arc Midpoint"
                elif primitive_id in {'CYMA_RECTA', 'CYMA_REVERSA'}:
                    midpoint_label = "Curve Midpoint"
                else:
                    midpoint_label = "Curve Midpoint"
                host_hit = {
                    "type": "HOSTED",
                    "host": obj,
                    "kind": "MIDPOINT",
                    "fraction": 0.5,
                }
                add_candidate(2, midpoint, None, host_hit, "MIDPOINT", f"{midpoint_label} • {obj.name}")

        if not candidates:
            return None
        return min(candidates, key=lambda c: (c[0], c[1]))

    def _orient_preview(self, context, target_world, outward=None):
        local_anchor = library.curve_endpoint_local(self._obj, self.anchor_index)
        local_interior = library.curve_endpoint_interior_dir_local(self._obj, self.anchor_index)

        sx = self._scale * (-1.0 if self._flip_x else 1.0)
        sy = self._scale * (-1.0 if self._flip_y else 1.0)
        scale_m = Matrix.Diagonal((sx, sy, self._scale, 1.0))

        scaled_dir = scale_m.to_3x3() @ local_interior
        angle = self._rotation_offset
        if self._auto_align and outward is not None and outward.length > 1e-8 and scaled_dir.length > 1e-8:
            angle += _angle_2d(outward) - _angle_2d(scaled_dir)

        rotation_m = Matrix.Rotation(angle, 4, 'Z')
        orient = rotation_m @ scale_m
        anchor_offset = (orient @ local_anchor.to_4d()).to_3d()
        location = target_world - anchor_offset
        self._obj.matrix_world = Matrix.Translation(location) @ orient

    def _update_preview(self, context, event):
        free_target = self._mouse_to_builder_plane(context, event)
        snap = self._nearest_snap(context, event)
        if snap:
            _priority, _dist, target, outward, hit, kind, label = snap
            self._snap_target = target
            self._snap_hit = hit
            self._snap_kind = kind
            self._snap_label = label
            self._current_target = target.copy()
            self._current_outward = outward.copy() if outward is not None else None
            self._orient_preview(context, target, outward)
        else:
            self._snap_target = None
            self._snap_hit = None
            self._snap_kind = ""
            self._snap_label = ""
            self._current_target = free_target.copy()
            self._current_outward = None
            self._orient_preview(context, free_target, None)
        _sync_placement_overlay(self, context, event)

    def _refresh_preview(self, context, event):
        if self._hold_target_after_rotate and self._current_target is not None:
            self._orient_preview(context, self._current_target, self._current_outward)
            _sync_placement_overlay(self, context, event)
        else:
            self._update_preview(context, event)

    def _begin_rotation(self, context, event):
        if self._current_target is None:
            self._current_target = self._mouse_to_builder_plane(context, event)
        self._rotate_mode = True
        self._rotate_start_mouse_x = event.mouse_region_x
        self._rotate_last_mouse_x = event.mouse_region_x
        self._rotate_raw_delta = 0.0
        self._rotate_start_offset = self._rotation_offset
        self._rotate_numeric = ""
        self._rotate_target = self._current_target.copy()
        self._rotate_outward = self._current_outward.copy() if self._current_outward is not None else None
        _sync_placement_overlay(self, context, event)

    def _hold_rotation_target(self, event):
        self._hold_target_after_rotate = True
        self._hold_mouse_region = Vector((event.mouse_region_x, event.mouse_region_y))
        self._current_target = self._rotate_target.copy() if self._rotate_target is not None else self._current_target
        self._current_outward = self._rotate_outward.copy() if self._rotate_outward is not None else None

    def _rotation_status(self, context):
        angle_degrees = math.degrees(self._rotation_offset - self._rotate_start_offset)
        typed = f" | Typed: {self._rotate_numeric}°" if self._rotate_numeric else ""
        context.workspace.status_text_set(
            f"Rotate Part | Mouse: Free  Ctrl: {_settings(context).rotation_snap_degrees:.0f}° Snap  "
            f"Shift: Fine  Type Angle  LMB/Enter: Accept  RMB/Esc: Cancel | Δ {angle_degrees:.2f}°{typed}"
        )

    def _apply_rotation_from_mouse(self, context, event):
        dx = event.mouse_region_x - self._rotate_last_mouse_x
        self._rotate_last_mouse_x = event.mouse_region_x
        sensitivity = 0.005
        if event.shift:
            sensitivity *= 0.2
        self._rotate_raw_delta += dx * sensitivity
        delta = self._rotate_raw_delta
        if event.ctrl:
            snap = math.radians(max(1.0, _settings(context).rotation_snap_degrees))
            delta = round(delta / snap) * snap
        self._rotation_offset = self._rotate_start_offset + delta
        self._orient_preview(context, self._rotate_target, self._rotate_outward)

    def _apply_numeric_rotation(self, context):
        if not self._rotate_numeric or self._rotate_numeric in {'-', '.', '-.'}:
            return
        try:
            value = float(self._rotate_numeric)
        except ValueError:
            return
        self._rotation_offset = self._rotate_start_offset + math.radians(value)
        self._orient_preview(context, self._rotate_target, self._rotate_outward)

    @staticmethod
    def _numeric_char(event):
        if event.ascii and event.ascii in "0123456789.-":
            return event.ascii
        mapping = {
            'ZERO': '0', 'ONE': '1', 'TWO': '2', 'THREE': '3', 'FOUR': '4',
            'FIVE': '5', 'SIX': '6', 'SEVEN': '7', 'EIGHT': '8', 'NINE': '9',
            'NUMPAD_0': '0', 'NUMPAD_1': '1', 'NUMPAD_2': '2', 'NUMPAD_3': '3',
            'NUMPAD_4': '4', 'NUMPAD_5': '5', 'NUMPAD_6': '6', 'NUMPAD_7': '7',
            'NUMPAD_8': '8', 'NUMPAD_9': '9', 'PERIOD': '.', 'NUMPAD_PERIOD': '.',
            'MINUS': '-', 'NUMPAD_MINUS': '-',
        }
        return mapping.get(event.type, '')

    def _rotation_modal(self, context, event):
        self._rotation_status(context)

        if event.type == 'MOUSEMOVE':
            if not self._rotate_numeric:
                self._apply_rotation_from_mouse(context, event)
            _sync_placement_overlay(self, context, event)
            context.area.tag_redraw()
            return {'RUNNING_MODAL'}

        if event.value == 'PRESS':
            if event.type in {'ESC', 'RIGHTMOUSE'}:
                self._rotation_offset = self._rotate_start_offset
                self._orient_preview(context, self._rotate_target, self._rotate_outward)
                self._rotate_mode = False
                self._rotate_numeric = ""
                self._hold_rotation_target(event)
                _sync_placement_overlay(self, context, event)
                return {'RUNNING_MODAL'}

            if event.type in {'LEFTMOUSE', 'RET', 'NUMPAD_ENTER', 'R'}:
                self._apply_numeric_rotation(context)
                self._rotate_mode = False
                self._rotate_numeric = ""
                self._hold_rotation_target(event)
                _sync_placement_overlay(self, context, event)
                return {'RUNNING_MODAL'}

            if event.type == 'BACK_SPACE':
                self._rotate_numeric = self._rotate_numeric[:-1]
                if self._rotate_numeric:
                    self._apply_numeric_rotation(context)
                else:
                    self._rotation_offset = self._rotate_start_offset
                    self._rotate_raw_delta = 0.0
                    self._rotate_last_mouse_x = event.mouse_region_x
                    self._orient_preview(context, self._rotate_target, self._rotate_outward)
                _sync_placement_overlay(self, context, event)
                return {'RUNNING_MODAL'}

            char = self._numeric_char(event)
            if char:
                if char == '-' and self._rotate_numeric:
                    return {'RUNNING_MODAL'}
                if char == '.' and '.' in self._rotate_numeric:
                    return {'RUNNING_MODAL'}
                self._rotate_numeric += char
                self._apply_numeric_rotation(context)
                _sync_placement_overlay(self, context, event)
                return {'RUNNING_MODAL'}

        return {'RUNNING_MODAL'}

    def _placement_parameter_map(self):
        if not self._obj or not self._obj.get("cpc_parametric"):
            return ()
        return placement_parameters.basic_parameters(
            str(self._obj.get("cpc_primitive_id", "")),
            arc_mode=str(getattr(self._obj, "cpc_param_arc_construction_mode", "ARC_DEPTH")),
            shape_mode=str(getattr(self._obj, "cpc_param_shape_mode", "CIRCLE")),
        )

    def _placement_parameter_descriptor(self, mode):
        params = self._placement_parameter_map()
        field_name = str(getattr(self, "_dimension_field", "") or "")
        if field_name and str(getattr(self, "_dimension_mode", "") or "").upper() == str(mode or "").upper():
            for item in placement_parameters.by_hotkey_all(params, mode):
                if item.field == field_name:
                    return item
        return placement_parameters.by_hotkey(params, mode)

    def _get_placement_dimension(self, mode):
        descriptor = self._placement_parameter_descriptor(mode)
        if descriptor is None:
            raise KeyError(mode)
        return float(getattr(self._obj, "cpc_param_" + descriptor.field))

    def _placement_arc_radius(self):
        params = self._placement_parameter_map()
        active_desc = self._placement_parameter_descriptor(getattr(self, "_dimension_mode", None))
        depth_desc = active_desc if active_desc and active_desc.semantic == "ARC_DEPTH" else next((item for item in params if item.semantic == "ARC_DEPTH"), None)
        width_desc = next((item for item in params if item.semantic == "WIDTH_OR_CHORD"), None)
        if depth_desc is None or width_desc is None:
            return None
        try:
            primitive_id = str(self._obj.get("cpc_primitive_id", ""))
            depth = float(getattr(self._obj, "cpc_param_" + depth_desc.field))
            if primitive_id in {"CYMA_RECTA", "CYMA_REVERSA"}:
                orientation = "RECTA" if primitive_id == "CYMA_RECTA" else "REVERSA"
                solution = compound_geometry.solve_cyma_from_primary_depth(
                    float(self._obj.cpc_param_width),
                    float(self._obj.cpc_param_height),
                    depth,
                    orientation=orientation,
                )
                return solution.first.radius
            chord_field = depth_desc.chord_field or width_desc.field
            chord = float(getattr(self._obj, "cpc_param_" + chord_field))
            return primitive_geometry.arc_radius_from_chord_depth(chord, depth)
        except Exception:
            return None

    def _set_placement_dimension(self, context, mode, value):
        descriptor = self._placement_parameter_descriptor(mode)
        if descriptor is None:
            return
        value = max(float(value), 1.0e-6)
        attr_name = "cpc_param_" + descriptor.field
        self._obj["_cpc_param_initializing"] = True
        try:
            setattr(self._obj, attr_name, value)
        finally:
            self._obj["_cpc_param_initializing"] = False

        primitives.update_object_geometry(
            self._obj,
            width=self._obj.cpc_param_width,
            height=self._obj.cpc_param_height,
            shape_mode=self._obj.cpc_param_shape_mode,
            bias=self._obj.cpc_param_bias,
            fullness=self._obj.cpc_param_fullness,
            concave_fullness=self._obj.cpc_param_concave_fullness,
            convex_fullness=self._obj.cpc_param_convex_fullness,
            arc_construction_mode=self._obj.cpc_param_arc_construction_mode,
            arc_depth=self._obj.cpc_param_arc_depth,
            preserve_anchor=False,
            propagate_connected=False,
        )
        if self._dimension_target is not None:
            self._orient_preview(context, self._dimension_target, self._dimension_outward)

    def _begin_dimension_adjust(self, context, event, mode):
        descriptors = placement_parameters.by_hotkey_all(self._placement_parameter_map(), mode)
        if not descriptors:
            return False
        if self._current_target is None:
            self._current_target = self._mouse_to_builder_plane(context, event)
        self._dimension_mode = mode
        self._dimension_field = descriptors[0].field
        self._dimension_start_mouse_x = event.mouse_region_x
        self._dimension_last_mouse_x = event.mouse_region_x
        self._dimension_raw_delta = 0.0
        self._dimension_start_value = self._get_placement_dimension(mode)
        self._dimension_numeric = ""
        self._dimension_target = self._current_target.copy()
        self._dimension_outward = self._current_outward.copy() if self._current_outward is not None else None
        _sync_placement_overlay(self, context, event)
        return True

    def _cycle_dimension_descriptor(self, context, event):
        descriptors = placement_parameters.by_hotkey_all(self._placement_parameter_map(), self._dimension_mode)
        if len(descriptors) < 2:
            return False
        current = self._placement_parameter_descriptor(self._dimension_mode)
        try:
            index = next(i for i, item in enumerate(descriptors) if current and item.field == current.field)
        except StopIteration:
            index = -1
        self._dimension_field = descriptors[(index + 1) % len(descriptors)].field
        self._dimension_start_mouse_x = event.mouse_region_x
        self._dimension_last_mouse_x = event.mouse_region_x
        self._dimension_raw_delta = 0.0
        self._dimension_start_value = self._get_placement_dimension(self._dimension_mode)
        self._dimension_numeric = ""
        _sync_placement_overlay(self, context, event)
        return True

    def _dimension_status(self, context):
        descriptor = self._placement_parameter_descriptor(self._dimension_mode)
        label = descriptor.label if descriptor else "Dimension"
        value = self._get_placement_dimension(self._dimension_mode)
        typed = str(getattr(self, "_dimension_numeric", "") or "")
        suffix = f" | Typed {typed}" if typed else ""
        siblings = placement_parameters.by_hotkey_all(self._placement_parameter_map(), self._dimension_mode)
        cycle_hint = f"  {self._dimension_mode}: Next member" if len(siblings) > 1 else ""
        context.workspace.status_text_set(
            f"Adjust {label} | Mouse: Adjust  Shift: Fine{cycle_hint}  Type exact unit value  LMB/Enter: Accept  RMB/Esc: Cancel | Value {viewport_overlay.format_length(context, value)}{suffix}"
        )

    def _apply_dimension_from_mouse(self, context, event):
        dx = event.mouse_region_x - self._dimension_last_mouse_x
        self._dimension_last_mouse_x = event.mouse_region_x
        sensitivity = 0.01 * (0.2 if event.shift else 1.0)
        self._dimension_raw_delta += dx * sensitivity
        value = self._dimension_start_value * math.exp(self._dimension_raw_delta)
        self._set_placement_dimension(context, self._dimension_mode, value)

    def _dimension_modal(self, context, event):
        self._dimension_status(context)
        if event.type == 'MOUSEMOVE' and not str(getattr(self, "_dimension_numeric", "") or ""):
            self._apply_dimension_from_mouse(context, event)
            _sync_placement_overlay(self, context, event)
            context.area.tag_redraw()
            return {'RUNNING_MODAL'}
        if event.value == 'PRESS':
            if event.type == self._dimension_mode:
                typed = str(getattr(self, "_dimension_numeric", "") or "").strip()
                if typed:
                    try:
                        value = interaction_units.parse_length(
                            context, typed, reference_value=self._get_placement_dimension(self._dimension_mode)
                        )
                        self._set_placement_dimension(context, self._dimension_mode, value)
                    except Exception as exc:
                        self.report({'WARNING'}, f"Invalid dimension: {exc}")
                        _sync_placement_overlay(self, context, event)
                        return {'RUNNING_MODAL'}
                if self._cycle_dimension_descriptor(context, event):
                    return {'RUNNING_MODAL'}
            if event.type in {'ESC', 'RIGHTMOUSE'}:
                self._set_placement_dimension(context, self._dimension_mode, self._dimension_start_value)
                self._dimension_mode = None
                self._dimension_field = ""
                self._dimension_numeric = ""
                self._hold_target_after_rotate = True
                self._hold_mouse_region = Vector((event.mouse_region_x, event.mouse_region_y))
                _sync_placement_overlay(self, context, event)
                return {'RUNNING_MODAL'}
            if event.type == 'BACK_SPACE':
                self._dimension_numeric = str(getattr(self, "_dimension_numeric", "") or "")[:-1]
                _sync_placement_overlay(self, context, event)
                return {'RUNNING_MODAL'}
            if event.type == 'DEL':
                self._dimension_numeric = ""
                _sync_placement_overlay(self, context, event)
                return {'RUNNING_MODAL'}
            char = str(getattr(event, "unicode", "") or "")
            if char and char in "0123456789.+-/ '\"mMcC":
                self._dimension_numeric = str(getattr(self, "_dimension_numeric", "") or "") + char
                _sync_placement_overlay(self, context, event)
                return {'RUNNING_MODAL'}
            if event.type in {'RET', 'NUMPAD_ENTER'}:
                typed = str(getattr(self, "_dimension_numeric", "") or "").strip()
                if typed:
                    try:
                        value = interaction_units.parse_length(
                            context, typed, reference_value=self._get_placement_dimension(self._dimension_mode)
                        )
                        self._set_placement_dimension(context, self._dimension_mode, value)
                    except Exception as exc:
                        self.report({'WARNING'}, f"Invalid dimension: {exc}")
                        _sync_placement_overlay(self, context, event)
                        return {'RUNNING_MODAL'}
                self._dimension_mode = None
                self._dimension_field = ""
                self._dimension_numeric = ""
                self._hold_target_after_rotate = True
                self._hold_mouse_region = Vector((event.mouse_region_x, event.mouse_region_y))
                _sync_placement_overlay(self, context, event)
                return {'RUNNING_MODAL'}
            if event.type == 'LEFTMOUSE':
                self._dimension_mode = None
                self._dimension_field = ""
                self._dimension_numeric = ""
                self._hold_target_after_rotate = True
                self._hold_mouse_region = Vector((event.mouse_region_x, event.mouse_region_y))
                _sync_placement_overlay(self, context, event)
                return {'RUNNING_MODAL'}
        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        settings = _settings(context)

        try:
            obj = primitives.create_object(
                settings.parametric_part,
                settings.parametric_width,
                settings.parametric_height,
                shape_mode=settings.parametric_shape_mode,
                bias=settings.cyma_bias,
                fullness=settings.parametric_fullness,
                concave_fullness=settings.cyma_concave_fullness,
                convex_fullness=settings.cyma_convex_fullness,
                arc_construction_mode=settings.parametric_arc_construction_mode,
                arc_depth=settings.parametric_arc_depth,
            )
        except Exception as exc:
            self.report({'ERROR'}, f"Could not generate component: {exc}")
            return {'CANCELLED'}
        part_name = settings.parametric_part
        initial_scale = 1.0

        coll = library.ensure_builder_collection(context.scene)
        library.relink_object(obj, coll)
        display_name = obj.get("cpc_primitive_name") or library.display_name(part_name)
        obj.name = f"CPC_Part_{str(display_name).replace(' ', '_').replace('/', '_')}"
        obj["cpc_part"] = True
        obj["cpc_preview"] = True
        obj["cpc_seq"] = _next_seq(context.scene, settings)
        editing_profile_id = str(getattr(settings, "editing_profile_id", "") or "").strip()
        if editing_profile_id:
            obj["cpc_owner_profile_id"] = editing_profile_id
            obj.pop("cpc_build_session_id", None)
        else:
            session_id = _ensure_build_session(context)
            if session_id:
                obj["cpc_build_session_id"] = session_id
            obj.pop("cpc_owner_profile_id", None)
        _ensure_component_id(obj)
        obj.show_in_front = True

        self._obj = obj
        self._initial_part_name = str(part_name)
        self._scale = initial_scale
        self._flip_x = False
        self._flip_y = False
        self._rotation_offset = 0.0
        self._auto_align = True
        self._rotate_mode = False
        self._rotate_numeric = ""
        self._dimension_mode = None
        self._dimension_field = ""
        self._dimension_numeric = ""
        self._hold_target_after_rotate = False
        self._hold_mouse_region = None
        self._snap_kind = ""
        self._snap_label = ""
        self.anchor_index = 0

        for other in context.selected_objects:
            other.select_set(False)
        obj.select_set(True)
        context.view_layer.objects.active = obj

        _begin_placement_overlay(self, context, event)
        self._update_preview(context, event)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if self._dimension_mode:
            return self._dimension_modal(context, event)
        if self._rotate_mode:
            return self._rotation_modal(context, event)

        params = self._placement_parameter_map()
        dimension_keys = placement_parameters.shortcut_text(params)
        dimension_keys = ("  " + dimension_keys.replace(" • ", "  ")) if dimension_keys else ""
        context.workspace.status_text_set(
            "Place Profile Part | LMB/Enter: Commit  RMB/Esc: Cancel  "
            f"Tab: Swap End  X/Y: Flip  Wheel: Scale  R: Rotate{dimension_keys}  A: Auto Align"
        )

        if event.type == 'MOUSEMOVE':
            if self._hold_target_after_rotate and self._hold_mouse_region is not None:
                mouse = Vector((event.mouse_region_x, event.mouse_region_y))
                if (mouse - self._hold_mouse_region).length <= 8.0:
                    self._orient_preview(context, self._current_target, self._current_outward)
                else:
                    self._hold_target_after_rotate = False
                    self._hold_mouse_region = None
                    self._update_preview(context, event)
            else:
                self._update_preview(context, event)
            context.area.tag_redraw()
            return {'RUNNING_MODAL'}

        if event.type in {'ESC', 'RIGHTMOUSE'} and event.value == 'PRESS':
            self._cleanup(context, remove=True)
            return {'CANCELLED'}

        if event.type in {'LEFTMOUSE', 'RET', 'NUMPAD_ENTER'} and event.value == 'PRESS':
            if not self._obj:
                return {'CANCELLED'}
            self._obj["cpc_preview"] = False
            self._obj["cpc_anchor_index"] = self.anchor_index
            self._obj["cpc_scale"] = self._scale
            self._obj["cpc_flip_x"] = self._flip_x
            self._obj["cpc_flip_y"] = self._flip_y
            self._obj["cpc_rotation_offset"] = self._rotation_offset
            junctions.clear_object(self._obj)
            if self._snap_hit is not None:
                if isinstance(self._snap_hit, dict) and self._snap_hit.get("type") == "HOSTED":
                    junctions.set_hosted_attachment(
                        self._obj,
                        self.anchor_index,
                        self._snap_hit.get("host"),
                        kind=self._snap_hit.get("kind", "MIDPOINT"),
                        fraction=float(self._snap_hit.get("fraction", 0.5)),
                    )
                else:
                    target_obj, target_endpoint = self._snap_hit
                    junctions.connect_endpoints(
                        self._obj,
                        self.anchor_index,
                        target_obj,
                        int(target_endpoint),
                    )
            context.workspace.status_text_set(None)
            _clear_placement_overlay(self)
            self._obj = None
            return {'FINISHED'}

        if event.value == 'PRESS':
            if event.type == 'TAB':
                self.anchor_index = 1 - self.anchor_index
                self._refresh_preview(context, event)
                return {'RUNNING_MODAL'}
            if event.type == 'X':
                self._flip_x = not self._flip_x
                self._refresh_preview(context, event)
                return {'RUNNING_MODAL'}
            if event.type == 'Y':
                self._flip_y = not self._flip_y
                self._refresh_preview(context, event)
                return {'RUNNING_MODAL'}
            if event.type == 'A':
                self._auto_align = not self._auto_align
                self._refresh_preview(context, event)
                return {'RUNNING_MODAL'}
            if event.type in {'L', 'W', 'H', 'D', 'F'}:
                if self._begin_dimension_adjust(context, event, event.type):
                    return {'RUNNING_MODAL'}
            if event.type == 'R':
                self._begin_rotation(context, event)
                return {'RUNNING_MODAL'}

        if event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'} and event.value == 'PRESS':
            factor = 1.02 if event.shift else 1.10
            if event.type == 'WHEELDOWNMOUSE':
                factor = 1.0 / factor
            self._scale = max(0.00001, self._scale * factor)
            self._refresh_preview(context, event)
            return {'RUNNING_MODAL'}

        return {'RUNNING_MODAL'}


class CPC_OT_PlaceArchitecturalComponent(Operator):
    bl_idname = "cpc.place_architectural_component"
    bl_label = "Place Packed Component"
    bl_description = "Place a packed Constructed Shape or Architectural Component built from connected CPC parts"

    _parts = None
    _local_matrices = None
    _instance_id = ""
    _seq_start = 0
    _component_id = ""
    _arch_params = None

    anchor_index: IntProperty(default=0, min=0, max=1, options={'HIDDEN'})

    # Reuse the proven placement interaction implementation without deriving
    # from a registered RNA Operator class (which is fragile across Blender
    # versions). These are ordinary Python method aliases; this operator has
    # its own Blender RNA identity.
    _mouse_to_builder_plane = CPC_OT_PlacePart._mouse_to_builder_plane
    _nearest_snap = CPC_OT_PlacePart._nearest_snap
    _update_preview = CPC_OT_PlacePart._update_preview
    _refresh_preview = CPC_OT_PlacePart._refresh_preview
    _begin_rotation = CPC_OT_PlacePart._begin_rotation
    _hold_rotation_target = CPC_OT_PlacePart._hold_rotation_target
    _rotation_status = CPC_OT_PlacePart._rotation_status
    _apply_rotation_from_mouse = CPC_OT_PlacePart._apply_rotation_from_mouse
    _apply_numeric_rotation = CPC_OT_PlacePart._apply_numeric_rotation
    _numeric_char = staticmethod(CPC_OT_PlacePart._numeric_char)
    _rotation_modal = CPC_OT_PlacePart._rotation_modal
    _placement_parameter_descriptor = CPC_OT_PlacePart._placement_parameter_descriptor
    _begin_dimension_adjust = CPC_OT_PlacePart._begin_dimension_adjust
    _cycle_dimension_descriptor = CPC_OT_PlacePart._cycle_dimension_descriptor
    _dimension_status = CPC_OT_PlacePart._dimension_status
    _apply_dimension_from_mouse = CPC_OT_PlacePart._apply_dimension_from_mouse
    _dimension_modal = CPC_OT_PlacePart._dimension_modal

    def _cleanup(self, context, remove=True):
        context.workspace.status_text_set(None)
        _clear_placement_overlay(self)
        if remove:
            for obj in list(self._parts or []):
                if obj and obj.name in bpy.data.objects:
                    _remove_part_object(obj)
        if self._obj and self._obj.name in bpy.data.objects:
            data = self._obj.data if self._obj.type == 'CURVE' else None
            bpy.data.objects.remove(self._obj, do_unlink=True)
            if data and data.users == 0 and data.name in bpy.data.curves:
                bpy.data.curves.remove(data)
        self._obj = None
        self._parts = []
        self._local_matrices = []

    def _orient_preview(self, context, target_world, outward=None):
        # Reuse the proven modal placement math on a non-rendered proxy that
        # represents the complete component's start/end frame.
        CPC_OT_PlacePart._orient_preview(self, context, target_world, outward)
        if not self._obj:
            return
        group_world = self._obj.matrix_world.copy()
        for part, local_m in zip(self._parts or [], self._local_matrices or []):
            part.matrix_world = group_world @ local_m

    def _placement_parameter_map(self):
        return placement_parameters.architectural_parameters(self._component_id, self._arch_params)

    def _get_placement_dimension(self, mode):
        descriptor = self._placement_parameter_descriptor(mode)
        if descriptor is None:
            raise KeyError(mode)
        return float(self._arch_params.get(descriptor.field, 0.001))

    def _placement_arc_radius(self):
        params = self._placement_parameter_map()
        active_desc = self._placement_parameter_descriptor(getattr(self, "_dimension_mode", None))
        depth_desc = active_desc if active_desc and active_desc.semantic == "ARC_DEPTH" else next((item for item in params if item.semantic == "ARC_DEPTH"), None)
        width_desc = next((item for item in params if item.semantic == "WIDTH_OR_CHORD"), None)
        if depth_desc is None or width_desc is None:
            return None
        try:
            depth = float(self._arch_params.get(depth_desc.field, 0.006))
            if self._component_id in {'CYMA_RECTA_FILLETS', 'CYMA_REVERSA_FILLETS'}:
                orientation = "RECTA" if self._component_id == 'CYMA_RECTA_FILLETS' else "REVERSA"
                solution = compound_geometry.solve_cyma_from_primary_depth(
                    float(self._arch_params.get("width", 0.03)),
                    float(self._arch_params.get("height", 0.03)),
                    depth,
                    orientation=orientation,
                )
                return solution.first.radius
            chord_field = depth_desc.chord_field or width_desc.field
            chord = float(self._arch_params.get(chord_field, 0.03))
            return primitive_geometry.arc_radius_from_chord_depth(chord, depth)
        except Exception:
            return None

    def _set_placement_dimension(self, context, mode, value):
        descriptor = self._placement_parameter_descriptor(mode)
        if descriptor is None:
            return
        self._arch_params[descriptor.field] = max(float(value), 1.0e-6)
        self._arch_params = architectural_recipes.normalize_parameters(self._component_id, self._arch_params)
        self._local_matrices = architectural_components.refresh_preview(
            self._obj, self._parts, self._component_id, self._arch_params
        )
        if self._dimension_target is not None:
            self._orient_preview(context, self._dimension_target, self._dimension_outward)

    def invoke(self, context, event):
        settings = _settings(context)
        self._component_id = (
            settings.constructed_shape
            if str(getattr(settings, "construction_kind", "ARCH")) == "CONSTRUCTED"
            else settings.arch_component
        )
        self._arch_params = architectural_components.scene_parameters(settings, self._component_id)
        try:
            proxy, parts, local_matrices, instance_id = architectural_components.create_preview(
                context, self._component_id, self._arch_params
            )
        except Exception as exc:
            self.report({'ERROR'}, f"Could not generate packed component: {exc}")
            return {'CANCELLED'}

        self._obj = proxy
        self._parts = parts
        self._local_matrices = local_matrices
        self._instance_id = instance_id
        self._seq_start = _next_seq(context.scene, settings)

        editing_profile_id = str(getattr(settings, "editing_profile_id", "") or "").strip()
        session_id = "" if editing_profile_id else _ensure_build_session(context)
        for index, obj in enumerate(parts):
            obj["cpc_seq"] = self._seq_start + index
            if editing_profile_id:
                obj["cpc_owner_profile_id"] = editing_profile_id
                obj.pop("cpc_build_session_id", None)
            else:
                if session_id:
                    obj["cpc_build_session_id"] = session_id
                obj.pop("cpc_owner_profile_id", None)
            _ensure_component_id(obj)

        self._scale = 1.0
        self._flip_x = False
        self._flip_y = False
        self._rotation_offset = 0.0
        self._auto_align = True
        self._rotate_mode = False
        self._rotate_numeric = ""
        self._dimension_mode = None
        self._dimension_field = ""
        self._dimension_numeric = ""
        self._hold_target_after_rotate = False
        self._hold_mouse_region = None
        self._snap_hit = None
        self._snap_target = None
        self._snap_kind = ""
        self._snap_label = ""
        self._current_target = None
        self._current_outward = None
        self.anchor_index = 0

        for other in context.selected_objects:
            other.select_set(False)
        if parts:
            parts[0].select_set(True)
            context.view_layer.objects.active = parts[0]

        _begin_placement_overlay(self, context, event)
        self._update_preview(context, event)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def _finalize(self, context):
        if not self._parts or not self._obj:
            return {'CANCELLED'}
        parts = list(self._parts)
        count = len(parts)

        for obj in parts:
            obj["cpc_preview"] = False
            obj["cpc_scale"] = self._scale
            obj["cpc_flip_x"] = self._flip_x
            obj["cpc_flip_y"] = self._flip_y
            obj["cpc_rotation_offset"] = self._rotation_offset

        # Internal recipe neighbours share End->Start junctions; the placed
        # group anchor joins the snapped target endpoint.
        for obj in parts:
            obj["cpc_anchor_index"] = self.anchor_index
            junctions.clear_object(obj)
        junctions.connect_chain(parts)
        if self._snap_hit is not None:
            group_obj = parts[0] if self.anchor_index == 0 else parts[-1]
            group_endpoint = 0 if self.anchor_index == 0 else 1
            if isinstance(self._snap_hit, dict) and self._snap_hit.get("type") == "HOSTED":
                junctions.set_hosted_attachment(
                    group_obj,
                    group_endpoint,
                    self._snap_hit.get("host"),
                    kind=self._snap_hit.get("kind", "MIDPOINT"),
                    fraction=float(self._snap_hit.get("fraction", 0.5)),
                )
            else:
                target_obj, target_endpoint = self._snap_hit
                junctions.connect_endpoints(
                    group_obj,
                    group_endpoint,
                    target_obj,
                    int(target_endpoint),
                )

        architectural_components.initialise_instance(
            parts, self._component_id, self._arch_params, anchor_index=self.anchor_index
        )

        # Remove only the non-rendered placement proxy; the recipe children are
        # now normal CPC construction parts.
        proxy = self._obj
        proxy_data = proxy.data if proxy.type == 'CURVE' else None
        bpy.data.objects.remove(proxy, do_unlink=True)
        if proxy_data and proxy_data.users == 0 and proxy_data.name in bpy.data.curves:
            bpy.data.curves.remove(proxy_data)
        self._obj = None
        self._parts = []
        self._local_matrices = []

        for other in context.selected_objects:
            other.select_set(False)
        parts[0].select_set(True)
        context.view_layer.objects.active = parts[0]
        context.workspace.status_text_set(None)
        _clear_placement_overlay(self)
        return {'FINISHED'}

    def modal(self, context, event):
        if not self._rotate_mode and not self._dimension_mode and event.value == 'PRESS' and event.type in {'LEFTMOUSE', 'RET', 'NUMPAD_ENTER'}:
            return self._finalize(context)
        return CPC_OT_PlacePart.modal(self, context, event)


class CPC_OT_ViewportDimensionEdit(Operator):
    bl_idname = "cpc.viewport_dimension_edit"
    bl_label = "Edit Dimensions in Viewport"
    bl_description = "Drag CPC semantic values to scrub them live, or click and type exact Scene, Metric or Architectural Imperial values"
    bl_options = {'REGISTER', 'UNDO'}

    _target = None
    _target_ptr = 0
    _owner = ""
    _window_region = None
    _area_ptr = 0
    _region_ptr = 0
    _active_field = ""
    _input_text = ""
    _pending_field = ""
    _pointer_start_x = 0.0
    _pointer_start_y = 0.0
    _scrub_field = ""
    _scrub_start_value = 0.0
    _scrub_last_x = 0.0

    @classmethod
    def poll(cls, context):
        obj = getattr(context, "object", None)
        return bool(
            context.mode == 'OBJECT'
            and obj and obj.type == 'CURVE' and obj.get("cpc_part")
            and obj.get("cpc_parametric") and not obj.get("cpc_preview")
        )

    def _mouse_region(self, event):
        region = self._window_region
        if not region:
            return (float(getattr(event, "mouse_region_x", 0.0)), float(getattr(event, "mouse_region_y", 0.0)))
        return (float(event.mouse_x - region.x), float(event.mouse_y - region.y))

    def _target_valid(self, context):
        obj = self._target
        if not obj:
            return False
        try:
            if int(obj.as_pointer()) != self._target_ptr:
                return False
        except Exception:
            return False
        current = getattr(context, "object", None)
        return current is obj and obj.type == 'CURVE' and obj.get("cpc_part") and not obj.get("cpc_preview")

    def _set_status(self, context):
        unit_mode = str(getattr(_settings(context), "viewport_unit_mode", "SCENE"))
        context.workspace.status_text_set(
            f"CPC Viewport Edit [{unit_mode.title()}] | Drag value: scrub • Click value: type • L/W/H/D/F • Shift: fine • Esc exit"
        )

    def _clear_pointer_gesture(self):
        self._pending_field = ""
        self._pointer_start_x = 0.0
        self._pointer_start_y = 0.0
        self._scrub_field = ""
        self._scrub_start_value = 0.0
        self._scrub_last_x = 0.0

    def _begin_pointer_field(self, field, mouse_region):
        if not field or not field.editable:
            return False
        self._pending_field = str(field.field_id)
        self._pointer_start_x = float(mouse_region[0])
        self._pointer_start_y = float(mouse_region[1])
        self._scrub_field = ""
        viewport_overlay.update_dimension_edit(
            mouse_region=mouse_region,
            hover_field=field.field_id,
            active_field="",
            input_text="",
            scrub_active=False,
            message=f"Drag {field.label} to scrub • Release without dragging to type",
        )
        return True

    def _begin_scrub(self, context, field, mouse_region):
        if not field or not field.editable:
            return False
        self._scrub_field = str(field.field_id)
        self._scrub_start_value = float(field.value)
        self._scrub_last_x = self._pointer_start_x
        viewport_overlay.update_dimension_edit(
            mouse_region=mouse_region,
            hover_field="",
            active_field=self._scrub_field,
            input_text="",
            scrub_active=True,
            message=f"Scrub {field.label} • Shift fine • Esc/RMB cancel",
        )
        return True

    def _apply_scrub_mouse(self, context, event, mouse_region):
        field = viewport_semantics.field_by_id(self._target, self._scrub_field)
        if field is None or not field.editable:
            self._clear_pointer_gesture()
            viewport_overlay.update_dimension_edit(active_field="", scrub_active=False, message="Dimension is no longer available")
            return False
        mouse_x = float(mouse_region[0])
        dx = mouse_x - self._scrub_last_x
        self._scrub_last_x = mouse_x
        if abs(dx) <= 1.0e-9:
            return True
        sensitivity = 0.01 * (0.2 if bool(getattr(event, "shift", False)) else 1.0)
        value = max(float(field.value) * math.exp(dx * sensitivity), 1.0e-6)
        try:
            viewport_semantics.apply_value(self._target, field.field_id, value)
        except Exception as exc:
            viewport_overlay.update_dimension_edit(message=f"Error • {exc}")
            return False
        current = viewport_semantics.field_by_id(self._target, field.field_id)
        shown = viewport_overlay.format_length(context, current.value if current else value)
        viewport_overlay.update_dimension_edit(
            mouse_region=mouse_region,
            active_field=field.field_id,
            scrub_active=True,
            message=f"Scrubbing • {field.label} {shown} • Shift fine",
        )
        viewport_overlay.tag_redraw_all(context)
        return True

    def _cancel_scrub(self, context, mouse_region=None):
        field_id = self._scrub_field
        start_value = self._scrub_start_value
        field = viewport_semantics.field_by_id(self._target, field_id) if field_id else None
        if field is not None:
            try:
                viewport_semantics.apply_value(self._target, field_id, start_value)
            except Exception:
                pass
        label = field.label if field else "Dimension"
        self._clear_pointer_gesture()
        viewport_overlay.update_dimension_edit(
            mouse_region=mouse_region, active_field="", hover_field="", input_text="", scrub_active=False,
            message=f"Cancelled • {label}",
        )
        viewport_overlay.tag_redraw_all(context)

    def _finish_scrub(self, context, mouse_region=None):
        field = viewport_semantics.field_by_id(self._target, self._scrub_field) if self._scrub_field else None
        label = field.label if field else "Dimension"
        shown = viewport_overlay.format_length(context, field.value) if field else ""
        self._clear_pointer_gesture()
        viewport_overlay.update_dimension_edit(
            mouse_region=mouse_region, active_field="", hover_field="", input_text="", scrub_active=False,
            message=f"Applied • {label} {shown}".rstrip(),
        )
        viewport_overlay.tag_redraw_all(context)

    def _activate_field(self, field, mouse_region=None):
        if not field or not field.editable:
            return False
        self._clear_pointer_gesture()
        self._active_field = str(field.field_id)
        self._input_text = ""
        viewport_overlay.update_dimension_edit(
            mouse_region=mouse_region,
            active_field=self._active_field,
            input_text="",
            scrub_active=False,
            message=f"Type {field.label}",
        )
        return True

    def _cancel_field(self, mouse_region=None):
        self._active_field = ""
        self._input_text = ""
        viewport_overlay.update_dimension_edit(
            mouse_region=mouse_region,
            active_field="",
            input_text="",
            scrub_active=False,
            message="",
        )

    def _commit_field(self, context, mouse_region=None):
        field = viewport_semantics.field_by_id(self._target, self._active_field)
        if field is None:
            self._cancel_field(mouse_region)
            return False
        if not self._input_text.strip():
            viewport_overlay.update_dimension_edit(message=f"Error • Enter a value for {field.label}")
            return False
        try:
            value = interaction_units.parse_length(
                context,
                self._input_text,
                reference_value=field.value,
            )
            viewport_semantics.apply_value(self._target, field.field_id, value)
        except Exception as exc:
            viewport_overlay.update_dimension_edit(message=f"Error • {exc}")
            return False

        applied = viewport_semantics.field_by_id(self._target, field.field_id)
        shown = viewport_overlay.format_length(context, applied.value if applied else value)
        self._active_field = ""
        self._input_text = ""
        viewport_overlay.update_dimension_edit(
            mouse_region=mouse_region,
            active_field="",
            input_text="",
            scrub_active=False,
            message=f"Applied • {field.label} {shown}",
        )
        viewport_overlay.tag_redraw_all(context)
        return True

    def _finish(self, context):
        if self._scrub_field:
            self._cancel_scrub(context)
        self._clear_pointer_gesture()
        context.workspace.status_text_set(None)
        viewport_overlay.clear_modal(self._owner)
        return {'FINISHED'}

    def invoke(self, context, event):
        # The panel button is a true toggle while an existing viewport-edit
        # session is active.  This avoids stacking modal interaction handlers.
        if viewport_overlay.dimension_edit_active():
            viewport_overlay.clear_modal()
            context.workspace.status_text_set(None)
            return {'FINISHED'}

        obj = context.object
        if not obj:
            return {'CANCELLED'}
        fields = [field for field in viewport_semantics.fields_for(obj) if field.editable]
        if not fields:
            self.report({'INFO'}, "Selected CPC part has no viewport-editable dimensions")
            return {'CANCELLED'}

        area = context.area
        if not area or area.type != 'VIEW_3D':
            self.report({'ERROR'}, "Viewport dimension editing requires a 3D View")
            return {'CANCELLED'}
        window_region = next((region for region in area.regions if region.type == 'WINDOW'), None)
        if window_region is None:
            self.report({'ERROR'}, "Could not find the 3D View window region")
            return {'CANCELLED'}

        self._target = obj
        self._target_ptr = int(obj.as_pointer())
        self._owner = f"cpc.viewport_dimension_edit:{id(self)}"
        self._window_region = window_region
        self._area_ptr = int(area.as_pointer())
        self._region_ptr = int(window_region.as_pointer())
        self._active_field = ""
        self._input_text = ""
        self._clear_pointer_gesture()
        mouse_region = self._mouse_region(event)

        viewport_overlay.begin_dimension_edit(
            self._owner,
            obj,
            context,
            mouse_region=mouse_region,
            area_ptr=self._area_ptr,
            region_ptr=self._region_ptr,
        )
        viewport_overlay.update_dimension_edit(message="Drag a value to scrub, or click it to type an exact value")
        self._set_status(context)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if not viewport_overlay.dimension_edit_active():
            context.workspace.status_text_set(None)
            return {'FINISHED'}
        if not self._target_valid(context) or not viewport_overlay.enabled(context):
            return self._finish(context)

        mouse_region = self._mouse_region(event)
        self._set_status(context)

        if self._scrub_field:
            if event.type == 'MOUSEMOVE':
                self._apply_scrub_mouse(context, event, mouse_region)
                return {'RUNNING_MODAL'}
            if event.value == 'PRESS' and event.type in {'ESC', 'RIGHTMOUSE'}:
                self._cancel_scrub(context, mouse_region)
                return {'RUNNING_MODAL'}
            if event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
                self._finish_scrub(context, mouse_region)
                return {'RUNNING_MODAL'}
            return {'RUNNING_MODAL'}

        if self._pending_field:
            if event.type == 'MOUSEMOVE':
                dx = float(mouse_region[0]) - self._pointer_start_x
                if abs(dx) >= 4.0:
                    field = viewport_semantics.field_by_id(self._target, self._pending_field)
                    if self._begin_scrub(context, field, mouse_region):
                        self._apply_scrub_mouse(context, event, mouse_region)
                else:
                    viewport_overlay.update_dimension_edit(mouse_region=mouse_region, hover_field=self._pending_field)
                return {'RUNNING_MODAL'}
            if event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
                field = viewport_semantics.field_by_id(self._target, self._pending_field)
                self._clear_pointer_gesture()
                if field and field.editable:
                    self._activate_field(field, mouse_region)
                return {'RUNNING_MODAL'}
            if event.value == 'PRESS' and event.type in {'ESC', 'RIGHTMOUSE'}:
                self._clear_pointer_gesture()
                viewport_overlay.update_dimension_edit(active_field="", hover_field="", scrub_active=False, message="")
                return {'RUNNING_MODAL'}
            return {'RUNNING_MODAL'}

        if self._active_field:
            if event.value == 'PRESS':
                if event.type in {'ESC', 'RIGHTMOUSE'}:
                    self._cancel_field(mouse_region)
                    return {'RUNNING_MODAL'}
                if event.type in {'RET', 'NUMPAD_ENTER'}:
                    self._commit_field(context, mouse_region)
                    return {'RUNNING_MODAL'}
                if event.type == 'BACK_SPACE':
                    self._input_text = self._input_text[:-1]
                    viewport_overlay.update_dimension_edit(
                        mouse_region=mouse_region,
                        input_text=self._input_text,
                        message="",
                    )
                    return {'RUNNING_MODAL'}
                if event.type == 'DEL':
                    self._input_text = ""
                    viewport_overlay.update_dimension_edit(
                        mouse_region=mouse_region,
                        input_text="",
                        message="",
                    )
                    return {'RUNNING_MODAL'}
                if event.type == 'TAB':
                    fields = [f for f in viewport_semantics.fields_for(self._target) if f.editable]
                    if fields:
                        ids = [f.field_id for f in fields]
                        try:
                            idx = ids.index(self._active_field)
                        except ValueError:
                            idx = -1
                        self._cancel_field(mouse_region)
                        self._activate_field(fields[(idx + 1) % len(fields)], mouse_region)
                    return {'RUNNING_MODAL'}

                if event.type in {'L', 'W', 'H', 'D', 'F'} and not self._input_text:
                    matches = viewport_semantics.shortcut_fields(self._target, event.type)
                    ids = [item.field_id for item in matches]
                    if len(ids) > 1 and self._active_field in ids:
                        current_index = ids.index(self._active_field)
                        next_field = matches[(current_index + 1) % len(matches)]
                        self._cancel_field(mouse_region)
                        self._activate_field(next_field, mouse_region)
                        return {'RUNNING_MODAL'}

                char = str(getattr(event, "unicode", "") or "")
                if char and char in "0123456789.+-/ '\"mMcC":
                    self._input_text += char
                    viewport_overlay.update_dimension_edit(
                        mouse_region=mouse_region,
                        input_text=self._input_text,
                        message="",
                    )
                    return {'RUNNING_MODAL'}

            # While entering a dimension, consume ordinary keyboard/mouse
            # events so Blender does not start unrelated transforms.  View
            # navigation remains available through middle mouse / wheel / NDOF.
            if event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE', 'NDOF_MOTION'}:
                return {'PASS_THROUGH'}
            if event.type == 'MOUSEMOVE':
                viewport_overlay.update_dimension_edit(mouse_region=mouse_region)
            return {'RUNNING_MODAL'}

        if event.type == 'MOUSEMOVE':
            hover = viewport_overlay.hit_test_dimension(
                context,
                mouse_region[0],
                mouse_region[1],
                area_ptr=self._area_ptr,
                region_ptr=self._region_ptr,
            )
            viewport_overlay.update_dimension_edit(
                mouse_region=mouse_region,
                hover_field=hover,
                message="" if hover else "Drag a value to scrub, or click it to type",
            )
            return {'PASS_THROUGH'}

        if event.value == 'PRESS':
            if event.type in {'ESC', 'RIGHTMOUSE'}:
                return self._finish(context)

            if event.type == 'TAB':
                current = 1 if int(self._target.get("cpc_anchor_index", 0)) else 0
                _set_part_edit_anchor(self._target, 1 - current)
                anchor_name = "End" if int(self._target.get("cpc_anchor_index", 0)) else "Start"
                viewport_overlay.update_dimension_edit(
                    mouse_region=mouse_region,
                    hover_field="",
                    message=f"Edit Anchor • {anchor_name} fixed",
                )
                viewport_overlay.tag_redraw_all(context)
                return {'RUNNING_MODAL'}

            if event.type == 'LEFTMOUSE':
                hit = viewport_overlay.hit_test_dimension(
                    context,
                    mouse_region[0],
                    mouse_region[1],
                    area_ptr=self._area_ptr,
                    region_ptr=self._region_ptr,
                )
                field = viewport_semantics.field_by_id(self._target, hit) if hit else None
                if field and field.editable:
                    self._begin_pointer_field(field, mouse_region)
                    return {'RUNNING_MODAL'}
                return {'PASS_THROUGH'}

            if event.type in {'L', 'W', 'H', 'D', 'F'}:
                field = viewport_semantics.shortcut_field(self._target, event.type)
                if field:
                    self._activate_field(field, mouse_region)
                    return {'RUNNING_MODAL'}

        return {'PASS_THROUGH'}


class CPC_OT_SetEditAnchor(Operator):
    bl_idname = "cpc.set_edit_anchor"
    bl_label = "Set Edit Anchor"
    bl_description = "Choose which endpoint stays fixed during CPC rotation and semantic dimension edits"
    bl_options = {'REGISTER', 'UNDO'}

    anchor: IntProperty(name="Anchor", default=0, min=0, max=1, options={'HIDDEN'})

    @classmethod
    def poll(cls, context):
        obj = context.object
        return bool(
            obj and obj.type == 'CURVE' and obj.get("cpc_part")
            and obj.get("cpc_parametric") and not obj.get("cpc_preview")
        )

    def execute(self, context):
        obj = context.object
        if not obj:
            return {'CANCELLED'}
        _set_part_edit_anchor(obj, self.anchor)
        try:
            viewport_overlay.tag_redraw_all(context)
        except Exception:
            pass
        return {'FINISHED'}


class CPC_OT_AdjustPartRotation(Operator):
    bl_idname = "cpc.adjust_part_rotation"
    bl_label = "Adjust Part Rotation"
    bl_description = "Rotate the selected CPC part around its chosen Edit Anchor; the opposite junction side follows"
    bl_options = {'REGISTER', 'UNDO'}

    action: EnumProperty(
        name="Action",
        items=(
            ('NEGATIVE', "Negative", "Rotate by the negative CPC rotation-snap increment"),
            ('RESET', "Reset", "Return this CPC part rotation offset to zero"),
            ('POSITIVE', "Positive", "Rotate by the positive CPC rotation-snap increment"),
        ),
        default='POSITIVE',
        options={'HIDDEN'},
    )

    @classmethod
    def poll(cls, context):
        obj = context.object
        return bool(
            obj and obj.type == 'CURVE' and obj.get("cpc_part")
            and obj.get("cpc_parametric") and not obj.get("cpc_preview")
        )

    def execute(self, context):
        obj = context.object
        if not obj:
            return {'CANCELLED'}
        if self.action == 'RESET':
            obj.cpc_part_rotation = 0.0
        else:
            step = math.radians(max(1.0, float(_settings(context).rotation_snap_degrees)))
            obj.cpc_part_rotation += -step if self.action == 'NEGATIVE' else step
        return {'FINISHED'}


class CPC_OT_DeleteLastPart(Operator):
    bl_idname = "cpc.delete_last_part"
    bl_label = "Delete Last Part"
    bl_description = "Remove the most recently committed profile part"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        parts = _active_builder_parts(context.scene, _settings(context))
        if not parts:
            self.report({'INFO'}, "No profile parts to remove")
            return {'CANCELLED'}
        obj = parts[-1]
        instance_id = str(obj.get("cpc_arch_instance_id", "") or "").strip()
        if instance_id:
            group = [part for part in parts if str(part.get("cpc_arch_instance_id", "") or "").strip() == instance_id]
            for part in list(group):
                _remove_part_object(part)
            self.report({'INFO'}, f"Removed Architectural Component ({len(group)} parts)")
        else:
            _remove_part_object(obj)
        return {'FINISHED'}


class CPC_OT_ClearParts(Operator):
    bl_idname = "cpc.clear_parts"
    bl_label = "Clear Parts"
    bl_description = "Remove all modular profile-construction parts"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        for obj in list(_active_builder_parts(context.scene, _settings(context), include_preview=True)):
            data = obj.data if obj.type == 'CURVE' else None
            bpy.data.objects.remove(obj, do_unlink=True)
            if data and data.users == 0:
                bpy.data.curves.remove(data)
        return {'FINISHED'}


class CPC_OT_CommitProfile(Operator):
    bl_idname = "cpc.commit_profile"
    bl_label = "Commit Profile"
    bl_description = "Commit the active construction session, or update a reopened committed profile in place"
    bl_options = {'REGISTER', 'UNDO'}

    profile_name: StringProperty(name="Profile Name", default="CPC_Profile")

    def execute(self, context):
        settings = _settings(context)
        parts = _active_builder_parts(context.scene, settings)
        if not parts:
            self.report({'ERROR'}, "Place at least one profile part first")
            return {'CANCELLED'}

        commit_mode = 'SAMPLED'
        chains = []
        fallback_reason = ""

        if settings.preserve_bezier:
            bezier_splines = []
            for obj in parts:
                splines, reason = geometry.bezier_splines_world(obj)
                if splines is None:
                    fallback_reason = f"{obj.name}: {reason}"
                    break
                bezier_splines.extend(splines)

            if not fallback_reason and bezier_splines:
                chains = geometry.stitch_bezier_splines(bezier_splines, settings.merge_tolerance)
                if chains:
                    commit_mode = 'BEZIER'
                else:
                    fallback_reason = "no usable Bézier chains were produced"

        if commit_mode == 'SAMPLED':
            sampled = []
            for obj in parts:
                sampled.extend(geometry.sample_curve_object_world(obj, settings.sample_resolution))
            if not sampled:
                self.report({'ERROR'}, "No usable curve splines found in profile parts")
                return {'CANCELLED'}
            chains = geometry.stitch_segments(sampled, settings.merge_tolerance)

        first = parts[0]
        first_anchor_index = int(first.get("cpc_anchor_index", 0))
        anchor = library.object_endpoint_world(first, first_anchor_index)
        coll = library.ensure_profile_collection(context.scene)

        editing_profile_id = str(getattr(settings, "editing_profile_id", "") or "").strip()
        updating_existing = bool(editing_profile_id)
        profile = None
        preserved_placement = profile_transforms.neutral_profile_placement()

        if updating_existing:
            candidate = settings.active_profile
            if candidate and str(candidate.get("cpc_profile_id", "")).strip() == editing_profile_id:
                profile = candidate
            if profile is None:
                profile = _profile_for_id(editing_profile_id)
            if profile is None:
                self.report({'ERROR'}, "The profile being edited no longer exists")
                return {'CANCELLED'}
            preserved_placement = profile_transforms.profile_placement_state(profile)

            # Generate replacement data through the proven profile builder, then
            # swap it onto the existing profile object. Existing sweeps continue
            # referencing the same bevel-object pointer and update automatically.
            if commit_mode == 'BEZIER':
                temp = geometry.create_profile_curve_bezier(
                    f"{profile.name}_Rebuild", chains, anchor, coll
                )
            else:
                temp = geometry.create_profile_curve(f"{profile.name}_Rebuild", chains, anchor, coll)
            new_data = temp.data
            old_data = profile.data
            profile.data = new_data
            profile["cpc_anchor_world"] = tuple(anchor)
            bpy.data.objects.remove(temp, do_unlink=True)
            if old_data and old_data.users == 0 and old_data.name in bpy.data.curves:
                bpy.data.curves.remove(old_data)
            profile_id = editing_profile_id
        else:
            if commit_mode == 'BEZIER':
                profile = geometry.create_profile_curve_bezier(
                    self.profile_name, chains, anchor, coll
                )
            else:
                profile = geometry.create_profile_curve(self.profile_name, chains, anchor, coll)
            profile_id = _ensure_profile_id(profile)

        # Once committed, every part belongs explicitly to this profile rather
        # than the transient build session.
        for obj in parts:
            obj["cpc_owner_profile_id"] = profile_id
            obj.pop("cpc_build_session_id", None)

        profile["cpc_profile_id"] = profile_id
        profile["cpc_commit_geometry"] = commit_mode

        # Persist all component transforms relative to one normalized profile frame.
        # The commit anchor becomes frame origin while the world-axis basis is retained,
        # so intrinsic profile orientation is preserved.
        profile_frame = profile_transforms.build_profile_frame(anchor)
        recipe_records = profile_transforms.normalize_recipe_records(
            _component_recipe_snapshot(parts), profile_frame
        )
        profile["cpc_recipe_version"] = profile_presets.MIN_PARAMETRIC_RECIPE_SCHEMA
        profile["cpc_recipe_transform_version"] = profile_transforms.PROFILE_TRANSFORM_SCHEMA
        profile["cpc_recipe_frame_policy"] = profile_transforms.PROFILE_FRAME_POLICY
        profile["cpc_recipe_frame_json"] = profile_transforms.matrix_to_json(profile_frame)
        profile["cpc_recipe_json"] = json.dumps(recipe_records, sort_keys=True)
        settings.editing_profile_id = ""
        settings.build_session_id = ""

        # New/rebuilt curve data is canonical geometry.  Rebase it neutrally,
        # then reapply the complete-profile placement state in one pass so
        # Recommit never bakes interaction order into the recipe.
        properties.bake_live_profile_adjustment(settings, profile)
        settings.active_profile = profile
        properties.set_profile_placement_state(
            settings, context, profile, state=preserved_placement
        )
        profile["cpc_recipe_geometry_hash"] = user_profiles.curve_authority_hash(profile)

        if settings.hide_builder_parts:
            for obj in parts:
                obj.hide_set(True)
                obj.hide_render = True

        for obj in context.selected_objects:
            obj.select_set(False)
        profile.hide_set(False)
        profile.select_set(True)
        context.view_layer.objects.active = profile
        _refresh_profile_dependents(context, profile)

        if fallback_reason and settings.preserve_bezier:
            self.report(
                {'WARNING'},
                f"Preserve Bézier unavailable ({fallback_reason}); used sampled commit",
            )
        elif updating_existing:
            self.report(
                {'INFO'},
                f"Updated profile '{profile.name}' from {len(parts)} parts as {commit_mode.lower()}",
            )
        else:
            self.report(
                {'INFO'},
                f"Created profile '{profile.name}' from {len(parts)} parts as {commit_mode.lower()}",
            )
        return {'FINISHED'}


def _reopen_profile_candidate(context, settings=None):
    """Prefer a directly selected committed CPC profile, then fall back to Active Profile.

    Direct viewport selection is the natural editing workflow.  The separate
    Active Profile pointer remains useful for sweep operations, so editing only
    overrides it when the active Blender object is itself an editable committed
    CPC profile.
    """
    obj = getattr(context, "object", None)
    if (
        obj
        and obj.type == 'CURVE'
        and obj.get("cpc_profile")
        and not obj.get("cpc_part")
        and obj.get("cpc_recipe_json")
    ):
        return obj

    settings = settings or (getattr(context.scene, "cpc_settings", None) if context.scene else None)
    profile = getattr(settings, "active_profile", None) if settings else None
    if profile and profile.type == 'CURVE' and profile.get("cpc_profile") and profile.get("cpc_recipe_json"):
        return profile
    return None


class CPC_OT_ReopenProfile(Operator):
    bl_idname = "cpc.reopen_profile"
    bl_label = "Edit Active Profile"
    bl_description = "Reopen the selected or active committed profile as its original parametric construction parts"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        settings = getattr(context.scene, "cpc_settings", None) if context.scene else None
        return _reopen_profile_candidate(context, settings) is not None

    def execute(self, context):
        settings = _settings(context)
        profile = _reopen_profile_candidate(context, settings)
        if not profile:
            self.report({'ERROR'}, "Selected or active profile has no CPC construction recipe")
            return {'CANCELLED'}

        # Keep the sweep/profile pointer synchronized when editing is initiated
        # directly from a selected committed profile.
        if settings.active_profile != profile:
            settings.active_profile = profile

        profile_id = _ensure_profile_id(profile)
        restored, warnings = _restore_recipe_parts(context, profile)
        if not restored:
            self.report({'ERROR'}, warnings[0] if warnings else "Could not restore profile parts")
            return {'CANCELLED'}

        settings.editing_profile_id = profile_id
        settings.build_session_id = ""

        for obj in context.selected_objects:
            obj.select_set(False)
        restored[0].select_set(True)
        context.view_layer.objects.active = restored[0]

        # 0.4.2 approval requires draw handlers to remain lazy.  Editing is an
        # explicit user-triggered CPC action, so this is the correct moment to
        # create them when Viewport Guides is enabled.
        if bool(getattr(settings, "viewport_guides", True)):
            viewport_overlay.ensure_handlers()
            viewport_overlay.tag_redraw_all(context)

        if warnings:
            self.report({'WARNING'}, f"Reopened {len(restored)} parts; {len(warnings)} item(s) could not be fully restored")
        else:
            self.report({'INFO'}, f"Reopened '{profile.name}' with {len(restored)} editable parts")
        return {'FINISHED'}


class CPC_OT_CancelProfileEdit(Operator):
    bl_idname = "cpc.cancel_profile_edit"
    bl_label = "Cancel Profile Edit"
    bl_description = "Leave component editing without changing the committed profile; reopening restores the saved recipe"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        settings = getattr(context.scene, "cpc_settings", None) if context.scene else None
        return bool(settings and str(getattr(settings, "editing_profile_id", "") or "").strip())

    def execute(self, context):
        settings = _settings(context)
        profile_id = str(settings.editing_profile_id or "").strip()
        for obj in _builder_parts(context.scene, include_preview=True, owner_profile_id=profile_id):
            obj.hide_set(True)
            obj.hide_render = True
        settings.editing_profile_id = ""

        profile = _profile_for_id(profile_id) or settings.active_profile
        if profile:
            for obj in context.selected_objects:
                obj.select_set(False)
            profile.hide_set(False)
            profile.select_set(True)
            context.view_layer.objects.active = profile
            settings.active_profile = profile

        self.report({'INFO'}, "Profile edit cancelled; committed profile left unchanged")
        return {'FINISHED'}


class CPC_OT_ShowParts(Operator):
    bl_idname = "cpc.show_parts"
    bl_label = "Show Builder Parts"
    bl_description = "Reveal modular profile parts for further editing"
    bl_options = {'REGISTER'}

    def execute(self, context):
        for obj in _active_builder_parts(context.scene, _settings(context), include_preview=True):
            obj.hide_set(False)
        return {'FINISHED'}


class CPC_OT_UseSelectedProfile(Operator):
    bl_idname = "cpc.use_selected_profile"
    bl_label = "Use Selected as Profile"
    bl_description = "Mark the selected 2D curve as the active sweep profile"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.object is not None and context.object.type == 'CURVE'

    def execute(self, context):
        obj = context.object
        obj["cpc_profile"] = True
        _settings(context).active_profile = obj
        self.report({'INFO'}, f"Active profile: {obj.name}")
        return {'FINISHED'}



class CPC_OT_SaveUserProfile(Operator):
    bl_idname = "cpc.save_user_profile"
    bl_label = "Save User Profile"
    bl_description = "Save the selected/active complete Curve as a reusable CPC preset with category metadata and an automatically generated thumbnail"
    bl_options = {'REGISTER'}

    preset_name: StringProperty(name="Preset Name", default="")
    description: StringProperty(name="Description", default="")
    category: StringProperty(name="Category", default="")
    tags: StringProperty(name="Tags", description="Comma-separated search tags", default="")
    source_collection: StringProperty(name="Source Collection", default="")
    source_reference: StringProperty(name="Source Reference", default="")
    source_url: StringProperty(name="Source URL", default="")
    source_license: StringProperty(name="Source License / Note", default="")

    @classmethod
    def poll(cls, context):
        settings = getattr(context.scene, "cpc_settings", None) if context.scene else None
        if settings and str(getattr(settings, "editing_profile_id", "") or "").strip():
            return False
        obj = context.object if context.object and context.object.type == 'CURVE' else None
        if obj and not obj.get("cpc_part"):
            return True
        profile = getattr(settings, "active_profile", None) if settings else None
        return bool(profile and profile.type == 'CURVE')

    def _source(self, context):
        settings = _settings(context)
        obj = context.object
        if obj and obj.type == 'CURVE' and not obj.get("cpc_part"):
            return obj
        return settings.active_profile

    def invoke(self, context, event):
        source = self._source(context)
        if not source:
            return {'CANCELLED'}
        settings = _settings(context)
        self.preset_name = source.name
        current = user_profiles.category_filter_value(settings)
        self.category = current if user_profiles.category_filter_is_real(settings) else ""
        self.description = ""
        self.tags = ""
        self.source_collection = ""
        self.source_reference = ""
        self.source_url = ""
        self.source_license = ""
        return context.window_manager.invoke_props_dialog(self, width=460)

    def draw(self, context):
        source = self._source(context)
        layout = self.layout
        layout.prop(self, "preset_name")
        layout.prop(self, "description")

        classification = layout.box()
        classification.label(text="Library Info", icon='ASSET_MANAGER')
        classification.prop(self, "category")
        classification.prop(self, "tags")
        hint = classification.row()
        hint.enabled = False
        hint.label(text="Category may be existing or new • Tags are comma-separated")

        source_box = layout.box()
        source_box.label(text="Source (Optional)", icon='INFO')
        source_box.prop(self, "source_collection")
        source_box.prop(self, "source_reference")
        source_box.prop(self, "source_url")
        source_box.prop(self, "source_license")

        if source:
            preset_type, reason = user_profiles.profile_type_for_save(source)
            box = layout.box()
            box.label(text="Editable CPC Profile" if preset_type == 'PARAMETRIC' else "Static Curve Profile",
                      icon='MODIFIER' if preset_type == 'PARAMETRIC' else 'CURVE_DATA')
            info = box.row()
            info.enabled = False
            info.label(text=reason)
            note = box.row()
            note.enabled = False
            note.label(text="PNG thumbnail is generated automatically")

    def execute(self, context):
        source = self._source(context)
        if not source:
            self.report({'ERROR'}, "No complete Curve profile is available")
            return {'CANCELLED'}
        try:
            result = user_profiles.save_profile_preset(
                source,
                _settings(context),
                self.preset_name,
                EXTENSION_VERSION,
                description=self.description,
                category=self.category,
                tags=self.tags,
                source_collection=self.source_collection,
                source_reference=self.source_reference,
                source_url=self.source_url,
                source_license=self.source_license,
            )
        except Exception as exc:
            self.report({'ERROR'}, f"Could not save User Profile: {exc}")
            return {'CANCELLED'}
        kind = "editable CPC" if result["profile_type"] == 'PARAMETRIC' else "static"
        if result.get("thumbnail_error"):
            self.report({'WARNING'}, f"Saved {kind} preset; thumbnail failed: {result['thumbnail_error']}")
        else:
            self.report({'INFO'}, f"Saved {kind} preset '{result['name']}' with thumbnail")
        return {'FINISHED'}


class CPC_OT_AddUserProfileCategory(Operator):
    bl_idname = "cpc.add_user_profile_category"
    bl_label = "Add User Profile Category"
    bl_description = "Add a user-managed category to the active CPC profile library"
    bl_options = {'REGISTER'}

    category_name: StringProperty(name="Category", default="")

    def invoke(self, context, event):
        self.category_name = ""
        return context.window_manager.invoke_props_dialog(self, width=360)

    def draw(self, context):
        self.layout.prop(self, "category_name")

    def execute(self, context):
        try:
            category = user_profiles.add_category(_settings(context), self.category_name)
        except Exception as exc:
            self.report({'ERROR'}, f"Could not add category: {exc}")
            return {'CANCELLED'}
        self.report({'INFO'}, f"Added category '{category}'")
        return {'FINISHED'}


class CPC_OT_RenameUserProfileCategory(Operator):
    bl_idname = "cpc.rename_user_profile_category"
    bl_label = "Manage User Profile Category"
    bl_description = "Rename the selected real category and update matching preset metadata without changing geometry or thumbnails"
    bl_options = {'REGISTER'}

    old_name: StringProperty(name="Current Category", default="", options={'HIDDEN'})
    new_name: StringProperty(name="Rename To", default="")

    @classmethod
    def poll(cls, context):
        settings = getattr(context.scene, "cpc_settings", None) if context.scene else None
        return bool(settings and user_profiles.category_filter_is_real(settings))

    def invoke(self, context, event):
        self.old_name = user_profiles.category_filter_value(_settings(context))
        self.new_name = self.old_name
        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.enabled = False
        row.label(text=f"Category: {self.old_name}")
        layout.prop(self, "new_name")
        note = layout.row()
        note.enabled = False
        note.label(text="0.4.3 renames categories; merge/delete are intentionally not included")

    def execute(self, context):
        try:
            new_name, changed = user_profiles.rename_category(_settings(context), self.old_name, self.new_name)
        except Exception as exc:
            self.report({'ERROR'}, f"Could not rename category: {exc}")
            return {'CANCELLED'}
        self.report({'INFO'}, f"Renamed category to '{new_name}' ({changed} preset{'s' if changed != 1 else ''} updated)")
        return {'FINISHED'}


class CPC_OT_EditUserProfileInfo(Operator):
    bl_idname = "cpc.edit_user_profile_info"
    bl_label = "Edit User Profile Info"
    bl_description = "Edit display/classification/source metadata without changing preset geometry, recipe, ID or thumbnail"
    bl_options = {'REGISTER'}

    preset_name: StringProperty(name="Preset Name", default="")
    description: StringProperty(name="Description", default="")
    category: StringProperty(name="Category", default="")
    tags: StringProperty(name="Tags", description="Comma-separated search tags", default="")
    source_collection: StringProperty(name="Source Collection", default="")
    source_reference: StringProperty(name="Source Reference", default="")
    source_url: StringProperty(name="Source URL", default="")
    source_license: StringProperty(name="Source License / Note", default="")

    @classmethod
    def poll(cls, context):
        settings = getattr(context.scene, "cpc_settings", None) if context.scene else None
        return bool(settings and str(getattr(settings, "user_profile_selected", "") or "") not in {"", "__NONE__"})

    def invoke(self, context, event):
        metadata = user_profiles.selected_metadata(_settings(context))
        if not metadata:
            return {'CANCELLED'}
        self.preset_name = metadata.get("name", "")
        self.description = metadata.get("description", "")
        self.category = metadata.get("category", "")
        self.tags = ", ".join(metadata.get("tags", []) or [])
        self.source_collection = metadata.get("source_collection", "")
        self.source_reference = metadata.get("source_reference", "")
        self.source_url = metadata.get("source_url", "")
        self.source_license = metadata.get("source_license", "")
        return context.window_manager.invoke_props_dialog(self, width=460)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "preset_name")
        layout.prop(self, "description")
        classification = layout.box()
        classification.label(text="Library Info", icon='ASSET_MANAGER')
        classification.prop(self, "category")
        classification.prop(self, "tags")
        source_box = layout.box()
        source_box.label(text="Source (Optional)", icon='INFO')
        source_box.prop(self, "source_collection")
        source_box.prop(self, "source_reference")
        source_box.prop(self, "source_url")
        source_box.prop(self, "source_license")
        note = layout.row()
        note.enabled = False
        note.label(text="Geometry, recipe, preset ID and PNG thumbnail are not rewritten")

    def execute(self, context):
        settings = _settings(context)
        identifier = settings.user_profile_selected
        try:
            result = user_profiles.update_preset_metadata(
                settings,
                identifier,
                name=self.preset_name,
                description=self.description,
                category=self.category,
                tags=self.tags,
                source_collection=self.source_collection,
                source_reference=self.source_reference,
                source_url=self.source_url,
                source_license=self.source_license,
            )
        except Exception as exc:
            self.report({'ERROR'}, f"Could not edit User Profile info: {exc}")
            return {'CANCELLED'}
        self.report({'INFO'}, f"Updated preset info for '{result['name']}'")
        return {'FINISHED'}


class CPC_OT_LoadUserProfile(Operator):
    bl_idname = "cpc.load_user_profile"
    bl_label = "Load User Profile"
    bl_description = "Instantiate the selected reusable profile and make it the active sweep profile"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        settings = getattr(context.scene, "cpc_settings", None) if context.scene else None
        return bool(settings and str(getattr(settings, "user_profile_selected", "") or "") not in {"", "__NONE__"})

    def execute(self, context):
        settings = _settings(context)
        try:
            obj, document = user_profiles.load_profile_preset(context, settings, settings.user_profile_selected)
        except Exception as exc:
            self.report({'ERROR'}, f"Could not load User Profile: {exc}")
            return {'CANCELLED'}
        if document["profile_type"] == 'PARAMETRIC':
            self.report({'INFO'}, f"Loaded editable CPC preset '{obj.name}'")
        else:
            self.report({'INFO'}, f"Loaded static profile preset '{obj.name}'")
        return {'FINISHED'}


class CPC_OT_DeleteUserProfile(Operator):
    bl_idname = "cpc.delete_user_profile"
    bl_label = "Delete User Profile"
    bl_description = "Delete the selected .cpcprofile file and its generated thumbnail"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        settings = getattr(context.scene, "cpc_settings", None) if context.scene else None
        return bool(settings and str(getattr(settings, "user_profile_selected", "") or "") not in {"", "__NONE__"})

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        settings = _settings(context)
        try:
            user_profiles.delete_preset(settings, settings.user_profile_selected)
        except Exception as exc:
            self.report({'ERROR'}, f"Could not delete User Profile: {exc}")
            return {'CANCELLED'}
        self.report({'INFO'}, "User Profile deleted")
        return {'FINISHED'}


class CPC_OT_RefreshUserProfiles(Operator):
    bl_idname = "cpc.refresh_user_profiles"
    bl_label = "Refresh User Profiles"
    bl_description = "Rescan .cpcprofile files and regenerate missing preview thumbnails"
    bl_options = {'REGISTER'}

    def execute(self, context):
        user_profiles.refresh_library(_settings(context), force_reload=True)
        self.report({'INFO'}, "User Profile library refreshed")
        return {'FINISHED'}


class CPC_OT_SweepSelectedEdges(Operator):
    bl_idname = "cpc.sweep_selected_edges"
    bl_label = "Sweep Selected Edges"
    bl_description = "Create an editable curve from selected mesh edges and bevel it with the active profile"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj is not None and obj.type == 'MESH' and obj.mode == 'EDIT'

    def execute(self, context):
        settings = _settings(context)
        profile = settings.active_profile
        if not profile or profile.type != 'CURVE':
            self.report({'ERROR'}, "Choose or commit an active profile first")
            return {'CANCELLED'}

        # Resolve the complete profile through the same canonical state used by
        # post-placement edits. This makes transform-before-sweep and
        # transform-after-sweep consume identical profile geometry.
        properties.ensure_profile_placement_applied(settings, context, profile)

        source = context.object
        paths = geometry.selected_edge_paths_world(source)
        if not paths:
            self.report({'ERROR'}, "Select one or more mesh edges in Edit Mode")
            return {'CANCELLED'}

        coll = library.ensure_sweep_collection(context.scene)
        sweep = geometry.create_sweep_path(
            name=f"CPC_Sweep_{source.name}",
            world_paths=paths,
            profile_obj=profile,
            collection=coll,
            resolution=settings.path_resolution,
            twist_mode=settings.twist_mode,
            fill_caps=settings.fill_caps,
            path_mode=settings.sweep_path_mode,
        )

        bpy.ops.object.mode_set(mode='OBJECT')
        for obj in context.selected_objects:
            obj.select_set(False)
        sweep.select_set(True)
        context.view_layer.objects.active = sweep

        smooth_ok, smooth_message = geometry.ensure_smooth_by_angle(
            context, sweep, settings.smooth_angle, enabled=settings.smooth_by_angle
        )
        sweep["cpc_smooth_by_angle_enabled"] = bool(settings.smooth_by_angle and smooth_ok)
        sweep["cpc_smooth_angle"] = float(settings.smooth_angle)
        if settings.smooth_by_angle and not smooth_ok:
            self.report({'WARNING'}, f"Sweep created, but Smooth by Angle was not added: {smooth_message}")

        self.report({'INFO'}, f"Created {sweep.get('cpc_path_mode', '3D')} sweep '{sweep.name}' from {len(paths)} edge path(s)")
        return {'FINISHED'}


class CPC_OT_ApplyProfileToCurve(Operator):
    bl_idname = "cpc.apply_profile_to_curve"
    bl_label = "Apply Profile to Curve"
    bl_description = "Use the active profile as the bevel object of the selected curve"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.object is not None and context.object.type == 'CURVE'

    def execute(self, context):
        settings = _settings(context)
        profile = settings.active_profile
        path = context.object
        if not profile or profile.type != 'CURVE':
            self.report({'ERROR'}, "Choose an active profile first")
            return {'CANCELLED'}
        if path == profile:
            self.report({'ERROR'}, "Select a path curve, not the profile itself")
            return {'CANCELLED'}

        # Applying a profile after its CPC transform must be identical to
        # applying first and then editing the same semantic placement state.
        properties.ensure_profile_placement_applied(settings, context, profile)

        data = path.data
        # AUTO respects an existing curve's 2D/3D choice. Explicit modes are
        # available when the user wants to override it.
        if settings.sweep_path_mode == '2D':
            data.dimensions = '2D'
        elif settings.sweep_path_mode == '3D':
            data.dimensions = '3D'
        data.bevel_mode = 'OBJECT'
        data.bevel_object = profile
        geometry.set_curve_fill_both(data)
        data.use_fill_caps = settings.fill_caps
        if data.dimensions == '3D':
            data.twist_mode = settings.twist_mode
        data.update_tag()
        path.update_tag()
        context.view_layer.update()

        smooth_ok, smooth_message = geometry.ensure_smooth_by_angle(
            context, path, settings.smooth_angle, enabled=settings.smooth_by_angle
        )
        path["cpc_smooth_by_angle_enabled"] = bool(settings.smooth_by_angle and smooth_ok)
        path["cpc_smooth_angle"] = float(settings.smooth_angle)
        if settings.smooth_by_angle and not smooth_ok:
            self.report({'WARNING'}, f"Profile applied, but Smooth by Angle was not added: {smooth_message}")

        self.report({'INFO'}, f"Applied '{profile.name}' to '{path.name}' ({data.dimensions})")
        return {'FINISHED'}


class CPC_OT_FlipActiveProfileX(Operator):
    bl_idname = "cpc.flip_active_profile_x"
    bl_label = "Flip Profile X"
    bl_description = "Mirror the active committed profile across its local X axis; existing sweeps update live"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        profile = _settings(context).active_profile
        if not profile or profile.type != 'CURVE':
            self.report({'ERROR'}, "Choose an active profile first")
            return {'CANCELLED'}
        settings = _settings(context)
        state = profile_transforms.profile_placement_state(profile)
        properties.set_profile_placement_state(
            settings, context, profile, flip_x=not state["flip_x"]
        )
        return {'FINISHED'}


class CPC_OT_FlipActiveProfileY(Operator):
    bl_idname = "cpc.flip_active_profile_y"
    bl_label = "Flip Profile Y"
    bl_description = "Mirror the active committed profile across its local Y axis; existing sweeps update live"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        profile = _settings(context).active_profile
        if not profile or profile.type != 'CURVE':
            self.report({'ERROR'}, "Choose an active profile first")
            return {'CANCELLED'}
        settings = _settings(context)
        state = profile_transforms.profile_placement_state(profile)
        properties.set_profile_placement_state(
            settings, context, profile, flip_y=not state["flip_y"]
        )
        return {'FINISHED'}


class CPC_OT_RotateActiveProfile90(Operator):
    bl_idname = "cpc.rotate_active_profile_90"
    bl_label = "Rotate Profile 90°"
    bl_description = "Rotate the active committed profile 90 degrees around its local origin"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        profile = _settings(context).active_profile
        if not profile or profile.type != 'CURVE':
            self.report({'ERROR'}, "Choose an active profile first")
            return {'CANCELLED'}
        settings = _settings(context)
        state = profile_transforms.profile_placement_state(profile)
        properties.set_profile_placement_state(
            settings,
            context,
            profile,
            rotation=state["rotation"] + math.radians(90.0),
        )
        return {'FINISHED'}


class CPC_OT_ApplyProfileAdjustment(Operator):
    bl_idname = "cpc.apply_profile_adjustment"
    bl_label = "Bake Profile Adjustment"
    bl_description = "Make the currently visible live profile adjustment the new neutral baseline"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = _settings(context)
        profile = settings.active_profile
        if not profile or profile.type != 'CURVE':
            self.report({'ERROR'}, "Choose an active profile first")
            return {'CANCELLED'}

        # The adjustment fields are live; baking makes the current visible
        # result the new neutral baseline.
        properties.bake_live_profile_adjustment(settings, profile)
        profile["cpc_recipe_geometry_hash"] = user_profiles.curve_authority_hash(profile)
        _refresh_profile_dependents(context, profile)
        self.report({'INFO'}, f"Baked live adjustment for '{profile.name}'")
        return {'FINISHED'}


class CPC_OT_ConvertSweepToMesh(Operator):
    bl_idname = "cpc.convert_sweep_to_mesh"
    bl_label = "Convert Sweep to Mesh"
    bl_description = "Convert the selected curve sweep to a mesh, keeping its current evaluated shape"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.object is not None and context.object.type == 'CURVE'

    def execute(self, context):
        bpy.ops.object.convert(target='MESH')
        return {'FINISHED'}


_KEYMAPS = []


_CLASSES = (
    CPC_OT_PlacePart,
    CPC_OT_PlaceArchitecturalComponent,
    CPC_OT_ViewportDimensionEdit,
    CPC_OT_SetEditAnchor,
    CPC_OT_AdjustPartRotation,
    CPC_OT_DeleteLastPart,
    CPC_OT_ClearParts,
    CPC_OT_CommitProfile,
    CPC_OT_ReopenProfile,
    CPC_OT_CancelProfileEdit,
    CPC_OT_ShowParts,
    CPC_OT_UseSelectedProfile,
    CPC_OT_SaveUserProfile,
    CPC_OT_AddUserProfileCategory,
    CPC_OT_RenameUserProfileCategory,
    CPC_OT_EditUserProfileInfo,
    CPC_OT_LoadUserProfile,
    CPC_OT_DeleteUserProfile,
    CPC_OT_RefreshUserProfiles,
    CPC_OT_SweepSelectedEdges,
    CPC_OT_ApplyProfileToCurve,
    CPC_OT_FlipActiveProfileX,
    CPC_OT_FlipActiveProfileY,
    CPC_OT_RotateActiveProfile90,
    CPC_OT_ApplyProfileAdjustment,
    CPC_OT_ConvertSweepToMesh,
)


def register():
    for cls in _CLASSES:
        bpy.utils.register_class(cls)

    # Object Mode E is intentionally CPC-contextual: the operator poll only
    # succeeds for a selected, placed CPC parametric part in the 3D View.
    keyconfig = getattr(bpy.context.window_manager.keyconfigs, "addon", None)
    if keyconfig is not None:
        km = keyconfig.keymaps.new(name='Object Mode', space_type='EMPTY')
        kmi = km.keymap_items.new("cpc.viewport_dimension_edit", 'E', 'PRESS')
        _KEYMAPS.append((km, kmi))


def unregister():
    for km, kmi in reversed(_KEYMAPS):
        try:
            km.keymap_items.remove(kmi)
        except Exception:
            pass
    _KEYMAPS.clear()

    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)
