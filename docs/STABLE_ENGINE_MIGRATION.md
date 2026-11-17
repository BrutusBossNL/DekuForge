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

## Local migration run (2026-11-17)

Destination: `build/stable-windows-game`, separate from both existing games.
Game input: 1.1.1 build `e0f3ccfa`. The 26.24 GB RomFS image was assembled and
checked. Native compilation/linking completed (719 files, 848 seconds).
The first complete build took 46.3 minutes. All 42,142 shader variants were
prepared and built for the driver: zero failures, zero skipped variants.
The final content scan checked 186,583 files and found no damaged content.

Hardware: NVIDIA GeForce RTX 2080, driver 617.42, Windows. Output is 1080p
with DLSS Quality (1280x720 scene reconstructed to 1920x1080). Frame generation
is off. Testing uses a separate copy of the existing test profile; the original
installation, preferences and saves remain untouched.

Three bounded game runs exited normally. The cold first run included substantial
pipeline compilation stalls. The next moving-world run measured 35.93 average
FPS, 25.75 FPS one-percent low, and 53.705 ms maximum frame interval over all
720 presentation intervals after the world clock started (20.039 seconds).
The recorder-enabled repeat measured 35.80 FPS and a 25.40 FPS one-percent low
over 718 intervals (20.056 seconds). These are presentation cadence measurements,
not GPU timings. Loading/title frames are excluded by the explicitly recorded
world-clock boundary rather than by removing slow gameplay samples.

The assistant's image viewer now works. The final world screenshot and a contact
sheet from two recorded sequences show complete terrain, rock textures, grass,
Link and cloud detail. No former large disappearing surfaces were visible in the
reviewed images. This is scoped visual evidence, not a claim that every scene or
all temporal artifacts have been tested. The first complete 90-frame trace reports
about 0.99 game seconds per wall second and no frames with zero draws.

Four in-game settings pages were rendered and captured. The stable engine provides
Screen, Game, Sound and Controls, including video/upscaler options. F1 opens this
menu; F10 controls the performance overlay. The visible menu version label is
adapted to DekuForge without changing the renderer.

Important test distinction: `--shot` disables asynchronous pipeline building for
deterministic captures. `tools/test_stable_game.py` now defaults to the ordinary
startup route, with periodic captures; `--deterministic-shot` remains explicit.
Ordinary startup/prewarm verification follows the deterministic baseline before
activation. `--capture` enables bounded frame recording and settings-page captures.

The launcher build route is the same `build_independent` route exercised by
`run_builder.py`. Successful builds receive version metadata and enter the build
library; discovery also recognizes completed stable builds after a restart.
An unchanged archive identity can use the stable builder's `--rebuild` mode;
a changed archive or incomplete extraction uses the selected NUP again.

The stable translator's synthetic smoke test passed, including malformed-request
recovery and SPIR-V validation. All 69 project tests pass. The separate launcher
self-test rendered 40 views in five languages with the correct project logo,
verified native icon and one top-level window.

Older experimental render PNG sets and their reproducible shader cache were
removed to provide build space. The latest raw-depth capture, test logs, input
dump, original game and save profiles were retained.

## Remaining delivery work

- Complete ordinary startup/prewarm and launcher Play validation of the final binary.
- Test additional scenes, save/write/load, controllers and audio interactively;
  movie decoding already logs 1920x1080 AV1 at approximately 60 presented FPS.
- Activate only the tested installation; retain the previous entry for rollback.
- Complete fresh-machine compiler/SDK provisioning; this PC currently reuses its
  installed native toolchain and an independently installed .NET SDK.
- Bring over custom cheats and related game-menu extensions after the desktop
  baseline gates, without replacing the validated stable renderer.
- Validate a complete first-time wizard build on a clean installation.
