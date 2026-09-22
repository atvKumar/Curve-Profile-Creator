# Curve Profile Creator — Roadmap

## Current release — 0.4.4 Transform and Connectivity

The 0.4.4 milestone closes issues #2 through #10 while preserving the
recipe/preset compatibility floor and the validated modelling behavior from
0.4.1–0.4.3.

### Scope

- canonical complete-profile placement state for Offset X/Y, Rotation, Flip X/Y and Uniform Scale;
- equivalent placement-time and post-placement transform results;
- semantic Blender G/R/S routing for profiles and construction parts;
- component wheel/S/panel/HUD Size with neutral Object Scale;
- committed-profile HUD Rotation and Uniform Scale with shared Shift/Ctrl gestures;
- explicit metadata-only Reconnect Touching Endpoints;
- persistent custom User Profile paths and immediate `cpc_library.json` initialization;
- authoritative 2D Sweep Caps/Fill Mode behavior and retained 3D sweep support;
- clean extension packaging that excludes source tests and development artifacts.

### Acceptance

1. CRN-4000 through CRN-4004 pass the versioned Blender production matrix.
2. Existing PARAMETRIC and STATIC presets load with recipe schema 11+, transform schema 1 and `.cpcprofile` format v1.
3. Edit Active Profile/Recommit preserves committed object identity and linked Sweep bevel objects.
4. Component and profile semantic edits do not leave native Object Scale as a second size authority.
5. Reconnect repairs only touching endpoint metadata and Maintain Connected follows the rebuilt chain.
6. User library path, category registry and PNG preview behavior survive restart and new-file checks.
7. The install archive contains no tests, bytecode, Git metadata, planning documents or nested archives.

## Later candidates

- WebP preview storage using Blender-native APIs while continuing to read existing PNG previews;
- batch migration/export of existing Blender curve/profile asset collections into `.cpcprofile` libraries;
- explicit category merge/delete only if production use justifies it;
- broader public profile-library tooling after metadata and licensing workflows are proven.
