# Curve Profile Creator — Current Design Decisions 0.4.2

## DD-001 — Construction first
CPC is primarily a profile construction/adaptation system rather than a catalogue.

## DD-002 — Small procedural kernel
Canonical geometry is generated mathematically; architectural names do not automatically justify new kernels.

## DD-003 — Recipe authority
Semantic recipe state is authoritative for parametric reconstruction. Manual low-level curve edits do not silently rewrite semantic parameters.

## DD-004 — Preserve anchors and directed connectivity
Regeneration preserves the chosen Edit Anchor and propagates endpoint-frame changes through CPC relationships without becoming a general CAD constraint solver.

## DD-005 — Recommit in place
The committed profile object retains identity so existing sweep bevel-object references survive recommit.

## DD-006 — Constructed orientations derive from points
Line-built packed shapes derive base orientation from endpoint vectors, never fragile stored `-90/180` constants.

## DD-007 — Rotation Offset is separate semantic state
Recipe/base orientation and user `cpc_part_rotation` are distinct and must remain so through regeneration, commit, presets and reload.

## DD-008 — Profile transforms use Blender matrices
Normalized recipe transforms use `mathutils.Matrix` and a reusable Profile Frame.

## DD-009 — PARAMETRIC and STATIC are distinct preset classes
Certified CPC construction may remain editable; arbitrary/manually changed curves are preserved as STATIC without false semantic editability.

## DD-010 — JSON is authoritative; PNG is cache
`.cpcprofile` is the portable profile document. PNG thumbnails are generated automatically and can be regenerated.

## DD-011 — No Pillow dependency
Preview generation uses CPC geometry plus Blender's Image API.

## DD-012 — Extension-owned default storage
Default user data belongs in Blender's extension user directory via `bpy.utils.extension_path_user()`, not in the installed extension directory or a generic global data-files namespace. Custom user-selected library locations remain supported.

## DD-013 — 0.4.x is the supported persistence floor
Recipe schema 11+ and preset format v1 are the minimum supported persistent contracts; pre-0.4.0 migration machinery remains out of the runtime.
