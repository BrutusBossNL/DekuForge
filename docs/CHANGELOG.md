# Release history

Component versions are independent. Published releases are not replaced in place.

## Launcher 0.3.0-preview.2 / buildkit 0.2.3 - updater compatibility

Fixes an application-update rollback from 0.2.0: that release's frozen helper
requires exactly 40 entries in the health report's `screens` field. Preview 1
returned 45 after adding Mods, causing a successful file installation to be
rolled back. The original 40 views remain in `screens`; five Mods views have
their own field, alongside the five report forms. All views are still tested.

New helpers validate the target release's declared counts, launcher version,
branding and hidden single-window checks instead of assuming a fixed total.
An isolated Windows acceptance test runs the original 0.2.0 helper: it reproduces
Preview 1's rollback, then installs Preview 2, verifies every package file and
confirms that synthetic saves, settings and tool caches are unchanged.

Preview 2 includes all Preview 1 features and fixes below. Stable stays on 0.2.0.
Updating the application no longer requires an uninstall or setup workaround.

## Launcher 0.3.0-preview.1 / buildkit 0.2.3 - Preview

Includes all changes since 0.2.0 listed below. Fixes
[issue #3](https://github.com/BrutusBossNL/DekuForge/issues/3): local build preparation
now stages the complete pinned NVIDIA Frame Generation library set and its notices
from the verified 0.10.1 application archive. Completed builds verify those files
beside the game. Previously only the separate DLSS upscaling library was prepared.
Existing builds need the managed game rebuild after updating. The stable renderer
and engine version 0.11.0 are unchanged. Hardware/driver requirements still apply;
dependency checks do not establish generated-frame performance on every GPU.

This is a GitHub prerelease for the Preview channel only; Stable remains 0.2.0.
The launcher explicitly labels itself Preview. No ROM, game assets, generated
game source, shaders, pipelines or compiled game binaries are release assets.

## Launcher 0.3.0 / buildkit 0.2.2 - original mod manager (included in 0.3.0-preview.1)

Implements [issue #1](https://github.com/BrutusBossNL/DekuForge/issues/1) with own
launcher code: add a folder/ZIP or use installed 7-Zip for 7z/RAR, normalize nested
layouts, switch mods On/Off, set priority and inspect RomFS file conflicts.
Play prepares mods before starting the game. Code mods require an explicit local
rebuild with receipt validation and rollback on handled build failure. Managed
game updates preserve mods and import receipts. Engine 0.11.0 is unchanged.

The native health check now visits 45 core views plus five report forms in five
languages, including Mods. See [mods.md](mods.md) for layout, limits and validation
scope; this manager does not make the underlying game engine independent.

## Launcher 0.2.1 - scroll-background fix (included in 0.3.0-preview.1)

Engine 0.11.0 and buildkit 0.2.1 are unchanged. Fixes
[issue #2](https://github.com/BrutusBossNL/DekuForge/issues/2): the page artwork
stays fixed while content scrolls. Translucent child surfaces are realigned after
scrollbar, mouse-wheel and keyboard-focus scrolling, including surfaces behind
ordinary layout frames. Cached viewport pixels are reused during scrolling.
Pixel regression tests cover both scroll directions and background refreshes.
Existing games, saves and game settings do not need rebuilding for this fix.

## Launcher 0.2.0 — first Early Access release

Buildkit 0.2.1; engine 0.11.0. This release uses a normal version, without a
preview suffix, and the launcher shows the Early Access stage. The preceding
private test releases remain recorded below for update compatibility and history.

The Windows launcher, installer, guided NX2navi save import, update path, issue
reports and Cheat Manager integration are included. Broader platform and in-game
acceptance limits remain documented in the README and roadmap. Release v0.2.0
is published. Unresolved component terms remain recorded in
[PUBLICATION_REVIEW.md](PUBLICATION_REVIEW.md); publication does not change them
or the scope of testing.

## Launcher 0.2.0-preview.2 / buildkit 0.2.1

Engine: 0.11.0 over the pinned stable NX2navi 0.10.1 reference. No new game-engine
version is introduced by these launcher changes.

- Guided NX2navi save-folder discovery and automatic active-game destination
  selection, with review, confirmation and a retained destination backup.
- Unified padded, scrollable pages; stable backdrop and corrected logo animation.
- Invisible installation/update health checks instead of a visible language tour.
- Reviewed hardware/log issue reports, managed-build removal fixes and save-aware
  native uninstallation with original game archive protection.
- Hidden native build-worker consoles and clearer Windows interruption recovery.
- Updated installation, update, SmartScreen and component-provenance documentation.

The launcher updater replaces the application itself. Build dependencies are
checked/downloaded when needed by a local build. Uninstalling is not required for
an ordinary launcher update. Private previews require repository access and the
Preview channel; draft releases remain hidden from the updater.

## Launcher 0.2.0-preview.1

Initial private setup/updater test identity. Several subsequent test packages
incorrectly reused this identity. That made different installed launchers look
identical and prevented normal newer-version detection. Those packages were
distributed through a draft release, which the updater intentionally ignores.
Preview 2 establishes a distinct update identity; later distributed changes must
advance the version rather than replacing a published package.
