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

## Windows code signing

Checked on 2026-11-17: the local setup, launcher and uninstaller report
`NotSigned` in Windows Authenticode inspection. Branding and SHA-256 inventories
are not publisher signatures. The current preview documents possible SmartScreen
warnings in the README; it does not claim a verified publisher.

Signing is feasible once a trusted signing identity is available. Microsoft
[Artifact Signing](https://learn.microsoft.com/en-us/azure/artifact-signing/quickstart)
requires identity validation. Public Trust currently accepts EU organizations;
individual developers must be located in the US or Canada, so a Netherlands-based
individual cannot assume eligibility. Microsoft's
[comparison](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/code-signing-options)
lists an indicative starting cost of about USD 9.99/month; confirm eligibility
and current charges before subscribing. A suitable trusted certificate provider
is another route, subject to its identity and key-storage requirements.

[SignPath Foundation](https://signpath.org/terms) offers free signing to qualifying
open-source projects. It requires open-source licensing for all components,
maintained/released software and an approved build/review process. Our private
preview and restricted backend terms must not be presented as automatically
qualifying. A self-signed certificate does not establish public Windows trust.

Planned signing order, not yet implemented in the packaging scripts:

1. Build `DekuForge.exe` and `DekuForge-Uninstall.exe`, sign both with SHA-256
   and a trusted timestamp, and verify their Authenticode signatures.
2. Package those exact signed files, then generate the ZIP inventory and hashes.
3. Embed that ZIP in `DekuForge-Setup.exe`, sign and verify the completed setup.
4. Generate `DekuForge-release.json` from the final signed setup and final ZIP.
   Publish those exact bytes together; do not alter an EXE after signing or use
   hashes from an earlier unsigned package.

This needs explicit packaging hooks: `tools/build_setup.py` currently recompiles
the uninstaller and immediately packages it. Signing an old uninstaller before
running that script would be overwritten. Configure signing credentials outside
the repository, with restricted CI permissions; never commit private keys or
tokens. No certificate has been purchased or signing account configured.

Sign only the project's distributed launcher/tooling artifacts. The locally
generated game is not a release asset and is not uploaded for signing.
According to Microsoft's
[SmartScreen documentation](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation),
trusted signatures can show the verified publisher and build reputation, but
new files can still receive warnings. EV certificates no longer provide an
automatic SmartScreen bypass. Never promise a warning-free first installation.

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

The preview now includes application installation/update transactions, durable
recovery journals, pre-update backups and a post-install launcher health check.
Stable/Preview filtering and manual release selection also support downgrades.
Automatic updates are opt-in and install only a newer semantic launcher version.
The native setup was tested from an empty destination: it downloaded its own
runtime and complete toolchain, installed successfully in 57 seconds on the
local machine, and passed all 40 UI views. A clean Windows VM is still a separate
gate; this timing is not a first-install duration promise.

Game rebuilds use a separate owned destination. Existing profiles and verified
caches are copied locally, the old game stays selected during the build, and only
a successful result is activated. A failed build preserves the previous game.
Existing game executables are never downloaded as release assets.

Release assets are the setup EXE, launcher ZIP and `DekuForge-release.json`.
Users only download the EXE manually. The updater checks GitHub's asset digest,
the descriptor, every ZIP member and package component identity. It rejects
unexpected paths, content signatures and missing inventory entries. Packages are
cached by SHA-256; matching installed application files are not replaced.
A frozen external helper waits for the launcher to exit before application writes.

Private testing can use an existing authorized GitHub CLI session or GH_TOKEN;
tokens are never saved in launcher settings and are stripped on asset redirects.
Draft releases are not offered by the normal release selector. Public installers
will not need a GitHub account. Keep the repository private until setup/update,
failed-update recovery and local game-rebuild acceptance are complete.

## Reporting and uninstallation

The preview has a user-reviewed issue form with hardware/version information and
bounded, filtered text logs. It offers a prefilled GitHub browser page or direct
submission using the user's existing GitHub CLI/token. It does not include an
embedded maintainer token or submit automatically. Nonzero game exit codes and
recorded launcher errors can offer a report; this is not a full crash-dump service
and does not detect every possible failure. Redaction is best effort: review the
preview before sending. Direct API submission is covered by mocked tests, not
an automatically posted live test issue.

Installed copies include a native uninstaller and Windows Installed apps entry.
Managed directories require ownership markers; external installations are not
removed. Save retention is selected by default and verifies a separate backup
before removal. Original configured ROM/NUP paths and recognized game archives
are excluded from deletion and save backup. Synthetic PowerShell integration
checks exercise keep/remove/refusal cases. The native setup/uninstall flow is
also checked in an isolated directory on the development machine; this is not a
clean Windows VM or a test of every possible user installation.

A real authenticated private-draft update downloaded and installed the package in
an isolated folder, passed UI checks and preserved settings and a synthetic save.
The subsequent full separate game rebuild did not finish. Its large acceptance
folder was removed at the owner's request; do not report it as a successful
end-to-end fresh install, game rebuild or rollback play test.
