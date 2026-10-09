# Curve Profile Creator — 0.4.7

Curve Profile Creator (CPC) is a Blender Extension for constructing, editing, committing, saving, reusing and sweeping architectural profile curves.

CPC is construction-first: semantic primitives and architectural components remain editable where dimensions matter, while native Blender Bézier sections are used where freeform shape matters.

**0.4.7 completes the direct CPC → Blender Bézier → CPC workflow.**

- **Blender:** 4.3 or newer
- **Persistence baseline:** CPC 0.4.0
- **Recipe schema:** 11+
- **Preset format:** `.cpcprofile` v1
- **Transform schema:** 1
- **Development line:** 0.4.7 builds on the validated 0.4.6 Custom Bézier integration and the 0.4.4 Transform/Connectivity baseline

## What 0.4.7 changes

0.4.7 adds **Custom Bézier Creation**.

A user can now continue directly from an existing CPC construction part without manually creating and positioning a Blender curve first.

```text
CPC Line
→ CPC Ovolo
→ Add Custom Bézier
→ native Blender Edit Mode
→ continue shaping / extruding
→ CPC Cove / Line / next component
→ Commit
```

The underlying representation is the same native `CUSTOM_BEZIER` component introduced and validated in 0.4.6.

> CPC owns the connections. Blender owns the freeform curve.

## Add Custom Bézier

Select a CPC construction part and use:

**Add Custom Bézier**

CPC uses the endpoint opposite the selected part's current **Edit Anchor** as the continuation endpoint.

The new section starts with exactly two native Blender Bézier points:

```text
preceding CPC tangent ─────────────►

                            P0 ●────────────● P1
                               continuation
```

- **P0** is placed exactly on the CPC continuation endpoint.
- **P0** is the custom section's local origin.
- **P1** is placed along the preceding CPC endpoint's outward tangent.
- both initial points use explicit collinear Blender **ALIGNED** handles;
- the new section is immediately connected to the CPC endpoint;
- CPC attempts to enter Blender Edit Mode with the end point selected for continued shaping.

The starter length is derived from the selected component's span rather than using an arbitrary fixed modelling-unit distance.

### Edit Anchor controls continuation direction

Changing a CPC component's Start/End Edit Anchor changes which opposite endpoint is treated as the continuation side.

This allows the same workflow to operate cleanly in either construction direction.

## ALIGNED is a creation default only

0.4.7 initializes new custom sections with native Blender **ALIGNED** handles because CPC can explicitly position the handle geometry to match the incoming tangent without relying on Blender AUTO recalculation.

The handle coordinates are created first and already satisfy the aligned constraint before the handle type is applied.

After creation, Blender owns the curve.

The user may change any point to:

- Free
- Vector
- Aligned
- Auto
- Auto Clamped

Commit/Recommit preserves the actual handle positions and handle types that exist after editing.

CPC does **not** force the section back to ALIGNED later.

## Existing Bézier adoption remains available

0.4.6 introduced:

**Adopt Selected Blender Bézier**

That workflow remains unchanged and complements the new creation command.

```text
Add Custom Bézier
→ start a freeform section directly from CPC

Adopt Selected Blender Bézier
→ bring an already-modelled native Blender curve into CPC
```

Both workflows produce the same `CUSTOM_BEZIER` recipe representation.

Adoption preserves:

- control-point coordinates;
- left and right handle coordinates;
- Blender handle types;
- radius;
- tilt;
- soft-body weight;
- spline resolution information;
- CPC entry/exit connectivity;
- Commit/Recommit reconstruction data.

The curve is not sampled into a dense static polyline.

## Custom Bézier local origin and anchors

For every CPC custom Bézier section:

```text
first Bézier point = CPC entry anchor / local origin
last Bézier point  = CPC exit anchor
```

The first point is represented locally as:

```text
(0, 0, 0)
```

without changing the curve's world-space shape.

The transform model remains:

```text
local Bézier geometry
→ component transform
→ profile / construction transform
→ world
```

This keeps freeform geometry stable while CPC moves the section as part of a connected chain.

## Maintain Connected Parts

Custom Bézier sections participate in CPC's existing endpoint-junction graph.

Example:

```text
Line → Ovolo → Custom Bézier → Cove
```

When upstream geometry moves, CPC repositions the custom section rigidly through its component transform.

```text
upstream endpoint moves
→ custom section placement follows
→ local Bézier shape remains unchanged
→ custom exit anchor moves
→ downstream CPC parts follow
```

0.4.7 deliberately does **not** continuously reshape the freeform curve to chase later tangent changes.

The preceding CPC tangent is inherited only when the new custom section is created.

## Graph safety

**Add Custom Bézier** will not silently branch an endpoint that is already semantically connected downstream.

If the chosen continuation endpoint is occupied, CPC asks the user to change the Edit Anchor or remove/restructure the existing downstream connection.

This keeps normal profile construction one-dimensional and predictable.

## Move, Rotate and connected transforms

Custom Bézier sections use the same connected-transform system as other CPC construction parts.

Validated behaviour includes:

- moving a connected construction;
- rotating connected parts;
- switching Start/End Edit Anchor;
- Maintain Connected propagation;
- preserving custom local shape;
- maintaining valid entry/exit junctions;
- adding a normal CPC component after the custom Bézier exit.

## Commit, Edit and Recommit

Mixed profiles use the normal CPC workflow:

```text
construct semantic CPC parts
→ Add or Adopt Custom Bézier
→ continue CPC construction
→ Commit
→ Edit Active Profile
→ edit CPC parts and/or native Bézier
→ Recommit
```

On Commit, CPC stores native Bézier point and handle data inside the profile recipe.

On **Edit Active Profile**, CPC reconstructs the custom section as a native Blender Bézier Curve.

Recommit preserves the actual edited handle state rather than applying a new creation default.

Committed-profile identity and existing Sweep bevel-object linkage continue to use the established 0.4.4 behaviour.

## User Profiles and custom Bézier presets

Mixed CPC/Bézier profiles can be saved as normal CPC User Profile presets.

A PARAMETRIC preset may contain:

```text
semantic CPC recipe records
+
CUSTOM_BEZIER recipe records
```

Custom Bézier recipe members intentionally do not require a CPC `primitive_id`; they carry their native Bézier payload instead.

0.4.6 fixed library validation so these presets remain visible after:

- Refresh Library;
- Blender restart;
- extension reinstall.

Existing 0.4.4 User Profiles remain compatible.

## User Profile library

The indexed User Profiles system remains compatible with:

- user-managed Categories;
- global Search;
- indexed preset metadata;
- Tags and Source information;
- PNG thumbnail previews;
- metadata-only Edit Info;
- PARAMETRIC and STATIC presets;
- persistent custom library paths.

`cpc_library.json` remains the category-vocabulary registry only. Each `.cpcprofile` remains authoritative for its own geometry, recipe, identity and metadata.

## 0.4.4 foundation retained

0.4.7 continues to use the validated 0.4.4 transform and connectivity model.

### Complete-profile placement

Committed profiles resolve through one canonical placement state:

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

For committed profiles:

```text
G → CPC Offset X / Y
R → CPC Rotation
S → CPC Uniform Scale
```

### Semantic component Size

Normal CPC construction components resize through semantic dimensions and regenerate back to neutral Object Scale.

```text
resize
→ dimensional CPC parameters
→ regenerate
→ Object Scale = 1,1,1
```

Custom Bézier sections intentionally do not expose CPC semantic Size parameters; their internal shape is edited with Blender's native curve tools.

## Reconnect Touching Endpoints

CPC continues to distinguish physical coincidence from semantic connectivity.

**Reconnect Touching Endpoints** explicitly repairs endpoint metadata without moving geometry.

Custom Bézier entry/exit anchors participate in this same junction system.

## Sweep Caps and Fill Mode

The validated 0.4.4 2D Sweep Caps behaviour remains authoritative:

```text
Caps OFF
→ use_fill_caps = False
→ Fill Mode = None

Caps ON
→ use_fill_caps = True
→ Fill Mode = Both
```

Mixed CPC/Bézier committed profiles can be used as Sweep profiles in the same way as ordinary CPC profiles.

## Compatibility

0.4.7 preserves:

- `.cpcprofile` format v1;
- recipe schema 11+;
- transform schema 1 using `matrix_profile`;
- complete-profile placement schema 1;
- existing 0.4.4 User Profiles;
- existing 0.4.6 `CUSTOM_BEZIER` presets;
- independent `cpc_part_rotation`;
- PARAMETRIC / STATIC provenance rules;
- geometry-authority hashing;
- profile normalization;
- packed component restoration;
- Commit → Edit Active Profile → Recommit;
- Categories, Search, Tags and Source metadata;
- persistent custom library paths;
- lazy viewport-overlay activation required by Blender Extensions.

No new persistent schema version is required for 0.4.7.

## 0.4.5 development note

The earlier 0.4.5 edit-point / specialised S-curve experiment was intentionally abandoned and is not part of the supported development lineage.

0.4.6 returned development to the validated 0.4.4 baseline and introduced the native Blender Bézier model that 0.4.7 now refines.

## Validation

The 0.4.7 source gate passed:

- Python compilation;
- **55/55 automated tests**;
- extension/manifest version checks;
- custom-Bézier preset regression coverage.

Blender validation confirms:

- two-point Add Custom Bézier creation;
- tangent-aware P1 placement;
- initial ALIGNED handles;
- Start/End Edit Anchor reversal;
- CPC → Bézier → CPC chaining;
- downstream CPC placement from the Bézier exit;
- native curve editing;
- Maintain Connected;
- Commit/Edit/Recommit;
- compatibility with the 0.4.6 adoption/preset model.

Validation records are organized under [docs/validation](docs/validation/README.md).

## Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md)
- [DESIGN_DECISIONS.md](DESIGN_DECISIONS.md)
- [CHANGELOG.md](CHANGELOG.md)
- [ROADMAP.md](ROADMAP.md)
- [Validation records](docs/validation/README.md)
- [0.4.6 Custom Bézier Integration Design](docs/superpowers/specs/2026-10-07-cpc-0.4.6-custom-bezier-integration-design.md)

## 0.4.7 in one sentence

**Curve Profile Creator 0.4.7 lets a CPC component continue directly into a tangent-aware native Blender Bézier section and back into CPC, while preserving Blender-native editing, CPC connectivity, Commit/Recommit and User Profile workflows.**
