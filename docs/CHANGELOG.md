# Release history

Component versions are independent. Published releases are not replaced in place.

## Independent engine 0.1.0-independent.3 - memory addressing

Launcher `0.3.0-independent.2`, engine `0.1.0-independent.3`; buildkit unchanged.
On the experimental `independent` branch only: original LDP/STP/LDPSW and
register-offset scalar memory emission, full-state/memory oracle comparisons,
adjacent-region stack-frame execution and explicit pair-fault prevalidation.
Reject SIMD encodings that the older scalar masks incorrectly accepted.
This does not implement a complete CPU, guest services or renderer and is not
a playable-game release. Main and its published releases are unchanged. The branch launcher retains
main's original image-lifetime cleanup and Tk root-method naming repair.
Static coverage evidence and its limitations are in [INDEPENDENT_EVIDENCE.md](INDEPENDENT_EVIDENCE.md).

The historical main release entries below describe the inherited stable route,
not the capabilities of this independent backend.

## Launcher 0.2.0 — first Early Access release

Buildkit 0.2.1; engine 0.11.0. This release uses a normal version, without a
preview suffix, and the launcher shows the Early Access stage. The preceding
private test releases remain recorded below for update compatibility and history.

The Windows launcher, installer, guided NX2navi save import, update path, issue
reports and Cheat Manager integration are included. Broader platform and in-game
acceptance limits remain documented in the README and roadmap. Publication is
pending the concrete component-rights review in [PUBLICATION_REVIEW.md](PUBLICATION_REVIEW.md).

## Launcher 0.2.0-preview.2 / buildkit 0.2.1

Engine: 0.11.0 over the pinned stable NX2navi 0.10.1 reference. No new game-engine
version is introduced by these launcher changes.

- Guided NX2navi save-folder discovery and automatic active-game destination
  selection, with review, confirmation and a retained destination backup.
- Unified padded, scrollable pages; stable backdrop and corrected logo animation.
- Invisible installation/update health checks instead of a visible language tour.
- Reviewed hardware/log issue reports, managed-build removal fixes and save-aware
  native uninstallation with original game archive protection.
- Hidden native build-worker consoles and clearer Windows interruption recovery.
- Updated installation, update, SmartScreen and component-provenance documentation.

The launcher updater replaces the application itself. Build dependencies are
checked/downloaded when needed by a local build. Uninstalling is not required for
an ordinary launcher update. Private previews require repository access and the
Preview channel; draft releases remain hidden from the updater.

## Launcher 0.2.0-preview.1

Initial private setup/updater test identity. Several subsequent test packages
incorrectly reused this identity. That made different installed launchers look
identical and prevented normal newer-version detection. Those packages were
distributed through a draft release, which the updater intentionally ignores.
Preview 2 establishes a distinct update identity; later distributed changes must
advance the version rather than replacing a published package.
