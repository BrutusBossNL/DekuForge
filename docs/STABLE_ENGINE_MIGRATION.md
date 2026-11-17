# Stable 0.10.1 engine migration

The owner selected the complete stable 0.10.1 engine as the new game backend.
Pinned revision: `5ae55db41c7d11c4e997d2676019939a936e560b` (tag `v0.10.1`).
The old 0.3.10 import and its experimental extensions are retained for provenance
and investigation; they are not the launcher game-build route.

## Active path

`build_independent` now delegates explicitly to `dekuforge/stable_engine.py`.
It exports the pinned source into owned `build/engine-0.10.1`, preserving source
notices and LICENSE-ADDITIONS. The local reference repository can supply the Git objects. Without it, the
exact commit archive is downloaded from GitHub. Every selected source file is
checked against `dekuforge/stable_engine_source.json`; missing or changed bytes
stop staging before a build can run. The source manifest records the revision
and original file hashes.
The source is not committed or relabeled as MIT. Original DekuForge orchestration
remains under its existing license.

The stable source builder performs extraction, RomFS assembly, CPU generation
with its full version-specific patch table, native compilation/linking, shader
preparation, button prompts and scanning. Its structured progress events feed
the existing single-window DekuForge launcher in all five UI languages.
A failed build does not select an installation or alter the active game's saves.
An owned marker is required to reuse a nonempty destination.

The exact stable AmpereLowering.cs and MeshSpirv.cs are used. The migration
translator is a self-contained .NET 10 single-file executable because this
machine lacks the MSVC NativeAOT linker. It has a distinct translator identity;
no cache is falsely presented as NativeAOT output. No experimental GLSL mesh
wrapper is applied. `tools/build_stable_translator.py` reproduces this build.

Visible application titles and executable names are adapted in the owned
workspace, and the project icon is supplied. The DekuForge launcher, settings,
build library and save management remain the project's own UI. Further game-menu
and cheat-manager integration follows verified core rendering.

## Local migration run

Destination: `build/stable-windows-game`, separate from both existing games.
Game input identified as 1.1.1 build e0f3ccfa. The 26.24 GB RomFS image was checked
and completed. CPU lifting and native compilation/linking completed (719 files, compile stage
848 seconds). The executable is approximately 305 MB. Stable shader preparation
is now running against 42,142 shader combinations.
The stable shader translator has been built from the pinned source. Its own
synthetic smoke test passed: constant fragment output, image reads, array-layer
query, malformed-request recovery and SPIR-V validation. The 67 project tests
also pass, including source-integrity and destination-protection checks.
The isolated profile and graphics/controller settings were copied from local test
data and the working reference; active installations and saves were not changed.
The matching pinned DLSS library and its vendor notice are present. No visual
acceptance, gameplay performance or playable-release claim yet.

Older generated render PNG sets were removed to provide build space; the latest
raw-depth capture and test logs were retained. Existing game installations,
input dump and save profiles were preserved.

## Remaining delivery work

- Finish native compilation and the stable shader/pipeline preparation.
- Copy a save into the isolated profile and compare the same moving scene.
- Confirm terrain, sky, foliage, shadows, movies, timing, controllers and audio.
- Activate only the verified installation; retain the previous one for rollback.
- Complete fresh-machine compiler/SDK provisioning; source retrieval no longer
  requires an installed NX2navi checkout.
- Integrate custom game menus and cheats without changing the validated renderer.
- Verify the complete launcher wizard from the user's NUP selection.
