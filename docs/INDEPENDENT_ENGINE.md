# Independent engine: implementation and acceptance

This branch develops alongside main. Its initial independent engine is incomplete;
it must not replace a working installation or be published as a playable installer.
Main's stable 0.10.1-based game supplies behavior/performance evidence, not an
automatic source-code dependency. No existing user game or save is part of a test.

## Initial code and provenance inventory

| Component | Current route | Reuse status |
| --- | --- | --- |
| Launcher, preferences, saves, updater | Original `dekuforge/` tooling | Retained project code; bundled dependencies still need individual terms |
| NUP/archive and module preparation | Original `nup.py`, `gameplan.py`, `modules.py`, `romfs.py` | Retained; lz4/zbic and other libraries retain their separate licenses |
| CPU block generator | New `independent_cpu.py` | Original implementation from ISA facts, not a port of the NX2navi lifter |
| CPU state | Own minimal C ABI emitted by the generator | Partial integer/PC/SP/NZCV state only; vectors, memory and runtime ABI still missing |
| Historical `engine/` | Immutable earlier MIT import | Reference only; not selected as the new backend |
| Stable 0.10.1 backend/patches | Inherited reference integration | Excluded from independent build route; scoped grants do not clear surrounding code |
| Shader/Vulkan/guest services | Not implemented in this backend | Audit reusable upstream components or implement independently |
| Portable Python/Tk/compiler packaging | Not implemented for this branch | No download from an NX2navi release; developer interpreter is external |

For every future reused component, record the original source, exact revision,
file/function scope, license/grant, retained notices and validation. Published
source alone does not establish an open-source license. Honor conditions such as
notice/source availability; do not claim every dependency uses MIT. Restricted
code is replaced with a new implementation, not renamed into apparent ownership.
The inherited tree/history is not automatically cleared by new work on this branch.

## First working CPU component

The original decoder/generator currently supports 64-bit ADD/SUB immediate without
flag updates, MOVZ/MOVK and RET. ADD/SUB register 31 is SP; MOVZ/MOVK register 31
is the zero register and writes are discarded. Block bounds and terminators are
checked before output. Unsupported neighbors and other instructions are rejected.
Generated C carries the game-output marker and stays local even for synthetic
development inputs. Successful translation of a tiny block is not game readiness.

ISA references: [Arm ADD immediate](https://documentation-service.arm.com/static/68ffa09902789941c1920a53),
[Arm MOVZ](https://support.arm.com/documentation/dui0801/j/A64-General-Instructions/MOVZ).
The native differential test compiles emitted C and compares registers, SP, PC
and NZCV with Unicorn on synthetic inputs. The oracle is a development dependency.
Local validation covers 291 instruction encodings across four initial states
(1,164 native/oracle comparisons), plus 1,164 rejected wrong-PC calls that must
leave state unchanged. These checks cover only the instruction subset above.
Other registers/state and instruction families are not validated by that test.

## Build and tooling boundaries

`run_builder.py --doctor` describes this backend. A normal build stops before
multi-gigabyte extraction because host, graphics and linking stages are absent.
Explicit `--prepare` can exercise original verified input preparation. Legacy
compatibility/generation/runtime CLI routes are rejected; historical developer
tools are retained only for provenance and isolated research.

Installer packaging and vendor-based tool/runtime provisioning are blocked.
Main's application update channel is disabled so it cannot replace this branch
with the old backend. No runtime, toolchain, generated source or user profile is
copied from main into this worktree. An external development interpreter/compiler
can run tests without becoming a distributed engine dependency.

## Implementation sequence for contributors

1. Extend original A64 decoding/IR/emission with complete-state differential tests:
   flags, control flow, memory, SIMD/FP and atomics. Unknown semantics must fail.
2. Implement module loading/relocation and guest memory, scheduling, synchronization,
   filesystem transactions and platform services against explicit contracts.
3. Establish a separately sourced shader translator and Vulkan backend with audited
   licenses. Validate stage bindings, counter/query ordering, resource lifetime,
   texture/depth aliases and synchronization before performance shortcuts.
4. Add runtime input/audio, real-time pacing, movie decoding, scalable rendering,
   pipeline preparation and settings. Reuse approved libraries with their notices.
5. Provision tools from independently identified providers, build/link locally,
   then integrate the already owned Cheat Manager through new stable interfaces.

## Equal-or-better acceptance gate

Test baseline and candidate on the same machine, driver, resolution/upscaler,
controller mapping, scene and copied save state. Record source/component/build IDs,
settings, warmed/cold caches and instrumentation. Repeat measurements to distinguish
noise from regression; do not select only favorable frame windows.

- Complete terrain, foliage, sky, shadows, Link, HUD, menus and movies. No known
  missing surfaces or temporal flicker across moving sequences.
- Correct menu/movement/physics/day-clock timing. FPS counters alone cannot prove
  real-time game speed. Match main's observed game-clock/wall-clock behavior.
- No measured FPS/frame-time regression beyond measurement uncertainty: average,
  low-percentile FPS, p95/p99 frame times and stalls. Peak RAM/commit/VRAM must be
  compared on the same route; do not hide regressions by reducing image quality.
- Save/load/write, transaction recovery, controller layouts, audio, area transitions,
  a repeatable long session and each Cheat Manager feature pass independently.
- Compare title/intro, Kokiri Forest, Market Square, Hyrule Field and a dungeon.
  Core rendering and stability gates precede Linux/iOS or release claims.

A failing gate keeps the independent engine experimental. The default production
route on main is not replaced merely because new code compiles or one frame looks
correct. No inferior result is accepted as equivalent to main.
