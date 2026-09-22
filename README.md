# Curve Profile Creator — 0.4.4

Curve Profile Creator (CPC) is a Blender Extension for constructing, editing, committing, saving, reusing and sweeping parametric architectural profile curves.

CPC is construction-first: profiles are built from semantic primitives and architectural components rather than treated as arbitrary curve geometry. CPC preserves construction intent so profiles can be edited, reconnected, recommitted and reused later.

- **Blender:** 4.3 or newer
- **Persistence baseline:** CPC 0.4.0
- **Recipe schema:** 11+
- **Preset format:** `.cpcprofile` v1
- **Transform schema:** 1

## What 0.4.4 changes

0.4.4 is the **Transform and Connectivity** release. It makes complete-profile placement, component resizing and endpoint relationships behave consistently across CPC controls and normal Blender interaction.

### One authoritative profile placement state

A committed CPC profile now resolves through one canonical placement state:

- Offset X
- Offset Y
- Rotation
- Flip X
- Flip Y
- Uniform Scale

Equivalent operations produce the same final geometry whether they are applied before placement or after placement.

```text
canonical profile geometry
→ uniform scale
→ flip
→ rotation
→ profile-local offset
→ path / sweep frame
```

The same state is used by placement, editing, reload, Recommit and Sweep.

### Blender G / R / S integration

Normal Blender transforms now edit CPC semantics instead of creating a second transform authority.

For committed profiles:

```text
G → CPC Offset X / Y
R → CPC Rotation
S → CPC Uniform Scale
```

CPC numeric controls, viewport interaction and supported Blender transforms therefore remain synchronized.

## Semantic component Size

Construction components use their semantic dimensions as the source of truth for size.

A component resize updates relevant dimensional parameters, regenerates the component and restores neutral Blender Object Scale.

```text
resize
→ uniform size factor
→ dimensional construction parameters
→ regenerate
→ Object Scale = 1,1,1
```

Length-valued parameters such as Width, Height, Chord, Depth and Fillet dimensions are scaled. Dimensionless controls such as Bias, Fullness, flips and construction mode are not.

Component Size is available through:

- mouse wheel during placement;
- Blender `S`;
- selected-part panel **Size**;
- viewport HUD **Size**.

Packed architectural components resize through their controller/construction parameters rather than arbitrary child transforms.

## Component Size vs profile Uniform Scale

These operations are intentionally different.

| Editing target | Meaning of scaling |
|---|---|
| Construction component | Change semantic construction dimensions and regenerate |
| Committed complete profile | Change placement-level **Uniform Scale** |

For a component:

```text
S 1.5
→ construction dimensions × 1.5
→ regenerate
→ Object Scale = 1,1,1
```

For a committed profile:

```text
S 1.5
→ CPC Uniform Scale = 1.5
→ rebuild canonical profile placement
```

## Rotation and Size controls

For an individual construction component:

- **Rotation** edits `cpc_part_rotation`;
- **Size** performs semantic uniform resizing.

For a committed complete profile:

- **Rotation** edits profile placement Rotation;
- **Uniform Scale** edits profile placement Uniform Scale.

Panel and HUD pointer gestures share the same modifier model:

| Input | Behaviour |
|---|---|
| Normal drag | Standard adjustment |
| `Shift` | Fine adjustment |
| `Ctrl` | Snapped adjustment |
| `Shift + Ctrl` | Fine snapped adjustment |
| Typed value | Exact value |

## Reconnect Touching Endpoints

CPC distinguishes physical coincidence from semantic connectivity.

Two endpoints may occupy the same position without sharing a CPC junction relationship. This is intentional: proximity alone must not silently alter construction topology.

**Reconnect Touching Endpoints** explicitly rebuilds semantic endpoint relationships.

```text
snap endpoints together
→ Reconnect Touching Endpoints
→ CPC junction metadata rebuilt
→ Maintain Connected works again
```

The operator:

1. scans eligible CPC construction endpoints;
2. detects coincident endpoints within `merge_tolerance`;
3. preserves a stable existing junction ID where possible, otherwise creates one;
4. rebuilds the affected semantic chain;
5. updates metadata without moving geometry.

## User Profiles in 0.4.4

The indexed User Profiles system introduced in **0.4.3 remains the library foundation in 0.4.4**.

Retained capabilities include:

- user-managed Categories;
- global Search;
- indexed preset metadata;
- Tags and Source information;
- PNG thumbnail previews;
- metadata-only Edit Info;
- PARAMETRIC and STATIC presets.

These are retained 0.4.3 features rather than the main focus of 0.4.4.

### Browser behaviour

With Search empty:

```text
metadata index
→ selected Category
→ visible presets
```

With Search non-empty:

```text
metadata index
→ global search across all categories
→ visible presets
```

Search temporarily ignores the selected Category without overwriting it. Clearing Search returns to that Category.

`All Categories` is a virtual filter. `Uncategorized` is the fallback for presets without category metadata.

### Preset classes

- **PARAMETRIC** presets retain CPC recipe state and remain editable when their geometry-authority information is valid.
- **STATIC** presets preserve normalized curve geometry without claiming parametric reconstructability.

### Preset metadata

Optional classification/source metadata remains part of `.cpcprofile` format v1:

```json
{
  "classification": {
    "category": "Cornice / Crown",
    "tags": ["georgian", "classical"]
  },
  "source": {
    "collection": "Reference Library",
    "reference": "CRN-001",
    "url": "",
    "license": ""
  }
}
```

## Persistent User Profile library

The default library remains Blender's extension-owned writable user directory.

A custom User Profile folder can also be selected. In 0.4.4 the custom path is persisted through CPC preferences so it survives Blender restart and new-file workflows unless an explicit scene path overrides it.

When CPC activates a library without a registry, it initializes:

```text
cpc_library.json
```

The registry stores the ordered category vocabulary only. It is not a preset database; each `.cpcprofile` remains authoritative for its own geometry, recipe, identity and metadata.

PNG previews remain regenerable cache artifacts. CPC uses Blender's Image API and has no Pillow/PIL dependency.

## Sweep Caps and Fill Mode

0.4.4 makes CPC **Caps** authoritative for 2D sweep fill behaviour.

For a 2D CPC sweep/path:

```text
Caps OFF
→ use_fill_caps = False
→ Fill Mode = None

Caps ON
→ use_fill_caps = True
→ Fill Mode = Both
```

Changing Caps on an active CPC sweep updates the Curve data live. Applying a profile to an existing 2D Curve also respects the current Caps state.

3D paths retain Blender's supported bevel-cap behaviour without forcing a 2D Fill Mode value.

## Commit, Edit and Recommit

The established CPC workflow remains:

```text
construct profile
→ Commit
→ Edit Active Profile
→ modify CPC construction
→ Recommit
```

0.4.4 preserves committed-object identity, normalized Profile Frame storage, packed component restoration and Sweep bevel-object linkage.

## Compatibility

0.4.4 preserves:

- `.cpcprofile` format v1;
- recipe schema 11+;
- transform schema 1 using `matrix_profile`;
- complete-profile placement schema 1 using `cpc_profile_placement_json`;
- independent `cpc_part_rotation`;
- PARAMETRIC / STATIC provenance rules;
- geometry-authority hashing;
- profile normalization;
- packed component restoration;
- Commit → Edit Active Profile → Recommit;
- 0.4.3 User Profile categories, search and metadata;
- lazy viewport-overlay activation required by Blender Extensions.

## Validation

0.4.4 passed the automated release gate with **52/52 tests** and was production-validated in Blender against:

- CRN-4000
- CRN-4001
- CRN-4002
- CRN-4003
- CRN-4004

The validation set covers combined placement transforms, pre/post placement equivalence, Blender G/R/S, component sizing, panel/HUD modifiers, Object Scale normalization, endpoint reconnection, Maintain Connected, save/reload, Edit/Recommit and Sweep.

See [VALIDATION_Curve_Profile_Creator_0.4.4.md](VALIDATION_Curve_Profile_Creator_0.4.4.md) for the complete validation matrix.

## Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md)
- [DESIGN_DECISIONS.md](DESIGN_DECISIONS.md)
- [CHANGELOG.md](CHANGELOG.md)
- [ROADMAP.md](ROADMAP.md)

## 0.4.4 in one sentence

**Curve Profile Creator 0.4.4 makes transforms, resizing and connectivity semantic and predictable: complete profiles use one placement model, components resize through construction dimensions, snapped endpoints can be explicitly reconnected, User Profile locations persist, and 2D Sweep Caps behave consistently.**
