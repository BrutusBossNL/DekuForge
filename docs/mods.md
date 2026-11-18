# Mods in DekuForge

Launcher 0.3.0-preview.2 adds an original DekuForge mod manager. Select a built game, then
open **Mods** in the left navigation. This works with the current stable-based
game; you do not need to rebuild that game for ordinary RomFS asset mods.

1. Choose **Add archive** or **Add folder**. ZIP works with the bundled Python.
   For `.7z` and `.rar`, install 7-Zip, or unpack the archive yourself and add its
   folder. DekuForge finds an installed `7z`/`7zz` or Windows' standard 7-Zip path;
   it does not bundle or silently download that program.
2. New imports start **Off**. Select the mod and choose **Turn on**.
3. Use **Move up** / **Move down** to set priority. For RomFS files, the highest
   enabled mod wins a shared path. Select a mod to see file paths and conflicts,
   including the winner and the priority rule. Only enabled, usable mods compete.
4. Choose **Play**. Preparation happens on a worker thread before the game starts.
   Restart the game to apply later changes; this is not live mod injection.

**Open mods folder** opens the selected game's `mods` folder. A folder placed
there manually is discovered by **Refresh** or the next Play. Archives placed
there are unpacked on Play, left intact and remembered so unchanged archives are
not unpacked repeatedly. Their imported mods also start Off. A changed archive
never overwrites an existing mod of the same name; use a distinct folder name or
manage the old copy explicitly in the opened folder.
Unchanged archives are recognized by size and modification time; changed archives
are hashed before import. Enabled code files are content-hashed before Play.

## Supported layout

One mod per archive/folder, with `romfs/` (or `romfslite/`), `exefs/`, `cheats/`,
or a combination. Selecting a `romfs` folder directly is accepted. Two wrapper
folders are tolerated, and these Atmosphere layouts are recognized for title
`0400486024DEC000`:

- `atmosphere/contents/<title>/romfs` (also exefs/cheats)
- `contents/<title>/romfs` or `<title>/romfs`
- `atmosphere/exefs_patches/<patch-name>/*.ips` or `*.pchtxt`

Imports are copied into a private staging folder and normalized before activation.
Source archives/folders stay untouched. Manually placed nested folders inside the
managed library are rearranged before Play without deleting unrelated metadata.
An optional UTF-8 `mod.json` may provide a `description`; it is text, never code.
Readme/license/notice documents outside the payload roots are retained under the
imported mod's `metadata/` folder, with their original relative paths.

## Code patches and cheats

Supported ExeFS `.ips`/`.pchtxt` patches and Atmosphere cheat files can be passed
to the current game's existing local builder. Turn the mod on, then choose
**Build code mods**. Select your original NUP in **Build game** if it is not
already selected. Code rebuilding requires a DekuForge-owned game build and its
standard `mods` directory. No NUP or game code is downloaded.

Changed enabled code files prevent Play until their content matches the builder's
receipt. Patch status is checked too: unsupported or other-version ExeFS patches
do not become usable merely because the executable linked. Individual cheats
are selected in the game's menu. Native plugins and replacement `main`/`subsdk`
executables are unsupported; a mixed asset/plugin mod is blocked as a whole.
RomFS conflict reporting does not analyze overlapping instruction writes or prove
that every community code patch is compatible with the game.

The launcher retains the executable, configuration and build receipts before a
code rebuild and restores them if the builder or patch acceptance fails. Saves
and original archives are not modified by this rollback. This covers handled
build failures, not a guaranteed recovery from power loss or forced termination
of the launcher. Do not terminate it during compilation.

## Storage, updates and limits

Mods belong to the selected game build. Managed game updates copy their mod
library, import receipts and configuration into the new build. Application-only
updates leave game builds in place. Removing a whole managed build also removes
its local mods; keep your downloaded originals elsewhere if you need them.

The manager writes only the runtime's mod configuration keys, preserving other
game settings. In-game switches/order are read on Refresh. Its current adapter
uses the existing game's `nx2navi.ini` interface; that compatibility filename is
not an NX2navi-launcher dependency. External mod directories remain controlled by
the game and are not modified by this manager. Managed directories must stay
inside the selected game folder and outside save/runtime directories.

Imports reject traversal, links/junctions, duplicate or case-colliding paths and
unsafe Windows names. Limits: 50,000 entries, 8 GiB expanded total, 2 GiB per file,
32 path components; code/cheat files are additionally limited to 64 MiB. Mod folder
names are limited to 240 UTF-8 bytes (the runtime has a fixed name buffer). Changes
are refused while a game is running. Downloaded mod files are never executed.
No mods, game assets or generated game code are included in releases.

## Validation scope

Synthetic tests cover ZIP/folder/Atmosphere normalization, a real 7z round trip
when 7-Zip is installed, archive rejection, switches, conflicts, code receipts,
rollback and update preservation. UI tests cover import, enabling, language
switches, deferred Play and blocking changed code. The native health check covers
45 core views plus five report forms across five languages.

A local copy of the existing engine passed its native mod-interface probe with
synthetic input; the original game and saves were untouched. That probe is a
runtime-contract check, not an end-to-end gameplay test of third-party texture
packs, RAR fixtures or compiled community code mods. Those remain mod-specific
acceptance work; a recognized layout is not a promise of compatibility.
