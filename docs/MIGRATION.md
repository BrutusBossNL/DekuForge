# Implementation status

| Area | Status |
| --- | --- |
| Launcher | Original home and builder windows; persistent installation selection |
| Archive | Independent NUP reader, structural checks, verified streaming extraction |
| Build preparation | Independent base/update module selection, NSO metadata and module layout |
| Module decoding | Segment normalization with size and declared-hash validation |
| CPU translation | Baseline included; limited SDK generation exercised; unsupported instructions remain |
| Host runtime | Baseline included; game 1.1.1 port unvalidated |
| Vulkan and shaders | Source included; compilation and game validation pending |
| Native game link | Not integrated; no independent playable executable |
| Compatibility build | Explicit optional adapter for an existing backend |
| Equipment | Bomb arrows, black aura, spin reach and charge controls remain to be ported |
| World | Skulltula, heart, grotto, chest, planting, fairy and upgrade markers remain to be ported |
| Memory and performance | Per-feature integration and in-game measurements pending |
| Saves | Existing installations untouched; independent migration not implemented |
| Updater and packaging | Pending playable build and validation |

The baseline engine is a pinned source import, not a claim of game compatibility.
`engine/SOURCE.json` records its source inventory. All local game-derived outputs
stay in ignored build directories.

Next work: instruction compatibility and differential validation; game-specific
host imports and boot paths; patch locations for the selected build ID; RomFS
composition; shader translation; native compilation and linking; isolated game
validation; then cheat features and performance fixes. Producing files in one
stage must not mark the remaining stages complete.
