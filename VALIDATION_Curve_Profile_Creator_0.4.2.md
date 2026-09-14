# CPC 0.4.2 — Blender Extension Compliance Validation

0.4.2 is a compliance/storage-only release. The target is behavioral equivalence with validated 0.4.1 plus Blender Extension storage compliance.

## 1. Install / version
1. Install `curve_profile_creator-0.4.2.zip` in Blender 5.2.
2. Confirm CPC reports version 0.4.2.
3. Confirm Basic, Constructed, Architectural, Build Profile, User Profiles and Sweep sections appear normally.

## 2. Default User Profiles directory
With **Library Location > Folder** blank, run in Blender's Python Console:

```python
import bpy
from bl_ext import *
```

Rather than depending on the repository namespace manually, the practical validation is:
1. Save a new preset with the CPC Folder field blank.
2. Expand **Library Location** and confirm the UI identifies the blank default as Blender extension user storage.
3. Confirm `.cpcprofile` and `.png` are created and the preset appears in both dropdown and thumbnail selection.

For source-level confirmation, CPC 0.4.2 uses:

```python
bpy.utils.extension_path_user(__package__, path="profiles", create=True)
```

## 3. Hosted-release startup behavior
1. Install/enable 0.4.2.
2. Confirm extension registration does not scan or copy from earlier private-development profile locations.
3. Confirm no viewport draw handlers are added merely by enabling the extension.
4. Start a CPC placement operator or viewport dimension-edit operator and confirm the overlay appears normally.
5. Toggle the Viewport Guides property and confirm handlers are created/removed through explicit user interaction.

Existing private-development libraries remain accessible by selecting their folder explicitly under **Library Location**; there is no automatic migration in the hosted build.

## 4. Existing PARAMETRIC preset
1. Load a validated 0.4.1 PARAMETRIC preset.
2. Use Edit Active Profile.
3. Change one semantic dimension and one child Rotation Offset.
4. Recommit.
5. Save a new preset and reload it.
6. Confirm geometry and editability remain correct.

## 5. Existing STATIC preset
1. Load a validated 0.4.1 STATIC preset.
2. Confirm geometry matches the saved profile.
3. Confirm it is not presented as editable CPC construction.
4. Confirm it remains usable as a sweep profile.

## 6. Custom User Profiles path
1. Choose a custom Folder under Library Location.
2. Save a PARAMETRIC and STATIC preset.
3. Confirm JSON and PNG files are written to that folder.
4. Refresh and reload them.
5. Clear the Folder field and confirm CPC returns to Blender extension user storage.

## 7. Modelling regression
Test at least:
- Chamfer `W/H/F`;
- Nose + Cove independent depths;
- one Cyma Circular component;
- one deliberate child Rotation Offset;
- viewport numeric scrubbing;
- Commit -> Edit Active Profile -> Recommit;
- one sweep linked across recommit.

Expected: no behavior change from 0.4.1.

## 8. Official validator
Run with Blender available:

```text
blender --command extension validate curve_profile_creator-0.4.2.zip
```

Expected: validation succeeds with no manifest errors.

## Acceptance
0.4.2 is accepted when the official extension validator passes, default preset storage uses Blender extension user storage, extension startup performs no legacy-library migration or eager draw-handler registration, custom folders still work, and all frozen 0.4.1 modelling/preset behavior remains unchanged.
