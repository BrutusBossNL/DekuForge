# Independent engine: implementation and acceptance

This branch develops alongside main. Its original CPU prototype is incomplete.
The Windows Preview installer sets up the separately evaluated provider in its
own installation.
Main's stable 0.10.1-based game supplies behavior/performance evidence, not an
automatic source-code dependency. No existing user game or save is part of a test.
Consult [INDEPENDENT_EVIDENCE.md](INDEPENDENT_EVIDENCE.md) before repeating earlier
investigations; it records reusable work, failed approaches and measurement scope.

## Initial code and provenance inventory

| Component | Current route | Reuse status |
| --- | --- | --- |
| Launcher, preferences, saves, updater | Original `dekuforge/` tooling | Retained project code; bundled dependencies still need individual terms |
| NUP/archive and module preparation | Original `nup.py`, `gameplan.py`, `modules.py`, `romfs.py` | Retained; lz4/zbic and other libraries retain their separate licenses |
| CPU block generator | New `independent_cpu.py` | Original implementation from ISA facts, not a port of the NX2navi lifter |
| CPU state and native correctness runner | Own integer/PC/SP/NZCV C ABI and explicit checked memory regions | Original; SIMD/FP, full dispatch and platform ABI still missing |
| Guest memory/module prototype | New `guest_memory.py`, `guest_linker.py` | Original bounded MOD0/ELF discovery, symbol and RELA/RELR pointer relocation; not a complete platform loader |
| Historical `engine/` | Immutable earlier MIT import | Reference only; not selected as the new backend |
| Stable 0.10.1 backend/patches | Inherited reference integration | Excluded from independent build route; scoped grants do not clear surrounding code |
| Shader/Vulkan/guest services | Not implemented in this backend | Audit reusable upstream components or implement independently |
| Python/Tk/compiler provisioning | Official hash-pinned Python/Tk/Pillow and generic compiler bootstrap, experimental Windows only | No NX2navi runtime download; installer acceptance is still open |

For every future reused component, record the original source, exact revision,
file/function scope, license/grant, retained notices and validation. Published
source alone does not establish an open-source license. Honor conditions such as
notice/source availability; do not claim every dependency uses MIT. Restricted
code is replaced with a new implementation, not renamed into apparent ownership.
The inherited tree/history is not automatically cleared by new work on this branch.

## First working CPU component

The original decoder/generator supports 32/64-bit ADD/SUB immediate and shifted
register forms, NZCV updates, shifted logical operations, MOVN/MOVZ/MOVK, ADR/ADRP,
direct/indirect calls/returns, condition/zero/bit branches and NOP. Scalar memory
operations cover unsigned scaled, unscaled/pre/post-indexed offsets, literal
loads and register offsets (UXTW/LSL/SXTW/SXTX), including sign extension.
Integer LDP/STP and LDPSW support signed-offset, pre- and post-index forms with
32/64-bit results, SP/ZR handling and writeback. Reserved and constrained-overlap
forms are rejected. SIMD/FP encodings are kept out of the integer decoder;
non-temporal, exclusive and atomic accesses remain unsupported. Unsupported encodings and constrained writeback
aliases are rejected. Register 31 follows each instruction's SP/zero-register rule.
Blocks stop at branches/services. A bounded native development dispatcher executes
loops/calls and resumes after an exact guest-instruction budget. It is not the
final game's optimized dispatcher. SVC, unknown PCs and memory faults stop explicitly.

`emit_machine` requires explicit guest regions and validates a complete memory
access before touching bytes or applying register writeback. Pair operations
prevalidate both elements, including adjacent mappings and the second element's
permissions, before committing any bytes or registers. This is a deterministic
fault-handling contract of the correctness runner, not a claim of hardware
atomicity, concurrent guest-memory ordering or complete architectural exceptions. Little-endian byte
accesses avoid unaligned host casts. The Python memory prototype maps verified
NSO segments RX/R/RW, zeroes BSS and applies RELATIVE relocations transactionally.
The original bounded module linker now discovers MOD0 dynamic tables, SysV/GNU
symbol tables, RELA and RELR relocation streams. ABS64, GLOB_DAT, JUMP_SLOT and
RELATIVE pointer writes are validated as one plan before any are committed.
Synthetic tests include unresolved weak, absolute and protected symbols, malformed
tables and cross-module calls through relocated function pointers. `emit_image`
executes sparse synthetic code mappings. TLS, ELF symbol versions, initializers,
dependency loading, scheduling and the full platform ABI remain absent.
Generated C carries the game-output marker and stays local even for synthetic
development inputs. Successful translation of a tiny block is not game readiness.

ISA references: [Arm ADD immediate](https://documentation-service.arm.com/static/68ffa09902789941c1920a53),
[Arm instruction reference](https://documentation-service.arm.com/static/5f3fa899428f7a6b3328fd44),
[Arm load/store addressing](https://support.arm.com/documentation/ddi0487/mb/-Part-C-The-AArch64-Instruction-Set/-C1-3-Address-generation/-C1-3-3-Load-store-addressing-modes)
[Arm STP](https://support.arm.com/documentation/100076/0100/A64-Instruction-Set-Reference/A64-Data-Transfer-Instructions/STP),
[Arm LDR register](https://support.arm.com/documentation/ddi0596/2020-12/Base-Instructions/LDR--register---Load-Register--register--?lang=en)
and [Arm ELF64 ABI](https://github.com/ARM-software/abi-aa/blob/main/aaelf64/aaelf64.rst).
The native differential test compiles emitted C and compares registers, SP, PC
and NZCV with Unicorn on synthetic inputs. The oracle is a development dependency.
The original 1,164 native/oracle comparisons and wrong-PC checks are retained.
Additional native tests cover overflow, width/shift boundaries, all 16 conditions
under all 16 NZCV combinations, link aliases, budgeted loops/calls, scalar memory
forms and fault atomicity. A synthetic NSO is mapped, relocated and executed
natively through checked stores/loads to an SVC boundary. This is not the game;
the checks cover only the instruction subsets above.
Pair and register-offset tests add full-state and memory comparisons against
Unicorn, signed/unsigned index extensions, negative and scaled offsets, SP/ZR,
aliases and LDPSW sign extension. Native fault tests cover address wrap, partial
mappings, second-element permission failures and stack save/restore across two
adjacent regions. Other registers/state and instruction families are not
validated by these tests.

## Build and tooling boundaries

`run_builder.py --doctor` describes this backend. A normal build stops before
multi-gigabyte extraction because host, graphics and linking stages are absent.
Explicit `--prepare` can exercise original verified input preparation. Legacy
compatibility/generation/runtime CLI routes are rejected; historical developer
tools are retained only for provenance and isolated research.

`python tools/analyze_independent.py --exefs PATH --out local/analysis.json` reads
already extracted modules without changing them or extracting the game again.
It records static text-word decoder coverage and module layouts, not gameplay or
dynamic instruction coverage: text can contain data/literal pools. Reports are
local, require a new filename, and may only be written under this worktree's
ignored `local/` or `build/`, outside the input directory.
Reports fingerprint their decoder, analyzer, module-normalization and layout
source as well as each input module. Reuse only results for the same source/input
identities; changing the decoder invalidates prior coverage, not all old gameplay
or movie benchmarks.

Independent setup and updates use the pinned generic toolchain and licensed
provider source. A stable installation cannot be converted in-place. No
runtime, toolchain, generated source or user profile is copied from main.

## Separately licensed runtime feasibility candidate

An isolated developer experiment evaluates
[Ocarina Recomp](https://github.com/sostenesfreitas/ocarina-recomp) at
`406b3ae0321eff8dd083a607a8186aa56b52b873`. This is a GPL-3.0-or-later composed
runtime, based on MIT TotK Recomp 0.2.8 and scoped MIT/GPL components listed in
its notices. It is not the excluded NX2navi backend. Its GPL code must not be
described or redistributed as original MIT DekuForge code. The source audit,
managed translator build and game compilation remain local experiments until
moving gameplay meets the acceptance gates below. No game outputs are published.

The archive's 900 source blobs were checked against their pinned Git blob IDs;
only documented CRLF checkout normalization was reversed. Its own ExeFS hashes
are enforced. A managed, self-contained .NET translator build avoids an MSVC
dependency; this build mode is distinct from the upstream NativeAOT identity.
Existing packed game data is opened read-only; output and profiles stay in this
worktree. This does not establish standalone installer or gameplay readiness.

`dekuforge/open_engine.py` stages only that exact source archive. Its lock records
the archive SHA-256 and all 900 canonical Git blob identities and sizes. It
rejects missing/extra members, traversal, case aliases, links, encrypted members,
oversized archives and changed source in an existing owned tree. License texts
and upstream notices remain in the staged source. It downloads no game files,
compiled game code or caches, and is not selected by the default launcher yet.

The first isolated candidate compiled and passed its runtime self-test, but
moving Death Mountain captures exposed black objects in shadow. It is rejected
for gameplay acceptance. Its first-present clock is not a loaded-world detector;
startup averages must not be presented as gameplay performance. Full recorded
compute preparation is a diagnostic, not an accepted renderer fix.

A second source-only evaluation uses the publicly GPL-3.0-or-later
[Hookshot source mirror](https://github.com/Z-TOON/Hookshot) at
`1c7e70bb035a7f45419b23882e73d7eb09b93e16`. All 2,188 source blobs were checked
against the pinned Git tree. Its retained component notices identify the
Rexcomp/a64-kit CPU path, GPL Eden/suyu shader compiler and separately licensed
libraries. This route uses direct NVN2 shader translation and reports ambient
probe/culling fixes relevant to the observed defect. Those reports are reasons
to test it, not proof of parity. Its source and local outputs remain under
ignored experiment directories; no candidate is selected automatically.

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

The direct NVN2 candidate now runs isolated moving scenes, with the DekuForge
window/menu branding composed through generated GPL-attributed UI copies.
Its original source remains immutable. Direct NUP directory extraction,
explicit local runtime metadata and a pinned source-built dav1d AV1 dependency
are implemented. An existing developer build can use this branch's launcher Play
action; this does not complete first-install provisioning or the default wizard.
The complete experimental NUP pipeline now has an original orchestration layer,
owned output/work folders, pinned generic-tool provisioning and explicit local
launcher opt-in. Save discovery understands its `user/save` layout. Asset mods
are composed in launcher priority order without altering base assets; code mods
and the Cheat Manager are not yet connected. The official Python/Tk/Pillow
bootstrap and owned build-wheel provisioning now work separately from main.
The independent installer passed local Windows setup and tool provisioning.
First-build gameplay on fresh installations and main performance parity remain open.
See [OPEN_ENGINE_EVALUATION.md](OPEN_ENGINE_EVALUATION.md) for those commands and
the evidence index for measured scope. Main remains unchanged.
