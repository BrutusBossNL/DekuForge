# Licensed engine evaluation

This guide covers the developer build route on `independent`. The Preview
installer configures the same experimental Windows builder in its own folder.
Gameplay parity with main remains under evaluation.

`tools/evaluate_open_engine.py` evaluates the GPL Hookshot provider pinned in
`dekuforge/hookshot_source.json`. Source archive and individual Git blob checks
retain its licenses/notices and reject changes to original files. Compiler
outputs may coexist below a staged tree; they are never committed.

## Inputs and tools

Use your own supported 1.1.1 game files. This guide does not supply game files
or explain how to obtain them. Keep verified, decompressed ExeFS inputs under
this worktree's `build/`, separate from generated output. The provider's
`nx2/unpack.py` can normalize copies of compressed modules; never point it at
the user's original files.

Python requirements are those in the pinned provider's `requirements.txt`.
Development now uses its own Python 3.14.10, Capstone 5.0.9 and a pinned official
LLVM-MinGW 20261104 compiler. Codec/header libraries and control DLLs retain
their individual codec, Vulkan, SPIR-V, VMA and SDL terms.

The evaluation requires explicit compiler and dependency paths. It does not
silently select another project's compiler, source tree, generated runtime,
hot-function profile, shader cache or game installation.

## Stages

### Complete experimental Windows NUP build

This Windows developer route provisions its own generic Python/Tk and tools.
From PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/bootstrap_runtime.ps1 -Root $PWD
$forgePython = (Get-Content local/python-path.txt -Raw).Trim()
& $forgePython -B tools/provision_open_tools.py --work build/open-engine-work --jobs 4 --configure-launcher
& $forgePython -B tools/build_launcher.py --toolchain local/build-tools/hookshot-llvm-20261104/bin
.\DekuForge.exe
```

Alternatively build explicitly with `& $forgePython -B tools/build_open_game.py
--nup "C:\path\to\your-own.nup" --out build/windows-independent`.

The bootstrap verifies official Python-build-standalone 20261110 / CPython 3.14.10
and Pillow 12.0.0, preserves their notices, and imports Tk/Pillow before committing
the runtime marker. Bounded tar/ZIP validation rejects links, traversal and
aliases. It does not download an NX2navi runtime. The tool provisioner installs
hash-pinned NumPy/lz4/fontTools wheels into this owned Python only. External
development Python is checked and never changed automatically; install
`requirements-open-engine.txt` explicitly if needed.

The tool provisioner verifies the pinned GPL source and downloads hash-pinned
LLVM-MinGW, codec/header and SDL packages. It extracts only generic dependencies,
then compiles dav1d from source. The engine and instruction lifter are compiled
from verified source; no NX2navi install, downloaded compiled engine or shared
game shader cache is used. `--source build/<verified-source>` reuses an existing
verified checkout. `--configure-launcher` explicitly enables the experimental
Build game wizard; without it the default backend stays gated.

The renderer builds FSR 3.1 from source, and the Windows preview builder also
compiles FSR 4 support. Read [AMD's FSR SDK license](https://github.com/GPUOpen-LibrariesAndSDKs/FidelityFX-SDK/blob/7539ae8b6568ad29ed78a753404351daf3b5cca7/Kits/FidelityFX/docs/license.md).
If you accept it, set `"amd_fsr4_license_accepted": true` in
`local/open-engine-builder.json` before building. The pinned provider verifies
and installs AMD's SDK DLLs locally. FSR 4 availability depends on the GPU.

The output contains `DekuForgeGame.exe`, its own image/RomFS, libraries, notices,
runtime metadata and `user/save`. Keep every output under this worktree's
`build/`; the original NUP must remain outside the output. Work, source and
installed game folders must be separate. Keep the same work folder to reuse
unchanged object files. The provider cleans its transient native link folder
after copying the installation, so never register an executable inside work.

The independent builder generates the optional World map materials in
`<game>/.world-markers` from the local ROM filesystem. The same prompt pipeline
still applies the selected controller glyphs to the map's derived UI resources.
A user mod replacing the affected UI archive, MapParam or resource-size table
takes priority and disables World markers for that launch.

Shader preparation can be long on a cold cache. The pinned provider deliberately
requires an additional ordinary-play driver-cache warmup on NVIDIA after its
prepare-only process. DekuForge now starts its own preparation child with a
separate empty profile, waits for actual Vulkan frames, and closes only that
child before reporting success. It never manufactures the provider's completion
marker. The validation child waits for pipeline preparation to finish and
explicitly saves the driver cache next to the game executable before the build
can succeed. Inspect `dekuforge-play-cache.log` inside work for this final stage.
Graphics and compute pipeline preparation have separate measured progress stages;
finishing the graphics count alone is not reported as a complete build.
The experimental adapter selects the provider's documented `RX_VK_LOAD=start`
mode. On the measured NVIDIA driver, cache-only loading at program creation
still missed thousands of prepared pipelines and left incomplete initial world
frames; start mode keeps known programs and pipelines ready before the title.
It still recreates the in-memory pipeline handles on each launch. Two starts
of engine `0.1.0-independent.7` under the ordinary Windows account read the
persisted cache and reached the menu in about 30 seconds each. Cold-cache
timings, portable support and matched performance with main remain open.
See the [evidence ledger](INDEPENDENT_EVIDENCE.md) for the measured scope.
`--no-prepare-shaders` is diagnostic only and skips that readiness check too.

The launcher retains its original async Play, save import/export, build inventory,
release list/notes and update-outcome views. Main-channel installs remain blocked.
Controller prompt generation requires the locked Windows build wheels in
`requirements-open-engine.txt`. The build checks the generated font and texture
packs before selecting the new executable. Auto prompts follow input from the
most recently used SDL controller. Controls keeps separate prompt and layout
choices so a manually remapped pad can keep its own button icons.
The build fingerprints the independent gameplay hook source as part of the CPU
translation key. On 1.1.1, every expected guest instruction must match before
any magic or spin hook is attached. The Cheat Manager's one-shot bottle editor
validates each unlocked slot and the game's list of allowed contents.
Asset mods use immutable verified snapshots so the first enabled provider wins,
matching the launcher order; disabled mods are excluded. No base game file is
overwritten. Code-patch/cheat mods remain blocked. The provider's Windows path
limit is checked before starting; excessively long mod paths report an error.
Crash reports include bounded text logs and graphics settings, never binary
shader/pipeline caches. Deleting an owned build can preserve its `user` profile,
as well as the legacy `profile` layout; the original game archive is protected.
With the experimental builder enabled, **Updates → Rebuild for current
version** opens the regular build progress view and starts the independent
builder. It reuses a compatible owned installation and its cache, or creates
a separate local build for a custom installation. It prompts for an archive
when the saved path is unavailable. Main-engine rebuilds through the legacy
update API remain disabled.

### Individual investigation stages

Fetch and verify source only:

```powershell
python -B tools/evaluate_open_engine.py fetch
```

For a prepared local input, run the explicit stages (replace paths with owned
directories under this worktree; preserve the same paths for incremental reuse):

```powershell
python -B tools/evaluate_open_engine.py lift --source build/<verified-source> --exefs build/<input>/exefs --work build/<evaluation>/work --toolchain local/build-tools/<llvm-mingw>
python -B tools/evaluate_open_engine.py compile --source build/<verified-source> --exefs build/<input>/exefs --work build/<evaluation>/work --toolchain local/build-tools/<llvm-mingw> --deps local/build-tools/<codec-headers> --jobs 4
python -B tools/evaluate_open_engine.py shaders --source build/<verified-source> --exefs build/<input>/exefs --romfs build/<input>/romfs --work build/<evaluation>/work
```

The output marker binds the work directory to source revision and module hashes.
An unowned existing directory or a different input is rejected. Inputs, source
and generated output stay separate. Commands never select a game, import saves
or overwrite a running installation. Generated C, images, executables and shader
seeds stay private in ignored output directories.

Before play, prepare the generated shaders/pipelines through the provider's
documented runtime command. Test ordinary startup separately, using a copied
save and the matching account identity. Do not benchmark a menu as gameplay,
or compare instrumented captures with an uninstrumented baseline.

Compilation applies `dekuforge/open_engine_branding.py`: generated GPL-attributed
copies of the window/menu source use the DekuForge name, logo and forest palette.
The original provider files remain unchanged. An adaptation manifest records both
hashes. The engine component version is embedded without rebuilding unrelated
guest-code objects. Internal DLL/cache names remain provider names for ABI/cache
compatibility; attribution remains intact. This adaptation module is GPL-3.0-or-
later, not covered by the root MIT grant; see the third-party notices.

`dekuforge/romfs_directory.py` extracts a selected complete NUP RomFS snapshot
directly to an owned directory, with atomic per-file commits and verified resume.
It does not merge base/update trees or write into the user's archive. This avoids
keeping both a packed image and an unpacked copy for the direct-file provider.
`dekuforge/open_engine_runtime.py` validates explicit local launch resources;
metadata cannot supply arbitrary command arguments, environment overrides or
resources outside this worktree. These modules are not yet an automatic installer.

For Windows AV1 movies, build dav1d into the explicit codec package before the
game compile; the older generic FFmpeg package has no AV1 decoder. This avoids a
dependency on Microsoft's separately installed Store extension:

```powershell
python -B tools/build_av1_decoder.py --compiler local/build-tools/<llvm-mingw> --deps local/build-tools/<codec-headers> --jobs 4
```

The tool checks fixed archive hashes, the VideoLAN 1.5.4 source-tree hash, safe
extraction and existing files. It builds the BSD-2-Clause decoder with SIMD and
retains its COPYING file. Meson, Ninja and NASM are generic build tools, not game
engines. The default build wizard does not yet provision this dependency.

An existing experimental executable can be connected to this branch's Play
action without a command wrapper. Provide existing absolute or project-relative
paths; all resources must remain under this worktree's `build/`:

```powershell
python -B tools/configure_open_game.py --executable build/<native>/DekuForgeGame.exe --image build/<work>/sa/image/image.bin --romfs build/<input>/romfs --user build/<profile> --activate
```

This registers an experiment, not a completed wizard build. It refuses to replace
existing runtime metadata and leaves main's launcher and saves alone. The build
library does not own/delete the shared source-evaluation workspace. A future
standalone installation needs its own complete build lifecycle and acceptance.

Acceptance gates and current findings are in
[INDEPENDENT_ENGINE.md](INDEPENDENT_ENGINE.md) and
[INDEPENDENT_EVIDENCE.md](INDEPENDENT_EVIDENCE.md).
