# Curve Profile Creator — Current Design Decisions 0.4.3

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

## DD-010 — JSON is authoritative; preview image is cache
`.cpcprofile` is the portable profile document. Preview images are generated automatically and can be regenerated. 0.4.3 writes PNG; WebP is reserved for 0.4.4.

## DD-011 — No Pillow dependency
Preview generation uses CPC geometry plus Blender's Image API.

## DD-012 — Extension-owned default storage
Default user data belongs in Blender's extension user directory via `bpy.utils.extension_path_user()`. Custom user-selected library locations remain supported.

## DD-013 — 0.4.x is the supported persistence floor
Recipe schema 11+ and preset format v1 are the minimum supported persistent contracts; pre-0.4.0 migration machinery remains out of the runtime.

## DD-014 — Categories are user-managed library data
Starter categories are conveniences, not a fixed enum. `cpc_library.json` stores persistent category vocabulary while each preset stores its own assignment.

## DD-015 — Category + Tags, not Category + Style hierarchy
0.4.3 intentionally has no dedicated Style filter. Descriptive style terms such as Georgian/Federal/Classical belong naturally in Tags and global Search unless production use later proves a hierarchy is necessary.

## DD-016 — Search is global
Non-empty User Profile Search ignores the Category filter and searches the complete in-memory library index. Clearing Search restores category browsing.

## DD-017 — Metadata index before previews
Library JSON is scanned into a lightweight in-memory metadata index. Blender preview icons are loaded only for presets visible under the current Category/global Search result set.

## DD-018 — Metadata edits never rebuild profile geometry
Edit Info and category rename modify only optional descriptive/classification/source fields. Geometry, recipe, matrices, preset identity, PARAMETRIC authority and preview geometry remain untouched.
