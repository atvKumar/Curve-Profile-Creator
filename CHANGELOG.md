# Curve Profile Creator — Changelog

## 0.4.4 — Transform and Connectivity

- Adds one canonical complete-profile placement state for Offset X/Y, Rotation, Flip X/Y and Uniform Scale, with placement-time/post-placement equivalence.
- Routes semantic Blender G/R/S gestures through CPC placement or construction dimensions instead of leaving native transforms as a second authority.
- Adds component wheel/S/panel/HUD Size gestures with Shift fine sensitivity, Ctrl snapping, Shift+Ctrl fine snapping, exact typed values, and Object Scale normalization.
- Adds committed-profile HUD Rotation and Uniform Scale controls using the canonical placement setter.
- Adds explicit **Reconnect Touching Endpoints**, scoped to the active build/edit session or selected eligible parts and limited to metadata writes.
- Retains persistent custom User Profile library paths and immediate `cpc_library.json` initialization for new library roots.
- Makes 2D Sweep Caps and Fill Mode authoritative and live; 3D paths retain Blender's supported cap behavior.
- Preserves `.cpcprofile` format v1, recipe schema 11+, transform schema 1, PARAMETRIC/STATIC compatibility, packed restoration, profile normalization and Sweep bevel linkage.
- Release archives exclude tests, planning documents, bytecode, Git metadata and nested ZIP files.

## 0.4.3 — User Profile Library Classification and Indexed Browsing

- Adds user-managed **Category** filtering above the existing User Profile dropdown/thumbnail selector.
- Adds **[ + ]** category creation and **Manage** category rename.
- Adds optional `cpc_library.json` library configuration so empty, custom, and renamed categories persist independently of preset files.
- Keeps starter architectural categories as editable defaults rather than a fixed taxonomy.
- Adds **global Search across all categories**; while Search contains text, Category is temporarily ignored.
- Adds optional `.cpcprofile` metadata for category, tags, and source provenance while retaining preset format v1.
- Adds **Edit Info** for metadata-only updates without changing geometry, recipe, matrices, preset ID, or preview geometry.
- Separates the library metadata index from preview loading so only the current filtered result set loads PNG icons.
- Existing 0.4.0–0.4.2 presets remain valid and appear under `Uncategorized` until classified.
- Keeps PNG thumbnail generation; WebP preview storage remains a later candidate.
- **Edit Active Profile** now prefers the directly selected committed CPC profile and synchronizes the Active Profile pointer automatically.
- Starting profile editing now activates viewport draw handlers lazily when Viewport Guides is enabled, so reopened `.blend` files do not require cycling the toggle off/on.
- No intended modelling, transform, connectivity, Commit/Recommit, or sweep behavior changes.

## 0.4.2 — First Extensions Platform Release

- Added packaging and storage support for the hosted Extensions platform.
- Moved the default User Profiles library to extension-managed user storage.
- Added the public GitHub Issues URL through the manifest `support` field.
- Deferred viewport draw-handler creation until CPC viewport interaction is explicitly used.
- Removed automatic migration from earlier private-development profile locations.
- Updated manifest metadata and permission descriptions for platform requirements.
- No intended geometry, editing, preset-format, or sweep behavior changes from validated 0.4.1.

## 0.4.1 — Frozen Baseline Cleanup

- Declared 0.4.0 the persistence floor and removed older migration/compatibility machinery.
- Retained recipe schema 11+, preset format v1, normalized Matrix transforms, User Profiles and all validated modelling behavior.
