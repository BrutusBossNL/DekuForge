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
