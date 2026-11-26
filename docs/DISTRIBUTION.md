# Local builds and launcher distribution

The independent Windows installer configures the same source-based backend on
Stable and Preview. The frozen NX2navi-based 0.3.0 Legacy release is a separate
installation. The launcher identifies compatible Windows packages with
`DekuForge-independent-release.json`.

Experimental selects Windows artifacts of successful pushes to `main`,
using the GitHub Actions digest and the embedded commit identity. Expired
artifacts drop out of the list. GitHub CLI sign-in or a token with Actions read
permission is required. Keep Preview at the same source as Stable or ahead of
it. For paired releases, tag both from the same commit, verify both packages
and publish Preview first. Each package embeds its own version and the
same commit identity as the corresponding Experimental artifact. Ready pull
requests, pushes to `main` and version tags use the same source checks and
clean Windows setup test. A pull request never publishes an update artifact.
Pushes publish the appropriate artifact only after their checks pass.

Changes limited to the launcher skip the game build. Engine inputs and build
tool changes queue a local rebuild. A compatible installed build keeps its
working directory, shader cache and saves. Stages whose inputs change are
recomputed by the pinned provider. A new provider revision may require a
separate build and save import.

The repository retains the latest 10 published stable releases and 15
published previews. Legacy `v0.3.0` is permanently exempt. Git tags and drafts are retained. Experimental artifacts
expire after 14 days and are outside the release counts.

Distribute the small Windows launcher package, not a built game. The package
contains `DekuForge.exe`, launcher source, original extensions, branding and build
orchestration. `tools/package_launcher.py` uses an explicit allowlist and checks
source contents before producing a ZIP under the ignored `build/releases` folder.
Its inventory records SHA-256 for every included file.

Never distribute ROMs, keys, extracted game data, saves, generated game code,
compiled game executables, generated shaders or pipeline caches. Each user must
supply their own supported game dump. These restrictions also apply to issues,
pull requests and attached diagnostic files.

## Changelog and release notes

For RecompLauncher, every tagged release includes a Windows x64 portable ZIP
with `recomplauncher.json` next to `DekuForge.exe` and the same manifest as a
standalone asset for the catalog checker. Publish the portable ZIP, the
standalone manifest and the regular DekuForge setup/update assets together.
The portable ZIP runs a windowless setup from the player's NUP and uses the
same executable to start the generated game. RecompLauncher manages updates
for that installation. Saves and the editable settings file live in
`recompdata/`. Generated game files, tools and build caches remain local to
the installed folder. Use the [RecompLauncher SDK](https://github.com/elripalda/RecompLauncher/blob/main/docs/ADD-SUPPORT.md)
when changing the manifest.

Keep [CHANGELOG.md](https://github.com/BrutusBossNL/DekuForge/blob/main/CHANGELOG.md)
current under **Unreleased (Experimental)**. Before publishing, identify the
previous published tag of the same channel and audit the candidate commit
against it:

```text
git fetch --tags
git log --oneline PREVIOUS_TAG..CANDIDATE
git diff --stat PREVIOUS_TAG CANDIDATE
git diff PREVIOUS_TAG CANDIDATE
```

Use the full tag-to-tag diff and logs to catch changes that arrived through
Experimental or were omitted from earlier notes. If the tags diverge, check
both sides and document the net changes users will receive. An unpublished
tag does not reset the comparison baseline.

Use **New**, **Patches (fixes)**, **Preview-to-Stable (tested)** and **Thank
you** in the changelog entry and the GitHub release notes. Link the tag
comparison and credit the people behind the relevant PRs and issues. For
Stable, also compare the candidate with the tested Preview. Record what was
promoted, what changed since that Preview, and the scope and limits of testing.
Keep later Experimental work under Unreleased.

Before tagging Stable, check each change against its related GitHub issues
and PRs. Both need to be closed where applicable, with validation confirming
the fix. Keep any change awaiting closure or confirmation in Preview or
Experimental and out of the Stable candidate. If a release was not explicitly
requested, land the change as a commit for the Experimental channel.

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

## Updating without uninstalling

Normal updates do not require uninstalling DekuForge. The release ZIP replaces
the native launcher, interface/source modules, build scripts, branding and the
uninstaller. A helper waits for the launcher to exit, installs the verified
package, prepares the selected Python runtime, runs the invisible health check
and restarts the launcher. Failed application updates retain recovery copies.
From launcher 0.4.4 the helper prepares the runtime with
`DekuForge.exe --prepare-runtime`. Helpers frozen by older launchers still run
`tools/bootstrap_runtime.ps1` from the new package, so the package keeps it.

The updater prepares Windows build tools when configuration is missing or tool
inputs change. A moved installation configures the AV1 decoder in a cache keyed
to its current paths. Tool preparation output is recorded in the update log.
The local build verifies pinned dependencies and reuses matching tools and
build products. Game rebuilding is determined by relevant source/build-input
hashes, not just a higher launcher version. Existing builds, saves, settings and
the original NUP are retained. A game update builds into a separate destination
and activates it only after success; the local full-rebuild acceptance limits
below still apply.

Use **Updates**, choose **Preview** for prereleases, check for releases and install
the selected version. Draft releases are never listed, even with credentials.
Public Stable and Preview downloads work without a GitHub account. You can
also close the launcher and run the new setup over the same application folder
to upgrade the application and retain its local game builds.

Every delivered application update gets a distinct launcher version. Published
release assets are immutable: later changes use the next preview/version. The
separate buildkit and engine numbers describe their own changes; a launcher-only
UI improvement does not advance the game engine version.

## Windows code signing

Checked on 2026-11-17: the local setup, launcher and uninstaller report
`NotSigned` in Windows Authenticode inspection. Branding and SHA-256 inventories
are not publisher signatures. The current Early Access candidate documents possible SmartScreen
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

### Antivirus heuristics

On 2026-11-20 Avira reported `DekuForge-Setup.exe` as
`Drop.Win64.FakeProgSelfRun` (upstream issue #12). A source review found no
malicious behavior. The earlier setup did match common dropper heuristics: an
unsigned EXE extracted an embedded ZIP and `install.ps1` into `%TEMP%`, ran them
through a hidden `powershell.exe -ExecutionPolicy Bypass` and then downloaded and
started more executables. Its uninstaller extracted a script into `%TEMP%` the
same way, and the setup and uninstaller had no version information.

Launcher 0.4.4 changes the shipped executables:

- `DekuForge-Setup.exe` starts no script host and writes nothing to `%TEMP%`. It
  checks the embedded package against a SHA-256 compiled into the setup, then
  unpacks it with Windows `tar.exe` into `local\setup-*` inside the chosen
  folder after checking the archive listing. It prepares the runtime natively,
  runs `tools/install_package.py` with that runtime and creates the Start Menu
  shortcut and Installed apps entry through Windows APIs. It removes its
  workspace afterwards and logs to `local\setup.log`.
- `DekuForge.exe` prepares a missing runtime natively instead of through
  `tools/bootstrap_runtime.ps1`.
- `DekuForge-Uninstall.exe` runs the installed `installer/uninstall.ps1` only
  when its SHA-256 matches the digest compiled into the uninstaller. It still
  starts PowerShell, because a separate process must remove the uninstaller
  itself, but no script is written to `%TEMP%`.
- All three executables carry complete version information (company, product,
  copyright and original file name) and an `asInvoker` manifest.

These changes remove known heuristic triggers, but nobody has checked whether
any antivirus product now accepts the files. Unsigned new files can still be
flagged. Report false positives to the vendor, and rely on publisher signing
(above) for a lasting fix.

Sign only the project's distributed launcher/tooling artifacts. The locally
generated game is not a release asset and is not uploaded for signing.
According to Microsoft's
[SmartScreen documentation](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation),
trusted signatures can show the verified publisher and build reputation, but
new files can still receive warnings. EV certificates no longer provide an
automatic SmartScreen bypass. Never promise a warning-free first installation.

## Bootstrap and cache

The native launcher looks for its pinned runtime in `python/<component-id>`.
When absent it prepares the runtime natively (`launcher/runtime.c`). The pins
from `dekuforge/components.json` are compiled into the executable. It downloads
the CPython archive and Pillow wheel with WinHTTP and verifies their size and
SHA-256 with Windows CNG. Windows `tar.exe` (Windows 10 version 1803 or newer)
lists each archive. Members are rejected for traversal, absolute or reserved
names, links, special files, case collisions or the expansion limit before
`tar.exe` extracts them into an isolated staging directory. A Python/Tk/Pillow
import check runs before the runtime is moved into place. Different runtime
identities use separate directories. Verified existing archives and installed
versions are reused. `tools/bootstrap_runtime.ps1` stays as the developer
bootstrap for a checkout without `DekuForge.exe`, and for older update helpers.

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

The application includes installation/update transactions, durable
recovery journals, pre-update backups and a post-install launcher health check.
The health check renders its views with the root window withdrawn, records
whether it was ever mapped, and fails if it becomes visible. Setup and updates
therefore show no page/language tour before the normal launcher starts.
Stable/Preview filtering and manual release selection also support downgrades.
Automatic updates are opt-in and install only a newer semantic launcher version.
Switching into or out of the Experimental channel requires a manual selection.
The native setup was tested from an empty destination: it downloaded its own
runtime and complete toolchain, installed successfully in 57 seconds on the
local machine, and passed all 40 UI views. A clean Windows VM is still a separate
gate; this timing is not a first-install duration promise.

Game rebuilds use a separate owned destination. Existing profiles and verified
caches are copied locally, the old game stays selected during the build, and only
a successful result is activated. A failed build preserves the previous game.
Existing game executables are never downloaded as release assets.

For a normal manual install, download `DekuForge-Setup.exe`. The updater uses
the launcher ZIP and `DekuForge-independent-release.json`. It checks GitHub's asset digest,
the descriptor, every ZIP member and package component identity. It rejects
unexpected paths, content signatures and missing inventory entries. Packages are
cached by SHA-256; matching installed application files are not replaced.
A frozen external helper waits for the launcher to exit before application writes.

Experimental downloads can use an existing authorized GitHub CLI session or
`GH_TOKEN`. Tokens are never saved in launcher settings and are stripped on
asset redirects. Draft releases are not offered by the normal release selector.

## Reporting and uninstallation

Save migration now detects the selected owned game's destination profile and
searches a user-chosen NX2navi/Play/save folder in a bounded background worker.
Users review source profiles before an explicit copy, with a retained destination
backup. See [saves.md](saves.md) for scope, supported layouts and compatibility
limits. This is folder/transaction validation, not a new in-game save-load result.

The launcher has a user-reviewed issue form with hardware/version information and
bounded, filtered text logs. It offers a prefilled GitHub browser page or direct
submission using the user's existing GitHub CLI/token. Confirmed direct
submissions show a read-only copy of the title and body with **View on GitHub**
and **New report**. It does not include an
embedded maintainer token or submit automatically. Nonzero game exit codes and
recorded launcher errors can offer a report; this is not a full crash-dump service
and does not detect every possible failure. Redaction is best effort: review the
preview before sending. Direct API submission is covered by mocked tests, not
an automatically posted live test issue.

Installed copies include a native uninstaller and Windows Installed apps entry.
The uninstaller starts the installed, digest-checked `installer/uninstall.ps1`.
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
