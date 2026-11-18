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
inspection copies at 1280x720 opened successfully, with original PNGs retained.
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
