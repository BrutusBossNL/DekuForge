<p align="center"><img src="assets/branding/logo.png" alt="DekuForge" width="600"></p>

# DekuForge

**Reforging a legend.** DekuForge builds a local Windows game from your own
game archive. Main uses the independent build path with the pinned GPL Hookshot
engine and DekuForge's launcher and runtime adaptations. Thanks to the NX2navi
contributors for the original reference and to the Hookshot contributors for
their work on the engine.

> [!IMPORTANT]
> No ROMs, game assets, keys, generated game source or compiled games are supplied.
> Use your own legally obtained game dump. Do not share game-derived outputs.

## Current status

Windows is the current release platform. The **Stable** channel now ships
the independent launcher, build tools and source-based engine path. Preview
and Experimental are for testing. Gameplay parity with the retired engine and
full coverage on AMD hardware are still under evaluation.

The last NX2navi-based release is [DekuForge 0.3.0 Legacy](https://github.com/BrutusBossNL/DekuForge/releases/tag/v0.3.0).
It is retained for existing users as a frozen release. All new development
and releases use the independent build path.

## Features

- The default independent backend reports its real capabilities with `--doctor`.
- Original NUP inspection, package selection, verified module preparation and the
  launcher/save-management tooling are retained for development.
- The original A64-to-C translator covers integer arithmetic/flags, branches and
  scalar/register-offset and paired memory operations with a bounded native
  correctness runner, checked against an
  independent ARM64 oracle. It is not a complete CPU backend.
- A guest-memory prototype loads verified NSO segments and bounded MOD0/ELF
  symbol and RELA/RELR pointer relocations; synthetic cross-module calls execute.
  Read-only module analysis reuses extracted inputs without rebuilding them.
- DekuForge's mod manager, release list/notes and update outcome reporting
  are retained. Asset-mod order and On/Off selections now reach the independent
  runtime through verified snapshots. Code-mod builds remain disabled.
- Two pinned, separately licensed GPL providers have been evaluated. The first
  was rejected for incorrect shadows. The second verifies 2,188 source blobs
  and runs moving Death Mountain and Kokiri scenes with DekuForge UI adaptations.
  See the [engine plan](docs/INDEPENDENT_ENGINE.md) and
  [scoped measurements](docs/INDEPENDENT_EVIDENCE.md). Full gameplay acceptance
  remains outstanding. The
  [experimental Windows build guide](docs/OPEN_ENGINE_EVALUATION.md) covers
  pinned generic tools and compilation from source.
- No automatic fallback to the old experimental 0.3.10 or stable 0.10.1 renderer.
- FSR 3.1 is supported by the renderer. FSR 4 requires AMD's separate
  runtime and a supported GPU. The Windows build guide explains the opt-in.
- The provisioner downloads verified generic tools. The pinned GPL engine and
  AV1 decoder are compiled locally from source.

The independent Windows bootstrap provisions official generic Python 3.14.10/Tk
and hash-pinned Pillow in this checkout. The locally compiled `DekuForge.exe`
uses that runtime for the launcher. A development
Python is also supported for source commands. `run_builder.py --doctor` reports
independent capabilities; `--prepare` prepares modules only and is not a game.
With the experimental builder configured, **Updates → Rebuild for current
version** starts a local game build and opens its progress and log view.

## Install or update on Windows

Download `DekuForge-Setup.exe` from [Releases](https://github.com/BrutusBossNL/DekuForge/releases)
and choose an installation folder. Setup provisions Python, the pinned build
tools and licensed engine source. Keep a Legacy installation in a separate
folder. Select your own NUP in **Build game** and use **Saves** to import
progress from a previous installation.

- **Stable** installs tagged independent Windows releases.
- **Preview** also lists tagged prereleases.
- **Experimental** offers checked commits from the `independent` branch via
  GitHub Actions for 14 days. Downloads require a GitHub CLI sign-in or a token
  with Actions read access. A Preview and an Experimental build from the same
  commit carry the same engine changes.

Switches into or out of Experimental need confirmation. A launcher-only
update skips the game build, and an engine update reuses compatible local
build caches. Windows SmartScreen can prompt about the unsigned installer.
To uninstall, open **Installed apps** in Windows or run
`DekuForge-Uninstall.exe` from the installation folder. The uninstaller offers to keep
a backup of your saves. Your input game archive stays in place.

## Building from source

Follow the [Windows source-build guide](docs/OPEN_ENGINE_EVALUATION.md) for
the compiler, tool provisioning, and local build. Build outputs and caches stay
in ignored directories. Run `python tools/check_source.py --tracked` and the
source tests before contributing.

## Known issues

The legacy reports for Hyrule Town and Lon Lon Ranch document a Radeon
RX 9070 XT configuration. The independent engine validates Vulkan imports and
reclaims cached textures earlier under Windows memory pressure. The original
reports still need confirmation on that AMD setup. Report new issues through
the launcher, including from its crash prompt.

The Windows game builder saves the Vulkan pipeline cache beside the game during
its final validation step. With that cache and a warm NVIDIA driver cache, two
starts on the tested RTX 2080 reached the menu in about 30 seconds and averaged
about 48 fps at native 1080p on Death Mountain Trail. Driver changes and cold
caches can take longer. See [the test evidence](docs/INDEPENDENT_EVIDENCE.md).
The Windows game supports SDL gamepads and locally built Switch, Xbox, PS4 and
PS5 prompts. In **Controls**, use **PlayStation / Xbox** for bottom-button
confirm (Cross or A), or **Nintendo** for right-button confirm. Hold the left
stick click (L3) while moving to sprint. The **Cheat Manager** includes sprint
speed and the engine's player, inventory and travel cheats. **Controls → L3
sprint** offers **Hold L3** or **Click to toggle**. A second click or stopping
movement ends a toggled sprint. Sprint speed includes the original 2×, 3.5×
and 5× settings.

The Cheat Manager is grouped into **Link**, **Equipment**, **World**,
**Inventory**, **Ammunition**, and **Timers & minigames**. Link holds sprint,
jumps, heart, wallet and magic refills. Inventory holds the individual edits
for unlocked bottles, magic beans and Scrub seeds. Timers & minigames contains
the shared countdown freeze and **Instant fish catch**, which skips reeling
once you hook a fish at the fishing pond.
Bottle edits apply once and can be kept with an in-game save. Equipment
options cover charged spin range, magic spin charge and bomb arrows. Bomb
arrows require adult Link's bow. The separate explosive Deku seed option
requires young Link's slingshot. Both require an unlocked bomb bag and
use one bomb per explosive impact.
Both explosive projectiles have a black aura while held ready or in flight.
**Cheat Manager → World** controls Gold Skulltulas, heart pieces, grottos,
chests, bean plots, Great Fairies and upgrades separately. The markers follow
Link's current age. Night-only Skulltulas carry a crescent, and markers with
known completion data show their collected state. Rebuild to generate the map
assets from your own game files. A mod replacing the same map resources takes
priority over these markers.

DekuForge's heart-refill option is the only health cheat shown. The existing
engine tools for flight, teleporting, time, age and inventory remain available.

**Gameplay → Game language → System language** follows the system UI language
on restart, falling back to English. New builds select it by default. Explicit
game and overlay language choices are kept. Broad controller/audio validation
and Linux/iOS gameplay remain open.

## Reuse and contributions

Reuse only components with an identified open-source license or redistribution
grant, preserving all applicable notices. Changing names or structure does not
remove upstream terms. Original project code remains MIT licensed. The inherited
legacy patches are recorded in Git history for provenance review. The repository also inherits Git history;
it is not presented as a clean-room or fully cleared codebase.

We welcome issues and pull requests and aim to respond or review within 48 hours,
subject to volunteer availability. See [CONTRIBUTING.md](CONTRIBUTING.md) and the
[roadmap](roadmap.md) for Linux, iOS and VR plans. Linux and iOS build and
testing contributors are especially welcome.

This is a non-commercial hobby project. We oppose piracy, encourage purchasing
the game/console and do not provide dump/acquisition instructions. We are not
affiliated with Nintendo. Preserve credits for NX2navi and all legitimately reused
upstream components; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
