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

Acceptance gates and current findings are in
[INDEPENDENT_ENGINE.md](INDEPENDENT_ENGINE.md) and
[INDEPENDENT_EVIDENCE.md](INDEPENDENT_EVIDENCE.md).
