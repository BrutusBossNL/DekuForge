# Contributing to DekuForge

Thank you for helping. DekuForge develops independently of NX2navi, using its
stable 0.10.1 source as a reference and foundation. Preserve credits and notices
for upstream and other reused components. Original contributions use the root
license; third-party components retain their own terms.

Issues, documentation, reproducible bug reports, performance measurements and
pull requests are welcome. We aim to acknowledge or review within **48 hours**;
this is a volunteer target, not a guaranteed response or merge deadline.
See [roadmap.md](roadmap.md) for current priorities. Linux and iOS build/testing
contributors are especially welcome; those platforms and VR remain planned.

## No game content

Never upload or link ROM downloads, encryption keys, game assets, extracted game
files, saves containing game content, generated game code, compiled games,
compiled shaders or pipeline caches. This applies to source, releases, issue/PR
text, attachments, screenshots containing embedded files and external download
links. We do not provide instructions for obtaining game files. Build locally
from your own legally obtained dump; share only project source and safe diagnostics.

Automated checks reject recognized forbidden files and generated-code markers.
Maintainers may close violating issues/PRs and notify the author in the GitHub
thread. Automatic attachment moderation is not active yet. Source checks cannot
inspect every external link, private attachment or disguised file; maintainers
must still review reports. Automation does not make prohibited uploads acceptable.
Do not repost a rejected attachment or quote its contents into a new report.

## Reporting bugs

Include DekuForge launcher and engine versions, local build ID, game version,
Windows version, CPU/GPU and driver, reproduction steps and relevant **text** logs.
The launcher's **Report a problem** page collects these details and bounded text
log excerpts for review. It filters common personal paths and token patterns;
check the preview yourself before sending. Browser reports use a shorter excerpt;
export the full text report when more detail is needed. Direct submission uses
an existing GitHub CLI/token, while browser submission uses your GitHub account.
Nothing is submitted without your action.

Remove personal paths, account details and tokens. Describe the save state rather
than uploading saves. For performance, include settings, scene, frame times and
repeatable measurements; distinguish source-test results from actual play tests.
Check existing reports and keep separate problems in separate issues.

## Pull requests

Describe the concrete problem, resulting behavior and validation. Keep changes
focused, use English for code/comments/docs and translate launcher UI strings in
all five languages. Add tests for meaningful behavior and failure paths, with
synthetic fixtures only. Never change the immutable historical `engine/` import;
compose current extensions through the pinned stable-source layer.

Before committing, run:

```text
python -m unittest discover -s tests
python tools/check_content.py
git diff --check
```

`check_content.py` checks staged files; CI checks the full tracked checkout.
Stage your intended source changes before running that check. Do not stage local
inputs, tool binaries or build results. See [docs/building.md](docs/building.md).

Instruction-lifting changes need comparison with an independent ARM64 oracle.
Runtime, graphics and memory changes need isolated in-game validation; source
checks alone are insufficient. Installer/updater changes need bounded-package,
rollback, interruption and save/settings-preservation tests. Never stop a tester's
running game or overwrite their working installation to run an experiment.

## Review and release

Maintainers review contributions before merging. The project stays private until
Windows installation/update acceptance passes and component distribution terms
are resolved. Publishing a setup must include
only the launcher and tooling, with appropriate notices. Every player builds
locally from their own input. Do not publish generated game artifacts to CI.
