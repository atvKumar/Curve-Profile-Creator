# Curve Profile Creator 0.4.4 Validation

Status: Passed — automated checks and CRN-4000 through CRN-4004 production validation complete.

## Candidate

- Branch: `dev/0.4.4`
- Source commit: `82794baf70ce5bcaee855510abee5ffecbf144f9`
- Archive: `curve_profile_creator-0.4.4-rc-82794ba.zip`
- SHA-256: `688b5231cd9a5588e42cc38ad86a55b9ba51c33accc23f1085d51730febd4ee2`
- Blender: 4.3 or newer

## Automated gate

Recorded before documentation and packaging:

- Unit suite: **52/52 passed** with `PYTHONDONTWRITEBYTECODE=1`.
- Top-level shipped Python modules: **23 parsed successfully** with `ast`.
- `git diff --check`: passed.
- Endpoint planner: inclusive tolerance, outside-boundary, transitive clustering, stable ID survival, new-ID assignment and self-junction exclusion covered.
- Semantic gesture math: Shift fine motion, Ctrl snapping, Shift+Ctrl fine snapping and exact typed Rotation/Size values covered.
- Final review regression: typed panel Rotation is absolute; mouse Rotation remains delta-based from the captured start.
- Reconnect adapter: metadata-only assignment, stale ID isolation, hosted-attachment clearing and coordinate preservation covered.

## Issue coverage

| Issue | Automated evidence | Blender evidence |
|---|---|---|
| #2 authoritative placement | `profile_transforms.py`, `viewport_semantics.py`, placement/gesture tests | CRN combined transform, reload and Sweep rows |
| #3 pre/post equivalence | canonical placement-state and profile gesture tests | CRN pre/post comparison rows |
| #4 semantic G/R | `connected_transforms.py`, profile gesture lifecycle tests | Blender G/R plus numeric-equivalence rows |
| #5 semantic component/profile S | `profile_resize.py`, `semantic_gestures.py`, `viewport_semantics.py` tests | wheel/S/panel/HUD normalization rows |
| #6 reconnect | `endpoint_reconnect.py`, `junctions.py`, planner/adapter/scope tests | snapped-chain and Maintain Connected rows |
| #7 production validation | this document and full automated gate | every CRN-4000–CRN-4004 row |
| #8 overlay/panel controls | semantic-field, modifier and UI-contract tests | panel/HUD interaction rows |
| #9 persistent library | `user_profiles.py` path/registry implementation and existing library coverage | restart, new-file and custom-library rows |
| #10 Caps/fill mode | `geometry.py`, `properties.py`, sweep implementation | 2D Caps OFF/ON/live-toggle and 3D rows |

## Production matrix

Every feature cell is reported separately so one failure cannot be hidden by an overall profile result.

Production result: On 2026-09-22, the user confirmed that the complete
CRN-4000 through CRN-4004 Blender validation set is working, including the
transform, semantic gesture, panel/HUD modifier, scale-normalization,
reconnection, save/reload, Recommit and Sweep checks below.

| Profile | Placement + combined transforms | Pre/post equivalence | G/R/S + wheel | Panel/HUD + modifiers | Scale normalization | Reconnect + Maintain Connected | Save/reload + Edit/Recommit | Sweep | Result |
|---|---|---|---|---|---|---|---|---|---|
| CRN-4000 | Pass — user-confirmed | Pass — user-confirmed | Pass — user-confirmed | Pass — user-confirmed | Pass — user-confirmed | Pass — user-confirmed | Pass — user-confirmed | Pass — user-confirmed | Pass — user-confirmed |
| CRN-4001 | Pass — user-confirmed | Pass — user-confirmed | Pass — user-confirmed | Pass — user-confirmed | Pass — user-confirmed | Pass — user-confirmed | Pass — user-confirmed | Pass — user-confirmed | Pass — user-confirmed |
| CRN-4002 | Pass — user-confirmed | Pass — user-confirmed | Pass — user-confirmed | Pass — user-confirmed | Pass — user-confirmed | Pass — user-confirmed | Pass — user-confirmed | Pass — user-confirmed | Pass — user-confirmed |
| CRN-4003 | Pass — user-confirmed | Pass — user-confirmed | Pass — user-confirmed | Pass — user-confirmed | Pass — user-confirmed | Pass — user-confirmed | Pass — user-confirmed | Pass — user-confirmed | Pass — user-confirmed |
| CRN-4004 | Pass — user-confirmed | Pass — user-confirmed | Pass — user-confirmed | Pass — user-confirmed | Pass — user-confirmed | Pass — user-confirmed | Pass — user-confirmed | Pass — user-confirmed | Pass — user-confirmed |

## Protected behavior checks

| Behavior | Result |
|---|---|
| Recipe schema 11+ | Pass — user-confirmed Blender validation |
| Transform schema 1 and `matrix_profile` | Pass — user-confirmed Blender validation |
| PARAMETRIC preset load/edit | Pass — user-confirmed Blender validation |
| STATIC preset load/use | Pass — user-confirmed Blender validation |
| Committed-object identity across Recommit | Pass — user-confirmed Blender validation |
| Sweep bevel-object linkage | Pass — user-confirmed Blender validation |
| Packed component restoration | Pass — user-confirmed Blender validation |
| Profile normalization and neutral Object Scale | Pass — user-confirmed Blender validation |
| Lazy viewport overlay activation | Pass — user-confirmed Blender validation |
| #9 custom library path, `cpc_library.json`, restart/new-file behavior | Pass — user-confirmed Blender validation |
| #10 2D Caps OFF/ON/live toggle and 3D sweep behavior | Pass — user-confirmed Blender validation |

## Evidence boundary

This workspace contains no Blender executable or CRN-4000–CRN-4004 production files. The following behaviors cannot be truthfully proven by the automated suite and are assigned to the production matrix above:

- GPU viewport HUD drawing, hit testing and modal focus;
- Blender restart and new-file preference inheritance;
- live depsgraph transform routing and connected graph movement;
- committed object identity and linked bevel evaluation inside Blender;
- packed architectural regeneration and Sweep evaluation;
- native 2D Fill Mode/Caps display and live toggle behavior.

Issue #7 production gate is satisfied by the user confirmation recorded above.
