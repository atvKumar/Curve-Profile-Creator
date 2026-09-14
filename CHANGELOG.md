# Curve Profile Creator — Changelog

## 0.4.2 — Blender Extension Compliance

- Shortens the manifest tagline to Blender's 64-character maximum.
- Shortens the `files` permission explanation to Blender's 64-character maximum.
- Moves the default User Profiles directory to `bpy.utils.extension_path_user(__package__, path="profiles", create=True)`.
- Treats 0.4.2 as the first hosted-release storage baseline and performs no automatic migration from earlier private-development library locations.
- Updates the User Profiles UI hint to describe Blender extension user storage.
- Keeps the `files` permission because CPC reads/writes presets, thumbnails and optional custom library folders.
- Adds the public GitHub Issues URL through the manifest `support` field.
- Defers viewport draw-handler creation until a CPC operator or relevant viewport property is explicitly used; extension registration itself installs no draw handlers.
- No intended geometry, editing, preset-format or sweep behavior change from validated 0.4.1.

## 0.4.1 — Frozen Baseline Cleanup

- Declared 0.4.0 the persistence floor and removed older migration/compatibility machinery.
- Retained recipe schema 11+, preset format v1, normalized Matrix transforms, User Profiles and all validated modelling behavior.
