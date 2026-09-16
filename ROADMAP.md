# Curve Profile Creator — Roadmap

## Current release — 0.4.3 User Profile Library Classification and Indexed Browsing

**Protected modelling baseline:** validated CPC 0.4.1. 0.4.2 storage/compliance behavior remains in place.

### Scope
- user-managed Category filter with `[ + ] [ Manage ]`;
- persistent category vocabulary through `cpc_library.json`;
- global Search across categories;
- optional Tags and Source metadata;
- Edit Info metadata-only workflow;
- lightweight in-memory library index;
- filtered/lazy PNG preview loading;
- no preset/recipe schema bump.

### Acceptance
1. Existing 0.4.2 PARAMETRIC and STATIC presets load unchanged.
2. Existing presets without classification metadata appear as `Uncategorized`.
3. Users can add and rename real categories; starter categories are not fixed.
4. `All Categories` and `Uncategorized` remain virtual/non-renameable.
5. Search is global across all categories and restores category browsing when cleared.
6. Save/Edit Info supports Category, Tags and optional Source metadata.
7. Category rename/Edit Info does not modify geometry, recipe, matrices, preset ID or thumbnail geometry.
8. Filtering uses the in-memory index rather than reparsing every preset.
9. Preview icons load only for the current visible result set.
10. Commit/Edit/Recommit, Rotation Offset, viewport editing, connectivity and sweeps regress cleanly.
11. Blender Extension packaging remains compliant.

## Next release — 0.4.4 WebP Thumbnail Storage

0.4.4 is reserved for preview-format work after 0.4.3 is validated in production:

- verify Blender preview/icon behavior with WebP on supported hosts;
- generate new previews as WebP with Blender-native APIs only;
- continue reading existing PNG previews;
- consider safe cache conversion/regeneration;
- keep `.cpcprofile` authoritative and format-agnostic through `preview.file`;
- no PIL/Pillow dependency.

## Later candidates

- batch migration/export of existing Blender curve/profile asset collections into `.cpcprofile` libraries;
- explicit category merge/delete only if production use justifies it;
- broader public profile-library tooling after metadata and licensing workflows are proven.
