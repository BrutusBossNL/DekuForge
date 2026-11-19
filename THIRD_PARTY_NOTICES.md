# Provenance and reuse

> Independent branch status: the stable backend described below is inherited
> reference material, not the default build route here. The new original CPU
> component and reuse gates are documented in [INDEPENDENT_ENGINE.md](docs/INDEPENDENT_ENGINE.md).
> Existing notices/history remain intact; no blanket relicensing or clean-room
> claim is made. Independent runtime/installer distribution is not ready.

The independent integer/control-flow/scalar, register-offset and paired-memory
generator, bounded native
runner, guest-memory/MOD0/ELF pointer-linking model and read-only analyzer are original
DekuForge code under the root MIT license. Arm ISA/ABI documents supply encoding
and behavior facts, not imported runtime code. Unicorn is a separately licensed
development oracle, not the game's CPU backend. Reuse and measurement scope are
indexed in [INDEPENDENT_EVIDENCE.md](docs/INDEPENDENT_EVIDENCE.md).

## Active Windows backend and scope of the root license

The default builder stages NX2navi **0.10.1**, revision
`5ae55db41c7d11c4e997d2676019939a936e560b`, into ignored
`build/engine-0.10.1`. Source: https://github.com/tangerineturtle1/NX2navi .
`dekuforge/stable_engine_source.json` pins the original file hashes;
`dekuforge/stable_engine.py` verifies and stages them. This is reused upstream
builder/runtime code, not an independently rewritten engine. The launcher uses
its own provisioned Python and tools; an installed NX2navi application is not
required. See [docs/STABLE_ENGINE_MIGRATION.md](docs/STABLE_ENGINE_MIGRATION.md).

The staged source retains `LICENSE`, `LICENSE-ADDITIONS`, component notices and
copyright headers. **The root MIT license covers original DekuForge code only.**
Upstream `LICENSE-ADDITIONS` explicitly grants no license for its covered later
changes. Downloading or locally staging source does not grant redistribution
rights. Do not describe the entire composed engine as MIT or fully open source.
Any public distribution must resolve the applicable rights and component terms;
keeping this preview private does not change those terms.

`dekuforge/runtime_layer.py` composes the DekuForge UI and scoped custom Cheat
Manager changes, recorded from fork revision
`8cb3f1c6c168fd36ff2dc08ecdd606508af10f9a`, over that backend. The original
contributions' scoped grant is retained in
`engine_overrides/dekuforge_0110/LICENSE-CUSTOM-ADDITIONS`; it does not relicense
surrounding upstream implementation. The complete patch and its provenance must
be considered together.

The verified official application archive supplies release-only pipeline
metadata, controller art, tool locks and credits for local preparation. It is
not included in the launcher package. Its Input Prompts Pack terms refer to
redistribution in NX2navi releases; those terms must not be assumed to grant
equivalent rights to a new project. No game-derived outputs are distributed.

## Downloaded tools and runtime dependencies

`dekuforge/components.json`, the native toolchain lock and shader-tool manifests
record the downloaded component identities. The managed Python runtime includes
third-party Python packages and Tcl/Tk; native tools include LLVM/Clang, SDL and
Vulkan tooling, with .NET used for the Ryujinx-based shader translator. Retain
their accompanying licenses and notices in downloaded installations. The full
upstream component inventory is in the staged `THIRD_PARTY_NOTICES.md`; do not
replace it with this overview or infer a common license for all dependencies.

The active build can download NVIDIA DLSS 310.9.1 under the NVIDIA RTX SDKs
License, pinned by upstream `tools/dlss_pin.py`, with its notice copied beside the
local game. It is not MIT licensed and is not bundled in our small launcher ZIP.
Optional SDK features remain subject to their own terms and hardware support.
Upstream feature availability does not establish that every option has been
tested in DekuForge.

## Historical experimental components

The sections below record the retired `engine/` import and its experimental
overrides. They remain in the repository for provenance and development, but
are not the default game-build route.

## NVN2 shader support

`engine_overrides/shader/ampere.patch` and `mesh-*.patch` adapt the permitted Ampere decoder and
emitters from MacNativeGames's Ocarina shader tooling at revision
`9e1c10b7d485e9978262dca8f01efde9ffad8f40`, originating in seedds/nxnative.
Their MIT notices are retained as `LICENSE-MNG` and `LICENSE-NXNATIVE` beside
the patch. Integration preserves the baseline's zero-local option and 32
constant-buffer banks. The Vulkan service and NVN2 short-control adaptation
are integrated separately; no Metal backend or game-derived shader is imported.
The NVN2 v0xc9 field layout and Ocarina SDK 22 driver-version facts are
documented in that revision's `nvn_ctl.h` and `hle_nvn.c`. Source:
https://github.com/ly05010419/MacNativeGames/tree/9e1c10b7d485e9978262dca8f01efde9ffad8f40 .

`mesh-0025.patch`, `mesh-0026.patch`, `mesh-0028.patch` and `mesh-0029.patch` adapt saturated byte-pair
conversion, register-handle texture sampling, surface reductions, global atomic
compare-and-swap and memory-descriptor addressing from seedds/nxnative revision
`23790f8dcc3a3491a44f125805dfbf1e5664cd2a` under the same retained MIT license.
The source files are `dm/third_party/ryujinx/src/Ryujinx.Graphics.Shader/Instructions/InstEmitAmpereAlu.cs`
and `InstEmitAmpereMem.cs`. Only these instruction forms are added to the pinned
compiler; no game shader bytes are included.

## QARMA arithmetic

`engine_overrides/qarma.h` adapts gem5's `src/arch/arm/qarma.cc` at revision
`9d368896ce119c17e1289dcbb18f33624724b843` (Copyright 2020 Metempsy Technology Consulting),
under its BSD-style license, retained in full in the adapted source. The changes
replace gem5's C++ bitfield types with explicit portable-C nibble extraction;
they do not import gem5's platform simulator. Source:
https://github.com/gem5/gem5/blob/9d368896ce119c17e1289dcbb18f33624724b843/src/arch/arm/qarma.cc .

The DekuForge launcher and original archive orchestration are project code.
The active game build also calls the reused stable upstream builder described
above. No game-derived output is part of the launcher package.

## AV1 decoding dependency

Experimental local Windows builds link dav1d from the separately installed MSYS2
toolchain. Source: https://code.videolan.org/videolan/dav1d (BSD-2-Clause,
Copyright 2018 VideoLAN and dav1d authors; Copyright 2018 Two Orioles, LLC).
No dav1d binary is committed. Future tooling distributions must include its
license and accompanying component notices. `engine_overrides/av1_movie.c` is
an original adapter; input/output layout facts are checked against the owner's
local SDK modules. Game-derived modules and movie data are never distributed.

## Included engine source

`engine/` is exported from the MIT base import of NX2navi, revision
`0478c13e4503a8c1a75155b1e277b8cc53ce149a`, Copyright (c) 2026 Valiantsin Dzerakh.
Source: https://github.com/BrutusBossNL/NX2navi . Only `recomp/`, `runtime/`,
`tools/`, `VERSION`, `LICENSE` and `THIRD_PARTY_NOTICES.md` of that revision are
included. Later restricted changes are not part of this import. The MIT grant is
retained in `engine/LICENSE`; detailed component notices and authors remain in
`engine/THIRD_PARTY_NOTICES.md` and file headers. `engine/SOURCE.json` records each
imported file's SHA-256. `tools/import_engine.py` reproduces this source-only export.

This historical baseline did not pass game 1.1.1 rendering acceptance. Internal
engine names and formats remain unchanged in that import. The active route's
upscaler downloads are described above. Module normalization uses `lz4`
(BSD) and `zbic` (GPLv2); generation uses NumPy (BSD). Their licenses accompany
their separate installation; the Python packages are not bundled here.

Reused material must retain its notices and record source, revision, scope and
license. Historical files in `engine/` keep their original notices unchanged.

## Optional external compatibility adapter

Only the explicitly selected compatibility route (`run_builder.py --compat`)
uses the NUP adapter to call the command-line interface of an existing
NX2navi installation: `tools/make_game.py --nup --check`, or `--nup --out --msys
--jobs --events`. It starts that installation's Python with its own dependencies.
The backend stays external and its license remains unchanged. The adapter is not
a port of its builder implementation and does not grant rights to the backend.

## Independent branch experiment

The independent Windows launcher bootstrap uses official Astral
python-build-standalone release 20261110 / CPython 3.14.10 (PSF license and bundled
component terms) and Pillow 12.0.0 (MIT-CMU). URLs, sizes and SHA-256 identities are
pinned in `components.json`; installed license files remain with those packages.
No Python runtime from an NX2navi release is used. NumPy 2.5.4 (BSD-3-Clause),
lz4 4.4.5 (BSD/LZ4 component terms) and fontTools 4.68.0 (MIT) are build-only
dependencies with hash-pinned Windows wheels in `requirements-open-engine.txt`.

The optional source-only candidate stager (`dekuforge/open_engine.py`) fetches
[Ocarina Recomp](https://github.com/sostenesfreitas/ocarina-recomp) at
`406b3ae0321eff8dd083a607a8186aa56b52b873`, checked by
`dekuforge/open_engine_source.json`. Its composed runtime is GPL-3.0-or-later,
with scoped MIT and other component terms retained in its `LICENSE`,
`LICENSE-MIT` and `THIRD_PARTY_NOTICES.md`. Those source files and their notices
remain together in the local staged tree. This is not original MIT DekuForge
runtime code. The candidate is not a published or gameplay-approved backend;
see `docs/INDEPENDENT_ENGINE.md` for scope and acceptance requirements.

The second experimental provider is the GPL-3.0-or-later
[Hookshot source mirror](https://github.com/Z-TOON/Hookshot) at
`1c7e70bb035a7f45419b23882e73d7eb09b93e16`. Its archive SHA-256 and 2,188
canonical Git blob identities are recorded in `dekuforge/hookshot_source.json`.
Original headers, GPL texts and component notices remain in the staged source,
including `third_party/a64-kit/NOTICE.TOTKPort.md`. This is separately licensed
engine code, not original MIT DekuForge code. The development evaluation tool
does not distribute its source, game outputs or compiled runtime in a launcher
release. See `docs/OPEN_ENGINE_EVALUATION.md` for explicit build boundaries.

`dekuforge/open_engine_branding.py` adapts this GPL provider's UI, SDL input,
game language, sprint controls and build cache save. The adapter is GPL-3.0-or-later
(SPDX header), excepted from the root MIT grant.
Generated adapted sources retain the original headers and add an attribution
line; their original/adapted SHA-256 values are recorded locally. The complete
GPL text is retained in `licenses/GPL-3.0.txt` and in the verified provider tree.
This does not relicense the engine, remove its credits or grant rights to game
content. No compiled game or game-derived shader/cache is distributed.

The local shader census and controller prompt builder also use hash-pinned
[python-zstandard 0.25.0](https://pypi.org/project/zstandard/0.25.0/) (BSD-3-Clause),
[astc-encoder-py 0.1.12](https://pypi.org/project/astc-encoder-py/0.1.12/) (MIT,
with its bundled encoder notices),
[texture2ddecoder 1.0.6](https://pypi.org/project/texture2ddecoder/1.0.6/) (MIT),
and [archspec 0.2.7](https://pypi.org/project/archspec/0.2.7/) (Apache-2.0 OR MIT).
Their wheel metadata and license files remain installed with those tools.
Controller textures and fonts are generated locally from the player's copy.

The independent cheat headers and checked lift hooks use the project-owned
gameplay extensions identified by `engine_overrides/dekuforge_0110/LICENSE-CUSTOM-ADDITIONS`
as a behavioral and version-specific reference. The independent integration
uses Hookshot's GPL host APIs and does not apply the composite legacy patch.

The independent Windows movie path builds VideoLAN dav1d 1.5.4 from the official
source mirror, under BSD-2-Clause. `tools/build_av1_decoder.py` pins archive and
source-tree hashes and retains COPYING beside the local library. Meson 1.9.1
(Apache-2.0), Ninja 1.13.0 (Apache-2.0) and NASM 2.16.03 (BSD-2-Clause) keep their
distribution notices in the local tool tree. These tools and the decoder contain
no game content and are not licensed under the project's MIT grant.

`tools/provision_open_tools.py` pins the official LLVM-MinGW 20261104 UCRT
toolchain archive and the GPL provider's generic CPM and SDL dependency packages
by SHA-256 and size. Only the selected compiler/header/codec/SDL paths are used;
the combined dependency archive's prebuilt engine/lifter components are not
extracted or executed. SDL's license is retained beside the locally built game;
the verified source tree retains all component notices. These dependencies do
not make the composed GPL engine original MIT project code. NVIDIA's optional
proprietary DLSS SDK is not downloaded, linked or included in this experiment.
