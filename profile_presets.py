"""Pure data helpers for CPC user profile presets.

This module deliberately has no Blender dependency. CPC 0.4.0+ uses it for the
portable ``.cpcprofile`` JSON contract, deterministic geometry hashing and
identity remapping when one reusable PARAMETRIC preset is instantiated more
than once.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import uuid
from typing import Iterable, Mapping


PRESET_FORMAT = "CPC_PROFILE"
PRESET_FORMAT_VERSION = 1
PROFILE_TYPE_PARAMETRIC = "PARAMETRIC"
PROFILE_TYPE_STATIC = "STATIC"
MIN_PARAMETRIC_RECIPE_SCHEMA = 11


class PresetFormatError(ValueError):
    pass


def canonical_json_bytes(value) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def stable_digest(value) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def safe_stem(name: str, fallback: str = "profile") -> str:
    text = str(name or "").strip()
    text = re.sub(r"[\\/:*?\"<>|]+", "_", text)
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"[^0-9A-Za-z._-]+", "_", text)
    text = text.strip("._-")
    return (text or fallback)[:96]


def new_preset_id() -> str:
    return f"preset-{uuid.uuid4()}"


def _new_component_id() -> str:
    return f"cpc-{uuid.uuid4()}"


def _new_junction_id() -> str:
    return f"junction-{uuid.uuid4()}"


def _new_arch_instance_id() -> str:
    return f"arch-{uuid.uuid4()}"


def remap_recipe_identities(records: Iterable[Mapping]) -> list[dict]:
    """Clone a reusable recipe with fresh per-instance identities.

    Component IDs, endpoint junction IDs, hosted attachment host IDs and packed
    Architectural/Constructed instance IDs are remapped consistently. Recipe
    *type* identifiers such as ``OVOLO_FILLETS`` remain unchanged.
    """
    source_records = [copy.deepcopy(dict(record)) for record in records]

    component_map = {}
    junction_map = {}
    arch_instance_map = {}

    for record in source_records:
        old = str(record.get("id", "") or "").strip()
        if old:
            component_map.setdefault(old, _new_component_id())
        junctions = record.get("junctions")
        if isinstance(junctions, dict):
            for key in ("start", "end"):
                old_junction = str(junctions.get(key, "") or "").strip()
                if old_junction:
                    junction_map.setdefault(old_junction, _new_junction_id())
        arch = record.get("architectural_component")
        if isinstance(arch, dict):
            old_instance = str(arch.get("instance_id", "") or "").strip()
            if old_instance:
                arch_instance_map.setdefault(old_instance, _new_arch_instance_id())

    for record in source_records:
        old = str(record.get("id", "") or "").strip()
        if old:
            record["id"] = component_map[old]

        junctions = record.get("junctions")
        if isinstance(junctions, dict):
            for key in ("start", "end"):
                old_junction = str(junctions.get(key, "") or "").strip()
                if old_junction in junction_map:
                    junctions[key] = junction_map[old_junction]

        hosted = record.get("hosted_attachments")
        if isinstance(hosted, dict):
            for endpoint in ("start", "end"):
                attachment = hosted.get(endpoint)
                if not isinstance(attachment, dict):
                    continue
                host_id = str(attachment.get("host_component_id", "") or "").strip()
                if host_id in component_map:
                    attachment["host_component_id"] = component_map[host_id]

        arch = record.get("architectural_component")
        if isinstance(arch, dict):
            old_instance = str(arch.get("instance_id", "") or "").strip()
            if old_instance in arch_instance_map:
                arch["instance_id"] = arch_instance_map[old_instance]

    return source_records


def validate_preset_document(data: Mapping) -> dict:
    if not isinstance(data, Mapping):
        raise PresetFormatError("Preset root must be a JSON object")
    result = dict(data)
    if result.get("format") != PRESET_FORMAT:
        raise PresetFormatError("Not a Curve Profile Creator preset")
    version = int(result.get("format_version", 0))
    if version != PRESET_FORMAT_VERSION:
        raise PresetFormatError(f"Unsupported CPC preset format version {version}")
    profile_type = str(result.get("profile_type", "") or "").upper()
    if profile_type not in {PROFILE_TYPE_PARAMETRIC, PROFILE_TYPE_STATIC}:
        raise PresetFormatError("Preset profile_type must be PARAMETRIC or STATIC")
    if not isinstance(result.get("geometry"), Mapping):
        raise PresetFormatError("Preset has no geometry snapshot")
    if profile_type == PROFILE_TYPE_PARAMETRIC:
        recipe = result.get("recipe")
        if not isinstance(recipe, Mapping) or not isinstance(recipe.get("records"), list):
            raise PresetFormatError("PARAMETRIC preset has no reusable CPC recipe")
        schema_version = int(recipe.get("schema_version", 0))
        if schema_version < MIN_PARAMETRIC_RECIPE_SCHEMA:
            raise PresetFormatError(
                f"PARAMETRIC preset recipe schema {schema_version} predates the 0.4.0 baseline"
            )
        for record in recipe["records"]:
            if not isinstance(record, Mapping):
                raise PresetFormatError("PARAMETRIC recipe record must be a JSON object")
            if not str(record.get("primitive_id", "") or "").strip():
                raise PresetFormatError("PARAMETRIC recipe record has no primitive_id")
            if record.get("matrix_profile") is None:
                raise PresetFormatError("PARAMETRIC recipe record has no matrix_profile")
    return result
