# Building DekuForge from source

The independent engine on `main` uses the pinned GPL Hookshot provider. See
[the Windows development guide](OPEN_ENGINE_EVALUATION.md) for the complete
build and [the distribution guide](DISTRIBUTION.md) for release packaging.

The independent development route also provides read-only module analysis:
`python tools/analyze_independent.py --exefs PATH --out local/analysis.json`.
This reuses extracted input; it neither builds nor validates a playable game.
Use a new report filename. Consult [earlier evidence](INDEPENDENT_EVIDENCE.md)
before repeating retired experiments. Keep the installed game separate from tests.

Windows x64 is the current acceptance target. Linux source checks run in CI;
Linux gameplay, iOS and VR are not validated DekuForge targets yet.

## Source and bootstrap

Clone this repository to a writable development directory. No game input is
required to build the launcher or setup. Keep the component versions in
`dekuforge/components.json` and pinned tool manifests in sync.

From PowerShell in the checkout:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/bootstrap_runtime.ps1 -Root $PWD
```

Read `local/python-path.txt` to locate the installed Python executable. Use that
interpreter for the commands below (shown as `python` for readability).
This script is the developer bootstrap. A built `DekuForge.exe` and the setup
prepare the same pinned runtime natively without PowerShell
(`DekuForge.exe --prepare-runtime`).

```text
python tools/provision_open_tools.py --work build/open-engine-work --jobs 4 --configure-launcher
python tools/build_launcher.py --toolchain local/build-tools/hookshot-llvm-20261104/bin
python tools/build_setup.py --toolchain local/build-tools/hookshot-llvm-20261104/bin
```

Preparation verifies and caches the pinned engine source, LLVM-MinGW, SDL,
graphics and codec dependencies and the Python build wheels. Existing verified
versions are reused. This path uses the standalone Python and toolchain.

Setup, launcher ZIP, `DekuForge-independent-release.json`, RecompLauncher
portable ZIP and standalone manifest appear in `build/releases/`. Use the
[distribution guide](DISTRIBUTION.md) for the release asset list.

## Build a local game

Use the launcher wizard, or provide your own supported game 1.1.1 NUP:

```text
python tools/build_open_game.py --nup "YOUR_OWN_GAME.nup" --out build/windows-independent
```

Use a separate destination, outside the active game. The builder extracts inputs,
generates CPU code, links the runtime, prepares shaders/pipelines and generates
button prompts locally. Keep ample space for extracted assets, build cache and
one separate rollback build. First-build duration depends on hardware and cache;
the UI reports measured stage progress rather than a fixed promise.

The provider pin is recorded in `dekuforge/hookshot_source.json`. DekuForge
composes its extensions during the local build. The NX2navi 0.10.1 build route
belongs to the frozen Legacy release.

## Resuming an interrupted build

Keep the launcher open while building. If a tool exits with `0xC000013A`
(`3221225786` or `-1073741510`), Windows reported an interruption; this alone does
not identify its source or establish a shader/compiler defect. The launcher
preserves the detailed log and reports the interruption separately. Native tools
started by the pinned build worker run without interactive console windows.

Retry with the same unchanged archive and owned build destination. Completed
extraction/RomFS stages can be reused when their recorded input identity matches;
other stages and objects are reused only when their build keys match. Do not
delete the build folder or select a new destination just to retry. Failed or
partial stages are not marked complete. Recovery is not an automatic retry loop.

## Verification and content boundary

```text
python -m unittest discover -s tests
python run_launcher.py --self-test
python tools/check_launcher.py
python tools/check_content.py
git diff --check
```

A native self-test checks the icon, 40 core UI views and five report forms, not gameplay.
The self-test keeps its window withdrawn, including during setup/update health
checks; `window_was_mapped` must be false in its report. Normal startup is tested
separately and should show only the user's chosen language.
Validate game changes with normal startup and repeatable scenes; special screenshot mode changes
pipeline scheduling. Keep game screenshots and measurement captures local.

Game-generated files stay in ignored `build/`, `generated/` or the selected owned
installation; tools, preferences and logs stay in ignored `local/`, `python/` and
`pydeps/`. Compiled shader headers exist only in the ignored staged engine. Never
commit ROMs, game assets, generated game code, compiled games, shaders or caches.
`tools/check_content.py` wraps the same source-boundary check used in CI.
