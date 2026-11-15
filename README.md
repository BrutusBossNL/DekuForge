# DekuForge

**Reforging a legend.**

An independent launcher and a foundation for original game tooling. This repository
starts with newly written Python code, a forest-green and copper interface, and
an explicit migration plan. It is not a renamed NX2navi distribution.

## Run locally

Run `Start-DekuForge.cmd` on Windows, or `python -m dekuforge` with Python 3.11+
and Tk installed. Select an existing executable using **Installatie kiezen**, then
press **Spelen**. The launcher runs it in its own installation directory, keeping
that installation's saves, settings and existing features in place. Launching an
external installation does not turn its runtime into a DekuForge implementation.

The Windows script can use the Python already installed by NX2navi, without
copying or distributing it. Otherwise install Python with Tk support.

Local configuration stays in ignored `local/settings.json`. No game data,
encryption keys, saves, external executables, or local paths belong in Git.
The launcher does not download, update, modify or shut down an existing game.

## Build from your NUP

Choose **NUP / Game bouwen**, select your own `.nup` file, and select the root
of an existing NX2navi launcher installation (containing `app`, `python`,
`pydeps` and `toolchain`). The normal local installation is selected by default.
Use **NUP controleren** to validate the title and game version without extraction
or compilation. **Game bouwen** uses the external backend's Python, dependencies
and compiler. Output stays in `DekuForge/build/game`; the backend can also use its
normal local caches.

This is original build orchestration around an **external NX2navi backend**,
not an independent recompiler or runtime. No backend source or binaries are
bundled, copied, renamed or relicensed. Features of the resulting game come from
the selected backend version. Missing build tools are not installed automatically.

The window shows progress and a bounded live log; full logs stay in ignored
`local/logs`. Builds require at least 40 GiB of free space. The output must carry
a DekuForge ownership marker and contain no symlinks or junctions. An exclusive
project lock prevents simultaneous checks/builds. After a process crash, inspect
the running processes before manually removing `local/build.lock`. No automatic
directory deletion is performed.

After success, **Deze build gebruiken** explicitly selects the new executable.
Saves and settings are not automatically copied. Leave the launcher open until
the build finishes. Shader preparation can use the GPU; start a full build when
you are finished playing.

Command line: `python run_builder.py --nup "D:/Games/own.nup" --check`, or omit
`--check` to build. Optional `--backend` selects the existing launcher root and
`--jobs` limits compiler workers. With embedded Python, invoke the script with
that interpreter. No global PATH workaround is required.

## Implementation status

- Implemented: original desktop launcher, installation selection, persistent
  local settings, existing-game launch, duplicate-launch guard within the launcher.
- Implemented: NUP selection, external-backend validation, isolated build
  orchestration, progress, logs and explicit selection of the result.
- Planned: independent runtime, updater, cheat manager, equipment
  extensions, world markers and memory/performance fixes.
- Not included: NX2navi runtime, game data, generated game code or upstream
  additions for which reuse permission has not been established.

See [migration inventory](docs/MIGRATION.md) and [provenance](THIRD_PARTY_NOTICES.md).
All newly written code in this repository is MIT licensed. External installations
and future dependencies keep their own licenses.

## Development

`python -m unittest discover -s tests`

Contributions and bug reports are welcome. Preserve attribution, document the
origin and license of reused code, and never commit game-derived material.
No public release or installation package is available at this stage.
