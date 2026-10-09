# Curve Profile Creator — 0.4.7 Development

## Roadmap

### Stable baseline — 0.4.4

CPC 0.4.7 builds on the validated 0.4.6 Custom Bézier Integration line, which itself branches directly from the validated 0.4.4 release baseline. All validated 0.4.4 and 0.4.6 behaviour is to be preserved unless a later decision explicitly supersedes it.

### Historical note — 0.4.5

0.4.5 is treated as an abandoned experimental point upgrade. Its edit-point / S-curve direction is not part of the active development lineage and must not be merged into the active 0.4.6/0.4.7 development lineage.

If the experimental 0.4.5 work is preserved on GitHub, it should be kept only as an archive/history branch rather than published as a supported release.

### Validated milestone — 0.4.6 Custom Bézier Integration

0.4.6 proved the mixed CPC–Blender curve model: existing native Blender Bézier curves can be adopted as CPC custom construction sections while preserving native points/handles, CPC endpoint connectivity, Maintain Connected behaviour, Commit/Recommit and User Profile persistence.

The validated architectural rule remains:

> CPC owns the connections. Blender owns the freeform curve.

### Active milestone — 0.4.7 Custom Bézier Creation

0.4.7 adds a CPC-native entry point for creating the same validated `CUSTOM_BEZIER` representation without requiring the user to manually create and position a Blender curve first.

#### Creation workflow

1. select the CPC construction part to continue from;
2. CPC uses the endpoint opposite that part's current Edit Anchor as the continuation endpoint;
3. **Add Custom Bézier** creates a native two-point Blender Bézier section;
4. point P0 is placed exactly on the CPC continuation endpoint and acts as the custom section's local origin;
5. point P1 is placed along the source endpoint's outward tangent;
6. both control points start with explicit collinear **ALIGNED** handles;
7. CPC immediately hands the new section to Blender's native Edit Mode when context permits;
8. the user continues shaping/extruding with Blender's normal Bézier tools;
9. Commit/Recommit stores the actual points, handle coordinates and handle types that exist after editing.

#### Design constraints

- 0.4.7 must reuse the existing 0.4.6 `CUSTOM_BEZIER` storage and restoration model;
- no second CPC-specific Bézier solver or point-editing system is introduced;
- initial tangent matching happens only at creation time;
- Maintain Connected continues to move the custom section rigidly rather than deforming it to follow later tangent changes;
- Commit/Recommit must never force handles back to ALIGNED after the user changes them;
- existing **Adopt Selected Blender Bézier** remains available for pre-existing/freeform curves;
- the operator must not silently create an endpoint branch when the selected continuation endpoint is already connected downstream.

#### 0.4.7 acceptance targets

1. Add Custom Bézier creates exactly two native Bézier control points;
2. P0 coincides with the selected CPC continuation endpoint;
3. P1 lies on the outgoing tangent of that endpoint;
4. both initial points use Blender `ALIGNED` handles with explicit handle geometry;
5. the seed curve does not visibly reshape when created;
6. CPC endpoint metadata connects source endpoint → custom P0 immediately;
7. native Blender Edit Mode can reshape/extrude the custom section normally;
8. Commit → Edit Active Profile → Recommit preserves the actual edited handle coordinates/types;
9. Maintain Connected and Rotate/Move behaviour remain unchanged from 0.4.6;
10. existing 0.4.6 adopted Bézier profiles and User Profile presets remain compatible.

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
- optional additional creation handle modes after the ALIGNED workflow is validated in production;
- WebP preview storage using Blender-native APIs while continuing to read existing PNG previews;
- batch migration/export of existing Blender curve/profile asset collections into `.cpcprofile` libraries;
- explicit category merge/delete if production use justifies it;
- broader public profile-library tooling after metadata and licensing workflows are proven;
- further semantic transform coverage only where Blender interaction can map cleanly to CPC construction intent;
- additional production regression profiles as the component catalogue expands.
