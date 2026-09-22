# Curve Profile Creator — 0.4.4

Curve Profile Creator (CPC) is a Blender Extension for constructing, editing, committing, reusing and sweeping parametric architectural profile curves.

**Minimum supported CPC persistence baseline: 0.4.0 / recipe schema 11+.** The validated 0.4.1 modelling behavior remains the protected runtime baseline.

## What 0.4.4 changes

0.4.4 closes the transform and connectivity milestone while retaining the persistent User Profiles library introduced in 0.4.3.

- stores one canonical complete-profile placement state: Offset X/Y, Rotation, Flip X/Y and Uniform Scale;
- makes placement-time and post-placement transforms resolve to the same result;
- routes Blender G/R/S through CPC semantic placement or component dimensions;
- adds component wheel/S/panel/HUD **Size** gestures that regenerate dimensions and leave Object Scale at `1,1,1`;
- adds committed-profile HUD **Rotation** and **Uniform Scale** controls;
- adds explicit **Reconnect Touching Endpoints** for metadata-only endpoint junction repair;
- keeps custom User Profile library paths persistent and initializes `cpc_library.json` immediately for a new library;
- makes 2D Sweep Caps/Fill Mode authoritative and live, while retaining the existing 3D sweep behavior;
- keeps `.cpcprofile` format v1, recipe schema 11+, transform schema 1 and PNG thumbnails unchanged.

## User Profiles browser

```text
Category  [ Cornice / Crown ▼ ]  [ + ] [ Manage ]
Search    [____________________________]

Preset    [ profile name ▼ ]
[ synchronized thumbnail grid ]
```

When Search is empty, Category filters the library. As soon as Search contains text, Search becomes global and the Category filter is temporarily ignored. Clearing Search returns to the selected Category.

Search matches profile name, description, category, tags and source metadata.

### Category behavior

CPC supplies these starter categories for an unconfigured library:

- Cornice / Crown
- Casing / Architrave
- Skirting / Baseboard
- Chair Rail
- Picture Rail
- Panel Moulding
- Door / Window Trim
- Classical Orders
- Cabinet / Furniture Mouldings
- Other

Users may add or rename real categories. `All Categories` is a virtual filter item. `Uncategorized` is the virtual fallback for existing presets without category metadata. Neither is renameable. Category merge/delete remains outside 0.4.4.

## Preset metadata

`.cpcprofile` remains authoritative JSON format v1. The library metadata added in 0.4.3 remains optional:

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

Existing 0.4.0–0.4.2 presets remain valid and appear as `Uncategorized` until classified.

## Preset classes

- **PARAMETRIC** presets retain recipe schema 11+ state and remain editable CPC constructions when their authority hash is valid.
- **STATIC** presets preserve normalized curve geometry without claiming parametric editability.

## Storage and previews

The default library remains Blender's extension-owned writable user directory via `bpy.utils.extension_path_user()`. A custom folder may be selected and is synchronized through CPC preferences and scenes. When a library is first indexed, CPC creates `cpc_library.json` with the starter/discovered category vocabulary.

PNG preview files remain regenerable cache artifacts. WebP preview storage is a later candidate, not part of 0.4.4. CPC continues to use Blender's Image API directly and has no Pillow/PIL dependency.

## Compatibility

0.4.4 preserves:

- `.cpcprofile` format v1;
- recipe schema 11+;
- transform schema 1 using `matrix_profile`;
- complete-profile placement schema 1 using `cpc_profile_placement_json`;
- independent `cpc_part_rotation`;
- PARAMETRIC/STATIC provenance rules;
- geometry-authority hashing;
- Commit → Edit Active Profile → Recommit;
- connected editing, semantic viewport editing and explicit endpoint reconnection;
- profile normalization, packed component restoration and Sweep bevel linkage;
- 2D Caps OFF/ON behavior and live Fill Mode updates;
- lazy viewport overlay handlers required by Blender Extensions.
