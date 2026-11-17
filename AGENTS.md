# DekuForge

Reforging a legend. An independent desktop launcher and local game-build project.
The project's original source is open source under the root MIT license.

## Architecture

- The base game backend is stable 0.10.1, pinned in `dekuforge/stable_engine.py`.
- Compose owned UI and cheats through `dekuforge/runtime_layer.py`; keep the
  stable renderer unchanged. Component versions belong in `dekuforge/components.json`.
- Ship only the launcher/tooling allowlist; never include local game build results.
- `tools/build_stable_translator.py` builds its unmodified shader translation logic.
- Include the separately verified 0.10.1 release pipeline data and controller art;
  the Git source checkout alone lacks these inputs and produced incomplete first-play frames.
- Test ordinary startup: `--shot` disables asynchronous pipeline work and cannot
  establish ordinary Play behavior. Preserve measured graphics preferences.
- Follow `docs/STABLE_ENGINE_MIGRATION.md`; the old `engine/` import is diagnostic history.

- `dekuforge/core.py`: installation selection and local preferences.
- `dekuforge/nup.py`: bounded NUP v1 parsing and verified streaming reads.
- `dekuforge/native.py`: archive inspection and extraction.
- `dekuforge/gameplan.py`: package selection, NSO metadata and independent build preparation.
- `dekuforge/builder.py`: optional compatibility adapter, not the independent builder.
- `dekuforge/ui.py`: single-window home, settings and three-step build wizard.
- `dekuforge/i18n.py`: English, Dutch, German, Spanish and French launcher text.
- `dekuforge/workflow.py`: validated requests and measured stage-level progress.
- `engine_overrides/`: original extensions composed over the immutable engine.
- `dekuforge/boot_profile.py`: bounded boot metadata and verified local assertions.
- `tools/build_runtime.py`: Windows host compilation, separate from final game linking.
- `launcher/main.c`: native Windows bootstrap with embedded project icon.
- `run_launcher.py`: interpreter bootstrap; `run_builder.py`: build CLI.

## Engineering

- Write code, comments, documentation and commits in English. All launcher text
  must have matching keys and placeholders in all five supported languages.
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
- Navigation stays inside one root window. Language switches preserve wizard
  state and logs. Use the project PNG bytes explicitly rather than automatic
  file-format detection; verify dimensions and rendered brand colors.
- Set the explicit Windows application identity before creating the root window.
  Keep the native executable, taskbar icon and visible logo consistent.
- Windows users start `DekuForge.exe`. Do not introduce CMD launchers into the
  user workflow; the final distribution includes its launcher dependencies.
- Time estimates use measured progress for the current stage; unknown work must
  stay indeterminate. Never invent an overall completion percentage or duration.
- Keep planned stages visible as missing; extraction, manifests and inspector
  programs must never be reported as a playable game build.
- Keep one authoritative module layout and one explicit capability report.
  Future generation and runtime loading must consume the same layout.
- Generated code is changed through its generator, not edited by hand.
- Do not stop the user's game or start GPU-heavy preparation during play.

## Release identities

Before distributing changed launcher behavior, increment the launcher version
in `dekuforge/components.json` (including the preview sequence). Increment the
buildkit for build-orchestration changes and the engine for game/runtime changes.
Do not reuse an installed preview identity for different delivered application
code. Never replace assets of a published release: publish a new version instead.
Draft assets may be prepared before release, but draft releases are deliberately
excluded from the updater. A private, published prerelease is visible only to
authorized repository users on the Preview channel; it does not make the repo
public. Keep game files out of every release. Component metadata is authoritative
for UI, executable packaging and release tags; avoid duplicate workflow defaults.

## Documentation accuracy

Every behavior, dependency, packaging or support-status change must update all
affected Markdown documentation in the same change. Review README, roadmap,
contribution instructions, build/distribution guides and third-party notices;
do not leave obsolete architecture or promises behind. Distinguish planned,
implemented and actually validated behavior. Scope measurements to their tested
revision, hardware and scenario; never turn a local smoke test into a platform
support claim. Mark retired investigation documents as historical and link to
the current status. Preserve imported license texts and attribution rather than
rewriting them to fit the project's branding. Verify documentation commands
against the current CLI and record remaining acceptance gaps honestly.

## Verification commands

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

`python run_launcher.py --self-test` renders 40 core views and five report forms across the five languages
without starting a game or changing preferences. `tools/check_launcher.py` checks
that this health check never maps a visible window: setup/update checks must not
flash pages or language changes in front of the user. It also checks
the native executable, embedded icon and the same one-window flow. Compile
emitted LDAPR test fragments with `tools/check_ldapr.py --compiler PATH` and
compare the resulting state with the ARM64 oracle.

The owner now prioritizes the stable Windows baseline, DekuForge in-game UI and
Cheat Manager before Linux parity, public distribution and iOS. Follow
`docs/ROADMAP.md`. The owner
now requires Windows setup, update, rollback and local game-rebuild acceptance
before changing repository visibility. Keep the repository private throughout
preview development. Keep source-test results separate from
in-game platform validation. Do not upload game inputs or derived game code to CI.
