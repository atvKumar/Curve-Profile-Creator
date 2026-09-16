# Curve Profile Creator — 0.4.3

Curve Profile Creator (CPC) is a Blender Extension for constructing, editing, committing, reusing and sweeping parametric architectural profile curves.

**Minimum supported CPC persistence baseline: 0.4.0 / recipe schema 11+.** The validated 0.4.1 modelling behavior remains the protected runtime baseline.

## What 0.4.3 changes

0.4.3 makes the User Profiles library practical for larger collections without changing CPC geometry, recipe or sweep semantics.

- adds **user-managed Categories** above the existing preset selector;
- ships starter architectural categories, but they are not a closed enum;
- adds **[ + ]** to create categories and **Manage** to rename the selected real category;
- stores persistent category vocabulary in optional `cpc_library.json` library configuration;
- adds **global Search across all categories**;
- adds optional **Tags** and **Source** metadata to `.cpcprofile` files;
- adds **Edit Info** to change display/classification/source metadata without changing geometry, recipe, preset ID or thumbnail;
- separates the in-memory metadata index from preview loading;
- loads PNG preview icons only for the current category or global-search result set;
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

Users may add or rename real categories. `All Categories` is a virtual filter item. `Uncategorized` is the virtual fallback for existing presets without category metadata. Neither is renameable. Category merge/delete is intentionally not part of 0.4.3.

## Preset metadata

`.cpcprofile` remains authoritative JSON format v1. 0.4.3 adds optional metadata only:

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

The default library remains Blender's extension-owned writable user directory via `bpy.utils.extension_path_user()`. A custom folder may still be selected.

PNG preview files remain regenerable cache artifacts in 0.4.3. **WebP is reserved for 0.4.4.** CPC continues to use Blender's Image API directly and has no Pillow/PIL dependency.

## Compatibility

0.4.3 preserves:

- `.cpcprofile` format v1;
- recipe schema 11+;
- transform schema 1 using `matrix_profile`;
- independent `cpc_part_rotation`;
- PARAMETRIC/STATIC provenance rules;
- geometry-authority hashing;
- Commit → Edit Active Profile → Recommit;
- connected editing, viewport semantic editing and sweep behavior.
