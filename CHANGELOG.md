# Curve Profile Creator — Changelog

## Curve Profile Creator — 0.4.7

### Custom Bézier Creation

- Adds **Add Custom Bézier** for direct CPC → native Blender Bézier continuation.
- Creates a native two-point Bézier seed from the endpoint opposite the selected CPC part's Edit Anchor.
- Places P0 on the CPC continuation endpoint and uses it as the custom section local origin.
- Places P1 along the source endpoint's outward tangent.
- Initializes both points with explicit collinear Blender **ALIGNED** handles.
- Enters native Blender Edit Mode when context permits so the user can immediately reshape/extrude the custom section.
- Keeps ALIGNED as a creation default only; Commit/Recommit preserves the actual later-edited handle coordinates and types.
- Prevents silent endpoint branching when the chosen continuation endpoint is already semantically connected downstream.
- Retains **Adopt Selected Blender Bézier** and reuses the same `CUSTOM_BEZIER` persistence model introduced in 0.4.6.
- Validated CPC → Bézier → CPC chaining, Edit Anchor reversal, downstream CPC continuation, Maintain Connected, Commit/Edit/Recommit and User Profile compatibility.
- Automated source gate: **55/55 tests passed**.

## Curve Profile Creator — 0.4.6

### Native Blender Bézier Integration

- Adds **Adopt Selected Blender Bézier** for bringing an existing native Blender Bézier Curve into a CPC construction chain.
- Stores native control-point coordinates, left/right handles, Blender handle types, radius, tilt, soft-body weight and spline resolution in the CPC recipe.
- Uses the first Bézier point as the custom section local origin and the last point as the exit anchor.
- Preserves native freeform editability across Commit → Edit Active Profile → Recommit.
- Integrates custom sections with CPC endpoint junctions, Maintain Connected and connected Move/Rotate behaviour.
- Preserves the user-drawn curve during adoption by rebasing the Curve datablock rigidly rather than moving constrained handles individually.
- Supports Free, Vector, Aligned, Auto and Auto Clamped native Blender handle types.
- Updates PARAMETRIC preset validation so `CUSTOM_BEZIER` recipe members remain indexable after library refresh/restart without requiring a CPC `primitive_id`.
- Retains `.cpcprofile` v1, recipe schema 11+ and transform schema 1.
- Existing 0.4.4 User Profiles remain compatible.

## Curve Profile Creator — 0.4.4

### Transform and Connectivity

- Adds one canonical complete-profile placement state for Offset X/Y, Rotation, Flip X/Y and Uniform Scale.
- Makes equivalent placement-time and post-placement transforms resolve to the same final geometry.
- Routes supported Blender `G`, `R` and `S` interactions through CPC semantic placement or construction dimensions instead of leaving raw object transforms as a second authority.
- Adds semantic component Size through placement wheel, Blender `S`, selected-part panel and viewport HUD.
- Keeps resized CPC construction components normalized at Object Scale `1,1,1`.
- Adds shared Rotation/Size pointer modifiers: Shift fine control, Ctrl snapping and Shift+Ctrl fine snapping; typed values remain exact.
- Adds committed-profile HUD Rotation and Uniform Scale controls using the canonical placement setter.
- Adds explicit **Reconnect Touching Endpoints** for metadata-only CPC junction repair.
- Persists custom User Profile library paths through CPC preferences and initializes `cpc_library.json` immediately for a newly activated library root.
- Makes 2D Sweep Caps authoritative over Fill Mode: Caps OFF uses None, Caps ON uses Both, with live updates.
- Retains Blender-supported 3D bevel-cap behaviour without forcing 2D Fill Mode identifiers.
- Preserves `.cpcprofile` format v1, recipe schema 11+, transform schema 1, PARAMETRIC/STATIC compatibility, packed restoration, profile normalization and Sweep bevel linkage.
- Release archives exclude tests, planning documents, bytecode, Git metadata and nested ZIP files.
- Automated release gate: **52/52 tests passed**.
- Production validation: CRN-4000 through CRN-4004 passed the 0.4.4 transform/connectivity matrix.

## Curve Profile Creator — 0.4.3

### User Profile Library Classification and Indexed Browsing

- Adds user-managed **Category** filtering above the existing User Profile dropdown/thumbnail selector.
- Adds **[ + ]** category creation and **Manage** category rename.
- Adds optional `cpc_library.json` library configuration so empty, custom and renamed categories persist independently of preset files.
- Keeps starter architectural categories as editable defaults rather than a fixed taxonomy.
- Adds **global Search across all categories**; while Search contains text, Category is temporarily ignored.
- Adds optional `.cpcprofile` metadata for category, tags and source provenance while retaining preset format v1.
- Adds **Edit Info** for metadata-only updates without changing geometry, recipe, matrices, preset ID or preview geometry.
- Separates the metadata index from preview loading so only the current filtered result set loads PNG icons.
- Existing 0.4.0–0.4.2 presets remain valid and appear under `Uncategorized` until classified.
- Keeps PNG thumbnail generation.
- **Edit Active Profile** prefers the directly selected committed CPC profile and synchronizes the Active Profile pointer automatically.
- Starting profile editing activates viewport draw handlers lazily when Viewport Guides is enabled.
- No intended modelling, transform, connectivity, Commit/Recommit or Sweep behaviour changes.

## Curve Profile Creator — 0.4.2

### First Extensions Platform Release

- Adds packaging and storage support for the hosted Blender Extensions platform.
- Moves the default User Profiles library to extension-managed user storage.
- Adds the public GitHub Issues URL through the manifest `support` field.
- Defers viewport draw-handler creation until CPC viewport interaction is explicitly used.
- Removes automatic migration from earlier private-development profile locations.
- Updates manifest metadata and permission descriptions for platform requirements.
- No intended geometry, editing, preset-format or Sweep behaviour changes from validated 0.4.1.

## Curve Profile Creator — 0.4.1

### Frozen Baseline Cleanup

- Declares 0.4.0 the persistence floor and removes older migration/compatibility machinery.
- Retains recipe schema 11+, preset format v1, normalized Matrix transforms, User Profiles and validated modelling behaviour.
