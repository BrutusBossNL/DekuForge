# Moving saves to DekuForge

## Import from NX2navi

1. Select your built DekuForge game. Start it once and close it so its user profile
   exists. Open **Saves** in the launcher.
2. The destination is detected from the selected game's `user/save/<user-id>`
   for independent builds, or `profile/save/<user-id>` for Legacy.
   If it has multiple user profiles, choose the destination profile explicitly.
3. Choose **Choose NX2navi / save folder** and select your old NX2navi folder,
   its `Play` folder, or the save folder itself. There is no need to find the
   long user-ID folder manually.
4. Review the result: source path, number of save slots and most recent progress
   file modification time. With multiple results, select the intended profile.
   The timestamp is a filesystem timestamp, not a decoded game playtime.
5. Choose **Import these saves**, check the source/destination confirmation and
   confirm. Both games must be closed. Search alone never imports anything.

Only an owned DekuForge build is used for automatic destination selection.
No profile ID is invented, and the launcher does not change your NX2navi setup.
If no destination appears, select a completed DekuForge build and start/close it
once. No installation or save folder is created just by searching.

## What is copied and preserved

The importer accepts `account.sav`, `option.sav` and supported `.sav` files under
`slot_00` through `slot_05`, including `progress.sav`. It copies the selected
profile; it does not move or delete its source. Matching destination files are
replaced, while destination slots absent from the import remain intact.

The existing destination is retained beside the imported profile in a uniquely
named `<user-id>.backup-...` folder. The launcher reports that location after
completion. A failed final replacement restores the previous directory.
Import/export ZIPs contain saves only; do not attach them to project issues.

Save compatibility still depends on the input game version. Folder detection
does not establish that a save from every game version will load. Test loading
the imported copy and keep the original installation and retained backup until
satisfied. Never assume a newer save will work after a game downgrade.

## Search scope and ZIP backups

Search is read-only and restricted to the folder you choose: at most seven
directory levels, 6,000 directory entries and 32 candidate profiles. It skips
links, game asset/build caches and automatic save-backup/transaction folders.
It lists supported profiles rather than searching file contents. A limit notice
asks you to choose a more specific folder when necessary. Results from the active
DekuForge installation are excluded from source selection.

**Import ZIP** accepts the flat user-profile layout created by DekuForge's save
export (`account.sav`, `slot_00/progress.sav`, etc.). Other exporters' wrapped ZIP
layouts are not automatically converted; use their existing save folder with the
folder search instead. **Export ZIP** and **Open current game's save folder**
operate on the detected destination profile.

## Adventure recap

In Experimental, **Play** opens the recap inside the launcher. **Continue to
game** starts the selected game through the standard launch path, including
enabled mods. The recap reads game version 1.1.1 saves from the account the
independent Windows build uses. Imported saves work after they are copied into
that profile. The launcher ranks compatible slots by the date stored in
`caption.sav`, with the modification time as a fallback when none of the
compatible slots has a readable game timestamp.

The recap shows the saved location, thumbnail, heart capacity, and the recorded
story, side-quest and collection state. It uses the launcher's language,
including its system-language setting. Location names and collectible
placements come from the selected build's local game files. The area breakdown
of Skulltulas is shown when the placement checks agree with the saved token
total. Loose heart pieces are shown separately from total collected pieces.

The percentage is the share of the DekuForge checklist completed. Each token
or other collectible counts as one objective. Claiming a quest reward can also
complete its own objective. The checklist covers major bosses, selected side
quests and one-time rewards, tokens, heart pieces, stones and medallions,
songs, bottles, equipment, capacity upgrades and Great Fairy gifts. It does
not count every optional interaction in the game. Unknown objectives remain in
the total and do not count as completed. The game records a snapshot of progress,
so this recap does not reconstruct the order in which milestones happened.

The recap reads files locally and leaves the saves untouched. If the selected
build or save is unsupported, **Continue to game** still works.
