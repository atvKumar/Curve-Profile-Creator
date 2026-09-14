"""User-facing reusable profile storage for CPC 0.4.0+.

Authoritative preset data is portable JSON (``.cpcprofile``). Preview PNGs are
cache artifacts generated directly from stored 2D curve geometry using a tiny
CPU rasterizer plus Blender's Image API; Pillow/PIL is intentionally not a
dependency.
"""

from __future__ import annotations

import json
import math
import os
import time
import uuid

import bpy
from mathutils import Matrix, Vector

from . import geometry, library, profile_presets, profile_transforms


_PREVIEWS = None
_ENUM_CACHE = []
_METADATA_CACHE = {}

THUMBNAIL_SIZE = 256


def register():
    global _PREVIEWS
    try:
        import bpy.utils.previews
        _PREVIEWS = bpy.utils.previews.new()
    except Exception:
        _PREVIEWS = None


def unregister():
    global _PREVIEWS, _ENUM_CACHE, _METADATA_CACHE
    if _PREVIEWS is not None:
        try:
            import bpy.utils.previews
            bpy.utils.previews.remove(_PREVIEWS)
        except Exception:
            pass
    _PREVIEWS = None
    _ENUM_CACHE = []
    _METADATA_CACHE = {}


def default_library_dir() -> str:
    """Return Blender-managed writable storage for this extension.

    Extension installs may live in read-only repositories, so CPC keeps user
    presets in Blender's extension-owned user directory rather than alongside
    the installed add-on.
    """
    path = bpy.utils.extension_path_user(__package__, path="profiles", create=True)
    return os.path.normpath(path) if path else ""



def library_dir(settings=None) -> str:
    configured = str(getattr(settings, "user_profile_library_path", "") or "").strip() if settings else ""
    if configured:
        path = bpy.path.abspath(configured)
        os.makedirs(path, exist_ok=True)
        return os.path.normpath(path)
    return default_library_dir()


def _first_curve_point_local(obj):
    if not obj or obj.type != 'CURVE':
        return Vector((0.0, 0.0, 0.0))
    for spline in obj.data.splines:
        if spline.type == 'BEZIER' and spline.bezier_points:
            return spline.bezier_points[0].co.copy()
        if len(spline.points):
            return Vector(spline.points[0].co[:3])
    return Vector((0.0, 0.0, 0.0))


def _vec3_data(value):
    return [float(value[0]), float(value[1]), float(value[2])]


def curve_geometry_snapshot(obj, *, static_visible=False) -> dict:
    """Capture exact Curve spline data in a normalized portable 2D frame.

    PARAMETRIC committed profiles use their existing object-local coordinates,
    already aligned with the CPC Profile Frame. STATIC curves bake object
    rotation/scale into the snapshot, remove world translation, and place the
    first curve point at the preset origin.
    """
    if not obj or obj.type != 'CURVE':
        raise ValueError("A Curve object is required")

    origin_local = _first_curve_point_local(obj)
    world_origin = obj.matrix_world @ origin_local

    if static_visible:
        def map_point(co):
            return (obj.matrix_world @ Vector(co)) - world_origin
    else:
        def map_point(co):
            return Vector(co)

    splines = []
    for spline in obj.data.splines:
        item = {
            "type": spline.type,
            "cyclic": bool(spline.use_cyclic_u),
            "resolution_u": int(spline.resolution_u),
        }
        if spline.type == 'BEZIER':
            points = []
            for bp in spline.bezier_points:
                points.append({
                    "co": _vec3_data(map_point(bp.co)),
                    "handle_left": _vec3_data(map_point(bp.handle_left)),
                    "handle_right": _vec3_data(map_point(bp.handle_right)),
                    "handle_left_type": str(bp.handle_left_type),
                    "handle_right_type": str(bp.handle_right_type),
                    "radius": float(bp.radius),
                    "tilt": float(bp.tilt),
                    "weight_softbody": float(bp.weight_softbody),
                })
            item["bezier_points"] = points
        else:
            points = []
            for point in spline.points:
                co = map_point(point.co[:3])
                points.append({
                    "co": [float(co.x), float(co.y), float(co.z), float(point.co[3])],
                    "radius": float(point.radius),
                    "tilt": float(point.tilt),
                    "weight_softbody": float(point.weight_softbody),
                })
            item["points"] = points
            item["order_u"] = int(getattr(spline, "order_u", 0))
            item["use_endpoint_u"] = bool(getattr(spline, "use_endpoint_u", False))

        splines.append(item)

    return {
        "dimensions": str(obj.data.dimensions),
        "resolution_u": int(obj.data.resolution_u),
        "render_resolution_u": int(obj.data.render_resolution_u),
        "splines": splines,
    }


def curve_authority_payload(obj) -> dict:
    """State that must stay unchanged for the embedded CPC recipe to remain authoritative."""
    return {
        "geometry": curve_geometry_snapshot(obj, static_visible=False),
        "matrix_world": profile_transforms.matrix_to_data(obj.matrix_world),
    }


def curve_authority_hash(obj) -> str:
    return profile_presets.stable_digest(curve_authority_payload(obj))


def profile_type_for_save(obj) -> tuple[str, str]:
    """Return preset type plus a short explanation for UI/reporting."""
    if not obj or obj.type != 'CURVE':
        return profile_presets.PROFILE_TYPE_STATIC, "Selected object is not a Curve"

    recipe_raw = str(obj.get("cpc_recipe_json", "") or "").strip()
    recipe_version = int(obj.get("cpc_recipe_version", 0))
    stored_hash = str(obj.get("cpc_recipe_geometry_hash", "") or "").strip()
    try:
        if profile_transforms.matrix_max_abs_error(obj.matrix_world, Matrix.Identity(4)) > 1.0e-9:
            return profile_presets.PROFILE_TYPE_STATIC, "Object transform differs from the committed CPC profile frame"
    except Exception:
        pass
    if recipe_raw and recipe_version >= profile_presets.MIN_PARAMETRIC_RECIPE_SCHEMA and stored_hash:
        try:
            if stored_hash == curve_authority_hash(obj):
                return profile_presets.PROFILE_TYPE_PARAMETRIC, "Editable CPC recipe is authoritative"
            return profile_presets.PROFILE_TYPE_STATIC, "Curve geometry changed after the last CPC Commit"
        except Exception:
            return profile_presets.PROFILE_TYPE_STATIC, "Could not verify CPC recipe authority"

    if recipe_raw and not stored_hash:
        return profile_presets.PROFILE_TYPE_STATIC, "Curve has no 0.4.0+ recipe authority hash"
    return profile_presets.PROFILE_TYPE_STATIC, "Curve has no authoritative CPC recipe"


def _read_recipe_records(obj):
    raw = str(obj.get("cpc_recipe_json", "") or "").strip()
    records = json.loads(raw) if raw else []
    if not isinstance(records, list):
        raise ValueError("CPC recipe is not a record list")
    return records


def _unique_paths(directory, name):
    stem = profile_presets.safe_stem(name)
    candidate = stem
    index = 2
    while True:
        preset_path = os.path.join(directory, candidate + ".cpcprofile")
        if not os.path.exists(preset_path):
            return candidate, preset_path, os.path.join(directory, candidate + ".png")
        candidate = f"{stem}_{index}"
        index += 1


def _metadata_for_document(document, preset_path):
    preview = document.get("preview") if isinstance(document.get("preview"), dict) else {}
    preview_file = str(preview.get("file", "") or "")
    preview_path = os.path.join(os.path.dirname(preset_path), preview_file) if preview_file else ""
    return {
        "identifier": os.path.basename(preset_path),
        "name": str(document.get("name", os.path.splitext(os.path.basename(preset_path))[0])),
        "description": str(document.get("description", "") or ""),
        "profile_type": str(document.get("profile_type", profile_presets.PROFILE_TYPE_STATIC)),
        "preset_path": preset_path,
        "preview_path": preview_path,
    }


def save_profile_preset(obj, settings, name: str, extension_version: str) -> dict:
    if not obj or obj.type != 'CURVE':
        raise ValueError("Select a complete Curve profile to save")
    if obj.get("cpc_part"):
        raise ValueError("Commit the CPC construction first, then save the completed profile preset")

    preset_type, reason = profile_type_for_save(obj)
    directory = library_dir(settings)
    stem, preset_path, preview_path = _unique_paths(directory, name or obj.name)

    if preset_type == profile_presets.PROFILE_TYPE_PARAMETRIC:
        geometry_data = curve_geometry_snapshot(obj, static_visible=False)
        recipe = {
            "schema_version": int(obj.get("cpc_recipe_version", profile_presets.MIN_PARAMETRIC_RECIPE_SCHEMA)),
            "transform_version": int(obj.get("cpc_recipe_transform_version", profile_transforms.PROFILE_TRANSFORM_SCHEMA)),
            "frame_policy": str(obj.get("cpc_recipe_frame_policy", profile_transforms.PROFILE_FRAME_POLICY)),
            "records": _read_recipe_records(obj),
        }
    else:
        geometry_data = curve_geometry_snapshot(obj, static_visible=True)
        recipe = None

    document = {
        "format": profile_presets.PRESET_FORMAT,
        "format_version": profile_presets.PRESET_FORMAT_VERSION,
        "id": profile_presets.new_preset_id(),
        "name": str(name or obj.name),
        "description": "",
        "profile_type": preset_type,
        "created_with": str(extension_version),
        "created_utc": int(time.time()),
        "geometry": geometry_data,
        "preview": {"file": os.path.basename(preview_path)},
    }
    if recipe is not None:
        document["recipe"] = recipe

    with open(preset_path, "w", encoding="utf-8") as handle:
        json.dump(document, handle, indent=2, sort_keys=True, ensure_ascii=False)
        handle.write("\n")

    thumbnail_error = ""
    try:
        generate_thumbnail(geometry_data, preview_path)
    except Exception as exc:
        thumbnail_error = str(exc)

    refresh_library(settings, force_reload=True)
    try:
        settings.user_profile_selected = os.path.basename(preset_path)
    except Exception:
        pass

    metadata = _metadata_for_document(document, preset_path)
    metadata["reason"] = reason
    metadata["thumbnail_error"] = thumbnail_error
    return metadata


def load_document(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    return profile_presets.validate_preset_document(data)


def _new_curve_from_geometry(document, name, collection):
    curve = bpy.data.curves.new(name=f"{name}_Curve", type='CURVE')
    dims = str(document.get("dimensions", "2D") or "2D")
    curve.dimensions = dims if dims in {'2D', '3D'} else '2D'
    curve.resolution_u = int(document.get("resolution_u", 12))
    curve.render_resolution_u = int(document.get("render_resolution_u", 24))
    geometry.set_curve_fill_both(curve)

    for spec in document.get("splines", []):
        spline_type = str(spec.get("type", "POLY") or "POLY")
        if spline_type not in {'BEZIER', 'POLY', 'NURBS'}:
            spline_type = 'POLY'
        spline = curve.splines.new(spline_type)
        spline.use_cyclic_u = bool(spec.get("cyclic", False))
        spline.resolution_u = int(spec.get("resolution_u", curve.resolution_u))

        if spline_type == 'BEZIER':
            points = list(spec.get("bezier_points", []))
            if not points:
                curve.splines.remove(spline)
                continue
            spline.bezier_points.add(len(points) - 1)
            for bp, point_spec in zip(spline.bezier_points, points):
                bp.co = point_spec.get("co", (0.0, 0.0, 0.0))
                bp.handle_left = point_spec.get("handle_left", bp.co)
                bp.handle_right = point_spec.get("handle_right", bp.co)
                bp.radius = float(point_spec.get("radius", 1.0))
                bp.tilt = float(point_spec.get("tilt", 0.0))
                bp.weight_softbody = float(point_spec.get("weight_softbody", 0.0))
            for bp, point_spec in zip(spline.bezier_points, points):
                bp.handle_left_type = str(point_spec.get("handle_left_type", "FREE"))
                bp.handle_right_type = str(point_spec.get("handle_right_type", "FREE"))
        else:
            points = list(spec.get("points", []))
            if not points:
                curve.splines.remove(spline)
                continue
            spline.points.add(len(points) - 1)
            for point, point_spec in zip(spline.points, points):
                co = list(point_spec.get("co", (0.0, 0.0, 0.0, 1.0)))
                while len(co) < 4:
                    co.append(1.0)
                point.co = co[:4]
                point.radius = float(point_spec.get("radius", 1.0))
                point.tilt = float(point_spec.get("tilt", 0.0))
                point.weight_softbody = float(point_spec.get("weight_softbody", 0.0))
            if spline_type == 'NURBS':
                try:
                    spline.order_u = max(2, min(int(spec.get("order_u", 4)), len(points)))
                    spline.use_endpoint_u = bool(spec.get("use_endpoint_u", False))
                except Exception:
                    pass

    obj = bpy.data.objects.new(name, curve)
    collection.objects.link(obj)
    obj["cpc_profile"] = True
    return obj


def load_profile_preset(context, settings, identifier: str):
    metadata = metadata_for_identifier(settings, identifier)
    if not metadata:
        raise ValueError("Choose a User Profile preset")
    document = load_document(metadata["preset_path"])
    name = str(document.get("name", "User Profile") or "User Profile")
    coll = library.ensure_profile_collection(context.scene)
    obj = _new_curve_from_geometry(document["geometry"], name, coll)
    obj["cpc_profile_id"] = f"profile-{uuid.uuid4()}"
    obj["cpc_user_preset_id"] = str(document.get("id", "") or "")
    obj["cpc_user_preset_type"] = str(document.get("profile_type", profile_presets.PROFILE_TYPE_STATIC))
    obj["cpc_anchor_world"] = (0.0, 0.0, 0.0)

    if document["profile_type"] == profile_presets.PROFILE_TYPE_PARAMETRIC:
        recipe = document["recipe"]
        records = profile_presets.remap_recipe_identities(recipe.get("records", []))
        obj["cpc_recipe_version"] = int(recipe["schema_version"])
        obj["cpc_recipe_transform_version"] = int(recipe.get("transform_version", profile_transforms.PROFILE_TRANSFORM_SCHEMA))
        obj["cpc_recipe_frame_policy"] = str(recipe.get("frame_policy", profile_transforms.PROFILE_FRAME_POLICY))
        obj["cpc_recipe_frame_json"] = profile_transforms.matrix_to_json(Matrix.Identity(4))
        obj["cpc_recipe_json"] = json.dumps(records, sort_keys=True)
        obj["cpc_commit_geometry"] = "BEZIER" if all(
            spec.get("type") == "BEZIER" for spec in document["geometry"].get("splines", [])
        ) else "SAMPLED"
        obj["cpc_recipe_geometry_hash"] = curve_authority_hash(obj)

    for selected in list(context.selected_objects):
        selected.select_set(False)
    obj.select_set(True)
    context.view_layer.objects.active = obj
    settings.active_profile = obj
    try:
        from . import properties
        properties.capture_profile_adjust_baseline(obj)
    except Exception:
        pass
    return obj, document


def delete_preset(settings, identifier: str):
    metadata = metadata_for_identifier(settings, identifier)
    if not metadata:
        raise ValueError("Choose a User Profile preset")
    for path in (metadata.get("preset_path"), metadata.get("preview_path")):
        if path and os.path.isfile(path):
            os.remove(path)
    entries = refresh_library(settings, force_reload=True)
    try:
        settings.user_profile_selected = entries[0][0]
    except Exception:
        pass


def metadata_for_identifier(settings, identifier: str):
    identifier = str(identifier or "")
    if identifier in _METADATA_CACHE:
        return dict(_METADATA_CACHE[identifier])
    refresh_library(settings)
    value = _METADATA_CACHE.get(identifier)
    return dict(value) if value else None


def selected_metadata(settings):
    return metadata_for_identifier(settings, getattr(settings, "user_profile_selected", ""))


def _iter_preset_files(settings):
    directory = library_dir(settings)
    try:
        names = sorted(os.listdir(directory), key=str.casefold)
    except OSError:
        return
    for filename in names:
        if filename.lower().endswith(".cpcprofile"):
            yield os.path.join(directory, filename)


def refresh_library(settings=None, *, force_reload=False):
    global _ENUM_CACHE, _METADATA_CACHE
    entries = []
    metadata_cache = {}

    if _PREVIEWS is not None and force_reload:
        try:
            for key in list(_PREVIEWS.keys()):
                del _PREVIEWS[key]
        except Exception:
            pass

    for path in _iter_preset_files(settings):
        try:
            document = load_document(path)
            metadata = _metadata_for_document(document, path)
        except Exception:
            continue
        identifier = metadata["identifier"]
        preview_path = metadata.get("preview_path", "")
        if force_reload and preview_path and not os.path.isfile(preview_path):
            try:
                generate_thumbnail(document["geometry"], preview_path)
            except Exception:
                pass

        icon_id = 0
        if _PREVIEWS is not None and preview_path and os.path.isfile(preview_path):
            key = os.path.normcase(os.path.abspath(preview_path))
            try:
                if key not in _PREVIEWS:
                    _PREVIEWS.load(key, preview_path, 'IMAGE', force_reload=force_reload)
                icon_id = _PREVIEWS[key].icon_id
            except Exception:
                icon_id = 0

        profile_type = metadata["profile_type"]
        type_label = "Editable CPC" if profile_type == profile_presets.PROFILE_TYPE_PARAMETRIC else "Static Curve"
        description = metadata.get("description") or type_label
        entries.append((identifier, metadata["name"], description, icon_id, len(entries)))
        metadata_cache[identifier] = metadata

    if not entries:
        entries = [("__NONE__", "No User Profiles", "Save a profile to create the first preset", 0, 0)]
    _ENUM_CACHE = entries
    _METADATA_CACHE = metadata_cache
    return entries


def enum_items(self, context):
    settings = self
    if not _ENUM_CACHE:
        refresh_library(settings)
    return _ENUM_CACHE


def on_library_path_changed(settings, context):
    refresh_library(settings, force_reload=True)


def _sample_geometry(snapshot, steps=24):
    chains = []
    for spline in snapshot.get("splines", []):
        spline_type = spline.get("type")
        chain = []
        if spline_type == 'BEZIER':
            points = spline.get("bezier_points", [])
            count = len(points)
            if count < 2:
                continue
            spans = count if spline.get("cyclic") else count - 1
            for index in range(spans):
                a = points[index]
                b = points[(index + 1) % count]
                p0 = Vector(a["co"])
                p1 = Vector(a["handle_right"])
                p2 = Vector(b["handle_left"])
                p3 = Vector(b["co"])
                for step in range(steps + 1):
                    if chain and step == 0:
                        continue
                    t = step / float(steps)
                    u = 1.0 - t
                    co = (u ** 3) * p0 + 3.0 * (u ** 2) * t * p1 + 3.0 * u * (t ** 2) * p2 + (t ** 3) * p3
                    chain.append((float(co.x), float(co.y)))
        else:
            for point in spline.get("points", []):
                co = point.get("co", (0.0, 0.0, 0.0, 1.0))
                chain.append((float(co[0]), float(co[1])))
            if spline.get("cyclic") and len(chain) > 1:
                chain.append(chain[0])
        if len(chain) > 1:
            chains.append(chain)
    return chains


def _draw_disk(pixels, size, x, y, radius, rgba):
    xmin = max(0, int(x - radius))
    xmax = min(size - 1, int(x + radius))
    ymin = max(0, int(y - radius))
    ymax = min(size - 1, int(y + radius))
    rr = radius * radius
    for py in range(ymin, ymax + 1):
        for px in range(xmin, xmax + 1):
            if (px - x) ** 2 + (py - y) ** 2 > rr:
                continue
            index = 4 * (py * size + px)
            pixels[index:index+4] = rgba


def _draw_line(pixels, size, a, b, width, rgba):
    x0, y0 = a
    x1, y1 = b
    distance = max(abs(x1 - x0), abs(y1 - y0))
    steps = max(1, int(math.ceil(distance * 1.5)))
    radius = max(1.0, width * 0.5)
    for i in range(steps + 1):
        t = i / float(steps)
        x = x0 + (x1 - x0) * t
        y = y0 + (y1 - y0) * t
        _draw_disk(pixels, size, x, y, radius, rgba)


def generate_thumbnail(snapshot: dict, filepath: str, size: int = THUMBNAIL_SIZE):
    chains = _sample_geometry(snapshot)
    if not chains:
        raise ValueError("Profile has no drawable spline geometry")
    all_points = [point for chain in chains for point in chain]
    min_x = min(p[0] for p in all_points)
    max_x = max(p[0] for p in all_points)
    min_y = min(p[1] for p in all_points)
    max_y = max(p[1] for p in all_points)
    width = max(max_x - min_x, 1.0e-9)
    height = max(max_y - min_y, 1.0e-9)
    padding = size * 0.12
    scale = min((size - 2.0 * padding) / width, (size - 2.0 * padding) / height)
    cx = 0.5 * (min_x + max_x)
    cy = 0.5 * (min_y + max_y)

    background = [0.12, 0.12, 0.12, 1.0]
    foreground = [0.92, 0.92, 0.92, 1.0]
    pixels = background * (size * size)

    def map_xy(point):
        x = (point[0] - cx) * scale + size * 0.5
        y = (point[1] - cy) * scale + size * 0.5
        return x, y

    for chain in chains:
        mapped = [map_xy(point) for point in chain]
        for a, b in zip(mapped, mapped[1:]):
            _draw_line(pixels, size, a, b, 3.0, foreground)

    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    image_name = f"CPC_Preset_Thumbnail_{uuid.uuid4().hex[:8]}"
    image = bpy.data.images.new(image_name, width=size, height=size, alpha=True)
    try:
        image.pixels.foreach_set(pixels)
        image.filepath_raw = filepath
        image.file_format = 'PNG'
        image.save()
    finally:
        bpy.data.images.remove(image)
