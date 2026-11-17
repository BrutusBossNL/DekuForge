<p align="center">
  <img src="assets/branding/logo.png" alt="DekuForge" width="680">
</p>

# DekuForge

**Reforging a legend.**

ROMs, game assets, keys, generated game source and compiled game binaries must
never be shared in this repository, its issues, pull requests or releases.
Issues and pull requests for the project itself are welcome; see `CONTRIBUTING.md`.

An open-source launcher and local game-build project, with a forest-green and
gold interface inspired by its leaf-and-forge logo. Original project code is MIT licensed. Reused engine components
retain their accompanying notices.

## Start

Start the Windows launcher with `DekuForge.exe`. The native executable has
the project's embedded icon and starts without a console window. The desktop
window sets its own application identity rather than inheriting the caller's.
Select an existing game installation to play without changing saves or settings.
Development from source can use `python run_launcher.py` with Python and Tk
installed. The local native bootstrap can read a developer interpreter path from
ignored `local/python-path.txt`; otherwise it checks the project's bundled Python
or `.venv`. The final user distribution must include the needed launcher runtime.
No CMD start script is provided.

## Game builder

The game backend is being migrated to the complete stable 0.10.1 engine. The
DekuForge launcher and management UI are retained. See
[stable-engine migration](docs/STABLE_ENGINE_MIGRATION.md) for the pinned revision,
current validation status and fresh-machine limitations. The migration build is
experimental until the rendering and gameplay checks pass.

The launcher keeps Home, Updates, Saves, Build game and Settings inside one window.
Home uses three artwork cards: Play (active game version), Update (latest release
in the selected channel), and (Re)build (game dump path). Pointer hover and keyboard
focus highlight the card; Tab navigates and Enter or Space activates it. Startup
first shows a very dark green gradient, brighter at its center; the unfinished
layout remains hidden until that cover has been painted. Artwork is revealed and
then fades to 46%. The navigation has a subtle green gradient behind its logo and
text. A logo starts horizontally centered with
32 pixels of top padding at 135% of its navigation size, shrinks without fading,
and moves into the navigation as it slides in. The three cards then rise in sequence.
Controls, dropdown lists and the Windows 11 native title bar use the forest and
gold palette; navigation buttons highlight on hover and keyboard focus.
Settings offers English, Nederlands,
Deutsch, Español and Français; changes apply immediately. The launcher can hide
while the game runs and restore the same window after it closes. New preferences
default to the system UI language, with English as the unsupported-language fallback.

Updates checks public repository releases on request or at startup, with Stable
and Preview channels. It displays the launcher version separately from the latest
release. A version selector lists eligible releases, including older versions.
Downloading/installing a selected release is not implemented yet; its button and
automatic-update setting remain disabled. Existing local builds can be switched
without rebuilding. Build cache is currently always retained.

Build game also opens the installed-build library. Successful builds are recorded
locally, and the native linking tool records experimental builds with their game
version. Select a build and choose Set active to change what Play starts. Deleting
an owned build requires confirmation and a separate choice to retain saves. If
retained, its complete `profile` is copied to `local/retained-saves` before removal.
An unsuccessful backup prevents removal. Externally selected installations cannot
be deleted here. Switching builds does not migrate or modify their individual saves.

Saves offers ZIP export and folder/ZIP import for an explicitly selected existing
user save folder containing `slot_00/progress.sav`. Select the user folder, not
the game installation. Import preserves slots absent from the source and retains
the previous destination beside it as a dated backup. Close the game before an
import. The source stays untouched. In-game compatibility and automatic account
migration remain unverified; a successful copy is not proof that the game can load it.

Choose **Build game** for the three-step wizard: game archive, installation
folder, then building with a live log, measured elapsed time and stage estimates
when there is enough progress to calculate them. Unknown work stays indeterminate.
Your current installation and saves are protected from being selected as output.
The independent engine reads NUP archives, including files with another extension
that contain the NUP format. Nintendo 64 ROMs need a different engine.

- The command-line archive check validates the index, checksum, paths and directory structure.
- Command-line extraction streams and verifies files into a fresh build folder.
- The command-line preparation stage selects executable modules from base/update
  packages, verifies their content and writes NSO metadata and a module layout.
- The independent build runs preparation, module decoding and SDK generation
  before attempting the larger game modules. Experimental native linking now
  succeeds and the isolated test reaches the title and game world. World rendering
  still flickers and loses surfaces; intro movie quality also remains incorrect. The launcher
  does not yet deliver a verified playable independent build.
- An optional command-line compatibility build uses an existing installation.
  It is never silently substituted for an independent build.

Included engine source contains an ARM64 lifter, C generator, host runtime,
Vulkan renderer, shader translator and native build tools. This baseline is not
yet validated for game 1.1.1. Full SDK generation found 68 unsupported instructions
across 45,907 functions after return and acquire-load extensions. No independently
built playable executable is available yet. Existing installations can still be
started from Home; no game is automatically closed for testing.

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

The native launcher can be built with `python tools/build_launcher.py --toolchain
PATH_TO_COMPILER_BIN` (Clang and windres). This packs the application emblem into a
multi-size Windows icon and embeds product metadata. Packaging needs Pillow from
`requirements-dev.txt`. `python tools/check_launcher.py` verifies the native
bootstrap and exercises 25 views across five languages in one window.

Delivery order: Windows parity, Linux parity, custom cheats/fixes, public release,
then iOS. See `docs/ROADMAP.md` for measurable acceptance gates. The repository
stays private until the first three priorities pass. Desktop source tests do not
establish Linux game compatibility or iOS support.

The Windows host runtime can be compiled separately with
`python run_builder.py --runtime build/prepared-ID --toolchain PATH_TO_UCRT64_BIN`.
This creates a development library and diagnostic report in `build/windows-runtime`;
it does not create a playable executable. Constructor assertions are derived from
the verified local module metadata instead of another game's version constants.
