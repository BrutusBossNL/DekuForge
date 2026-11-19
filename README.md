<p align="center"><img src="assets/branding/logo.png" alt="DekuForge" width="600"></p>

# DekuForge: independent engine development

**Reforging a legend.** This is the `independent` branch. The existing working
Windows build remains on [main](https://github.com/BrutusBossNL/DekuForge/tree/main).

> [!IMPORTANT]
> No ROMs, game assets, keys, generated game source or compiled games are supplied.
> Use your own legally obtained game dump. Do not share game-derived outputs.

## Current status

This branch starts the replacement of the NX2navi-dependent build path with an
original implementation and explicitly approved, redistributable components.
The engine replacement is planned so future releases can use engine components
with clear open-source and redistribution rights. This Windows preview is for
testing the migration.
**A source-built experimental Windows game runs locally. The complete NUP build
route is available through the Preview setup or the developer build guide.
Full gameplay parity with main is still under evaluation.**

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
- Main's original mod manager, release list/notes and update outcome reporting
  are retained. Asset-mod order and On/Off selections now reach the independent
  runtime through verified snapshots. Code-mod builds remain disabled.
- Two pinned, separately licensed GPL providers have been evaluated. The first
  was rejected for incorrect shadows. The second verifies 2,188 source blobs
  and runs moving Death Mountain and Kokiri scenes with DekuForge UI adaptations.
  See the [engine plan](docs/INDEPENDENT_ENGINE.md) and
  [scoped measurements](docs/INDEPENDENT_EVIDENCE.md). Full gameplay acceptance
  remains outstanding. The
  [experimental Windows build guide](docs/OPEN_ENGINE_EVALUATION.md) covers
  pinned generic tools, source compilation and explicit launcher opt-in.
- No automatic fallback to the old experimental 0.3.10 or stable 0.10.1 renderer.
- FSR 3.1 is native to the preview renderer. FSR 4 requires AMD's separate
  runtime and a supported GPU. The Windows build guide explains the opt-in.
- NX2navi runtime/tool downloads and main-channel app updates are excluded.
  The independent provisioner downloads verified generic tools;
  the selected GPL engine and AV1 decoder are compiled from source.

The independent Windows bootstrap provisions official generic Python 3.14.10/Tk
and hash-pinned Pillow in this checkout. The locally compiled `DekuForge.exe`
uses that runtime without depending on main's interpreter. A development
Python is also supported for source commands. `run_builder.py --doctor` reports
independent capabilities; `--prepare` prepares modules only and is not a game.
With the experimental builder configured, **Updates → Rebuild for current
version** starts a local game build and opens its progress and log view.

## Install or update on Windows

Run `DekuForge-Setup.exe` from an installable independent Preview release and
choose a separate folder. Setup provisions Python, the pinned build tools and the
licensed engine source. Then select your own NUP in **Build game**. Updates on
**Preview** use the independent release package. **Experimental** uses checked
commits built by GitHub Actions without a release tag. Experimental downloads
require GitHub CLI sign-in or a token with Actions read access.

## Known experimental limits

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

The Cheat Manager has separate controls for unlimited jumps, shared countdown
freeze, heart, wallet, ammunition and magic refills, and each unlocked bottle's contents.
**Instant fish catch** skips the reeling phase once you hook a fish at the
fishing pond.
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
engine and historical patches remain available for provenance review, not as
blanket-approved inputs to the new backend. This branch also inherits Git history;
it is not presented as a clean-room or fully cleared codebase.

The goal is **at least main's stability, rendering, timing and performance**.
Main remains the reference until the independent implementation passes the same
scenarios. See [INDEPENDENT_ENGINE.md](docs/INDEPENDENT_ENGINE.md) for the component
inventory, acceptance gates and contributor work. Windows comes first; Linux and
iOS testing contributors are welcome after the desktop core is ready.
Earlier failed approaches and reusable measurements are indexed in
[INDEPENDENT_EVIDENCE.md](docs/INDEPENDENT_EVIDENCE.md); main remains untouched.

This is a non-commercial hobby project. We oppose piracy, encourage purchasing
the game/console and do not provide dump/acquisition instructions. We are not
affiliated with Nintendo. Preserve credits for NX2navi and all legitimately reused
upstream components; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
