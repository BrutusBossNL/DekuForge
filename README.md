<p align="center">
  <img src="assets/branding/logo.png" alt="DekuForge" width="680">
</p>

# DekuForge

**Reforging a legend.**

An open-source launcher and local game-build project, with a forest-green and
gold interface inspired by its leaf-and-forge logo. Original project code is MIT licensed. Reused engine components
retain their accompanying notices.

## Start

Run `Start-DekuForge.cmd`, or `python run_launcher.py` with Python and Tk installed.
Select an existing game installation to play without changing saves or settings.
A local interpreter override can be stored as one path in ignored
`local/python-path.txt`; otherwise the Windows script uses `py -3`.

## Game builder

Open **NUP / Game bouwen** and choose your own NUP archive.

- **NUP controleren** validates the index, checksum, paths and directory structure.
- **Uitpakken** independently streams and verifies files into a fresh build folder.
- **Alleen voorbereiden** selects executable modules from base/update packages,
  verifies their content, and writes NSO metadata and a reproducible build plan.
- **Zelfstandig bouwen** runs preparation and checks engine readiness. It currently
  stops before native compilation: the game 1.1.1 port and toolchain integration
  are unfinished.
- An optional compatibility build uses an existing installation. It is never
  silently substituted for an independent build.

Included engine source contains an ARM64 lifter, C generator, host runtime,
Vulkan renderer, shader translator and native build tools. This baseline is not
yet validated for game 1.1.1. A limited SDK generation experiment found unsupported
instructions. No independently built playable executable is available yet.

Module normalization decodes segments and checks declared hashes. Full extraction
keeps package trees separate; RomFS update composition still needs validation.

## Command line

```text
python run_builder.py --doctor
python run_builder.py --nup "D:/Games/own.nup" --check
python run_builder.py --nup "D:/Games/own.nup" --extract
python run_builder.py --nup "D:/Games/own.nup" --prepare
python run_builder.py --nup "D:/Games/own.nup"
```

The final command requests an independent game build and currently reports the
unfinished integration. `--compat --backend PATH` explicitly selects an external
compatibility builder. Install engine dependencies from `requirements-engine.txt`
in your development environment. Python 3.14+ supports compressed NUP members;
the launcher alone supports Python 3.11+ with Tk.

`--generate build/prepared-ID --modules sdk --limit 3 --jobs 1` exercises the
included C generator on a prepared input. Unsupported instruction reports fail
the stage. Omit `--limit` for full generation; this still does not link a game.

## Local files and development

Preferences and logs stay in ignored `local/`. Extracted game files, normalized
modules, plans and generated C stay in ignored `build/` or `generated/`. No game
files, keys, saves or built game executables are included. Full extraction needs
the expanded archive size plus 2 GiB free space. Independent preparation leaves
the selected installation untouched. Run GPU preparation outside play sessions.

Run `python -m unittest discover -s tests`. See `AGENTS.md` for engineering rules,
`docs/MIGRATION.md` for implementation status, and `THIRD_PARTY_NOTICES.md` for
technical source attribution. The repository remains private; no public installer
or release is available. Contributions, issues and pull requests are welcome.
