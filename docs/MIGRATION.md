# Historical implementation status

> Archived snapshot of the retired experimental engine, before the switch to
> stable 0.10.1. The table below is not the current product status. See
> [INDEPENDENT_EVIDENCE.md](INDEPENDENT_EVIDENCE.md),
> [DISTRIBUTION.md](DISTRIBUTION.md) and the [README](../README.md) for the active
> build path, tested results and remaining release gates.

| Area | Status |
| --- | --- |
| Launcher | Single-window home/settings/wizard; installation folder and Play; hide/restore while playing |
| Localization | English, Dutch, German, Spanish and French; immediate persistent switching |
| Branding | Explicit PNG decoding, native icon, application identity and product metadata |
| Archive | Independent NUP reader, structural checks, verified streaming extraction |
| Build preparation | Independent base/update module selection, NSO metadata and module layout |
| Module decoding | Segment normalization with size and declared-hash validation |
| CPU translation | Return, LDAPR and FP16 FNEG extensions independently checked; full SDK has 68 unsupported instructions remaining |
| Host runtime | 112 Windows sources compiled; constructor metadata and PAC prologue decoding extended; game boot remains unvalidated |
| Vulkan and shaders | Vulkan host sources compile; guest shader translation and game validation pending |
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

The standalone path now attempts the included code generator rather than stopping
after a source inventory. It fails on the measured unsupported instructions.
There is no fallback to a separate installation, and no fake successful build.

Next work: instruction compatibility and differential validation; game-specific
host imports and boot paths; patch locations for the selected build ID; RomFS
composition; shader translation; native compilation and linking; isolated game
validation; then cheat features and performance fixes. Producing files in one
stage must not mark the remaining stages complete.
