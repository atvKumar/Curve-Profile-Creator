# Curve Profile Creator — 0.4.4

## Roadmap

### Current release — Transform and Connectivity

The 0.4.4 milestone closes issues #2 through #10 while preserving the 0.4.x persistence floor and the validated modelling behaviour carried forward from 0.4.1–0.4.3.

#### Completed scope

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

#### Release acceptance

0.4.4 is accepted when:

1. CRN-4000 through CRN-4004 pass the versioned Blender production matrix.
2. Existing PARAMETRIC and STATIC presets load with recipe schema 11+, transform schema 1 and `.cpcprofile` format v1.
3. Edit Active Profile / Recommit preserves committed object identity and linked Sweep bevel objects.
4. Complete-profile transforms resolve through one canonical placement state.
5. Component resize operations update semantic dimensions and return Object Scale to `1,1,1`.
6. Reconnect repairs only touching endpoint metadata and Maintain Connected follows the rebuilt chain.
7. Custom User Profile path and category registry survive restart/new-file workflows.
8. 2D Sweep Caps update Fill Mode correctly and live.
9. The install archive contains no tests, bytecode, Git metadata, planning documents or nested archives.
10. Automated release checks pass.

All listed 0.4.4 release acceptance items have been validated.

## Later candidates

The following are candidates, not commitments:

- WebP preview storage using Blender-native APIs while continuing to read existing PNG previews;
- batch migration/export of existing Blender curve/profile asset collections into `.cpcprofile` libraries;
- explicit category merge/delete if production use justifies it;
- broader public profile-library tooling after metadata and licensing workflows are proven;
- further semantic transform coverage only where Blender interaction can map cleanly to CPC construction intent;
- additional production regression profiles as the component catalogue expands.
