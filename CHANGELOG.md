# Curve Profile Creator — Changelog

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
- Keeps PNG thumbnail generation in 0.4.3; WebP is reserved for 0.4.4.
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
- Retained recipe schema 11+, preset format v1, normalized Matrix transforms, User Profiles, and all validated modelling behavior.
