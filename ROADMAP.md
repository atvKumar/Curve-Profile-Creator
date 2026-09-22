# Curve Profile Creator — 0.5.0

## Roadmap

### Development milestone — Sweep Assemblies

CPC 0.5.0 introduces a new construction layer above complete profiles: **Sweep Assemblies**.

A Sweep Assembly combines multiple complete CPC profiles into one reusable cross-section arrangement that can be edited hierarchically and applied across multiple scene Curve paths.

The validated CPC 0.4.4 release remains the implementation baseline.

## 0.5.0 primary goals

### 1. Multi-profile Sweep Assemblies

Allow two or more complete profiles to be arranged as one assembly.

Each member retains:

- its own complete profile payload;
- stable member identity;
- canonical Offset X/Y;
- Rotation;
- Flip X/Y;
- Uniform Scale;
- optional source provenance.

The assembly uses the 0.4.4 canonical placement model rather than a new transform authority.

### 2. Visual assembly authoring

Support **Create Sweep Assembly from Selected Profiles**.

Users may arrange complete profiles visually in the profile plane, select them, and capture their relative arrangement as one Assembly Definition.

### 3. Embedded profile variants are authoritative

Adding a User Profile to an assembly copies its complete usable payload into the assembly.

After insertion, the embedded member variant is authoritative.

Ordinary assembly editing must never overwrite the source User Profile preset.

This includes:

- Edit Member Profile;
- Recommit Profile;
- member placement changes;
- Recommit Assembly;
- instance refresh.

Source preset identity/hash is retained only as provenance.

### 4. Safe explicit source-preset actions

Assembly members may expose explicit secondary actions:

- **Save as New User Profile** — preferred/default;
- **Update Source User Profile…** — deliberate overwrite with confirmation;
- **Reload from Source…** — deliberate replacement of the embedded variant.

Recommit must never be overloaded to mean "write back to the library."

### 5. Nested assembly/member editing

The intended workflow is:

```text
Edit Assembly
→ select member
→ Edit Member Profile
→ edit normal CPC construction
→ Recommit Profile
→ return to Assembly Editor
→ adjust relative placement
→ Recommit Assembly
→ refresh assembly instances
```

Other members remain visible as locked/ghosted context while one profile is edited.

Recommit Profile updates only the assembly working copy.

Recommit Assembly updates the authoritative Assembly Definition.

### 6. Non-destructive working-copy editing

Starting Edit Assembly does not mutate the committed Assembly Definition.

The committed JSON remains unchanged while temporary authoring objects represent the working copy.

Therefore:

```text
Edit Assembly
→ working authoring objects

Cancel
→ discard working objects
→ committed assembly unchanged

Recommit Assembly
→ serialize working objects
→ replace committed assembly definition
```

### 7. Multi-Curve application

One active assembly can be applied to multiple selected Curve paths in one operation.

For M enabled assembly members and N source paths, CPC may generate M × N CPC-owned sweep children.

Existing Single Profile Sweep remains available and behaviorally compatible.

### 8. Stable assembly instance relationships

Generated results must be traceable through stable IDs rather than object names.

The scene relationship is:

```text
Assembly Definition
        ↓
Assembly Instance
        ↓
Source Path(s)
        ↓
Generated Sweep Children
```

Refresh affects only CPC-owned children belonging to the selected assembly/instance and never edits source paths or unrelated geometry.

### 9. Portable `.cpcassembly` v1

Introduce a self-contained Sweep Assembly document format separate from `.cpcprofile`.

A valid `.cpcassembly` must reconstruct all member profiles without requiring the original User Profile library.

The existing `.cpcprofile` format v1 remains unchanged.

## Protected 0.4.4 baseline

0.5.0 development must preserve:

- recipe schema 11+;
- transform schema 1;
- `.cpcprofile` format v1;
- PARAMETRIC / STATIC behavior;
- canonical complete-profile placement;
- in-place profile Recommit;
- semantic component Size and neutral Object Scale;
- explicit endpoint reconnection;
- User Profile Categories/Search/indexing;
- persistent custom User Profile path;
- existing single-profile Sweep;
- 2D Caps / Fill Mode semantics;
- lazy viewport overlay lifecycle.

## 0.5.0 release acceptance

0.5.0 is accepted when:

1. a two-member assembly can be created visually from complete CPC profiles;
2. member payloads are self-contained and survive deletion/change of their source presets;
3. PARAMETRIC members can be reopened and Recommitted inside an Assembly Edit session;
4. other members remain visible as non-editable context during member editing;
5. member Recommit preserves member ID, relative placement, ordering, and provenance;
6. Cancel Member Edit restores the member working copy;
7. Cancel Assembly Edit restores the complete committed assembly;
8. Recommit Assembly refreshes matching scene instances safely;
9. one assembly can be applied to multiple selected Curve paths;
10. generated children retain stable assembly/member/path/instance relationships;
11. `.cpcassembly` save/load round-trips PARAMETRIC and STATIC members;
12. ordinary assembly editing never modifies User Profile preset files;
13. Save as New User Profile creates a separate preset;
14. Update Source User Profile requires explicit confirmation;
15. existing Single Profile Sweep and 0.4.4 production behavior remain valid;
16. automated and production Blender validation pass.

## Deferred beyond the core 0.5.0 milestone

Candidates for later work include:

- assembly thumbnail previews and indexed browser;
- Path Roles such as CROWN / BASE / PANEL;
- tagged-path and collection-wide application;
- optional source-difference comparison UI;
- selective member refresh;
- controlled live refresh;
- room-wide trim packages;
- higher-level architectural path discovery;
- WebP preview storage;
- public profile/assembly library tooling.
