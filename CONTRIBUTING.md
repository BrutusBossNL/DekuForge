# Contributing to DekuForge

Issues, bug reports, performance measurements, documentation and pull requests
are welcome. Follow the current delivery order in `docs/ROADMAP.md`.

Never upload or link ROM downloads, game assets, encryption keys, generated game
source, or compiled game binaries. This applies to commits, issues, pull requests,
attachments and releases. Use synthetic test fixtures. Share diagnostics only
after removing personal paths, secrets and any game content.

For a bug, include the project revision, platform, CPU/GPU, driver, game version,
steps to reproduce and relevant text logs. For performance, include settings,
scene and repeatable measurements. Do not include saves without first checking
their contents and ownership; a description or synthetic fixture is preferred.

For a pull request, explain the problem, behavior after the change and how it was
validated. Run the source checks and relevant tests. Preserve source attribution.
Instruction changes require independent ARM64 comparison; runtime and graphics
changes require isolated game validation. Source tests alone do not prove that a
game build works. Pull requests are reviewed before merging.
