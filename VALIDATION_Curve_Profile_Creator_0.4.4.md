# Curve Profile Creator — 0.4.4

## Validation

**Status: Passed — automated checks and CRN-4000 through CRN-4004 production validation complete.**

### Candidate

- Branch: `dev/0.4.4`
- Source commit: `82794baf70ce5bcaee855510abee5ffecbf144f9`
- Archive: `curve_profile_creator-0.4.4-rc-82794ba.zip`
- SHA-256: `688b5231cd9a5588e42cc38ad86a55b9ba51c33accc23f1085d51730febd4ee2`
- Blender: 4.3 or newer

### Automated gate

Recorded before final documentation and packaging:

- Unit suite: **52/52 passed** with `PYTHONDONTWRITEBYTECODE=1`.
- Top-level shipped Python modules: **23 parsed successfully** with `ast`.
- `git diff --check`: passed.
- Endpoint planner: inclusive tolerance, outside-boundary, transitive clustering, stable ID survival, new-ID assignment and self-junction exclusion covered.
- Semantic gesture math: Shift fine motion, Ctrl snapping, Shift+Ctrl fine snapping and exact typed Rotation/Size values covered.
- Final review regression: typed panel Rotation is absolute; mouse Rotation remains delta-based from the captured start.
- Reconnect adapter: metadata-only assignment, stale-ID isolation, hosted-attachment clearing and coordinate preservation covered.

### Issue coverage

| Issue | Feature | Automated evidence | Blender evidence |
|---|---|---|---|
| #2 | Authoritative profile placement | `profile_transforms.py`, `viewport_semantics.py`, placement/gesture tests | CRN combined transform, reload and Sweep rows |
| #3 | Pre/post placement equivalence | canonical placement-state and profile gesture tests | CRN pre/post comparison rows |
| #4 | Semantic Blender G/R | `connected_transforms.py`, profile gesture lifecycle tests | Blender G/R plus numeric-equivalence rows |
| #5 | Semantic component/profile S | `profile_resize.py`, `semantic_gestures.py`, `viewport_semantics.py` tests | wheel/S/panel/HUD normalization rows |
| #6 | Reconnect Touching Endpoints | `endpoint_reconnect.py`, `junctions.py`, planner/adapter/scope tests | snapped-chain and Maintain Connected rows |
| #7 | Production validation | this document and full automated gate | every CRN-4000–CRN-4004 row |
| #8 | Overlay/panel semantic controls | semantic-field, modifier and UI-contract tests | panel/HUD interaction rows |
| #9 | Persistent User Profile library | `user_profiles.py` path/registry implementation and library coverage | restart, new-file and custom-library rows |
| #10 | Sweep Caps / Fill Mode | `geometry.py`, `properties.py`, Sweep implementation | 2D Caps OFF/ON/live-toggle and 3D rows |

### Production matrix

Every feature cell is reported separately so one failure cannot be hidden by an overall profile result.

On **2026-09-22**, CRN-4000 through CRN-4004 were confirmed working in Blender across the complete 0.4.4 transform, semantic gesture, panel/HUD modifier, scale-normalization, reconnection, save/reload, Recommit and Sweep validation set.

| Profile | Placement + combined transforms | Pre/post equivalence | G/R/S + wheel | Panel/HUD + modifiers | Scale normalization | Reconnect + Maintain Connected | Save/reload + Edit/Recommit | Sweep | Result |
|---|---|---|---|---|---|---|---|---|---|
| CRN-4000 | Pass | Pass | Pass | Pass | Pass | Pass | Pass | Pass | Pass |
| CRN-4001 | Pass | Pass | Pass | Pass | Pass | Pass | Pass | Pass | Pass |
| CRN-4002 | Pass | Pass | Pass | Pass | Pass | Pass | Pass | Pass | Pass |
| CRN-4003 | Pass | Pass | Pass | Pass | Pass | Pass | Pass | Pass | Pass |
| CRN-4004 | Pass | Pass | Pass | Pass | Pass | Pass | Pass | Pass | Pass |

### Protected behaviour checks

| Behaviour | Result |
|---|---|
| Recipe schema 11+ | Pass |
| Transform schema 1 and `matrix_profile` | Pass |
| Complete-profile placement schema 1 | Pass |
| PARAMETRIC preset load/edit | Pass |
| STATIC preset load/use | Pass |
| Committed-object identity across Recommit | Pass |
| Sweep bevel-object linkage | Pass |
| Packed component restoration | Pass |
| Profile normalization and neutral Object Scale | Pass |
| Independent `cpc_part_rotation` | Pass |
| Lazy viewport overlay activation | Pass |
| Persistent custom library path and `cpc_library.json` initialization | Pass |
| 2D Caps OFF/ON/live toggle | Pass |
| 3D Sweep cap behaviour | Pass |

### Semantic transform checks

0.4.4 specifically validates that CPC does not retain competing transform authorities.

#### Complete profile

- Offset X/Y are canonical profile-local placement values.
- Rotation is canonical CPC placement Rotation.
- Flip X/Y remain explicit mirror state.
- Uniform Scale remains placement-level state.
- Blender G/R/S resolves back into the same CPC state.
- Equivalent pre-placement and post-placement edits produce the same result.

#### Construction component

- placement wheel Size updates semantic dimensions;
- Blender `S` updates semantic dimensions;
- selected-part panel Size updates semantic dimensions;
- viewport HUD Size updates semantic dimensions;
- resized objects return to Object Scale `1,1,1`;
- dimensionless construction controls are not multiplied by the resize factor.

### Reconnection checks

**Reconnect Touching Endpoints** was validated for:

- touching endpoints inside tolerance;
- endpoints outside tolerance;
- transitive endpoint clusters;
- preservation of stable existing junction IDs;
- new junction-ID assignment where required;
- self-junction exclusion;
- stale-ID isolation;
- hosted-attachment cleanup where affected;
- unchanged endpoint coordinates;
- Maintain Connected operation after reconnection.

### User Profile library checks

0.4.4 retains the 0.4.3 indexed browser and validates the new persistence behaviour:

- custom library path survives Blender restart;
- a new file inherits the persistent custom path when no explicit scene override exists;
- selecting a new empty library initializes `cpc_library.json`;
- copied-in presets and discovered categories remain visible;
- existing Category/Search/Edit Info behaviour remains functional;
- default extension-owned storage remains the fallback;
- PNG previews remain compatible.

### Sweep checks

For 2D CPC sweep/path Curves:

```text
Caps OFF → use_fill_caps = False → Fill Mode = None
Caps ON  → use_fill_caps = True  → Fill Mode = Both
```

Validation covers:

- newly created CPC 2D sweeps;
- applying a CPC profile to an existing 2D Curve;
- live Caps toggle on an active CPC sweep;
- preservation of complete-profile/bevel-object fill behaviour;
- unchanged supported 3D path behaviour apart from `use_fill_caps`.

### Evidence boundary

The automated suite does not itself prove Blender-runtime behaviours such as:

- GPU viewport HUD drawing and hit testing;
- Blender restart/new-file preference inheritance;
- live depsgraph transform routing;
- connected graph movement;
- committed-object identity inside Blender;
- linked bevel evaluation;
- packed architectural regeneration;
- native 2D Fill Mode/Caps display.

Those behaviours are covered by the production validation matrix above.

### Release result

The 0.4.4 production gate is satisfied.

The release preserves the established 0.4.x persistent contracts while completing the planned Transform and Connectivity milestone.
