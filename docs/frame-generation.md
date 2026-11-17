# NVIDIA Frame Generation

Launcher 0.3.0-preview.1 / buildkit 0.2.3 fixes missing Windows Frame Generation
dependencies in local builds (issue #3). DLSS upscaling and DLSS Frame Generation
use separate libraries; having `nvngx_dlss.dll` alone was not sufficient.

## Updating an existing game

1. Select **Preview** under Updates and install 0.3.0-preview.1 or later.
2. Complete the managed game rebuild offered after the application update, using
   your own NUP. The previous build is retained until the new build succeeds.
3. In the game's video settings select NVIDIA DLSS Frame Generation, then restart
   the game if requested. The setting still requires compatible hardware and drivers.

The existing menu message `in use: off, its files are missing` means Frame
Generation is **off**, regardless of the selected setting. Selecting a mode is
not confirmation that it is active. On supported systems the runtime reports
availability and failures in its `dlssg` log entries; include those through the
launcher's reviewed issue-report form if it remains unavailable.

## What the builder verifies

The existing SHA-256-pinned 0.10.1 application archive is downloaded only when
its verified cache is absent. Preparation extracts an explicit list:

- `nx2navi_dlssg.dll` (the existing runtime's bridge)
- `sl.interposer.dll`, `sl.common.dll`, `sl.dlss_g.dll`, `sl.pcl.dll`, `sl.reflex.dll`
- `nvngx_dlssg.dll`
- `dlssg-NOTICE.txt`, `streamline-LICENSE.txt`, `nvidia-rtx-sdks-LICENSE.txt`

The stable builder places these beside `DekuForgeGame.exe`. DekuForge then checks
every file's size and SHA-256 against the prepared inputs. A missing or damaged
file fails the build instead of marking an incomplete dependency set ready.
The renderer, Frame Generation implementation, game settings and saves are unchanged.
These dependencies are downloaded for local use; they are not release assets.

Synthetic tests cover incomplete archives, cached-input repair, missing delivered
files and corruption. A Windows smoke test checks the real verified library set
through the stable builder's placement function and loads the bridge to check its
ABI version. This is dependency/loader validation, not an in-game generated-frame
benchmark or a claim of support on every NVIDIA GPU.
