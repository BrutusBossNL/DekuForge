# Delivery priorities

The owner has since prioritized DekuForge's in-game UI and Cheat Manager directly
after the stable Windows baseline, before Linux parity. The 0.11.0 candidate uses
the stable 0.10.1 renderer with a separate extension layer. Preparing portable tests
does not make a platform supported. Every game validation result must identify
the source revision, engine revision, game build ID, hardware and driver.

## 1. Windows parity

The retired renderer investigation is archived in
[RENDERER_GAP_ANALYSIS.md](RENDERER_GAP_ANALYSIS.md). Current stable-engine evidence
and delivery limits are in [STABLE_ENGINE_MIGRATION.md](STABLE_ENGINE_MIGRATION.md)
and [DISTRIBUTION.md](DISTRIBUTION.md).

The user entry point is `DekuForge.exe`, with the project's embedded icon and no
console or CMD script. A final distribution includes the launcher dependencies;
developer interpreter overrides are not an end-user installation workflow.

Deliver a local build from the owner's NUP input using the pinned stable 0.10.1
source backend and independently provisioned tools. The launcher wizard is now
connected to the complete extraction, CPU generation, native linking and shader
preparation pipeline. Its first full isolated build completed; the initial world
screenshots now show the missing terrain, foliage and sky correctly. The ordinary-start 60-second
world test measured 54.44 FPS on this machine, with complete captured surfaces
and a successful launcher Play/hide/return check. See
[STABLE_ENGINE_MIGRATION.md](STABLE_ENGINE_MIGRATION.md) for the exact evidence,
test-mode distinction and remaining acceptance checks. An empty-folder setup/tool download passed locally; full fresh-machine game
build acceptance remains pending.

Acceptance requires install, launch, title, save/load, controller mapping, audio,
rendering and a repeatable play session. Compare Kokiri Forest, Market Square,
Hyrule Field and a dungeon with the working reference installation on the same
machine, settings and save snapshot. Record average FPS, frame-time percentiles,
stalls, peak committed memory and peak VRAM. The owner must be able to continue
playing with no meaningful regression. An initial reference run and isolated
development measurements are recorded in `WINDOWS_BUILD.md`; the old experimental measurements do not establish parity for the new backend.

### Launcher updates and save migration

The original Mods page is implemented in launcher 0.3.0-preview.1: import, switches, RomFS
priority/conflicts, explicit code rebuilding and managed-update preservation.
See [mods.md](mods.md) for the tested contracts and remaining per-mod gameplay
acceptance. This does not replace the stable renderer or import upstream launcher
mod-management code.

Implemented locally: background public-release checks, Stable/Preview selection,
startup check preference, system-language default, existing-user-folder save
import/export and retained destination backups. The preview now implements application update installation, opt-in automatic
updates, recovery journals and separate engine rebuilding. Full clean-machine
acceptance, account migration and broader in-game save compatibility remain
pending. Automatic cache cleanup remains disabled.

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

The Windows candidate already composes the owned Cheat Manager. Validate its
features individually before claiming parity, then carry them to Linux: Equipment (bomb arrows with black aura, spin reach/charge), World markers,
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

The checked-in maintenance workflow requests a daily report and source tests at 09:17
Europe/Amsterdam. A workflow is active only after it reaches the default branch
and a run is observed. Reports are not automatic fixes or automatic PR merges.
Review new regressions, build failures and pull requests; reproduce defects,
add appropriate regression coverage and keep known-good releases available.
GitHub scheduling can be delayed or disabled; failures must remain visible.
