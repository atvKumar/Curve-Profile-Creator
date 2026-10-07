# Curve Profile Creator — 0.4.6

Curve Profile Creator (CPC) is a Blender Extension for constructing, editing, committing, saving, reusing and sweeping architectural profile curves.

CPC is construction-first: most profiles are built from semantic primitives and architectural components whose dimensions remain editable. **0.4.6 extends that workflow with native Blender Bézier sections**, allowing a CPC profile to move naturally between structured parametric construction and freeform curve modelling without losing CPC connectivity, Commit/Recommit or preset behaviour.

- **Blender:** 4.3 or newer
- **Persistence baseline:** CPC 0.4.0
- **Recipe schema:** 11+
- **Preset format:** `.cpcprofile` v1
- **Transform schema:** 1
- **Development line:** 0.4.6 branches from the validated 0.4.4 release

## What 0.4.6 changes

0.4.6 introduces **Custom Bézier Integration**.

A profile can now be constructed primarily with CPC components and extended with a native Blender Bézier curve wherever a semantic CPC component is not the right tool for the required shape.

Typical workflow:

```text
CPC Line
→ CPC Ovolo
→ native Blender Bézier
→ CPC Cove / Line / next component
→ Commit
```

The goal is not to replace Blender's Bézier tools. Blender remains responsible for editing the freeform curve; CPC adds the construction, connectivity and persistence layer around it.

## Adopt Selected Blender Bézier

A normal Blender Bézier Curve can now be adopted into the active CPC construction using:

**Adopt Selected Blender Bézier**

The adopted curve becomes a CPC custom construction section while retaining its native Blender control points and handles.

CPC preserves:

- control-point coordinates;
- left and right handle coordinates;
- Blender handle types;
- radius;
- tilt;
- soft-body weight;
- spline resolution information;
- CPC entry/exit connectivity;
- Commit/Recommit reconstruction data.

The curve is **not sampled into a dense static polyline** during adoption.

### Native handle types

0.4.6 supports Blender-native Bézier handle semantics including:

- Free
- Vector
- Aligned
- Auto
- Auto Clamped

Adoption preserves the user's existing curve shape. CPC rebases the Curve datablock with one rigid local transform rather than moving control points and handles individually, avoiding handle recalculation or shape distortion.

If the selected Blender Curve datablock is shared by multiple objects, CPC first creates an independent copy before rebasing it so adoption does not alter another object using the same Curve data.

## Custom Bézier local origin

For an adopted custom section:

```text
first Bézier point = CPC local origin
last Bézier point  = CPC exit anchor
```

The first point is rebased to local:

```text
(0, 0, 0)
```

without changing the curve's world-space shape.

This gives the custom section the same clean component-transform model used elsewhere in CPC:

```text
local Bézier geometry
→ component transform
→ CPC assembly / profile transform
→ world position
```

The internal Bézier geometry therefore stays stable while CPC moves the section through its component transform.

## Maintain Connected Parts

Custom Bézier sections participate in CPC's existing endpoint-junction system.

Example:

```text
Line → Ovolo → Custom Bézier → Cove
```

If the Ovolo changes and its connected endpoint moves, **Maintain Connected Parts** moves the custom Bézier section with that endpoint while preserving the custom curve's local shape.

Conceptually:

```text
upstream endpoint moves
→ custom section transform follows
→ internal Bézier shape stays unchanged
→ custom exit anchor moves with it
→ downstream CPC components follow
```

0.4.6 intentionally uses **positional continuity** as the initial rule.

CPC does not automatically stretch the custom section, recalculate its control points or force tangent continuity when neighbouring components change.

> CPC owns the connections. Blender owns the freeform curve.

## Move, Rotate and connected transforms

Adopted custom Bézier sections participate in the same connected transform system as normal CPC construction parts.

Validated behaviour includes:

- moving the connected construction;
- rotating connected parts;
- Maintain Connected propagation;
- preserving the custom Bézier shape while the assembly moves;
- maintaining valid downstream connection anchors.

The custom section remains native Blender curve geometry throughout these operations.

## Commit, Edit and Recommit

The standard CPC workflow continues to work with mixed CPC/Bézier profiles:

```text
construct CPC components
→ adopt native Blender Bézier
→ continue CPC construction
→ Commit
→ Edit Active Profile
→ edit native Bézier or CPC parts
→ Recommit
```

On Commit, CPC stores the custom Bézier section inside the profile recipe rather than treating it as an external dependency.

On **Edit Active Profile**, CPC reconstructs the custom section as a native Blender Bézier Curve with its editable control points and handles restored.

Recommit preserves the committed profile object's identity, so existing Sweep bevel-object relationships continue to work as in 0.4.4.

## User Profiles and custom Bézier presets

Mixed CPC/Bézier profiles can be saved as normal CPC User Profile presets.

A PARAMETRIC preset may now contain both:

```text
semantic CPC recipe records
+
CUSTOM_BEZIER recipe records
```

The custom Bézier payload remains part of the reusable CPC recipe.

0.4.6 also updates preset validation so `CUSTOM_BEZIER` records are recognized as valid PARAMETRIC recipe members even though they intentionally do not use a CPC `primitive_id`.

This means custom Bézier presets:

- remain visible after Refresh Library;
- remain visible after Blender restart or extension reinstall;
- can be loaded like existing 0.4.4 PARAMETRIC presets;
- preserve native Bézier reconstruction on Edit/Recommit.

Existing CPC 0.4.4 `.cpcprofile` presets remain compatible.

## User Profile library

The indexed User Profiles system remains unchanged in principle.

Retained capabilities include:

- user-managed Categories;
- global Search;
- indexed preset metadata;
- Tags and Source information;
- PNG thumbnail previews;
- metadata-only Edit Info;
- PARAMETRIC and STATIC presets;
- persistent custom User Profile library paths.

The default library remains Blender's extension-owned writable user directory.

A custom library path can be configured and persists through CPC preferences.

`cpc_library.json` remains the category-vocabulary registry only. Each `.cpcprofile` remains authoritative for its own geometry, recipe, identity and metadata.

## 0.4.4 foundation retained in 0.4.6

0.4.6 is built directly from the validated 0.4.4 release and retains its transform and connectivity model.

### One authoritative complete-profile placement state

Committed profiles continue to resolve through:

- Offset X
- Offset Y
- Rotation
- Flip X
- Flip Y
- Uniform Scale

```text
canonical profile geometry
→ uniform scale
→ flip
→ rotation
→ profile-local offset
→ path / sweep frame
```

### Blender G / R / S integration

For committed profiles:

```text
G → CPC Offset X / Y
R → CPC Rotation
S → CPC Uniform Scale
```

Normal Blender transforms therefore continue to edit CPC semantic placement rather than creating a second persistent transform authority.

## Semantic component Size

Normal CPC construction components still resize through semantic construction dimensions rather than arbitrary Object Scale.

```text
resize
→ dimensional CPC parameters
→ regenerate
→ Object Scale = 1,1,1
```

Length-valued parameters such as Width, Height, Chord, Depth and Fillet dimensions are scaled.

Dimensionless controls such as Bias, Fullness, flips and construction mode remain unchanged.

Component Size continues to be available through:

- mouse wheel during placement;
- Blender `S`;
- selected-part panel **Size**;
- viewport HUD **Size**.

Custom Bézier sections intentionally do **not** expose semantic CPC Size parameters. Their internal shape is edited with Blender's native curve tools.

## Rotation and Size controls

For an individual semantic CPC construction component:

- **Rotation** edits `cpc_part_rotation`;
- **Size** performs semantic uniform resizing.

For a committed complete profile:

- **Rotation** edits profile placement Rotation;
- **Uniform Scale** edits profile placement Uniform Scale.

Panel and HUD pointer gestures retain the established modifier model:

| Input | Behaviour |
|---|---|
| Normal drag | Standard adjustment |
| `Shift` | Fine adjustment |
| `Ctrl` | Snapped adjustment |
| `Shift + Ctrl` | Fine snapped adjustment |
| Typed value | Exact value |

## Reconnect Touching Endpoints

CPC continues to distinguish physical coincidence from semantic connectivity.

Two endpoints may occupy the same position without sharing a CPC junction relationship.

**Reconnect Touching Endpoints** explicitly rebuilds semantic endpoint relationships without moving geometry.

Custom Bézier start/end anchors participate in this same junction system.

During initial adoption CPC only tests the adopted Bézier's own start/end anchors for touching CPC endpoints; unrelated touching parts elsewhere in the construction are not automatically reconnected.

## Sweep Caps and Fill Mode

The 0.4.4 Caps behaviour remains authoritative for 2D sweep fill.

For a 2D CPC sweep/path:

```text
Caps OFF
→ use_fill_caps = False
→ Fill Mode = None

Caps ON
→ use_fill_caps = True
→ Fill Mode = Both
```

3D paths retain Blender-supported bevel-cap behaviour.

Mixed CPC/Bézier profiles can be committed and used as Sweep profiles in the same way as ordinary CPC profiles.

## Compatibility

0.4.6 preserves:

- `.cpcprofile` format v1;
- existing 0.4.4 User Profiles;
- recipe schema 11+;
- transform schema 1 using `matrix_profile`;
- complete-profile placement schema 1;
- independent `cpc_part_rotation`;
- PARAMETRIC / STATIC provenance rules;
- geometry-authority hashing;
- profile normalization;
- packed component restoration;
- Commit → Edit Active Profile → Recommit;
- Categories, Search, Tags and Source metadata;
- persistent custom library paths;
- lazy viewport-overlay activation required by Blender Extensions.

0.4.6 adds a new recipe member type:

```text
component_type = CUSTOM_BEZIER
```

which stores native Bézier data alongside ordinary CPC primitive records.

## 0.4.5 development note

The earlier 0.4.5 edit-point / S-curve experiment was intentionally abandoned.

It is not part of the supported development lineage.

0.4.6 branches directly from the validated 0.4.4 baseline and replaces the specialised edit-point direction with the more general native Blender Bézier workflow.

## Validation

The 0.4.4 foundation was previously validated through the full transform, connectivity, preset and Sweep regression set.

The new 0.4.6 Custom Bézier workflow has been manually validated in Blender for:

- adopting an existing native Blender Bézier;
- preserving its original shape and handle positions during adoption;
- native Bézier handle editing;
- endpoint connection to CPC components;
- Maintain Connected propagation;
- rotation and connected transforms;
- Commit;
- Edit Active Profile;
- Recommit;
- User Profile save/load;
- preset refresh/re-indexing;
- compatibility with existing 0.4.4 presets.

A dedicated regression test also verifies that `CUSTOM_BEZIER` records remain valid members of PARAMETRIC `.cpcprofile` recipes while ordinary semantic CPC records still require a valid `primitive_id`.

## Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md)
- [DESIGN_DECISIONS.md](DESIGN_DECISIONS.md)
- [CHANGELOG.md](CHANGELOG.md)
- [ROADMAP.md](ROADMAP.md)
- [0.4.6 Custom Bézier Integration Design](docs/superpowers/specs/2026-10-07-cpc-0.4.6-custom-bezier-integration-design.md)

## 0.4.6 in one sentence

**Curve Profile Creator 0.4.6 lets structured CPC construction hand off to Blender's native Bézier modelling and return to CPC without losing connectivity, editable handles, Commit/Recommit, presets or Sweep workflows.**
