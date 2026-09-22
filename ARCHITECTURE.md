# Curve Profile Creator — 0.4.4

## Architecture

### Product model

CPC is construction-first:

`geometry kernel → semantic role → packed component → complete profile → reusable preset → sweep`

The semantic recipe is authoritative for CPC-parametric reconstruction. The committed Blender Curve is the generated/editable profile representation.

### Persistent contract

Supported persistent data begins with the 0.4.x baseline:

- embedded recipe schema: **11+**;
- transform schema: **1**;
- per-component transform: `matrix_profile`;
- `.cpcprofile` preset format: **v1**;
- PARAMETRIC and STATIC User Profiles;
- geometry-authority hash for editable preset certification;
- complete-profile placement schema: **1**, stored as `cpc_profile_placement_json`.

0.4.4 adds canonical complete-profile placement and semantic interaction without advancing recipe, transform or preset schemas. The optional User Profile classification/source metadata introduced in 0.4.3 remains compatible.

### Complete-profile transform model

Commit establishes a normalized Profile Frame. Components are stored in profile space using Blender `mathutils.Matrix`:

`M_profile_component = inverse(M_profile_frame) @ M_component_world`

Restore/place uses the normalized component recipe plus one canonical complete-profile placement state:

`M_component_world = M_placement_frame @ M_profile_component`

`cpc_part_rotation` remains separate semantic user intent and is never flattened into recipe-derived base orientation.

The complete-profile placement state is authoritative for:

- Offset X;
- Offset Y;
- Rotation;
- Flip X;
- Flip Y;
- Uniform Scale.

Composition is fixed:

```text
canonical geometry
→ uniform scale
→ flip
→ rotation
→ profile-local offset
→ path / sweep frame
```

The canonical placement setter resolves every complete-profile placement path through the same state, making equivalent placement-time and post-placement edits geometrically identical.

Legacy positive uniform Object Scale can be absorbed through the supported profile-resize path. Non-uniform or non-positive raw scale is rejected rather than guessed.

### Semantic component editing

Construction component Rotation is stored in `cpc_part_rotation`.

Construction component Size is an action over semantic dimensional state, not a second persistent scale property.

The following interaction paths use the same semantic resize backend:

- placement mouse wheel;
- Blender `S`;
- selected-part panel Size;
- viewport HUD Size.

The resize factor is applied to length-valued construction parameters and packed-controller dimensions, then the component is regenerated. Dimensionless parameters remain unchanged.

Accepted or cancelled component Size gestures leave affected Blender Object Scale at `1,1,1`.

### Committed profile editing

For a committed complete profile:

- Blender `G` resolves to CPC Offset X/Y;
- Blender `R` resolves to CPC Rotation;
- Blender `S` resolves to CPC Uniform Scale;
- panel/HUD Rotation and Uniform Scale read and write the same placement state.

The overlay owns only transient gesture state. Authoritative values remain on CPC construction objects, packed controllers, or the committed profile placement record.

### Gesture modifier contract

Panel and HUD pointer gestures share one modifier model:

- `Shift`: one-tenth continuous sensitivity;
- `Ctrl`: snapped adjustment;
- `Shift + Ctrl`: one-tenth snap increment;
- typed values: exact.

Viewport draw handlers are created lazily when CPC viewport interaction begins.

### Connectivity model

Endpoint junctions and hosted midpoint attachments are semantic metadata.

During ordinary **Maintain Connected** edits, connected transforms traverse the existing junction/host graph. Physical coincidence alone never mutates that graph.

**Reconnect Touching Endpoints** is explicit. It scans the active build/Edit Active Profile session first, or selected eligible non-preview parametric CPC parts otherwise.

The reconnection planner:

1. evaluates eligible endpoints in world space;
2. clusters endpoints within `merge_tolerance`;
3. keeps a stable existing junction ID where possible;
4. creates a new ID when required;
5. updates affected endpoint/host metadata only.

It does not move geometry, rewrite placement matrices, regenerate curves or run automatically from a depsgraph callback.

### User Profile storage

`.cpcprofile` JSON remains authoritative. PNG previews are regenerable cache files.

The default writable library is:

```python
bpy.utils.extension_path_user(__package__, path="profiles", create=True)
```

A user-configured custom profile-library path takes precedence where applicable.

0.4.4 persists the custom path through CPC add-on preferences and synchronizes the existing scene/UI field with that preference. New scenes/files inherit the persistent path unless an explicit CPC scene path is already present.

### Library registry

The active library may contain:

```json
{
  "format": "CPC_LIBRARY",
  "format_version": 1,
  "categories": ["Cornice / Crown", "Custom Profiles"]
}
```

`cpc_library.json` stores only the ordered user-managed category vocabulary. It is not a preset database.

In 0.4.4 CPC initializes the registry when an active library is missing one. Categories discovered in copied-in presets remain visible even when absent from the registry.

Each `.cpcprofile` remains authoritative for its own:

- preset ID;
- geometry;
- recipe;
- PARAMETRIC/STATIC class;
- category;
- tags;
- source metadata.

### User Profile index

The 0.4.3 lightweight in-memory index remains in use. It stores metadata needed for browsing without keeping complete geometry/recipes resident.

Indexed fields include:

- identifier / preset ID;
- display name and description;
- profile type;
- category and tags;
- source metadata;
- preset path;
- preview path.

A full scan occurs when CPC first needs the library, the library path changes or Refresh is pressed. Save/Delete/Edit Info update the index directly.

### Browser filtering and previews

With empty Search:

`metadata index → Category filter → visible preset set`

With non-empty Search:

`metadata index → global search across every category → visible preset set`

Search temporarily ignores Category without overwriting the current category selection.

Preview loading occurs after filtering:

`visible preset set → load/generate matching PNG previews → dropdown + thumbnail view`

A missing visible PNG can be regenerated from authoritative preset geometry.

### Category management

Starter categories are defaults, not a fixed enum.

- `All Categories` is virtual/filter-only.
- `Uncategorized` is virtual/fallback-only.
- Category names are unique case-insensitively.
- Rename rewrites matching preset classification metadata plus the registry.
- Geometry, recipe, matrices, preset ID and thumbnail geometry are not rebuilt.
- Merge/delete semantics remain deferred.

### Preset classes

**PARAMETRIC** presets retain certified CPC recipe state and remain reconstructable when their authority hash is valid.

**STATIC** presets preserve normalized curve geometry without claiming semantic parametric reconstruction.

Metadata edits do not alter PARAMETRIC/STATIC provenance or authority hashing.

### Sweep Caps

For 2D CPC sweep/path Curves, the CPC Caps property is authoritative:

```text
Caps OFF → use_fill_caps = False → Fill Mode = None
Caps ON  → use_fill_caps = True  → Fill Mode = Both
```

The setting is applied to newly generated sweeps, existing 2D Curves receiving a CPC profile, and live Caps changes on active CPC sweeps.

3D paths retain Blender-supported bevel-cap behaviour without forcing a 2D Fill Mode identifier.

### Hosted Extensions baseline

0.4.2 remains the first hosted-release storage baseline. The default User Profiles library uses extension-owned user storage. CPC does not automatically migrate arbitrary earlier private-development folders.

The manifest declares `files` because CPC reads/writes User Profile JSON, `cpc_library.json`, PNG previews and optional custom profile-library folders.

CPC requires no network permission and no third-party image dependency.

### Runtime modules

- `primitive_geometry.py` / `compound_geometry.py`: analytic geometry.
- `primitives.py`: Blender Curve primitive creation/regeneration and endpoint semantics.
- `constructed_shapes.py`: canonical line-based point chains.
- `architectural_recipes.py` / `architectural_components.py`: packed component recipes and regeneration.
- `junctions.py` / `connected_transforms.py`: connectivity and hosted relationships.
- `endpoint_reconnect.py`: explicit touching-endpoint reconnection planning.
- `placement_parameters.py`: common semantic placement vocabulary.
- `semantic_gestures.py`: shared Rotation/Size gesture math.
- `viewport_overlay.py` / `viewport_semantics.py`: viewport presentation and semantic editing.
- `profile_transforms.py`: normalized Matrix transforms and complete-profile placement.
- `profile_presets.py`: pure preset validation/hashing/remapping.
- `user_profiles.py`: library paths, registry, indexing, categories, metadata, search and preview cache.
- `operators.py`, `properties.py`, `ui.py`: Blender interaction and presentation.
