# Curve Profile Creator — 0.4.2

Curve Profile Creator (CPC) is a Blender Extension for constructing, editing, committing, reusing and sweeping parametric architectural profile curves.

**Minimum supported CPC baseline: 0.4.1.** CPC 0.4.2 is a Blender Extensions compliance release and intentionally makes no modelling changes.

## What 0.4.2 changes

- updates the manifest tagline and file-permission explanation to Blender's 64-character limits;
- stores the default User Profiles library in Blender-managed extension user storage via `bpy.utils.extension_path_user()`;
- copies 0.4.0/0.4.1 presets from the former default Blender data-files location into the new extension user directory on upgrade, without deleting or overwriting user files;
- keeps custom User Profile library folders unchanged;
- retains `.cpcprofile` format v1, recipe schema 11+, automatic PNG previews, dropdown/image selection and all validated 0.4.1 construction behavior.

## Construction groups

### Basic
- Line / Fascia
- Ovolo
- Cavetto
- Half Round / Torus
- Cyma Recta
- Cyma Reversa

### Constructed
- Chamfer with same-side horizontal fillets
- V-Groove
- Rebate / Notch
- Single Step
- Double Step

### Architectural
- Ovolo + Fillets
- Cavetto + Fillets
- Cyma Recta + Fillets
- Cyma Reversa + Fillets
- Fascia + Ovolo + Fillet
- Fascia + Cavetto + Fillet
- Nose + Cove
- Simple Scotia
- Classical Scotia

## User Profiles

CPC uses portable `.cpcprofile` JSON presets with automatically generated PNG previews.

- **PARAMETRIC** presets retain recipe schema 11+ state and remain editable CPC constructions.
- **STATIC** presets preserve normalized curve geometry without claiming parametric editability.

The default library is stored under Blender's extension-owned writable user directory. Users may still choose a custom library folder in CPC's User Profiles panel.

## Compatibility

0.4.2 preserves the validated 0.4.1 persistence contract:

- embedded recipe schema 11+;
- transform schema 1 using `matrix_profile`;
- `.cpcprofile` format v1;
- PARAMETRIC and STATIC presets;
- independent `cpc_part_rotation`;
- generated PNG previews.

CPC does not restore pre-0.4.0 recipe formats.
