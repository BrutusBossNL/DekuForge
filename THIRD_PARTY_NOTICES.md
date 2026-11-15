# Provenance and reuse

The DekuForge launcher and archive/build orchestration are newly written Python.
No game-derived outputs or third-party binaries are bundled.

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
