# Provenance and reuse

The initial DekuForge launcher is newly written using Python's standard library.
No NX2navi source files, game-derived outputs or third-party binaries are copied.

NX2navi is the reference for the requested feature inventory and an optional,
separately installed external application. Its base MIT license does not cover
all subsequent changes. Its LICENSE-ADDITIONS and individual dependency licenses
must be reviewed before any reuse. A private repository does not alter those terms.

Original BrutusBossNL contributions in the existing fork have a scoped MIT grant
in LICENSE-CUSTOM-ADDITIONS. Mixed files must be reviewed at change level before
porting; the grant does not extend to the surrounding upstream implementation.
Reused material must retain its notices and have an entry here with source,
revision, scope and license. No such material has been imported yet.

The NUP build adapter calls the documented command-line interface of an existing
NX2navi installation: `tools/make_game.py --nup --check`, or `--nup --out --msys
--jobs --events`. It starts that installation's Python with its own dependencies.
The backend stays external and its license remains unchanged. The adapter is not
a port of its builder implementation and does not grant rights to the backend.
