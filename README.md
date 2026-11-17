<p align="center">
  <img src="assets/branding/logo.png" alt="DekuForge" width="600">
</p>

# DekuForge

**Reforging a legend.**

> [!IMPORTANT]
> DekuForge includes no ROMs, game assets, encryption keys or compiled game.
> You must provide a legally obtained copy dumped from your own console. We do
> not provide game downloads or instructions for obtaining game files.
>
> The launcher builds the game locally from your files. The resulting game,
> extracted data, generated code, shaders and pipeline caches are for your own
> use. Never upload or share them through releases, commits, issues or pull requests.

## About and credits

DekuForge is a **non-commercial hobby project**. We earn no income from it.
We oppose piracy and encourage you to support Nintendo by purchasing the game
and the console. Use only your own ROM/dump of a legally obtained copy, from
your own console. We do not explain how to dump, obtain or download game files.
We have no intention of undermining Nintendo or causing it harm.

DekuForge uses the stable **NX2navi 0.10.1** source as its reference and engine
foundation. Thank you to the NX2navi authors, upstream engine and tooling authors,
and everyone who contributed code, research, tests, fixes, documentation or feedback.
Their work made this project possible. Original DekuForge code is MIT licensed;
this does not relicense the upstream engine or restricted components. Reused
components retain their original notices; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

DekuForge develops independently of NX2navi, with its own launcher, interface,
extensions and release channel. Project code is open to contributions under its
applicable licenses. Issues and pull requests are welcome: **we aim to review or
respond within 48 hours**, although this is a volunteer target, not a guarantee.
See [CONTRIBUTING.md](CONTRIBUTING.md).

## Project status

**Private Windows preview, undergoing installation and update acceptance testing.**
The stable reference-based game has passed local play tests. The DekuForge 0.11.0
candidate adds the custom in-game interface and Cheat Manager. The launcher and
engine have independent versions; the launcher is currently 0.2.0-preview.1.
The repository stays private until the Windows setup, update and rollback paths
are stable and component distribution terms are resolved. No public installer
release is available yet.

## Features

- Native Windows game builds from your own supported **game 1.1.1 NUP** archive.
- A standalone `DekuForge-Setup.exe` with installation-folder selection; no manual
  Python, compiler or command-file launcher is needed for installation.
- A branded launcher with Play, Updates, Saves, a build wizard and build library.
- System-language default, with English, Dutch, German, Spanish and French UI.
- Verified, cached build-tool downloads and incremental game rebuilding.
- Stable/Preview release selection, manual update/downgrade, optional automatic
  updates, launcher health checks and recovery copies for failed app updates.
- Separate game rebuilds: keep the working game and its profile until the new
  build completes; retain the previous build for switching back.
- User-reviewed bug reports with CPU/GPU/driver, RAM, OS, versions and filtered
  log excerpts. Use a prefilled GitHub browser form, or send directly with an
  existing GitHub CLI sign-in/token. No automatic issue submission or game-file upload.
- An uninstaller for managed builds/tools, with verified save backup and explicit
  protection for original game archives, even inside the installation folder.
- Save import/export with destination backups, including compatible NX2navi
  profiles. Import copies files; it never moves or deletes the original saves.
- The stable engine's in-game graphics, resolution, upscaling, audio and control
  settings, with a DekuForge interface and performance display.
- Built-in Cheat Manager, including Equipment and World groups: bomb arrows,
  spin-attack options, heart refill and individually selectable map markers.
  Individual cheat scenarios in the new candidate are still being verified.

## How to install - Windows

When a tested release is available in [Releases](../../releases):

1. Download **`DekuForge-Setup.exe`**. This is the only file you need to download
   manually; it contains the launcher, not a game.
2. Run it, choose where to install DekuForge and select **Install DekuForge**.
   Setup downloads and verifies its runtime and, by default, prepares build tools.
   You can defer tool downloads until your first build.
3. Open **DekuForge** from the Start Menu or run `DekuForge.exe` in that folder.
4. Choose **(Re)build**, select your own supported NUP and a game destination,
   then build. The wizard shows the log and measured stage progress.
5. Choose **Play** when the build has completed. Use **Updates** to choose a
   release/channel; a changed engine is rebuilt locally from your own archive.

Windows x64 and a compatible Vulkan GPU/driver are required. Allow substantial
free space for your dump, tool cache and game build; updates retain a separate
working build until the replacement succeeds. See [building.md](docs/building.md).
Linux, iOS and VR are not supported releases yet.

## Uninstalling - Windows

Open **Settings > Apps > Installed apps > DekuForge > Uninstall**, or run
`DekuForge-Uninstall.exe` in your DekuForge installation folder. Close the game,
launcher and any active build first.

**Keep my saves** is selected by default. Choose a new backup folder outside the
installation; the uninstaller copies and verifies your saves before removing
anything. Clear the checkbox only if you also want the managed save profiles removed.

Uninstall removes this installation's launcher, managed builds, downloaded tools
and caches. It does not remove external installations such as NX2navi. **Your
original ROM/NUP is never deleted, moved or modified**, including when stored
inside a DekuForge folder. Such a folder can remain solely to hold that archive.

## Known issues

Found another issue? Use **Report a problem** in the launcher, or review the
report offered after a detected crash. Check the diagnostics before submitting.

- Full first-time Windows installation and automatic-update acceptance are still
  being tested. Local package checks do not replace a clean-machine game test.
- Game validation currently covers limited hardware and scenes; FPS and driver
  compatibility need broader testing. A local 20-second candidate test averaged
  51.9 FPS on an RTX 2080; this is not a general performance guarantee.
- Several Cheat Manager scenarios still need independent in-game verification.
- Save compatibility is checked by game version/layout; a save made by a newer
  game is not guaranteed to load after downgrading. Keep your save backups.
- Private release downloads require authorized GitHub access during development;
  public releases will not require a GitHub account.

## Roadmap

See the separate [roadmap.md](roadmap.md) for Windows release gates, Linux, iOS
and exploratory VR support. **Linux and iOS build/testing contributors are
especially welcome.** Planned platforms are not advertised as working builds.

## Building from source

[docs/building.md](docs/building.md) describes DekuForge's pinned tools, source
bootstrap, game builder and launcher/setup packaging. The upstream
[build guide](https://github.com/tangerineturtle1/NX2navi/blob/main/docs/building.md)
and [BuildKit guide](https://github.com/tangerineturtle1/NX2navi/blob/main/docs/README-BuildKit.md)
provide background; their current main branch can differ from our pinned 0.10.1
base. Upstream supports native Linux builds, but DekuForge's Linux game build is
not yet validated; our released launcher/setup target Windows first.

Game-generated outputs remain in ignored `build/` and `generated/` directories;
local preferences, verified downloads and logs remain under ignored `local/`.
Runtime dependencies are also ignored. The staged runtime's compiled shader
headers stay under `build/engine-0.10.1`, never in the source repository.
Run **`python tools/check_content.py`** before committing, plus the checks in
[CONTRIBUTING.md](CONTRIBUTING.md). Share source and tooling, never built games.
