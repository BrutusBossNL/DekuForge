# Migration inventory

Reference: BrutusBossNL/NX2navi stable custom 0.10.1.9, runtime revision
3b711b8ec85f7a2047ba4acb93de8865952f6056; documentation revision 8cb3f1c.
This is a requirements inventory, not a claim of feature parity or a legal audit.

| Area | Required behavior | Current status |
| --- | --- | --- |
| Launcher | Select and start an existing installation without changing saves | Implemented |
| Build and updates | Local build, private update feed, verification and rollback | Planned |
| Cheat manager | Categories, persistence, runtime integration and existing cheats | Pending ownership review and runtime adapter |
| Equipment | Bomb arrows with black aura; spin reach normal/1.5/2/2.5; charge normal/instant | Pending review and port |
| World | Independent skulltula, heart piece, grotto, chest, planting, fairy and upgrade switches | Pending review and port |
| World details | Collected checks, current-age filtering, moon for night skulltulas, Kakariko tree coverage | Pending review and port |
| Health | Automatic heart refill; refresh when maximum hearts increases | Verify reference behavior before port |
| Controls | Controller detection and PlayStation mapping; avoid duplicate fixes | Pending review and port |
| Performance | Memory/VRAM budgets, texture compression and caches, Hyrule Field/Market frame times | Inventory individual changes and licensing before port |
| Toolchain | ASTC preparation uses launcher-selected compiler and environment | Pending review and port |
| Saves | Preserve backups, profile location and recovery behavior | Existing installation untouched; independent support planned |

## Order of work

1. Keep playing through the external installation adapter.
2. Enumerate original owned commits and permissively licensed base components;
   record file-level or change-level provenance and required notices.
3. Select an authorized runtime and document its adapter contract. NX2navi targets
   a Switch ARM64 build; N64Recomp is not a drop-in replacement for this runtime.
4. Port owned cheat logic and configuration behind that adapter, retaining source
   attribution. Reimplement restricted integration without copying its expression.
5. Validate saves and each feature on an isolated installation, then profile
   performance in the same scenes. Never claim memory fixes from UI settings alone.
6. Add packaging and an opt-in update channel only for reviewed distributable files.

No automatic upstream merges or Triforce integration are planned. This inventory
does not establish that the reference implementation has every feature bug-free.
