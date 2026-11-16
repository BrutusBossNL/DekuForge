# Provenance and reuse

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

The DekuForge launcher and archive/build orchestration are newly written Python.
No game-derived outputs or third-party binaries are bundled.

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

The baseline is not validated for game 1.1.1. Internal engine names and formats
remain unchanged during integration. No proprietary upscaler binaries are bundled
or downloaded by DekuForge. Module normalization uses separately installed `lz4`
(BSD) and `zbic` (GPLv2); generation uses NumPy (BSD). Their licenses accompany
their separate installation; the Python packages are not bundled here.

NX2navi is the reference for the requested feature inventory and an optional,
separately installed external application. Its base MIT license does not cover
all subsequent changes. Its LICENSE-ADDITIONS and individual dependency licenses
must be reviewed before any reuse. A private repository does not alter those terms.

Original BrutusBossNL contributions in the existing fork have a scoped MIT grant
in LICENSE-CUSTOM-ADDITIONS. Mixed files must be reviewed at change level before
porting; the grant does not extend to the surrounding upstream implementation.
Reused material must retain its notices and have an entry here with source,
revision, scope and license. Custom contributions from mixed upstream files have
not yet been ported; the engine import above is the historical MIT base only.

The NUP build adapter calls the documented command-line interface of an existing
NX2navi installation: `tools/make_game.py --nup --check`, or `--nup --out --msys
--jobs --events`. It starts that installation's Python with its own dependencies.
The backend stays external and its license remains unchanged. The adapter is not
a port of its builder implementation and does not grant rights to the backend.
