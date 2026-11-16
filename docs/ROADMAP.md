# Delivery priorities

The order below is the owner's explicit delivery order. Preparing portable tests
does not make a platform supported. Every game validation result must identify
the source revision, engine revision, game build ID, hardware and driver.

## 1. Windows parity

The user entry point is `DekuForge.exe`, with the project's embedded icon and no
console or CMD script. A final distribution includes the launcher dependencies;
developer interpreter overrides are not an end-user installation workflow.

Deliver a standalone build from the owner's NUP input, using included source
and independently provisioned open-source build tools. No external application
may silently perform the build. Current gates are incomplete: remaining CPU
instructions, game-specific host calls and boot, NVN2/shader integration, RomFS
assembly, native linking and isolated in-game validation.

Acceptance requires install, launch, title, save/load, controller mapping, audio,
rendering and a repeatable play session. Compare Kokiri Forest, Market Square,
Hyrule Field and a dungeon with the working reference installation on the same
machine, settings and save snapshot. Record average FPS, frame-time percentiles,
stalls, peak committed memory and peak VRAM. The owner must be able to continue
playing with no meaningful regression. An initial reference run and isolated
development measurements are recorded in `WINDOWS_BUILD.md`; the test world
still has rendering defects. These measurements do not establish parity.

### Launcher updates and save migration

Implemented locally: background public-release checks, Stable/Preview selection,
startup check preference, system-language default, existing-user-folder save
import/export and retained destination backups. Not yet delivered: automatic
update installation, validated rollback, account migration and in-game save
compatibility. Automatic update and cache cleanup controls remain disabled.

The Windows delivery also requires an Updates action that checks releases from
the DekuForge repository. Show the installed launcher version, source revision,
game build ID and available release separately. Download only source/tooling;
build game-derived code locally. Reuse verified build products whose inputs,
compiler options and dependencies are unchanged. Install a completed build
atomically and retain the previous working installation when an update fails.

Offer import of an existing NX2navi save folder into a separate DekuForge
profile. Never move, modify or delete the source saves. Validate the selected
game/version and save layout, back up the destination before replacement, and
test loading and saving the imported copy. Preserve saves outside versioned
application folders. Document compatibility by tested game version; do not
promise that a save written by a newer game can always be loaded by an older
one. Keep a pre-upgrade save snapshot for rolling back the game build.

## 2. Linux parity

After Windows passes, validate the same functions and scenarios on Linux. Keep
platform-independent preparation, generation and manifests shared. Use the Linux
runtime/platform layer and native toolchain; validate input, audio, Vulkan,
filesystem paths, saves and packaging. Python tests on Linux alone do not satisfy
the native game acceptance gate.

## 3. Custom features

Port the owned cheat manager, fixes and extensions after both desktop baselines
pass: Equipment (bomb arrows with black aura, spin reach/charge), World markers,
health refill/max-heart handling, controller fixes and measured memory fixes.
Preserve per-age filtering, night icons, collected-state checks and independent
category toggles. Validate fixes individually and repeat affected baseline tests.

## 4. Public open-source repository

The owner has authorized making the repository public at this priority, after
priorities 1–3 pass. Until then, keep it private. Preserve component notices,
provide source/build instructions, accept issues and pull requests, and enforce
the game-content boundary in source checks and contribution templates.

Never share ROMs, game assets, keys, generated game source or compiled game
binaries. A launcher package may contain only independently distributable tooling
and no game-derived code or content. No game inputs belong in CI.

## 5. iOS

Investigate and validate a native ARM64/iOS path after the desktop delivery and
publication gates. A Windows executable cannot be repackaged as an iOS app.
Assess CPU execution/translation, iOS platform services, Metal or an appropriate
graphics translation layer, memory constraints, input, audio, signing and device
installation. A successful signed device build and actual game session are
required. macOS/Xcode and a suitable device are not available or verified in this
workspace; do not claim iOS support from a desktop test.

## Maintenance

Prepare a daily repository report and source tests, targeting 09:17
Europe/Amsterdam. A workflow is active only after it reaches the default branch
and a run is observed. Reports are not automatic fixes or automatic PR merges.
Review new regressions, build failures and pull requests; reproduce defects,
add appropriate regression coverage and keep known-good releases available.
GitHub scheduling can be delayed or disabled; failures must remain visible.
