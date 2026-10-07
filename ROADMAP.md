# Curve Profile Creator — 0.4.6 Development

## Roadmap

### Stable baseline — 0.4.4

CPC 0.4.6 branches directly from the validated 0.4.4 release baseline. All validated 0.4.4 behaviour is to be preserved unless a later decision explicitly supersedes it.

### Historical note — 0.4.5

0.4.5 is treated as an abandoned experimental point upgrade. Its edit-point / S-curve direction is not part of the active development lineage and must not be merged into 0.4.6.

If the experimental 0.4.5 work is preserved on GitHub, it should be kept only as an archive/history branch rather than published as a supported release.

### Active milestone — 0.4.6 Custom Bézier Integration

The primary 0.4.6 experiment is a mixed CPC–Blender curve workflow: a user may extend an existing CPC component chain with a native Blender Bézier section when CPC's semantic component catalogue is not appropriate for the required freeform shape.

#### Core requirements

- existing CPC components and their semantic controls remain unchanged;
- construction continues to use the existing Add + Snap workflow;
- a native/freeform Blender Bézier section can continue from a CPC component endpoint;
- the first Bézier control point acts as the custom section's entry anchor and local origin;
- Bézier control points, handle positions and handle types are preserved rather than sampled into static point geometry;
- CPC Commit/Recommit must preserve native Bézier editability;
- the final Bézier control point acts as the exit anchor for subsequent CPC components;
- Keep Components Together must propagate positional changes through the custom section without deforming its local shape;
- upstream motion is represented by moving the custom section's component/local transform, rather than rewriting every stored point;
- Move All and Rotate All must continue to transform the complete assembly coherently;
- version one requires positional continuity only; automatic tangent continuity and automatic Bézier deformation are explicitly deferred;
- Blender remains the authority for editing the internal Bézier geometry; CPC owns connection, placement, Commit/Recommit and assembly behaviour.

#### Preferred first spike

Prototype adoption of an already-created native Blender Bézier curve before building any dedicated CPC Bézier drawing mode.

The spike should prove:

1. a native Bézier can be attached to a CPC endpoint;
2. Commit/Recommit round-trips its points and handles losslessly;
3. its entry anchor can function as the local origin;
4. Keep Components Together can reposition it rigidly from upstream changes;
5. Rotate All and Move All preserve the custom section and its downstream chain;
6. a following CPC component can snap to its exit anchor;
7. Sweep continues to operate on the resulting combined profile.

A CPC-specific Draw Custom Section mode is a possible convenience layer only after this underlying model is validated.

## 0.4.4 validated scope

The 0.4.4 milestone closed issues #2 through #10 while preserving the 0.4.x persistence floor and the validated modelling behaviour carried forward from 0.4.1–0.4.3.

- canonical complete-profile placement state for Offset X/Y, Rotation, Flip X/Y and Uniform Scale;
- equivalent placement-time and post-placement transform results;
- semantic Blender `G` / `R` / `S` routing for committed profiles and construction parts;
- component placement-wheel / `S` / panel / HUD Size with neutral Object Scale;
- committed-profile Rotation and Uniform Scale controls;
- shared Shift/Ctrl fine and snapped semantic gestures;
- explicit metadata-only **Reconnect Touching Endpoints**;
- persistent custom User Profile library path;
- immediate `cpc_library.json` initialization for active library roots;
- authoritative 2D Sweep Caps / Fill Mode behaviour;
- retained Blender-supported 3D sweep cap behaviour;
- clean Extension packaging that excludes tests and development artifacts;
- production regression validation against CRN-4000 through CRN-4004.

## Later candidates

The following are candidates, not commitments:

- optional tangent-follow behaviour for custom Bézier connections after positional attachment is proven;
- CPC convenience drawing mode that creates native Blender Bézier points/handles;
- WebP preview storage using Blender-native APIs while continuing to read existing PNG previews;
- batch migration/export of existing Blender curve/profile asset collections into `.cpcprofile` libraries;
- explicit category merge/delete if production use justifies it;
- broader public profile-library tooling after metadata and licensing workflows are proven;
- further semantic transform coverage only where Blender interaction can map cleanly to CPC construction intent;
- additional production regression profiles as the component catalogue expands.
