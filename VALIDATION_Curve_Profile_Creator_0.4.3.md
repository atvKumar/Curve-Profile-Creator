# CPC 0.4.3 — Validation

0.4.3 changes User Profile library organization/indexing only. The validated modelling baseline must remain unchanged.

## 1. Install / version
1. Install `curve_profile_creator-0.4.3.zip` in Blender 5.2.
2. Confirm CPC reports version 0.4.3.
3. Confirm User Profiles shows Category, `[ + ]`, `Manage`, Search, Preset dropdown and thumbnail grid.

## 2. Existing 0.4.2 presets
1. Use a library containing validated 0.4.2 PARAMETRIC and STATIC presets.
2. Press Refresh.
3. Confirm both load and their PNG previews display.
4. Confirm presets without classification metadata appear under `Uncategorized`.
5. Confirm `.cpcprofile` format remains v1 and PARAMETRIC recipe schema remains 11+.

## 3. Category creation
1. Click `[ + ]` beside Category.
2. Add `Test Category`.
3. Confirm it becomes selectable immediately even while empty.
4. Restart/disable-enable CPC and confirm the category persists via `cpc_library.json`.
5. Confirm case-insensitive duplicate and blank names are rejected.

## 4. Category rename
1. Select a real category and click `Manage`.
2. Rename it.
3. Confirm matching presets move to the renamed category.
4. Compare one affected preset before/after: only category metadata should change.
5. Confirm preset ID, geometry, recipe, matrices and preview filename/content remain unchanged.
6. Confirm rename-to-existing is rejected rather than merged.
7. Confirm `All Categories` and `Uncategorized` cannot be managed/renamed.

## 5. Save Profile metadata
Save one PARAMETRIC and one STATIC profile with:
- Category;
- comma-separated Tags;
- optional Source Collection and Reference.

Confirm:
1. classification/source metadata appears in JSON;
2. PNG thumbnail is generated;
3. the newly saved preset appears in both dropdown and thumbnail views;
4. PARAMETRIC/STATIC certification behavior matches 0.4.2.

## 6. Edit Info
1. Select a preset and click Edit Info.
2. Change name, description, category, tags and source metadata.
3. Confirm the physical `.cpcprofile` filename may remain unchanged.
4. Confirm geometry, recipe, preset ID and PNG are not regenerated.
5. Confirm the metadata index/UI updates immediately.

## 7. Category browsing
With Search empty:
1. choose several categories;
2. confirm dropdown and thumbnail grid show the same filtered preset set;
3. confirm the visible/total profile count updates;
4. confirm the selected preset falls back cleanly when filtering hides it.

## 8. Global Search
1. Select a category that does **not** contain a known profile.
2. Enter that profile's name/tag/source text in Search.
3. Confirm it appears anyway: Search is global across categories.
4. Test multi-word search terms.
5. Clear Search and confirm the previously selected Category filter becomes active again.

Search should match case-insensitively against name, description, category, tags and source metadata.

## 9. Preview-index behavior
For a large library if available:
1. Refresh the library.
2. Change Category repeatedly and run global searches.
3. Confirm browsing stays responsive.
4. Delete one visible PNG and revisit that preset; confirm CPC regenerates the missing thumbnail from `.cpcprofile` geometry.
5. Confirm panel redraw/filter changes do not repeatedly parse every preset JSON file.

## 10. Custom library path
1. Switch to a custom User Profile folder.
2. Confirm its category registry/index is independent of the default library.
3. Add/rename a category in the custom folder.
4. Return to the default folder and confirm its category vocabulary is unaffected.

## 11. Modelling regression
Test at least:
- Chamfer W/H/F;
- Nose + Cove independent depths;
- one Cyma Circular component;
- one deliberate child Rotation Offset;
- viewport numeric scrubbing;
- Commit -> Edit Active Profile -> Recommit;
- PARAMETRIC preset Save -> Load -> Edit -> Recommit;
- STATIC preset load and sweep;
- one sweep linked across recommit.

Expected: no modelling behavior change from the validated baseline.

## 12. Reopened `.blend` profile-edit state
1. Open a `.blend` containing several committed PARAMETRIC CPC profiles, with their original construction parts absent/hidden.
2. Select one committed profile directly in the 3D Viewport or Outliner without changing the Sweep Active Profile field.
3. Click **Edit Active Profile**.
4. Confirm the selected profile becomes the CPC Active Profile automatically.
5. Confirm its construction parts are restored and the first restored part becomes active.
6. With Viewport Guides already enabled before opening the file, confirm the overlay appears immediately after invoking Edit Active Profile; do not cycle the toggle.
7. Repeat with a different committed profile and confirm the newly selected profile is edited rather than the previous sweep profile.

## 13. Hosted-release compliance regression
1. Confirm the manifest keeps the public GitHub Issues `support` URL.
2. Confirm extension registration itself installs no viewport draw handlers.
3. Confirm opening a `.blend` alone installs no viewport draw handlers.
4. Trigger Edit Active Profile or another CPC viewport interaction and confirm handlers are created lazily.
5. Disable CPC and confirm `shutdown()` removes any active handlers.
6. Confirm no automatic migration/copy from earlier private-development profile locations occurs.

## 14. Official extension validator
With Blender available:

```text
blender --command extension validate curve_profile_creator-0.4.3.zip
```

Expected: validation succeeds.

## Acceptance
0.4.3 is accepted when category creation/rename, global search, metadata editing and indexed/lazy thumbnail browsing work as specified while all protected CPC modelling/persistence behavior remains intact.
