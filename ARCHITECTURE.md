# Curve Profile Creator — Architecture 0.4.4

## 1. Product model

CPC is construction-first:

`geometry kernel -> semantic role -> packed component -> complete profile -> reusable preset -> sweep`

The semantic recipe is authoritative for CPC-parametric reconstruction. The committed Blender Curve is the generated/editable profile representation.

## 2. Persistent contract

Supported persistent data begins with the 0.4.x baseline:

- embedded recipe schema: **11+**;
- transform schema: **1**;
- per-component transform: `matrix_profile`;
- `.cpcprofile` preset format: **v1**;
- PARAMETRIC and STATIC user profiles;
- geometry-authority hash for editable preset certification;
- complete-profile placement schema: **1**, stored as `cpc_profile_placement_json`.

0.4.4 adds placement state and semantic interaction without advancing recipe,
transform, or preset schemas. 0.4.3 library metadata remains optional.

## 3. Transform model

Commit establishes a normalized Profile Frame. Components are stored in profile space using Blender `mathutils.Matrix`:

`M_profile_component = inverse(M_profile_frame) @ M_component_world`

Restore/place uses the normalized component recipe and one canonical complete-profile placement state:

`M_component_world = M_placement_frame @ M_profile_component`

`cpc_part_rotation` remains separate semantic user intent and is never flattened into recipe-derived base orientation.

The complete-profile placement state is authoritative for Offset X/Y, Rotation,
Flip X/Y and Uniform Scale. Its composition order is fixed:

```text
canonical geometry -> uniform scale -> flip -> rotation -> profile-local offset -> path/sweep frame
```

The canonical placement setter resolves all channels from one state, so a
placement-time edit and the equivalent post-placement edit produce the same
matrix. Legacy positive uniform Object Scale is absorbed through the existing
profile-resize migration path; non-uniform or non-positive raw scale is rejected
instead of guessed.

## 4. Semantic editing and presentation

Component Rotation is stored in `cpc_part_rotation`. Component Size is an
action backed by the existing semantic dimension/packed-controller state, not a
second persistent scale property. Wheel, Blender S, the selected-part panel,
and the viewport HUD all use the same gesture backend. Accepted or cancelled
component Size gestures leave every affected Object Scale at `1,1,1`.

Committed-profile HUD Rotation and Uniform Scale read and write the canonical
placement state. Panel and HUD pointer gestures share the modifier contract:
Shift is one-tenth continuous sensitivity, Ctrl snaps, Shift+Ctrl uses one-tenth
snap increments, and typed values remain exact. The overlay owns only transient
gesture state; authoritative values remain on CPC objects, packed controllers,
or the committed profile placement record. Viewport draw handlers are created
lazily when explicit CPC viewport interaction begins.

## 5. Connectivity and explicit reconnection

Endpoint junctions and hosted midpoint attachments are semantic metadata. During
ordinary Maintain Connected edits, connected transforms traverse the existing
junction/host graph. Physical coincidence alone never mutates that graph.

**Reconnect Touching Endpoints** is an explicit operator. It scans the active
build/Edit Active Profile session first, or selected non-preview parametric CPC
parts otherwise. A pure world-space planner clusters endpoints within
`merge_tolerance`, keeps a stable existing ID (or creates one), and the Blender
adapter writes only endpoint IDs and affected hosted metadata. It never moves
geometry, rewrites matrices, regenerates curves, or runs from a depsgraph
callback.

## 6. User Profiles storage

`.cpcprofile` JSON is authoritative; PNG previews are regenerable cache files.

The default writable library is:

```python
bpy.utils.extension_path_user(__package__, path="profiles", create=True)
```

A user-configured custom profile-library path takes precedence.

### Library configuration

0.4.3 may create `cpc_library.json` in the active library root:

```json
{
  "format": "CPC_LIBRARY",
  "format_version": 1,
  "categories": ["Cornice / Crown", "Custom Profiles"]
}
```

This file stores only the ordered user-managed category vocabulary. It is not a preset database. Each `.cpcprofile` remains authoritative for its own category assignment, geometry and recipe.

Categories discovered in copied-in preset files are exposed even when they are absent from the registry. Empty user-created categories remain possible because the registry can store them independently of presets.

## 7. 0.4.3 library index

`user_profiles.py` maintains a lightweight in-memory index containing only:

- identifier / preset ID;
- display name and description;
- profile type;
- category and tags;
- source metadata;
- preset path and preview path.

Geometry snapshots and PARAMETRIC recipes are not retained in this index. They are loaded from the selected `.cpcprofile` only when required.

A full index scan occurs when CPC first needs the active library, the library path changes, or Refresh is pressed. Save/Delete/Edit Info update the index directly.

### Browser filtering

With empty Search:

`metadata index -> Category filter -> visible preset set`

With non-empty Search:

`metadata index -> global search across every category -> visible preset set`

Search therefore temporarily ignores the selected Category but does not overwrite it. Clearing Search returns to that Category.

### Preview loading

Preview loading is downstream of filtering:

`visible preset set -> load/generate only matching PNG previews -> dropdown + template_icon_view`

Preview icons excluded by the current result set are released from CPC's preview collection. A missing PNG is regenerated from the authoritative preset geometry only when needed for a visible result.

## 8. Category management

Starter categories are UI defaults, not a fixed enum. Users may add and rename real categories.

- `All Categories` is virtual/filter-only.
- `Uncategorized` is virtual/fallback-only.
- Category names are unique case-insensitively.
- Rename rewrites only matching preset classification metadata plus the category registry.
- Geometry, recipe, matrices, preset ID and thumbnail are not regenerated by category rename.
- Merge/delete semantics are deferred.

## 9. Preset metadata

Optional v1 fields used by 0.4.3:

```json
"classification": {
  "category": "Cornice / Crown",
  "tags": ["georgian", "classical"]
},
"source": {
  "collection": "Reference Library",
  "reference": "CRN-001",
  "url": "",
  "license": ""
}
```

Metadata edits do not alter PARAMETRIC/STATIC provenance or authority hashing.

## 10. 0.4.2 hosted storage baseline

0.4.2 is the first hosted-release storage baseline. The default User Profiles library uses extension-owned user storage. CPC performs no automatic migration from earlier private-development library locations; users may select a custom library path when they need to access an existing library.

## 11. Permissions

The manifest declares `files` because CPC reads/writes User Profile JSON, `cpc_library.json`, PNG preview files and optional custom profile-library folders. CPC requires no network permission and no third-party image dependency.

## 12. Runtime modules

- `primitive_geometry.py` / `compound_geometry.py`: analytic geometry.
- `primitives.py`: Blender Curve primitive creation/regeneration and endpoint semantics.
- `constructed_shapes.py`: canonical line-based point chains.
- `architectural_recipes.py` / `architectural_components.py`: packed component recipes and regeneration.
- `junctions.py` / `connected_transforms.py`: connectivity and hosted relationships.
- `placement_parameters.py`: common semantic placement vocabulary.
- `viewport_overlay.py` / `viewport_semantics.py`: viewport presentation and semantic editing.
- `profile_transforms.py`: normalized Matrix transforms.
- `profile_presets.py`: pure preset validation/hashing/remapping.
- `user_profiles.py`: library indexing, categories, metadata, search and preview cache.
- `operators.py`, `properties.py`, `ui.py`: interaction and presentation.
