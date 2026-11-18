# Licensed engine evaluation

This is developer tooling on `independent`, not a released installer or a claim
of gameplay parity. Main's working installation is outside the experiment.
The default launcher builder remains gated until an evaluated provider is ready.

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
Development currently uses Python 3.14.9, Capstone 5.0.9 and a pinned official
LLVM-MinGW 20261104 compiler. Codec/header libraries and control DLLs retain
their individual FFmpeg, Vulkan, SPIR-V, VMA and SDL terms. These dependencies
are not yet provisioned by an independent installer.

The evaluation requires explicit compiler and dependency paths. It does not
silently select another project's compiler, source tree, generated runtime,
hot-function profile, shader cache or game installation.

## Stages

### Complete experimental Windows NUP build

Use a development Python 3.14+ with the repository's development requirements.
This is an opt-in developer route; it does not install Python or ship a setup.
From the independent checkout:

```powershell
python -B tools/provision_open_tools.py --work build/open-engine-work --jobs 4 --configure-launcher
python -B tools/build_open_game.py --nup "C:\path\to\your-own.nup" --out build/windows-independent
python run_launcher.py
```

For a native development entry point, compile `tools/build_launcher.py
--toolchain local/build-tools/hookshot-llvm-20261104/bin` with Python. Put the
absolute path of your chosen development `python.exe` in the UTF-8 file
`local/python-path.txt`. Then `DekuForge.exe` opens the same launcher without a
console. This explicit development override is accepted only for the
`development-interpreter` component; it neither downloads main's interpreter nor
completes independent runtime packaging. The selected interpreter needs Tk and
Pillow and must remain installed.

The first command verifies the pinned GPL source and downloads hash-pinned
LLVM-MinGW, codec/header and SDL packages. It extracts only generic dependencies,
then compiles dav1d from source. The engine and instruction lifter are compiled
from verified source; no NX2navi install, downloaded compiled engine or shared
game shader cache is used. `--source build/<verified-source>` reuses an existing
verified checkout. `--configure-launcher` explicitly enables the experimental
Build game wizard; without it the default backend stays gated.

The output contains `DekuForgeGame.exe`, its own image/RomFS, libraries, notices,
runtime metadata and `user/save`. Keep every output under this worktree's
`build/`; the original NUP must remain outside the output. Work, source and
installed game folders must be separate. Keep the same work folder to reuse
unchanged object files. The provider cleans its transient native link folder
after copying the installation, so never register an executable inside work.

Shader preparation can be long on a cold cache. The pinned provider deliberately
requires an additional ordinary-play driver-cache warmup on NVIDIA after its
prepare-only process. DekuForge now starts its own preparation child with a
separate empty profile, waits for actual Vulkan frames, and closes only that
child before reporting success. It never manufactures the provider's completion
marker. Inspect `dekuforge-play-cache.log` inside work for this final stage.
`--no-prepare-shaders` is diagnostic only and skips that readiness check too.

The launcher retains its original async Play, save import/export, build inventory,
release list/notes and update-outcome views. Main-channel installs remain blocked.
Asset mods use immutable verified snapshots so the first enabled provider wins,
matching the launcher order; disabled mods are excluded. No base game file is
overwritten. Code-patch/cheat mods remain blocked. The provider's Windows path
limit is checked before starting; excessively long mod paths report an error.
Crash reports include bounded text logs and graphics settings, never binary
shader/pipeline caches. Deleting an owned build can preserve its `user` profile,
as well as the legacy `profile` layout; the original game archive is protected.

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
