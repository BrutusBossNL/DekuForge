# DekuForge roadmap

This roadmap records planned work, not promises of support or delivery dates.
The repository remains private until Windows release gates and component
distribution requirements are satisfied.

## Windows - current priority

- Validate setup from a single EXE on a clean Windows machine: chosen install
  folder, own runtime, verified tool downloads, first local build and Play.
- Test Stable/Preview updates, downgrade, interruption recovery and failed-build
  rollback without losing settings, profiles or the previous working game.
- Complete Cheat Manager acceptance, additional scene/performance tests,
  controllers, audio and game-version-specific save import/load/write checks.
- Publish only launcher/setup, source and tooling after stability acceptance.
  Never publish game inputs, generated game source, compiled games or caches.

## Linux

Bring the stable core, portable build-tool provisioning, launcher and Cheat
Manager to Linux, then validate gameplay and performance against Windows.
**Contributors wanted specifically for Linux builds, drivers and testing.**
Source checks passing on Linux do not establish game support.

## iOS

Investigate the compiler/runtime path, Metal or a suitable graphics translation
layer, input, memory limits, device-local builds and permitted installation paths.
**Contributors wanted specifically for iOS builds and device testing.**
Feasibility work comes before any playable-build or distribution claim.

## VR - exploratory

Investigate OpenXR on supported desktop platforms, stereo rendering, camera and
UI comfort, controller mapping and performance. Start with a technical prototype
and a clear fallback to normal desktop play. No VR build or timeline is promised.

## Community and maintenance

Welcome issues and pull requests for DekuForge. Aim to acknowledge or review
within 48 hours, subject to volunteer availability. Review unsafe attachments and
content-rule violations without redistributing them. Preserve upstream credits,
component notices and useful reproducible tests.

Detailed engineering gates and evidence: [docs/ROADMAP.md](docs/ROADMAP.md).
