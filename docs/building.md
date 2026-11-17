# Building DekuForge from source

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

```text
python tools/prepare_installation.py
python tools/build_launcher.py --toolchain local/build-tools/native/msys64/ucrt64/bin
python tools/build_setup.py --toolchain local/build-tools/native/msys64/ucrt64/bin
```

Preparation verifies and caches the stable engine source, its required release
metadata, the native compiler/SDL/Vulkan headers, shader tools, .NET SDK and Python
dependencies. Existing verified versions are reused. The managed shader translator
is built on demand; the Windows path does not require system-wide MSYS2 or Python.
Downloads are pinned by hashes or verified against their provider metadata.

The setup, launcher package and updater descriptor appear in `build/releases/`.
Ship `DekuForge-Setup.exe` to users; publish all three release assets so the launcher
can use the verified ZIP and `DekuForge-release.json` for future updates. Tag and
component identities must match. Do not publish the whole build directory.

## Build a local game

Use the launcher wizard, or provide your own supported game 1.1.1 NUP:

```text
python run_builder.py --nup "YOUR_OWN_GAME.nup" --out "ABSOLUTE_EMPTY_GAME_DIRECTORY"
```

Use a separate destination, outside the active game. The builder extracts inputs,
generates CPU code, links the runtime, prepares shaders/pipelines and generates
button prompts locally. Keep ample space for extracted assets, build cache and
one separate rollback build. First-build duration depends on hardware and cache;
the UI reports measured stage progress rather than a fixed promise.

The engine is pinned to NX2navi 0.10.1 with DekuForge extensions composed separately.
Upstream [building instructions](https://github.com/tangerineturtle1/NX2navi/blob/main/docs/building.md)
and [BuildKit notes](https://github.com/tangerineturtle1/NX2navi/blob/main/docs/README-BuildKit.md)
are useful background, but their current main branch can differ from our pin.
Do not replace our backend with a newer upstream checkout without validation.

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

A native self-test checks the icon, 40 core UI views and five report forms, not gameplay. Validate game
changes with normal startup and repeatable scenes; special screenshot mode changes
pipeline scheduling. Keep game screenshots and measurement captures local.

Game-generated files stay in ignored `build/`, `generated/` or the selected owned
installation; tools, preferences and logs stay in ignored `local/`, `python/` and
`pydeps/`. Compiled shader headers exist only in the ignored staged engine. Never
commit ROMs, game assets, generated game code, compiled games, shaders or caches.
`tools/check_content.py` wraps the same source-boundary check used in CI.
