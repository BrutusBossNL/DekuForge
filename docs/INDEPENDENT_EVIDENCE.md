# Reusing earlier evidence without repeating failed experiments

This ledger carries forward earlier results. It does not turn old logs, source
tests or screenshots into acceptance of the independent engine. The stable
`main` branch and its installed games remain unchanged. Do not run old harnesses
against those installations: several write settings, captures or profiles. Read
existing records; use isolated copies for future gameplay tests.

## Established results

| Finding | Existing evidence | Decision for the new engine |
| --- | --- | --- |
| Experimental renderer failed gameplay acceptance | [Gap analysis](RENDERER_GAP_ANALYSIS.md), `146ed30`; [Windows investigation](WINDOWS_BUILD.md) | Do not revive it as the default renderer or call a clean exit a successful game. |
| Task/mesh/compute constant-bank cache aliasing was a real defect | `e44d2b5`; `tools/check_compute_bank.py`; Windows investigation, "Task and mesh constant-bank isolation" | Preserve stage identity in future cache keys. This repair did not eliminate world holes. |
| Mesh GLSL round trip lost FMA precision decorations | Windows investigation, FMA/NoContraction measurements; `tools/check_mesh_resources.py` | Avoid that lossy route or prove instruction/decorations survive. FMA repair alone did not fix flicker. |
| Replay counter ordering needs report serials and deferred-write ordering | `dbecdb9`; original `engine_overrides/condition_records.h`; `tools/check_condition_records.py` | Retain this original algorithm/test as reusable work. It is not a complete rendering fix. |
| Skipped conditional draws did not explain holes in the traced interval | Windows investigation, frames 2600-2615: no conditionally skipped draws; six skipped depth clears/frame | Do not force every draw visible as a presumed repair. Investigate ordered operations in a new failing trace. |
| Fully awaited shader/pipeline creation still produced holes | `284f166`; synchronous test in Windows investigation and gap analysis | Do not repeat synchronous waiting alone as the corruption fix. Still prewarm known pipelines for stalls. |
| GEQUAL/ALWAYS depth overrides broke occlusion | Gap analysis, exact-depth evidence | Never ship these diagnostics as a fix. Preserve correct depth rules. |
| Raw depth diverged before the color pass | Gap analysis: 56.6681% exact source/target agreement, 575,042 values differing by more than one ULP; later trace showed full-size copy | Capture immediately around the relevant copy/clear. This did not prove a broken copy/root cause. Individually normalized depth PNGs cannot prove float equality. |
| FPS and game-clock speed are separate properties | `772ab05`, `284f166`; `tests/test_frame_timing.py` | Retain the original timing-bridge model/test. Compare game time with wall time. |
| Heavy diagnostics distorted performance | Windows investigation: about 15-16 FPS instrumented, ordinary rendering later 32.4 FPS and clock ratio 0.999 | Separate gameplay cadence and targeted profiling. Record instrumentation. |
| Movie reconstruction improved cadence, not all world defects | `a948499`, `5238fd4`; Windows investigation | Retain scoped movie results; do not rerun this as a terrain fix. New integration still needs validation. |
| Stable migration needed release-only pipeline seed data | `b9ed2f5`, `aeb9a1d`; [migration record](STABLE_ENGINE_MIGRATION.md) | Source compilation alone did not reproduce first-play behavior. Generate permitted independent seeds; do not silently reuse unapproved release data. |
| Stable main has a useful, scoped gameplay baseline | Migration record: RTX 2080, 1080p, DLSS Quality, 60.180 seconds, 54.44 average presentation FPS; own 0.11.0 candidate later 51.37 FPS/20 seconds | Preserve as historical measurements, not a universal target for every scene. Compare matched settings/workloads before replacement. |

Some bulky artifacts were deleted during authorized cleanup. A removed capture
path remains a historical observation, not raw evidence available today. Never
claim to have re-viewed deleted imagery.

## Reusable work and scope

- Existing launcher, archive, normalization, RomFS, settings and save tests stay
  in the suite. Do not rebuild those original components for this branch.
- `dekuforge/arm64_models.py` and existing half-precision/dot-product oracle checks
  remain the starting point for those families. They are models, not an integrated
  native SIMD backend.
- The original replay ledger/native fixture remains available. Other old harnesses
  call `stage_engine()` or extract baseline functions: they test that historical
  composition. Adapt their contracts when the new implementation exists instead
  of calling them evidence for a different renderer.
- `tools/measure_game_frames.py` remains the cadence calculator. A source-only CPU
  edit does not need another unchanged movie benchmark or multi-gigabyte build.

Reuse rights and test validity are separate checks. A good result does not permit
porting restricted code. Original regression conditions can be retained even when
the implementation must be replaced.

## Evidence rules

Record revision, component identity, input build ID, scope, machine/driver,
settings, instrumentation and available artifact hashes for new results. Reuse
an earlier result only for its unchanged component and tested contract. Changed
CPU emission needs affected native/oracle tests; a changed renderer needs new
moving-scene evidence and comparable measurements.

Classify results as source/native contract, static-input analysis, diagnostic game
run or accepted gameplay. Source passes cannot promote gameplay gates. Owner
observations of holes/flicker override attractive still-image metrics. Compare
against `main` without modifying it. Acceptance requires all gates in
[INDEPENDENT_ENGINE.md](INDEPENDENT_ENGINE.md).

## 2026-11-18: independent CPU memory addressing

Engine `0.1.0-independent.3` adds original integer LDP/STP/LDPSW and scalar
register-offset addressing. `test_independent_pairs.py` executes 770 encodings
under three memory seeds (2,310 full-state/memory oracle comparisons);
`test_independent_register_memory.py` executes 1,248 encodings with six seed/index
combinations (7,488 comparisons). Both compare emitted native C with Unicorn,
including registers, SP, PC, NZCV and memory. Separate native tests cover denied
second pair elements, adjacent mappings, stack save/restore and address wrap.
This is 9,798 additional comparisons, not game execution or a CPU benchmark.

Stricter V-bit masks now reject SIMD/FP loads/stores that the previous scalar
masks accepted incorrectly. This also invalidates part of the previous static
coverage classification; it is not a new implementation of those vector forms.

Read-only analysis reused the same three existing ExeFS module hashes as the
2026-11-17 memory report, with no new extraction or modification of the input.
Recognized words increased from 13,712,252 to 14,768,450 out of 18,162,788
(75.496% to 81.312%), including the stricter SIMD rejection. Main alone changed
from 11,972,673 to 12,829,922 recognized words out of 15,800,436. Text sections
can contain data: these figures establish neither dynamic execution coverage
nor playable-game progress as a percentage. Local reports retain module and
analysis-source hashes; their raw input bytes are not published.

The launcher also carries forward original image-lifetime cleanup from main
`a04e2c1` and the PagePanel `_event_root` naming fix from `ad48093`. These scoped
project-code repairs avoid worker-thread PhotoImage finalization and preserve
Tk's inherited `_root()` method. They do not import main's vendor backend or
update channel into the independent branch. Launcher identity advances to
`0.3.0-independent.2`; no installer or release is produced.

## 2026-11-18: module linker and owned launcher fixes

Engine `0.1.0-independent.4` adds original bounded MOD0/ELF symbol discovery,
RELA/RELR planning and transactional pointer writes. Seven synthetic tests cover
malformed input, GNU/SysV hashes, cross-module symbols, weak/absolute/protected
definitions, RELR bitmap windows and native sparse cross-module execution.
A private read-only probe planned 578,422 pointer relocations across the same
three local game modules. This is an in-memory linking result, not game boot.

Launcher `0.3.0-independent.3` carries forward main's owned mod manager, styled
release list, release notes, outcome reporting and updated installer-worker
validation. Main-channel installation, legacy code-mod builds and pending main
engine rebuilds remain disabled here. Mod management rejects game paths outside
this worktree before changing files. Synthetic boundary tests assert those
restrictions. Main issue 3's NVIDIA frame-generation packaging change belongs to
the excluded runtime and is not imported. No independent installer is produced.

The separately licensed runtime experiment is documented in
[INDEPENDENT_ENGINE.md](INDEPENDENT_ENGINE.md). Neither its successful source
generation nor shader-translator build is accepted as working gameplay.

## 2026-11-18: first licensed runtime rejected; direct NVN2 evaluation

The pinned Ocarina Recomp candidate compiled 664 objects and linked a private
313 MiB game executable. Its runtime self-test passed, including tables for
297,414 functions. Its source-built managed translator passed six constant-bank
checks and a synthetic shader service test, including SPIR-V validation and
recovery after malformed input. These are scoped development results.

A first ordinary-start run used a new account and therefore tested the title
and intro, not the copied save. After copying the account identity into the
isolated profile, another ordinary run loaded the existing Death Mountain save
and executed scripted movement/camera input. Original save hashes were unchanged.
Captures visibly show black Link/objects in shadow. The runtime still reported
zero unimplemented calls, validation errors and shader failures: those counters
cannot establish correct rendering. This candidate fails gameplay acceptance.

Its clock starts at the first present, including menus/loading. The recorded
startup average must not be presented as gameplay FPS. A separate attempt to
prepare all 45 encountered large compute variants was bounded to 600 seconds;
39 finished before the timeout during the 346,306-word variant. Disabling skipped
compute shaders has not been validated as a fix. Do not repeat this preparation
or call it completed without a new reason.

Full-size raw PNGs exceeded the image tool's output allowance. Local JPEG
inspection copies at 1280x720 opened successfully. Rejected-candidate raw PNGs
and generated outputs were subsequently removed to recover disk space; compact
inspection copies, source, canonical module inputs and measurement logs remain.
Use compact inspection copies/native crops before concluding that visual tools
require additional user permissions. Inspect actual presentation/crop behavior
separately from unused black padding in a raw render-target capture.

The second evaluation pins GPL Hookshot source at
`1c7e70bb035a7f45419b23882e73d7eb09b93e16`. All 2,188 original source blobs were
verified before use and rechecked unchanged during compilation. It uses direct
NVN2 translation rather than the first candidate's Ampere-to-Maxwell route.
Its lifter reports 294,518 discovered functions and no untranslated recognized
instructions in 17,646,126 sites, emitting 292 source files. This is a static
translation report, not execution coverage or gameplay acceptance.

The shader census generated a private 38,809-program / 42,856-stage seed from
the owner's own game input. No shared shader or pipeline cache was downloaded.
Generic compiler, header/codec and SDL tools were fetched with pinned hashes;
the engine/runtime itself is compiled from the audited source. The independent
build is still under evaluation; main is unchanged.

## 2026-11-18: direct NVN2 gameplay and DekuForge UI

The second candidate compiled 695 files without errors in 1,246 seconds on the
local Windows machine (NVIDIA GeForce RTX 2080). Its first local shader/pipeline
preparation took 369 seconds: 38,809 programs, 46,666 translated variants and one
reported shader failure. A rare stage-5 program reported a branch outside its
program. This remains an investigation item; do not describe preparation as
error-free. No compiled engine, game seed or pipeline cache was downloaded.

Death Mountain ordinary-start tests used an isolated copy of the owner's save.
The original save hashes stayed unchanged. A 59.663-second loaded-world interval,
after loading/events settled, produced 2,835 native frames: **47.517 average fps**,
48.15 median reported fps, at 1920x1080 output with the Vulkan native renderer.
No world screenshots were taken during this measurement. This is not a matched
main benchmark, a low-percentile result or a claim of stable 60 fps.

Separate instrumented captures show complete terrain, rocks, grass, sky and
correctly lit Link in shadow. Twelve successive Death Mountain frames and twelve
Kokiri frames were inspected as contact sheets; a native-size crop was also
inspected for terrain/character detail. No holes or flashes were visible in these
samples. A 44.747-second instrumented Kokiri interval produced 2,067 native frames
(46.193 average fps), including screenshot overhead. The debug age switch reached
the child map but the character still appeared adult: age switching is not
accepted as correct. Intro captures were black and do not validate movie playback.

Engine identity `0.1.0-independent.5` adds a DekuForge window title, startup logo,
menu build label and forest-green/gold panels without modifying the renderer.
Only affected UI translation units are generated into a separate adaptation
folder, with original/adapted SHA-256 records; the 2,188 source inputs stay
unchanged. The incremental compile took eight seconds with zero failures.

Original direct NUP-to-directory extraction now verifies each file, rechecks
hashes before resuming and commits a completion marker only after all files pass.
Four synthetic tests cover reuse, same-size corruption, interrupted extraction
and protection of unowned output/another builder's lock. Runtime metadata can
launch an isolated local build with explicit image, RomFS and save paths; it
rejects resources outside this worktree. These are infrastructure contracts,
not evidence that the default build wizard or standalone installer is finished.

The black intro was traced to the generic FFmpeg package lacking an AV1 decoder
and the Windows AV1 Store extension being absent. Building VideoLAN dav1d 1.5.4
with LLVM-MinGW/NASM resolved this locally: logs identify the dav1d decoder at
1920x1080; three successive intro frames and a native-size crop were inspected
and show the moving moon/sky, horse/rider and vegetation. The source archive and
source-tree hashes are pinned in `tools/build_av1_decoder.py`; its public command
was rerun successfully against the existing tool cache. No OS codec was installed.

Additional isolated runs reached Hyrule Field, Market and Forest Temple, completed
scripted input, exited normally and preserved the original save hashes. The
59.669-second Hyrule Field interval averaged 40.591 native fps. The dungeon test
included a deliberately opened settings overlay and screenshot work, so its
cadence is not a comparable gameplay benchmark. PrintWindow produced black for
the Vulkan window; this capture method does not establish UI appearance. Broader
save/write, actual controller/audio and long-session acceptance remain open.

## 2026-11-18: complete NUP composition and cache-policy correction

The complete GPL source pipeline produced a self-contained private installation
in `build/windows-independent`, with its own executable, image, RomFS, controller
libraries, AV1 decoder and save profile. All 186,583 RomFS files (26,236,422,768
bytes) were checked against the original NUP: zero mismatches. A fresh NUP
extraction/build then reused the compiler cache: 3 of 696 files compiled, with
six seconds reported for compilation. This does not measure a cold build.
The original NUP, main's runtime and original saves were preserved.

The first ordinary-start run of engine `0.1.0-independent.6` completed all 25,451
noted graphics pipelines and 9,925 compute variants, with none reported unmade.
This took 1,019.9 seconds after the separate prepare-only build process. A
60-second instrumented Death Mountain interval then averaged 45.907 native fps
at 1920x1080, with three scripted movements and normal exit. Twelve consecutive
settled-world captures show complete terrain and vegetation. However, the first
world capture was incomplete: this run is **not** an accepted rendering result.

The cause was narrowed to the provider's cache-only load policy on the measured
RTX 2080 driver: 4,832 graphics and 557 compute requests missed the prepared
cache. The provider wrote its own safety marker and selected full startup loading
on the next run. The independent runtime adapter now explicitly selects its
documented `RX_VK_LOAD=start` policy: known programs/pipelines are held ready
before the title. This needs its own gameplay/startup and memory measurements;
neither a fabricated cache marker nor disabled waits are an acceptable fix.

The original launcher issue fixes from main were retained: background/image
lifetime (issue #2), mod archive UI/order/toggles (issue #1), release list/notes,
async Play and update outcomes. Independent asset mods have their own merged,
verified snapshot adapter rather than relying on the old renderer's mod loader.
NVIDIA Frame Generation packaging from issue #3 is excluded with that engine;
this experiment contains no NVIDIA proprietary SDK and does not advertise it.

The local source suite passed 222 tests with 16 environment skips. Native launcher
self-test passed with its embedded icon, five languages and one unmapped window.
Commit `55b89d4` passed both Windows and Linux source CI; a Linux test-root length
assumption found in the preceding run was corrected. These are source/UI results,
not substitutes for gameplay acceptance. Main remains at `2ec49ef` unchanged.

## 2026-11-18: complete first-world frames with startup loading

The subsequent ordinary windowed `RX_VK_LOAD=start` run of the complete NUP
product prepared 18,206 programs, 25,457 graphics and 1,107 compute pipelines
before the title (445.9 seconds). The first loaded-world screenshot showed
complete terrain, Link, HUD, vegetation and sky. Twelve consecutive settled
Death Mountain captures and the first-frame/settled contact sheet were inspected;
those samples showed no holes or flashes. This does not establish a whole-game
or long-session temporal guarantee.

A 59.833-second loaded-world interval produced 2,835 native frames: **47.382 fps**
average, 47.35 median reported fps, at 1920x1080 native with frame generation off.
It includes screenshot overhead, three scripted movements and a camera change.
The process exited normally and original profile hashes stayed unchanged. The
repeated preparation wait is a real limitation. Main's earlier 54.44 fps run used
DLSS Quality at a lower internal resolution; these figures cannot establish
matched performance parity.

A separate headless UI-only diagnostic captured the branded green/gold settings
menu and three moving AV1 intro frames. It disabled precompile only for UI
inspection, so its world/FPS output is not gameplay or startup acceptance. A
same-byte asset-mod probe was opened through the launcher's merged snapshot;
the runtime identified the selected file, the base hash stayed unchanged, and
the temporary mod/settings were restored afterward.

The launcher uses its own official Python-build-standalone 20261110 / CPython
3.14.10 with Tk, pinned Pillow 12.0.0 and hash-enforced NumPy/lz4/fontTools build
wheels. Cold bootstrap and cached reuse passed; native `DekuForge.exe` self-test
passed on that interpreter. The full source suite passed **226 tests with two
environment skips** using the owned Python, LLVM-MinGW and development ARM64
oracles. Main remains unchanged.

The actual `Launcher.start_build` worker then completed a NUP rebuild using the
owned interpreter/tools in **1,090.72 seconds**, compiling 2 of 696 files. It
returned the installed `DekuForgeGame.exe`, with no worker or Tk callback errors.
The developer test kept its window unmapped; all 14 owned profile files retained
their pre-build SHA-256 values. The final ordinary-play readiness process
presented Vulkan frames and exited normally (457.72 seconds for that stage).
This confirms the connected launcher build route locally; installer, controller,
audio, long-session and matched-main gates remain separate.

## 2026-11-18: persisted build cache and repeat Play

Engine `0.1.0-independent.7` snapshots the Vulkan pipeline cache next to the
game before the build's validation process reports success. The build waits
for the cache write and for Vulkan frames to be presented. The provider's
pipeline writer stages the file before replacing the previous cache.

An incremental NUP rebuild linked the adapted renderer. A separate invocation
of the build's final validation stage under the owner's ordinary Windows account
then wrote a 1,305,178,386-byte cache and exited normally after 113.21 seconds.
The earlier sandboxed attempt did not confirm the save. The final run used the
explicit snapshot writer and the driver had access to its own warm disk cache.
The changed account and cache state prevent a controlled speedup claim against
the earlier 445.9-second run.

| Repeat Play | First visible replay | Menu | World detected | Native 1080p, FPS |
|---|---:|---:|---:|---:|
| A | 25.15 s | 30.67 s | 51.22 s | 48.08 |
| B | 25.66 s | 30.17 s | 53.23 s | 47.67 |

Both launches read the saved cache and restored all 1,107 known compute
pipelines from cache. The 25,457 known graphics pipelines were made ready
before the title, and the timed gameplay intervals each lasted about 20
seconds on Death Mountain Trail. Both processes exited normally and the
baseline profile hashes matched. The first world-detection screenshot in
the repeat test could still fall during the load fade. These figures cover one
RTX 2080 and its warmed driver, with frame generation off.

## 2026-11-18: controller prompts, sprint and settings

Engine `0.1.0-independent.8` generated the local shader census and all six
controller/keyboard prompt packs. The final build validation wrote its
pipeline cache and presented Vulkan frames in 27.99 seconds on the previously
warmed RTX 2080. A normal launch detected a connected DualSense over SDL,
selected the PS5 font and textures automatically, and started the game in
Dutch using the system-language setting.

The Controls preset bound guest A to the physical bottom button. The gameplay
test enabled Sprint speed at 1.25× through the menu and sent a left-stick click
with stick movement on Death Mountain Trail. The input and character controller
logs confirmed L3 engaged sprint and the game applied the 125% multiplier.
Physical button presses across the other controller families remain untested.
Separate overlay captures showed the active-tab accent, the Cheat Manager,
and the frame-time graph on the green and gold performance panel. These
headless captures are for UI inspection only.

## 2026-11-19: configurable sprint and Cheat Manager

Engine `0.1.0-independent.9` rebuilt the locally lifted 1.1.1 program with
validated guest hooks. On Death Mountain Trail, a normal launch on the warmed
RTX 2080 reached the menu after 31.40 seconds and the adult world after 53.45
seconds. The adult gameplay interval produced 1,936 frames in 42.615 seconds
(45.43 FPS). The native log recorded two normal arrow impacts followed by
two bomb detonations, plus the instant magic charge and spin range multiplier.
The input log recorded an L3 sprint activation with click-to-toggle selected.

In a separate child-world run, bottle 1 reported Fairy and bottle 2 reported
Milk after independent edits. Both runs exited normally and the original
save hashes matched. The native fixture covers individual unlocked bottles,
hold and toggle sprint, and freezing and resuming a running countdown. The
countdown still needs gameplay acceptance in an actual minigame. World-map
markers, the black arrow aura and full Cheat Manager parity remain open.

The follow-up child acceptance on the same trail equipped the Fairy Slingshot
in the inventory and fired into the rock wall. The guest identifies the
in-flight actor as `Item_DekuSeed`. With the separate cheat enabled, the
log recorded two queued impacts and two bomb detonations. The test recorded
1,269 frames in 22.963 seconds (55.26 FPS) and exited normally.
The retest without diagnostic code recorded three seed detonations and
three native jump impulses from separate jump presses.

## 2026-11-19: native World markers and projectile aura

The build generated 163 additional marker records and 24 night-only hints
from local game files. The first copy of the layout archive moved offsets
used by the controller prompt patcher and crashed at the title. Appending the
grown map members preserved the original offsets. The corrected build then
loaded the DualSense layouts and entered ordinary gameplay.

A child-Link run used the same copied save to capture the Kakariko region
map before and after enabling the seven World settings. Night Skulltulas
gained crescent-marked icons on the region map and minimap. The existing
collected state stayed visible. Both test games exited normally with
unchanged baseline saves.

Separate adult bow and child slingshot runs on Death Mountain Trail logged
eligible aura points, projection in the presentation thread and subsequent
bomb detonation. The stock and equipment gates use the same native projectile
path. The control bridge's game-image captures precede the presentation overlay,
so they do not independently show its opacity. Git source tests checked the
archive offsets, native hook words, local asset selection and mod priority.
