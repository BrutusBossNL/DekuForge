# Changelog

This is DekuForge's release history. Stable entries compare against the previous
published Stable, and Preview entries compare against the previous published
Preview. The linked tag comparisons include Experimental commits that landed
between those releases. Legacy releases are kept below for reference.

Add user-facing, build, tooling, CI and documentation changes under **Unreleased
(Experimental)** in the same PR or commit. Link related PRs and issues and name
their contributors and reporters. During release preparation, check the entire
same-channel tag range against this log and the GitHub release notes. For Stable,
also check the tested Preview commit and record exactly what carried over.

## Unreleased (Experimental)

### New

- Maintain a project changelog with release comparisons, validation and named
  credits. The contribution guide and PR template explain how to keep it current.
- Thank contributors in the project README and welcome help of all kinds.

### Patches (fixes)

- None recorded.

### Preview-to-Stable (tested)

- No Stable promotion in this interval.

### Thank you

- No additional PR or issue credits in this interval.

## v0.4.6 Stable and v0.4.6-preview.1

Both tags use the same source.
[Stable changes since v0.4.1](https://github.com/BrutusBossNL/DekuForge/compare/v0.4.1...v0.4.6) ·
[Preview changes since v0.4.5-preview.1](https://github.com/BrutusBossNL/DekuForge/compare/v0.4.5-preview.1...v0.4.6-preview.1)

### New

- Add RecompLauncher Set Up and Play for Windows x64 with a supported player
  NUP, on-page display and frame pacing settings, and save backup paths.
- Ship a portable Windows package and release metadata alongside the existing
  standalone setup and in-app update files.
- Stable receives the native installer, clearer version labels and read-only
  GitHub report receipts already present in Preview.

### Patches (fixes)

- Reuse a completed local game build when the dump and build components match.
- Stable also receives the build progress, Capstone, German spelling and update
  fixes listed under v0.4.4-preview.2 and v0.4.5-preview.1, plus the CI checks
  introduced between those releases.

### Preview-to-Stable (tested)

- Promote the v0.4.5-preview.1 changes together with the RecompLauncher support.
  Both new tags require the same clean Windows installer and source checks.

### Thank you

- [sirtheta] submitted [#9], [#10], [#11] and [#13]. [Exposed77] and [EtaYorius]
  reported the build and installer problems ([#8], [#12]). [BrutusBossNL]
  reported the moved-installation update failure ([#14]).
- Thanks to [elripalda and the RecompLauncher contributors](https://github.com/elripalda/RecompLauncher/graphs/contributors)
  for the SDK and its documentation.

## v0.4.5-preview.1 · 2026-11-22

[Changes since v0.4.4-preview.2](https://github.com/BrutusBossNL/DekuForge/compare/v0.4.4-preview.2...v0.4.5-preview.1) · [Release](https://github.com/BrutusBossNL/DekuForge/releases/tag/v0.4.5-preview.1)

### New

- Show the submitted GitHub title and body in a read-only receipt with **View on
  GitHub** and **New report** after confirmed direct submission.

### Patches (fixes)

- Recover from stale AV1 tool caches after an installation moves. Record tool
  output and retain subprocess exit status in filtered diagnostics ([#14]).
- Run clean Windows setup and tool provisioning on ready PRs and pushes as well
  as release tags. Consolidate duplicate source checks and update artifact
  upload to the Node.js 24 action.

### Preview-to-Stable (tested)

- Preview validation only. The [Windows setup and source checks](https://github.com/BrutusBossNL/DekuForge/actions/runs/44980406465)
  passed. The original updater from [#14] also upgraded an isolated relocated
  installation and preserved its test data.

### Thank you

- [BrutusBossNL] reported the update regression in [#14].

## v0.4.4-preview.2 · 2026-11-21

[Changes since v0.4.1-preview.1](https://github.com/BrutusBossNL/DekuForge/compare/v0.4.1-preview.1...v0.4.4-preview.2) · [Release](https://github.com/BrutusBossNL/DekuForge/releases/tag/v0.4.4-preview.2)

### New

- Show the engine and game versions separately on Play and use the launcher
  version on the game startup screen.
- Source Experimental packages from `main`, also shipped in Stable 0.4.1.

### Patches (fixes)

- Replace the Windows setup's script bootstrap with native verification,
  extraction and runtime preparation following the Avira report ([#13], [#12]).
- Expand the build log and show measured progress and estimated time left ([#11]).
- Correct German umlauts ([#10]) and install the pinned Capstone wheel for
  translation ([#9], [#8]).
- Correct setup acceptance so its own result file is excluded from workspace
  cleanup checks. Verify zlib and Capstone on a clean installation.

### Preview-to-Stable (tested)

- Preview validation only. [Source checks and clean Windows setup with build
  tools](https://github.com/BrutusBossNL/DekuForge/actions/runs/44893695482)
  passed. This validation did not include an Avira rescan. Preview 1 was tagged
  for CI and was never published as a release.

### Thank you

- [sirtheta] submitted [#9], [#10], [#11] and [#13].
- [Exposed77] reported the missing build dependency in [#8].
- [EtaYorius] reported the installer detection in [#12] and provided a second
  build log in [#8].

## v0.4.1 · Stable · 2026-11-20

[Changes since v0.4.0](https://github.com/BrutusBossNL/DekuForge/compare/v0.4.0...v0.4.1) · [Release](https://github.com/BrutusBossNL/DekuForge/releases/tag/v0.4.1)

### New

- Move the Experimental artifact source to the default `main` branch.

### Patches (fixes)

- Separate the README's features and performance measurements from known issues.

### Preview-to-Stable (tested)

- Retains the engine checkpoint from Stable 0.4.0 and Preview 0.4.1-preview.1.
  The Stable delta changes the update source and documentation. The
  [tagged Windows setup and build-tool checks](https://github.com/BrutusBossNL/DekuForge/actions/runs/44668777743)
  passed.

### Thank you

- No additional PR or issue credits in this Stable delta.

## v0.4.1-preview.1 and v0.4.0 Stable · 2026-11-19

These published versions use the same source commit.
[Preview changes since v0.4.0-preview.5](https://github.com/BrutusBossNL/DekuForge/compare/v0.4.0-preview.5...v0.4.1-preview.1) ·
[Stable changes since v0.3.0 Legacy](https://github.com/BrutusBossNL/DekuForge/compare/v0.3.0...v0.4.0) ·
[Preview release](https://github.com/BrutusBossNL/DekuForge/releases/tag/v0.4.1-preview.1) ·
[Stable release](https://github.com/BrutusBossNL/DekuForge/releases/tag/v0.4.0)

### New

- Stable moves to the independent Windows build path with pinned GPL Hookshot.
  It carries forward the independent previews' launcher, local builder,
  controller support, runtime options, mods and cheats. The last NX2navi-based
  release stays available as Legacy.
- Retain up to ten Stable and fifteen Preview releases, with a permanent
  exception for v0.3.0 Legacy.

### Patches (fixes)

- Validate Vulkan host-memory imports against committed backing pages and
  receiving-buffer memory types ([#5]). Start reclaiming cached textures earlier
  under Windows Radeon commit pressure ([#7]).
- Restore the original Cheat Manager groups. Identify Experimental transitions
  as channel switches and show source-only previews as source downloads.

### Preview-to-Stable (tested)

- The release tags target the same source. Windows package checks passed and
  [scoped gameplay checks](docs/INDEPENDENT_EVIDENCE.md) were recorded.
  The RX 9070 XT reports in [#5] and [#7] still need a hardware retest.

### Thank you

- [Ripthorn] provided the Radeon crash reports [#5] and [#7] and the FSR report
  [#6] carried forward from the earlier releases.
- [vmpgninGIT] reported missing mod support in [#1], which the launcher carried
  forward. [BrutusBossNL] reported artwork, Frame Generation and setup issues
  [#2], [#3] and [#4] addressed along the migration path.

## Earlier independent previews

| Preview | Changes and validation | Thank you |
| --- | --- | --- |
| [v0.4.0-preview.5](https://github.com/BrutusBossNL/DekuForge/releases/tag/v0.4.0-preview.5) · 2026-11-19 | [Since preview.4](https://github.com/BrutusBossNL/DekuForge/compare/v0.4.0-preview.4...v0.4.0-preview.5). Verify runtime downloads using Windows built-in cryptography. Published Windows installer. | No additional linked PR or issue in the delta. |
| [v0.4.0-preview.4](https://github.com/BrutusBossNL/DekuForge/releases/tag/v0.4.0-preview.4) · 2026-11-19 | [Since preview.3](https://github.com/BrutusBossNL/DekuForge/compare/v0.4.0-preview.3...v0.4.0-preview.4). Fix Experimental ZIP handling and source line endings, and add clean-setup acceptance and diagnostic logging to release CI. | No additional linked PR or issue in the delta. |
| [v0.4.0-preview.3](https://github.com/BrutusBossNL/DekuForge/releases/tag/v0.4.0-preview.3) · 2026-11-19 | [Since the source preview](https://github.com/BrutusBossNL/DekuForge/compare/v0.4.0-preview.1...v0.4.0-preview.3). Add installable Windows packages, verified Preview and Experimental updates, world markers, black projectile auras and instant fishing. Repair local rebuild routing. Clean setup and isolated application update/downgrade were exercised. | No additional linked PR or issue in the delta. |
| [v0.4.0-preview.1](https://github.com/BrutusBossNL/DekuForge/releases/tag/v0.4.0-preview.1) · 2026-11-19 | First independent source preview. Adds local Hookshot builds, AV1 movies, shader/pipeline prewarming, packaged controller prompts, the independent Cheat Manager and crash diagnostics. Supports FSR 3.1 and a verified FSR 4 provisioning path. See [scoped evidence](docs/INDEPENDENT_EVIDENCE.md). | [Ripthorn] reported [#5] and [#6]. |

## Legacy releases

These releases used the NX2navi-based engine. Follow their release notes for
historical validation and limitations.

| Release | Main changes | Thank you |
| --- | --- | --- |
| [v0.3.0](https://github.com/BrutusBossNL/DekuForge/releases/tag/v0.3.0) · final Legacy | [Since Stable v0.2.1](https://github.com/BrutusBossNL/DekuForge/compare/v0.2.1...v0.3.0). Carries the 0.3.0 preview launcher changes forward and restores AMD FSR runtimes. Adds Vulkan memory diagnostics and a one-launch copied-buffer retry. | [Ripthorn] reported [#5] and [#6]. [vmpgninGIT] reported [#1]. [BrutusBossNL] reported [#2], [#3] and [#4]. |
| [v0.2.1](https://github.com/BrutusBossNL/DekuForge/releases/tag/v0.2.1) · Stable hotfix | [Since Stable v0.2.0](https://github.com/BrutusBossNL/DekuForge/compare/v0.2.0...v0.2.1). Fix 8.3 and dotted TEMP paths, shorten runtime staging and add cold setup validation. | [BrutusBossNL] reported [#4]. |
| [v0.3.0-preview.3](https://github.com/BrutusBossNL/DekuForge/releases/tag/v0.3.0-preview.3) | [Since preview.2](https://github.com/BrutusBossNL/DekuForge/compare/v0.3.0-preview.2...v0.3.0-preview.3). Fix setup paths and add the release list with contextual update actions. | [BrutusBossNL] reported [#4]. |
| [v0.3.0-preview.2](https://github.com/BrutusBossNL/DekuForge/releases/tag/v0.3.0-preview.2) | [Since preview.1](https://github.com/BrutusBossNL/DekuForge/compare/v0.3.0-preview.1...v0.3.0-preview.2). Restore the original updater health-report contract. Report update results and prefill failure reports. | No additional linked PR or issue in the delta. |
| [v0.3.0-preview.1](https://github.com/BrutusBossNL/DekuForge/releases/tag/v0.3.0-preview.1) | [Since the previous Preview](https://github.com/BrutusBossNL/DekuForge/compare/v0.2.0-preview.2...v0.3.0-preview.1). Add Mods and guarded code rebuilds. Fix scrolling artwork and prepare the complete NVIDIA Frame Generation dependencies. | [vmpgninGIT] reported [#1]. [BrutusBossNL] reported [#2] and [#3]. |
| [v0.2.0](https://github.com/BrutusBossNL/DekuForge/releases/tag/v0.2.0) and [v0.2.0-preview.2](https://github.com/BrutusBossNL/DekuForge/releases/tag/v0.2.0-preview.2) | First Early Access Stable and its preceding Preview. Include Windows setup and launcher updates, guided save import, diagnostics and the integrated Cheat Manager. | See the release notes and [third-party notices](THIRD_PARTY_NOTICES.md). |

[sirtheta]: https://github.com/sirtheta
[Exposed77]: https://github.com/Exposed77
[EtaYorius]: https://github.com/EtaYorius
[Ripthorn]: https://github.com/Ripthorn
[vmpgninGIT]: https://github.com/vmpgninGIT
[BrutusBossNL]: https://github.com/BrutusBossNL
[#1]: https://github.com/BrutusBossNL/DekuForge/issues/1
[#2]: https://github.com/BrutusBossNL/DekuForge/issues/2
[#3]: https://github.com/BrutusBossNL/DekuForge/issues/3
[#4]: https://github.com/BrutusBossNL/DekuForge/issues/4
[#5]: https://github.com/BrutusBossNL/DekuForge/issues/5
[#6]: https://github.com/BrutusBossNL/DekuForge/issues/6
[#7]: https://github.com/BrutusBossNL/DekuForge/issues/7
[#8]: https://github.com/BrutusBossNL/DekuForge/issues/8
[#9]: https://github.com/BrutusBossNL/DekuForge/pull/9
[#10]: https://github.com/BrutusBossNL/DekuForge/pull/10
[#11]: https://github.com/BrutusBossNL/DekuForge/pull/11
[#12]: https://github.com/BrutusBossNL/DekuForge/issues/12
[#13]: https://github.com/BrutusBossNL/DekuForge/pull/13
[#14]: https://github.com/BrutusBossNL/DekuForge/issues/14
