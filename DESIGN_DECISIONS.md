# Curve Profile Creator — 0.4.6 Development

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

### DD-030 — 0.4.5 is an abandoned experiment
The edit-point / S-curve direction explored for 0.4.5 is not part of the supported development lineage.

0.4.6 branches from the validated 0.4.4 baseline rather than inheriting 0.4.5 experimental work.

Any preserved 0.4.5 code is archive/history only and must not be treated as a supported release.

### DD-031 — Custom Bézier is an extension section, not a replacement component system
A native Blender Bézier section may extend a CPC-built chain where a semantic CPC component is not appropriate.

The feature is specifically intended to bridge from structured CPC construction into freeform Blender curve modelling and back into the CPC assembly.

### DD-032 — Blender owns internal Bézier editing; CPC owns assembly semantics
CPC must preserve native Bézier control points, handles and handle types.

CPC should not implement a competing Bézier solver or silently sample the section into static point geometry.

CPC owns the custom section's entry/exit anchors, placement, connectivity, Commit/Recommit integration and assembly-level transforms.

### DD-033 — Entry anchor is the custom section's local origin
The first Bézier control point defines the entry anchor and local origin of the custom section.

Internal points and handles are represented in the section's local space. When an upstream CPC component moves, Keep Components Together updates the section placement transform rather than deforming its stored local geometry.

### DD-034 — Exit anchor is derived from the final Bézier point
The last Bézier control point is the custom section's exit anchor and is a valid connection point for subsequent CPC components.

### DD-035 — Keep Components Together preserves custom-section shape
Upstream connection movement repositions the custom Bézier rigidly as a section.

All native points and handles retain their local relationship. Automatic stretching, reshaping or tangent solving is outside the initial 0.4.6 scope.

### DD-036 — Positional continuity first
0.4.6 requires positional continuity at custom Bézier entry/exit connections.

Automatic tangent continuity, tangent inheritance and deformation propagation are deferred until the basic attachment model is validated.

### DD-037 — Adopt existing native Bézier before building a drawing mode
The first implementation spike should adopt an already-created Blender Bézier curve into a CPC chain.

A CPC-specific custom-curve drawing mode may later automate creation of the same underlying native representation, but it must not introduce a separate curve model.

### DD-038 — 0.4.7 creates the same native CUSTOM_BEZIER representation
**Add Custom Bézier** is a convenience workflow over the validated 0.4.6 custom-section model.

It must create a normal Blender Bézier Curve and immediately register it as the same `CUSTOM_BEZIER` recipe member used by adopted curves. No second persistence format, point representation or reconstruction path is introduced.

### DD-039 — Custom Bézier creation starts with two tangent-aligned points
The selected CPC part's endpoint opposite its current Edit Anchor is treated as the continuation endpoint.

P0 is placed on that endpoint and remains the custom section's local origin. P1 is created along the endpoint's outward tangent so the new section begins with a meaningful continuation direction instead of an arbitrary default orientation.

### DD-040 — ALIGNED is the 0.4.7 creation default
Both initial control points use explicit collinear Blender `ALIGNED` handles.

CPC positions the complete handle geometry first and only then enables the ALIGNED constraint. The creation step therefore starts from handle coordinates that already satisfy Blender's alignment rule instead of asking Blender to reshape an existing curve to satisfy a newly applied handle type.

### DD-041 — Creation defaults do not become Commit/Recommit policy
ALIGNED is only the initial state of a newly created custom section.

After creation, Blender owns all point and handle editing. If the user changes handles to Free, Vector, Auto or another supported native type, Commit/Recommit must preserve the actual resulting handle coordinates and types rather than normalizing the section back to ALIGNED.

### DD-042 — Tangent inheritance is initialisation, not continuous deformation
0.4.7 inherits the preceding CPC endpoint tangent only when the custom section is created.

Later upstream edits may reposition the section through CPC connectivity, but CPC does not continuously rotate, stretch or reshape the custom Bézier to follow changing upstream tangents.

### DD-043 — Add Custom Bézier must not silently create graph branches
If the selected continuation endpoint is already semantically connected downstream or hosted, Add Custom Bézier should refuse creation and tell the user to choose the opposite Edit Anchor or remove the existing downstream connection.

This keeps the one-dimensional profile-chain workflow predictable and avoids accidental branching topology.
