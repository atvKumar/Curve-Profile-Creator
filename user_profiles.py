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
_CATEGORY_ENUM_CACHE = []
_CATEGORY_NAMES = []
_INDEX_LIBRARY_DIR = ""
_INDEX_READY = False
_VISIBLE_COUNT = 0
_FILTER_UPDATE_GUARD = False

THUMBNAIL_SIZE = 256
LIBRARY_FORMAT = "CPC_LIBRARY"
LIBRARY_FORMAT_VERSION = 1
LIBRARY_CONFIG_FILENAME = "cpc_library.json"
CATEGORY_ALL = "__ALL__"
CATEGORY_UNCATEGORIZED = "__UNCATEGORIZED__"
CATEGORY_ALL_LABEL = "All Categories"
CATEGORY_UNCATEGORIZED_LABEL = "Uncategorized"
STARTER_CATEGORIES = (
    "Cornice / Crown",
    "Casing / Architrave",
    "Skirting / Baseboard",
    "Chair Rail",
    "Picture Rail",
    "Panel Moulding",
    "Door / Window Trim",
    "Classical Orders",
    "Cabinet / Furniture Mouldings",
    "Other",
)


def register():
    global _PREVIEWS
    try:
        import bpy.utils.previews
        _PREVIEWS = bpy.utils.previews.new()
    except Exception:
        _PREVIEWS = None


def unregister():
    global _PREVIEWS, _ENUM_CACHE, _METADATA_CACHE, _CATEGORY_ENUM_CACHE
    global _CATEGORY_NAMES, _INDEX_LIBRARY_DIR, _INDEX_READY, _VISIBLE_COUNT
    if _PREVIEWS is not None:
        try:
            import bpy.utils.previews
            bpy.utils.previews.remove(_PREVIEWS)
        except Exception:
            pass
    _PREVIEWS = None
    _ENUM_CACHE = []
    _METADATA_CACHE = {}
    _CATEGORY_ENUM_CACHE = []
    _CATEGORY_NAMES = []
    _INDEX_LIBRARY_DIR = ""
    _INDEX_READY = False
    _VISIBLE_COUNT = 0


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



def _atomic_write_json(path: str, data: dict) -> None:
    """Write JSON in the destination directory and replace the target atomically."""
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    temp_path = os.path.join(directory, f".{os.path.basename(path)}.{uuid.uuid4().hex}.tmp")
    try:
        with open(temp_path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, sort_keys=True, ensure_ascii=False)
            handle.write("\n")
        os.replace(temp_path, path)
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


def _clean_category_name(value) -> str:
    return " ".join(str(value or "").strip().split())


def _normalize_tags(value) -> list[str]:
    if isinstance(value, str):
        raw = value.replace(";", ",").split(",")
    elif isinstance(value, (list, tuple, set)):
        raw = list(value)
    else:
        raw = []
    result = []
    seen = set()
    for item in raw:
        tag = " ".join(str(item or "").strip().split())
        key = tag.casefold()
        if tag and key not in seen:
            result.append(tag)
            seen.add(key)
    return result


def _unique_categories(values) -> list[str]:
    result = []
    seen = set()
    for value in values:
        name = _clean_category_name(value)
        key = name.casefold()
        if not name or key in seen:
            continue
        if key in {CATEGORY_ALL_LABEL.casefold(), CATEGORY_UNCATEGORIZED_LABEL.casefold()}:
            continue
        result.append(name)
        seen.add(key)
    return result


def _library_config_path(settings=None) -> str:
    return os.path.join(library_dir(settings), LIBRARY_CONFIG_FILENAME)


def _read_library_registry(settings=None) -> tuple[bool, list[str]]:
    path = _library_config_path(settings)
    if not os.path.isfile(path):
        return False, []
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict) or data.get("format") != LIBRARY_FORMAT:
            return False, []
        if int(data.get("format_version", 0)) != LIBRARY_FORMAT_VERSION:
            return False, []
        return True, _unique_categories(data.get("categories", []))
    except Exception:
        # A malformed library config must never hide valid .cpcprofile presets.
        return False, []


def _write_library_registry(settings, categories) -> None:
    data = {
        "format": LIBRARY_FORMAT,
        "format_version": LIBRARY_FORMAT_VERSION,
        "categories": _unique_categories(categories),
    }
    _atomic_write_json(_library_config_path(settings), data)


def category_filter_value(settings) -> str:
    value = str(getattr(settings, "user_profile_category_filter", "") or "") if settings else ""
    return value or CATEGORY_ALL


def category_filter_is_real(settings) -> bool:
    value = category_filter_value(settings)
    return value not in {CATEGORY_ALL, CATEGORY_UNCATEGORIZED} and any(
        value.casefold() == item.casefold() for item in _CATEGORY_NAMES
    )


def visible_count() -> int:
    return int(_VISIBLE_COUNT)


def total_count() -> int:
    return len(_METADATA_CACHE)


def _source_metadata(document) -> dict:
    source = document.get("source") if isinstance(document.get("source"), dict) else {}
    return {
        "collection": str(source.get("collection", "") or "").strip(),
        "reference": str(source.get("reference", "") or "").strip(),
        "url": str(source.get("url", "") or "").strip(),
        "license": str(source.get("license", "") or "").strip(),
    }


def _classification_metadata(document) -> tuple[str, list[str]]:
    classification = document.get("classification") if isinstance(document.get("classification"), dict) else {}
    category = _clean_category_name(classification.get("category", ""))
    tags = _normalize_tags(classification.get("tags", []))
    return category, tags


def _rebuild_category_enum(settings=None) -> None:
    global _CATEGORY_ENUM_CACHE
    entries = [(CATEGORY_ALL, CATEGORY_ALL_LABEL, "Browse every category")]
    entries.extend((name, name, f"Show profiles in {name}") for name in _CATEGORY_NAMES)
    if any(not str(meta.get("category", "") or "").strip() for meta in _METADATA_CACHE.values()):
        entries.append((CATEGORY_UNCATEGORIZED, CATEGORY_UNCATEGORIZED_LABEL, "Profiles without a category"))
    _CATEGORY_ENUM_CACHE = entries


def _refresh_category_names(settings, discovered_categories) -> None:
    global _CATEGORY_NAMES
    registry_exists, registered = _read_library_registry(settings)
    base = registered if registry_exists else list(STARTER_CATEGORIES)
    _CATEGORY_NAMES = _unique_categories([*base, *discovered_categories])
    _rebuild_category_enum(settings)


def _ensure_index(settings=None) -> None:
    current = library_dir(settings)
    if not _INDEX_READY or os.path.normcase(current) != os.path.normcase(_INDEX_LIBRARY_DIR):
        refresh_library(settings)


def add_category(settings, name: str) -> str:
    global _CATEGORY_NAMES
    _ensure_index(settings)
    category = _clean_category_name(name)
    if not category:
        raise ValueError("Category name cannot be blank")
    if category.casefold() in {CATEGORY_ALL_LABEL.casefold(), CATEGORY_UNCATEGORIZED_LABEL.casefold()}:
        raise ValueError(f"'{category}' is reserved by CPC")
    if any(category.casefold() == existing.casefold() for existing in _CATEGORY_NAMES):
        raise ValueError(f"Category '{category}' already exists")
    _CATEGORY_NAMES = [*_CATEGORY_NAMES, category]
    _write_library_registry(settings, _CATEGORY_NAMES)
    _rebuild_category_enum(settings)
    try:
        settings.user_profile_search = ""
        settings.user_profile_category_filter = category
    except Exception:
        pass
    rebuild_visible(settings)
    return category


def _ensure_category_registered(settings, category: str) -> None:
    global _CATEGORY_NAMES
    category = _clean_category_name(category)
    if not category:
        return
    _ensure_index(settings)
    if any(category.casefold() == existing.casefold() for existing in _CATEGORY_NAMES):
        return
    _CATEGORY_NAMES = [*_CATEGORY_NAMES, category]
    _write_library_registry(settings, _CATEGORY_NAMES)
    _rebuild_category_enum(settings)


def rename_category(settings, old_name: str, new_name: str) -> tuple[str, int]:
    global _CATEGORY_NAMES
    _ensure_index(settings)
    old_name = _clean_category_name(old_name)
    new_name = _clean_category_name(new_name)
    if not old_name or old_name.casefold() in {CATEGORY_ALL_LABEL.casefold(), CATEGORY_UNCATEGORIZED_LABEL.casefold()}:
        raise ValueError("Choose a real category to rename")
    if not any(old_name.casefold() == item.casefold() for item in _CATEGORY_NAMES):
        raise ValueError(f"Category '{old_name}' does not exist")
    if not new_name:
        raise ValueError("Category name cannot be blank")
    if new_name.casefold() in {CATEGORY_ALL_LABEL.casefold(), CATEGORY_UNCATEGORIZED_LABEL.casefold()}:
        raise ValueError(f"'{new_name}' is reserved by CPC")
    for item in _CATEGORY_NAMES:
        if item.casefold() == new_name.casefold() and item.casefold() != old_name.casefold():
            raise ValueError(f"Category '{new_name}' already exists; 0.4.3 does not merge categories")

    changed = 0
    for identifier, metadata in list(_METADATA_CACHE.items()):
        if str(metadata.get("category", "") or "").casefold() != old_name.casefold():
            continue
        document = load_document(metadata["preset_path"])
        classification = document.get("classification") if isinstance(document.get("classification"), dict) else {}
        classification = dict(classification)
        classification["category"] = new_name
        document["classification"] = classification
        _atomic_write_json(metadata["preset_path"], document)
        new_metadata = _metadata_for_document(document, metadata["preset_path"])
        _METADATA_CACHE[identifier] = new_metadata
        changed += 1

    _CATEGORY_NAMES = _unique_categories([
        new_name if item.casefold() == old_name.casefold() else item
        for item in _CATEGORY_NAMES
    ])
    _write_library_registry(settings, _CATEGORY_NAMES)
    _rebuild_category_enum(settings)
    try:
        if category_filter_value(settings).casefold() == old_name.casefold():
            settings.user_profile_category_filter = new_name
    except Exception:
        pass
    rebuild_visible(settings)
    return new_name, changed


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
    category, tags = _classification_metadata(document)
    source = _source_metadata(document)
    return {
        "identifier": os.path.basename(preset_path),
        "preset_id": str(document.get("id", "") or ""),
        "name": str(document.get("name", os.path.splitext(os.path.basename(preset_path))[0])),
        "description": str(document.get("description", "") or ""),
        "profile_type": str(document.get("profile_type", profile_presets.PROFILE_TYPE_STATIC)),
        "category": category,
        "tags": tags,
        "source_collection": source["collection"],
        "source_reference": source["reference"],
        "source_url": source["url"],
        "source_license": source["license"],
        "preset_path": preset_path,
        "preview_path": preview_path,
    }


def save_profile_preset(
    obj,
    settings,
    name: str,
    extension_version: str,
    *,
    description: str = "",
    category: str = "",
    tags=(),
    source_collection: str = "",
    source_reference: str = "",
    source_url: str = "",
    source_license: str = "",
) -> dict:
    if not obj or obj.type != 'CURVE':
        raise ValueError("Select a complete Curve profile to save")
    if obj.get("cpc_part"):
        raise ValueError("Commit the CPC construction first, then save the completed profile preset")

    _ensure_index(settings)
    preset_type, reason = profile_type_for_save(obj)
    directory = library_dir(settings)
    stem, preset_path, preview_path = _unique_paths(directory, name or obj.name)
    category = _clean_category_name(category)
    tags = _normalize_tags(tags)

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
        "description": str(description or "").strip(),
        "profile_type": preset_type,
        "created_with": str(extension_version),
        "created_utc": int(time.time()),
        "classification": {"category": category, "tags": tags},
        "geometry": geometry_data,
        "preview": {"file": os.path.basename(preview_path)},
    }
    if profile_transforms.has_profile_placement_state(obj):
        document["placement"] = profile_transforms.profile_placement_state(obj)
    source = {
        "collection": str(source_collection or "").strip(),
        "reference": str(source_reference or "").strip(),
        "url": str(source_url or "").strip(),
        "license": str(source_license or "").strip(),
    }
    if any(source.values()):
        document["source"] = source
    if recipe is not None:
        document["recipe"] = recipe

    _atomic_write_json(preset_path, document)

    thumbnail_error = ""
    try:
        generate_thumbnail(geometry_data, preview_path)
    except Exception as exc:
        thumbnail_error = str(exc)

    if category:
        _ensure_category_registered(settings, category)
    metadata = _metadata_for_document(document, preset_path)
    _METADATA_CACHE[metadata["identifier"]] = metadata
    _rebuild_category_enum(settings)

    # Keep the newly saved preset visible so both selector views can select it.
    try:
        search = str(getattr(settings, "user_profile_search", "") or "").strip()
        current_category = category_filter_value(settings)
        category_matches = (
            current_category == CATEGORY_ALL
            or (current_category == CATEGORY_UNCATEGORIZED and not category)
            or (category and current_category.casefold() == category.casefold())
        )
        if search or not category_matches:
            settings.user_profile_search = ""
            settings.user_profile_category_filter = category if category else CATEGORY_UNCATEGORIZED
    except Exception:
        pass
    rebuild_visible(settings)
    try:
        settings.user_profile_selected = metadata["identifier"]
    except Exception:
        pass

    metadata = dict(metadata)
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

    placement = document.get("placement")
    if isinstance(placement, dict):
        profile_transforms.set_profile_placement_state(obj, placement)

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
    _ensure_index(settings)
    metadata = metadata_for_identifier(settings, identifier)
    if not metadata:
        raise ValueError("Choose a User Profile preset")
    for path in (metadata.get("preset_path"), metadata.get("preview_path")):
        if path and os.path.isfile(path):
            os.remove(path)
    _METADATA_CACHE.pop(identifier, None)
    _rebuild_category_enum(settings)
    rebuild_visible(settings)


def update_preset_metadata(
    settings,
    identifier: str,
    *,
    name: str,
    description: str = "",
    category: str = "",
    tags=(),
    source_collection: str = "",
    source_reference: str = "",
    source_url: str = "",
    source_license: str = "",
) -> dict:
    _ensure_index(settings)
    metadata = metadata_for_identifier(settings, identifier)
    if not metadata:
        raise ValueError("Choose a User Profile preset")
    document = load_document(metadata["preset_path"])
    display_name = str(name or "").strip()
    if not display_name:
        raise ValueError("Preset name cannot be blank")
    category = _clean_category_name(category)
    tags = _normalize_tags(tags)

    document["name"] = display_name
    document["description"] = str(description or "").strip()
    classification = document.get("classification") if isinstance(document.get("classification"), dict) else {}
    classification = dict(classification)
    classification["category"] = category
    classification["tags"] = tags
    document["classification"] = classification

    source = {
        "collection": str(source_collection or "").strip(),
        "reference": str(source_reference or "").strip(),
        "url": str(source_url or "").strip(),
        "license": str(source_license or "").strip(),
    }
    if any(source.values()):
        document["source"] = source
    else:
        document.pop("source", None)

    _atomic_write_json(metadata["preset_path"], document)
    if category:
        _ensure_category_registered(settings, category)
    updated = _metadata_for_document(document, metadata["preset_path"])
    _METADATA_CACHE[identifier] = updated
    _rebuild_category_enum(settings)
    rebuild_visible(settings)
    try:
        if identifier in {item[0] for item in _ENUM_CACHE}:
            settings.user_profile_selected = identifier
    except Exception:
        pass
    return dict(updated)


def metadata_for_identifier(settings, identifier: str):
    identifier = str(identifier or "")
    _ensure_index(settings)
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


def _metadata_search_haystack(metadata) -> str:
    values = [
        metadata.get("name", ""),
        metadata.get("description", ""),
        metadata.get("category", ""),
        *(metadata.get("tags", []) or []),
        metadata.get("source_collection", ""),
        metadata.get("source_reference", ""),
        metadata.get("source_url", ""),
        metadata.get("source_license", ""),
    ]
    return "\n".join(str(value or "") for value in values).casefold()


def _matches_search(metadata, query: str) -> bool:
    tokens = [token for token in str(query or "").casefold().split() if token]
    if not tokens:
        return True
    haystack = _metadata_search_haystack(metadata)
    return all(token in haystack for token in tokens)


def _matches_category(metadata, category_filter: str) -> bool:
    category = str(metadata.get("category", "") or "").strip()
    if category_filter in {"", CATEGORY_ALL}:
        return True
    if category_filter == CATEGORY_UNCATEGORIZED:
        return not category
    return category.casefold() == category_filter.casefold()


def _release_previews_except(preview_paths) -> None:
    if _PREVIEWS is None:
        return
    desired = {
        os.path.normcase(os.path.abspath(path))
        for path in preview_paths
        if path
    }
    try:
        for key in list(_PREVIEWS.keys()):
            if key not in desired:
                del _PREVIEWS[key]
    except Exception:
        pass


def _preview_icon(metadata, *, force_reload=False) -> int:
    if _PREVIEWS is None:
        return 0
    preview_path = str(metadata.get("preview_path", "") or "")
    if not preview_path:
        return 0
    if not os.path.isfile(preview_path):
        try:
            document = load_document(metadata["preset_path"])
            generate_thumbnail(document["geometry"], preview_path)
        except Exception:
            return 0
    key = os.path.normcase(os.path.abspath(preview_path))
    try:
        if force_reload and key in _PREVIEWS:
            del _PREVIEWS[key]
        if key not in _PREVIEWS:
            _PREVIEWS.load(key, preview_path, 'IMAGE', force_reload=force_reload)
        return int(_PREVIEWS[key].icon_id)
    except Exception:
        return 0


def rebuild_visible(settings=None, *, force_preview_reload=False):
    global _ENUM_CACHE, _VISIBLE_COUNT
    if not _INDEX_READY:
        return refresh_library(settings, force_reload=force_preview_reload)

    category_filter = category_filter_value(settings)
    search = str(getattr(settings, "user_profile_search", "") or "").strip() if settings else ""
    metadata_values = list(_METADATA_CACHE.values())

    # Search is deliberately global: while text is present, Category is ignored.
    if search:
        visible = [item for item in metadata_values if _matches_search(item, search)]
    else:
        visible = [item for item in metadata_values if _matches_category(item, category_filter)]
    visible.sort(key=lambda item: (str(item.get("name", "")).casefold(), str(item.get("identifier", "")).casefold()))
    _VISIBLE_COUNT = len(visible)

    _release_previews_except(item.get("preview_path", "") for item in visible)
    entries = []
    for metadata in visible:
        icon_id = _preview_icon(metadata, force_reload=force_preview_reload)
        profile_type = metadata["profile_type"]
        type_label = "Editable CPC" if profile_type == profile_presets.PROFILE_TYPE_PARAMETRIC else "Static Curve"
        category_label = metadata.get("category") or CATEGORY_UNCATEGORIZED_LABEL
        description = metadata.get("description") or f"{type_label} • {category_label}"
        entries.append((metadata["identifier"], metadata["name"], description, icon_id, len(entries)))

    if not entries:
        entries = [("__NONE__", "No User Profiles", "No profiles match the current browser", 0, 0)]
    _ENUM_CACHE = entries

    if settings is not None:
        valid = {item[0] for item in entries}
        selected = str(getattr(settings, "user_profile_selected", "") or "")
        if selected not in valid:
            try:
                settings.user_profile_selected = entries[0][0]
            except Exception:
                pass
    return entries


def refresh_library(settings=None, *, force_reload=False):
    global _METADATA_CACHE, _INDEX_LIBRARY_DIR, _INDEX_READY
    metadata_cache = {}
    discovered_categories = []
    directory = library_dir(settings)

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
        metadata_cache[metadata["identifier"]] = metadata
        if metadata.get("category"):
            discovered_categories.append(metadata["category"])

    _METADATA_CACHE = metadata_cache
    _INDEX_LIBRARY_DIR = directory
    _INDEX_READY = True
    _refresh_category_names(settings, discovered_categories)

    # Recover gracefully when the Scene stores a category from a different library.
    if settings is not None:
        current = category_filter_value(settings)
        valid_categories = {item[0] for item in _CATEGORY_ENUM_CACHE}
        if current not in valid_categories:
            try:
                settings.user_profile_category_filter = CATEGORY_ALL
            except Exception:
                pass
    return rebuild_visible(settings, force_preview_reload=force_reload)


def enum_items(self, context):
    settings = self
    _ensure_index(settings)
    if not _ENUM_CACHE:
        rebuild_visible(settings)
    return _ENUM_CACHE


def category_enum_items(self, context):
    settings = self
    _ensure_index(settings)
    if not _CATEGORY_ENUM_CACHE:
        _rebuild_category_enum(settings)
    return _CATEGORY_ENUM_CACHE


def on_category_filter_changed(settings, context):
    if _FILTER_UPDATE_GUARD:
        return
    _ensure_index(settings)
    rebuild_visible(settings)


def on_search_changed(settings, context):
    if _FILTER_UPDATE_GUARD:
        return
    _ensure_index(settings)
    rebuild_visible(settings)


def on_library_path_changed(settings, context):
    global _INDEX_READY, _INDEX_LIBRARY_DIR
    _INDEX_READY = False
    _INDEX_LIBRARY_DIR = ""
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
