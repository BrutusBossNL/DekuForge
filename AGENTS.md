# DekuForge

Reforging a legend. An independent desktop launcher and local game-build project.
The project's original source is open source under the root MIT license.

## Architecture

- `dekuforge/core.py`: installation selection and local preferences.
- `dekuforge/nup.py`: bounded NUP v1 parsing and verified streaming reads.
- `dekuforge/native.py`: archive inspection and extraction.
- `dekuforge/gameplan.py`: package selection, NSO metadata and independent build preparation.
- `dekuforge/builder.py`: optional compatibility adapter, not the independent builder.
- `dekuforge/build_ui.py`: Tk build window; `__main__.py`: home window.
- `run_launcher.py`: interpreter bootstrap; `run_builder.py`: build CLI.

## Engineering

- Write code, comments, documentation and commits in English. Keep player text in Dutch for now.
- Python 3.14+ is required for compressed NUP members. The launcher itself supports Python 3.11+ with Tk.
- Keep user preferences and logs in ignored `local/`; extracted data in `build/`;
  generated source in `generated/`. Do not put game bytes, keys or saves in commits.
- Pass filesystem paths as separate subprocess arguments; never concatenate shell commands.
- Keep process output off the Tk thread. Workers send events through a queue;
  only the main thread accesses widgets.
- Build into a separate owned directory. Never overwrite a selected installation
  or change its saves, settings or caches during independent preparation.
- Check bounds before allocating or decoding. Reject invalid archive names,
  traversal, directory cycles, case collisions and links outside the workspace.
- Verify streamed content before marking a stage complete. Write manifests atomically.
- Do not silently substitute an external builder when independent compilation fails.
- Keep planned stages visible as missing; extraction, manifests and inspector
  programs must never be reported as a playable game build.
- Keep one authoritative module layout and one explicit capability report.
  Future generation and runtime loading must consume the same layout.
- Generated code is changed through its generator, not edited by hand.
- Do not stop the user's game or start GPU-heavy preparation during play.

## Verification

Run `python -m unittest discover -s tests` and `git diff --check` before committing.
Run `python tools/check_source.py` after staging. Preserve the pinned engine bytes;
record future engine changes separately from the import manifest.
For isolated embedded Python, insert the project directory into `sys.path` in a
test bootstrap. Cover malformed inputs, streamed decompression, failed stages,
configuration preservation and subprocess boundaries with synthetic fixtures.
Never commit game-derived fixtures.

Changes to future instruction lifting need differential tests against an
independent ARM64 implementation. Changes to runtime memory or rendering need
isolated in-game validation and measurements from repeatable scenes.

The repository remains private until the owner explicitly requests publication.
