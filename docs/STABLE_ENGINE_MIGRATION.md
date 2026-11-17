# Stable 0.10.1 engine migration

This document records dated migration measurements. Installation selections,
local capture paths and retained fallback builds below describe those runs,
not a guarantee that those files still exist after cleanup. Current delivery
status is in [DISTRIBUTION.md](DISTRIBUTION.md) and the [README](../README.md).

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
and original file hashes. The separately pinned official 0.10.1 application archive
supplies the release-only pipeline list, controller art, toolchain lock and credits.
Its size and SHA-256 are verified before selective bounded extraction. Neither
that archive nor the derived pipeline metadata enters the Git repository. Runtime
binaries from the archive are not extracted or substituted for our native build.
A changed release-data identity invalidates shader preparation while preserving
completed native compilation and extracted input. The stable shader-stage key alone
does not include the presence of this release-only data, so this explicit
invalidation is necessary.
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
build library and save management remain the project's own UI. The separate 0.11.0 layer described below now supplies the own game-menu skin
and Cheat Manager; individual cheat scenarios still need acceptance.

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
The first ordinary start reproduced temporary incomplete draws while compiling
pipelines: it had no pipeline keys from the source-only build. Its next start
prebuilt 500 recorded pipelines (zero failures or remaining jobs) before play,
measured 47.36 average FPS and a 20.63 FPS one-percent low over 951 gameplay
intervals, and logged zero incomplete frames shown at the available checkpoint.
This exposed the missing release-only list: the verified 0.10.1 release supplies
9,814 pipeline records and 7,447 associated shader variants. The completed
release preparation and activation are recorded in the later section below. `--capture` enables bounded frame recording and settings-page captures.

The launcher build route is the same `build_independent` route exercised by
`run_builder.py`. Successful builds receive version metadata and enter the build
library; discovery also recognizes completed stable builds after a restart.
An unchanged archive identity can use the stable builder's `--rebuild` mode;
a changed archive or incomplete extraction uses the selected NUP again.

The stable translator's synthetic smoke test passed, including malformed-request
recovery and SPIR-V validation. The project test suite covers archive integrity, safe extraction, input reuse,
release-data invalidation and destination protection. The separate launcher
self-test rendered 40 views in five languages with the correct project logo,
verified native icon and one top-level window.

Older experimental render PNG sets and their reproducible shader cache were
removed to provide build space. The latest raw-depth capture, test logs, input
dump, original game and save profiles were retained.

## Completed release test and activation

The complete release-data preparation finished successfully in 24.8 minutes,
reusing the extracted game and native compilation. It translated 49,208 variants,
built the applicable release pipelines and completed 42,239 driver-library builds
with zero failures. All seven sets of controller/keyboard prompts were generated.
The release archive identity is recorded beside the completed build.

For the first-start check, this installation's own `pipeline-keys.bin` and
`pipeline-cache-play.bin` were renamed to retained backups. The ordinary startup
therefore used the release seed, not our previously learned route. It read 9,814
records, built 6,384 pipelines, recognized 3,429 duplicates and dropped one record
whose shader this game version does not contain. It left zero builds in the
background and reported zero failures; prewarming took 3.163 seconds.

The local performance profile retains the reference's `lib_warm=0`, also sets
`lib_prebuild=0`, and uses `prewarm_full=1`: known graphics pipelines finish before
play, while unused compute/library compilations do not compete with drawing. The
ordinary-start trace had shown a four-thread library warm resuming during play;
turning that extra background work off changes configuration, not the renderer.
A new build carries the active build's graphics/controller preferences only when
its engine revision matches, and never overwrites an existing destination config.

The ordinary 60-second world run completed with exit code 0. All 3,276 presentation
intervals from world start were present: 60.180 seconds, 54.44 average FPS, 22.56 FPS
one-percent low, 17.730 ms median and 103.741 ms maximum. Periodic full-window
screenshots and two frame-recording dumps were enabled, so this includes capture
overhead. The final runtime frame-time window reported 55.9 FPS and a 48.8 FPS
one-percent low; that narrower interval is not substituted for the complete run.

Both 90-frame recordings reported zero skipped pipeline draws and zero skipped
shader draws. Their game-clock/wall-clock ratios were 0.9998 and 1.0011. The
assistant inspected the final screenshot and the twelve largest adjacent-image
changes: terrain, rocks, foliage, cloud detail and Link remain complete, with
PlayStation R1/R2 prompts visible. This validates the captured route, not every
area in the game.

The actual `Launcher.play()` action was then invoked with the selected executable
and no command-line arguments. The game reached the world and closed through its
window close handler with exit code 0. The launcher hid while playing and returned
to the same single window afterwards (52.06 seconds total). At that point the active installation
was set to `build/stable-windows-game/DekuForgeGame.exe`; the previous preference
file was backed up. The original reference installation and save files were not
modified. The test game and test launcher are closed.

Recorded evidence was local; some bulky captures were subsequently removed
during owner-authorized cleanup. Referenced original paths included: `dekuforge-validation.json`, `test-stable-world.png`,
`validation-frames/final-largest-differences.jpg`, `test-launcher-play.log` and
`local/launcher-play-smoke.json`. None of these game-derived artifacts enter Git.
`run_builder.py --doctor` reports the completed build and separately scoped local
world test; full platform parity remains a separate gate.

## Native tool provisioning

The stable release toolchain lock pins 31 native packages (170 MB compressed).
The three original bootstrap modules are included in the verified source manifest;
`tools/bootstrap_stable_toolchain.py` installs them under
`local/build-tools/native/msys64/ucrt64`. Previously downloaded archives can be
reused only after matching their pinned size and SHA-256. The owned installer checks the pinned lock on every build; an installed external
launcher is not required.
The shader compiler/linker tools and pinned .NET SDK are provisioned when missing.
Python dependencies, including Pillow/fonttools for controller prompts, are listed
in `requirements-engine.txt`.

The owned native toolchain was installed using 31 verified cached packages, without
changing the reference installation. Clang, clang++, SDL3.dll and the SDL import
library matched the reference bytes. The owned compiler then compiled and ran a
SDL/Vulkan probe successfully (SDL 3.4.20, Vulkan loader 1.4.341). A fresh machine's
full network download and final installer still need independent acceptance.

## Remaining delivery work

- Test additional scenes, save/write/load, controllers and audio interactively;
  movie decoding already logs 1920x1080 AV1 at approximately 60 presented FPS.
- Validate native-tool downloads and first-time setup in a clean Windows environment;
  owned local tool provisioning has passed the pinned-package and compile/run checks.
- Validate the composed custom cheats and game-menu extensions individually,
  without replacing the validated stable renderer.
- Validate a complete first-time wizard build on a clean installation.

## DekuForge 0.11.0 candidate and independent launcher bootstrap

The isolated 0.11.0 candidate composes the owned Cheat Manager patch and a new
forest-green ImGui skin over the pinned stable core. This includes Equipment and
World groups, the existing black-aura bomb-arrow implementation and the dynamic
maximum-heart refill fix. Individual cheat scenarios still need acceptance tests.
The settings header, boot skin and both performance displays use DekuForge branding.

A normal-start 20-second world capture completed with exit 0 and averaged 51.37 FPS.
The captured world and Cheats tab were visually checked: complete terrain, rocks,
grass, clouds, Link and controller prompts. This short result includes capture
and UI-test overhead and is not a new multi-scene parity claim. The candidate was subsequently selected locally. The original migration baseline
was removed through build management; it is not a retained fallback today. The
separate original NX2navi installation remains outside DekuForge management.

An incremental rebuild using DekuForge's own versioned Python runtime took 26.1
seconds: two files compiled, 722 retained, and unchanged shader/pipeline products
were preserved only after source, translator and seed comparison. Separate engine,
launcher, buildkit, input-game and local build identities are recorded in metadata.

See [DISTRIBUTION.md](DISTRIBUTION.md) for the launcher-only package and successful
empty-folder runtime-download test. Full fresh-machine game-building acceptance
remains incomplete. Application release installation is implemented and locally
tested; see the separate setup/update acceptance limits in DISTRIBUTION.md.
