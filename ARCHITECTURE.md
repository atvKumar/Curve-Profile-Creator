# Curve Profile Creator — Architecture 0.4.2

## 1. Product model

CPC is construction-first:

`geometry kernel -> semantic role -> packed component -> complete profile -> reusable preset -> sweep`

The semantic recipe is authoritative for CPC-parametric reconstruction. The committed Blender Curve is the generated/editable profile representation.

## 2. Persistent contract

Supported persistent data begins with the 0.4.x baseline:

- embedded recipe schema: **11+**;
- transform schema: **1**;
- per-component transform: `matrix_profile`;
- `.cpcprofile` preset format: **v1**;
- PARAMETRIC and STATIC user profiles;
- geometry-authority hash for editable preset certification.

## 3. Transform model

Commit establishes a normalized Profile Frame. Components are stored in profile space using Blender `mathutils.Matrix`:

`M_profile_component = inverse(M_profile_frame) @ M_component_world`

Restore/place uses:

`M_component_world = M_placement_frame @ M_profile_component`

`cpc_part_rotation` remains separate semantic user intent and is never flattened into recipe-derived base orientation.

## 4. User Profiles storage

`.cpcprofile` JSON is authoritative; PNG previews are regenerable cache files.

The default writable library is:

```python
bpy.utils.extension_path_user(__package__, path="profiles", create=True)
```

This follows Blender's Extension storage model and does not assume the installed extension directory is writable.

A user-configured custom profile-library path remains supported and takes precedence over the default.

### Hosted-release storage policy

0.4.2 is CPC's first Blender Extensions hosted release. Extension registration performs no automatic migration or scan of earlier private-development storage locations. The Blender-managed extension user directory is the default, while a user-configured custom profile-library path remains available when an existing library needs to be opened explicitly.

## 5. Permissions

The manifest declares `files` because CPC reads/writes User Profile JSON and PNG files and supports optional custom profile-library folders. CPC requires no network permission and has no PIL/Pillow dependency.

## 6. Runtime modules

- `primitive_geometry.py` / `compound_geometry.py`: analytic geometry.
- `primitives.py`: Blender Curve primitive creation/regeneration and endpoint semantics.
- `constructed_shapes.py`: canonical line-based point chains.
- `architectural_recipes.py` / `architectural_components.py`: packed component recipes and regeneration.
- `junctions.py` / `connected_transforms.py`: connectivity and hosted relationships.
- `placement_parameters.py`: common semantic placement vocabulary.
- `viewport_overlay.py` / `viewport_semantics.py`: viewport presentation and semantic editing.
- `profile_transforms.py`: normalized Matrix transforms.
- `profile_presets.py`: pure preset validation/hashing/remapping.
- `user_profiles.py`: preset library, automatic preview generation and Blender-owned user storage.
- `operators.py`, `properties.py`, `ui.py`: interaction and presentation.
