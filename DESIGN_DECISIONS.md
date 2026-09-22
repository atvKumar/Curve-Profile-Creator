# Curve Profile Creator — 0.4.4

## Design Decisions

### DD-001 — Construction first
CPC is primarily a profile construction/adaptation system rather than a catalogue.

### DD-002 — Small procedural kernel
Canonical geometry is generated mathematically; architectural names do not automatically justify new geometry kernels.

### DD-003 — Recipe authority
Semantic recipe state is authoritative for parametric reconstruction. Manual low-level curve edits do not silently rewrite semantic parameters.

### DD-004 — Preserve anchors and directed connectivity
Regeneration preserves the chosen Edit Anchor and propagates endpoint-frame changes through CPC relationships without becoming a general CAD constraint solver.

### DD-005 — Recommit in place
The committed profile object retains identity so existing Sweep bevel-object references survive Recommit.

### DD-006 — Constructed orientations derive from points
Line-built packed shapes derive base orientation from endpoint vectors, never fragile stored angle constants.

### DD-007 — Rotation Offset is separate semantic state
Recipe/base orientation and user `cpc_part_rotation` are distinct and must remain separate through regeneration, Commit, presets and reload.

### DD-008 — Profile transforms use Blender matrices
Normalized recipe transforms use `mathutils.Matrix` and a reusable Profile Frame.

### DD-009 — PARAMETRIC and STATIC are distinct preset classes
Certified CPC construction may remain editable; arbitrary or manually changed curves are preserved as STATIC without false semantic editability.

### DD-010 — JSON is authoritative; preview image is cache
`.cpcprofile` is the portable profile document. Preview images are generated automatically and may be regenerated. CPC 0.4.4 continues to use PNG previews; WebP remains a later candidate.

### DD-011 — No Pillow dependency
Preview generation uses CPC geometry plus Blender's Image API.

### DD-012 — Extension-owned default storage
Default user data belongs in Blender's extension user directory via `bpy.utils.extension_path_user()`. Custom user-selected library locations remain supported.

### DD-013 — 0.4.x is the supported persistence floor
Recipe schema 11+ and preset format v1 are the minimum supported persistent contracts; pre-0.4.0 migration machinery remains outside the runtime.

### DD-014 — Categories are user-managed library data
Starter categories are conveniences, not a fixed enum. `cpc_library.json` stores persistent category vocabulary while each preset stores its own assignment.

### DD-015 — Category + Tags, not a dedicated Style hierarchy
Descriptive style terms such as Georgian, Federal or Classical belong naturally in Tags and global Search unless production use later proves a separate hierarchy is necessary.

### DD-016 — Search is global
Non-empty User Profile Search ignores the Category filter and searches the complete in-memory library index. Clearing Search restores category browsing.

### DD-017 — Metadata index before previews
Library JSON is scanned into a lightweight in-memory metadata index. Blender preview icons are loaded only for presets visible under the current Category/global Search result set.

### DD-018 — Metadata edits never rebuild profile geometry
Edit Info and category rename modify only optional descriptive, classification and source fields. Geometry, recipe, matrices, preset identity, PARAMETRIC authority and preview geometry remain untouched.

### DD-019 — Complete profiles have one placement authority
Offset X/Y, Rotation, Flip X/Y and Uniform Scale belong to one canonical complete-profile placement state.

Equivalent user interactions must resolve through the same placement state rather than accumulating independent Blender transforms.

### DD-020 — Interaction order must not become transform order
Applying a CPC transform before placement and applying the equivalent transform after placement must produce the same final geometry.

The fixed conceptual composition is:

```text
canonical geometry
→ uniform scale
→ flip
→ rotation
→ profile-local offset
→ path / sweep frame
```

### DD-021 — Blender G/R/S are semantic CPC interaction paths
Supported Blender Move, Rotate and Scale operations are interpreted as edits to CPC semantic state.

For a committed profile:

- `G` updates profile-local Offset X/Y;
- `R` updates CPC Rotation;
- `S` updates CPC Uniform Scale.

Raw object transforms must not become a second persistent authority.

### DD-022 — Component Size belongs to construction dimensions
Parametric component size is represented by semantic dimensional parameters, not accumulated Object Scale.

Uniform component resizing scales relevant length-valued parameters, regenerates geometry and returns Object Scale to `1,1,1`.

Dimensionless parameters such as Bias, Fullness, flips and construction mode remain unchanged.

### DD-023 — Complete-profile Uniform Scale and component Size are different concepts
A committed profile's Uniform Scale is placement-level state.

A construction component's Size is a semantic reconstruction operation over its dimensional parameters.

The UI should preserve that distinction explicitly.

### DD-024 — Panel, HUD and viewport gestures share one semantic backend
Equivalent Rotation and Size interactions should produce equivalent CPC state regardless of whether they originate from the selected-part panel, viewport HUD, placement wheel or supported Blender transform gestures.

Shift/Ctrl modifiers alter gesture sensitivity/snapping only; typed values remain exact.

### DD-025 — Physical coincidence does not imply semantic connectivity
Two endpoints occupying the same position are not automatically considered connected.

Automatic proximity-based graph mutation would risk joining intentionally separate geometry.

### DD-026 — Reconnection is explicit and metadata-only
**Reconnect Touching Endpoints** repairs semantic junction relationships only when explicitly invoked.

It may update endpoint and affected hosted metadata, but must not move geometry, rewrite profile placement or regenerate shapes merely to establish the junction.

### DD-027 — Custom library location is persistent CPC configuration
A user-selected external User Profile library should persist across Blender restarts and new files through CPC preferences while retaining the existing scene/UI surface.

An explicit scene path may override inherited preference state.

### DD-028 — Library registry should exist when the library becomes active
If the active User Profile library lacks `cpc_library.json`, CPC initializes one using the current ordered category vocabulary.

The registry remains category vocabulary only, never an authoritative preset database.

### DD-029 — CPC Caps is authoritative for 2D sweep fill
For 2D CPC sweep/path curves:

```text
Caps OFF → Fill Mode None
Caps ON  → Fill Mode Both
```

The same rule applies at creation, when applying a profile to an existing Curve, and during live Caps changes.

3D paths retain Blender-supported bevel-cap behaviour without forcing 2D Fill Mode values.
