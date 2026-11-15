# Windows game-build progress

The launcher is usable. The independent game executable is not yet available.
The runtime library and generated C described below are intermediate local
artifacts and must never be presented as a playable build or uploaded as a game.

## Verified development stages

- All 112 selected Windows host-runtime translation units compile with Clang
  23.1.5 from an explicitly supplied MSYS2 UCRT64 toolchain. The separate static
  archive is approximately 20 MiB. This includes the Vulkan host code; graphics
  execution and guest shader translation have not been tested.
- A complete, real SDK-generated C chunk compiles with the same compiler using
  the portable SIMD path. Unsupported instructions elsewhere in the SDK remain
  fatal build blockers.
- Full main generation covers 249,960 functions and found four unsupported UDOT
  sites in one chunk. That 657-function chunk has been regenerated with the new
  lowering and compiles with zero unsupported instructions in a separate validation
  folder. The movie module's 1,547 functions generate without unsupported sites.
- Constructor-array assertions are derived from verified local module metadata:
  the selected main/subsdk0/sdk have 9,783/0/96 entries. These are local
  observations for the selected build, not hardcoded port constants.
- The loader's old constructor-flag decoder assumed a prologue without PACIBSP.
  The original extension handles both prologues with bounded reads and checks
  that the complete flag fits in module data. Thirty synthetic native checks and
  all three local module prologues pass. This does not execute constructors.
- Return projection, acquire loads, half-vector negation and byte-vector dot
  products have separate validation, documented in `CPU_COMPATIBILITY.md`.

## Reproducing the host compilation

Prepare and generate a module first so its authoritative layout exists. Then:

```text
python run_builder.py --runtime build/prepared-ID --toolchain PATH_TO_UCRT64_BIN
python tools/check_constructor.py --compiler PATH_TO_CLANG_EXE --prepared build/prepared-ID
python tools/check_dot_product.py --compiler PATH_TO_CLANG_EXE
python tools/check_port_chunks.py --prepared build/prepared-ID --module main --compiler PATH_TO_CLANG_EXE
```

The host command records compiler identity, layout hash, per-object hashes and
failures in `build/windows-runtime/report.json`, with individual compiler logs.
It uses the explicit toolchain directory on subprocess PATH; it does not depend
on a system-wide MSYS2 installation or launch an existing game. Installation-
specific sources and final executable resources remain separate from the archive.

## Remaining delivery gates

Complete instruction lowering and regenerate all modules. Integrate game-specific
host imports, boot checkpoints, NVN2 object layouts and shader translation, then
link against the independently assembled RomFS. Boot, rendering, audio, input,
save/load and repeatable play sessions must pass in a separate installation.
The older baseline's boot checkpoints and other title-specific runtime constants
are still unvalidated; adapting constructor metadata does not establish a full
port. No FPS, frame-time or memory parity claims are supported yet.

The working installation and saves remain separate throughout this work.
