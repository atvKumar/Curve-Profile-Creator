# Curve Profile Creator — Roadmap

## Current release — 0.4.2 Blender Extension Compliance

**Baseline:** validated CPC 0.4.1.

0.4.2 is packaging/storage compliance only.

### Scope
- preserve all 0.4.1 modelling and User Profile behavior;
- meet Blender Extension manifest length rules;
- use Blender's extension-owned writable user directory for the default profile library;
- preserve 0.4.1 default presets during the storage-path transition;
- keep `.cpcprofile` format v1 and recipe schema 11+ unchanged.

### Acceptance
1. CPC installs and reports version 0.4.2.
2. Existing 0.4.1 PARAMETRIC and STATIC presets load normally.
3. Presets in the former default library are copied to the new extension user directory without data loss.
4. Saving creates `.cpcprofile` and PNG files in the new default directory when no custom path is configured.
5. Custom User Profile library folders continue to work.
6. Dropdown and thumbnail selection remain synchronized.
7. Commit/Edit/Recommit, Rotation Offset, viewport editing, connectivity and sweeps regress cleanly.
8. The manifest passes Blender's extension validator.

## Next development

After 0.4.2, feature work should remain production-driven from the frozen 0.4.x architecture.
