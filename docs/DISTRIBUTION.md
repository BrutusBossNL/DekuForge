# Local builds and launcher distribution

Distribute the small Windows launcher package, not a built game. The package
contains `DekuForge.exe`, launcher source, original extensions, branding and build
orchestration. `tools/package_launcher.py` uses an explicit allowlist and checks
source contents before producing a ZIP under the ignored `build/releases` folder.
Its inventory records SHA-256 for every included file.

Never distribute ROMs, keys, extracted game data, saves, generated game code,
compiled game executables, generated shaders or pipeline caches. Each user must
supply their own supported game dump. These restrictions also apply to issues,
pull requests and attached diagnostic files.

## Component versions

`dekuforge/components.json` records independent identities:

| Component | Purpose |
| --- | --- |
| Launcher | Desktop application and management interface |
| Engine | Source backend and DekuForge runtime extensions |
| Buildkit | Build orchestration and tool dependency requirements |
| Python and compiler dependencies | Exact tools needed by the selected build |
| Game version | Version read from the user's input, never supplied by us |
| Build ID | Hash of the user's locally linked executable |

A launcher update does not itself require rebuilding the game. Rebuild when
engine inputs or build dependencies change. Existing per-stage build state tracks
input identity and generated products; verified shader preparations can be reused
only when GPU source, translator and shader seed inputs still match.

## Bootstrap and cache

The native launcher looks for its pinned runtime in `python/<component-id>`.
When absent it invokes `tools/bootstrap_runtime.ps1`, downloads the specified
archive, verifies its size and SHA-256, validates archive members and installs it
through an isolated staging directory. Different runtime identities use separate
directories. Verified existing archives and installed versions are reused.

The game builder separately prepares the pinned native toolchain, shader tools,
.NET SDK and decompression dependency under `local/build-tools` and `pydeps`.
The native tool installer compares the release lock and downloads only required
packages, retaining verified package archives. Tools are downloaded from the
declared upstream providers; an installed NX2navi launcher is not required.
Notices accompanying reused components remain available.

## Verification and remaining work

On 2026-11-17 the 11.78 MiB launcher package was extracted into an empty folder
without runtime or preferences. Its native executable downloaded and verified its
own runtime, then passed the 40-screen, five-language, single-window self-test.
This was an isolated-folder test on the development Windows machine, not a clean
Windows VM or a complete fresh-machine game build.

Automatic release installation and rollback are still pending. The release list
and version selector already exist; installation controls stay disabled until
that path is tested. Do not interpret the local package test as an update-system
acceptance result. The repository and package remain private during development.
