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

## Implementation status

- Implemented: original desktop launcher, installation selection, persistent
  local settings, existing-game launch, duplicate-launch guard within the launcher.
- Planned: independent runtime/build adapter, updater, cheat manager, equipment
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
