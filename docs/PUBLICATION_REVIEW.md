# First Early Access publication review

Target: DekuForge 0.2.0 — Early Access. The owner has requested public release.
The owner subsequently made the repository public separately. That visibility
change does not resolve the findings below. The `independent` branch now starts
replacing the dependencies identified here; it is not yet a cleared replacement
engine. See [INDEPENDENT_ENGINE.md](INDEPENDENT_ENGINE.md).

## Content and validation

The tracked-source boundary check passes. The launcher release is assembled from
an explicit source/tooling/branding allowlist; ROMs, user saves, generated game
source and compiled game executables are not release assets. Existing Windows
CI and the isolated authenticated application-update test have passed. These
checks do not establish distribution rights or complete game compatibility.

## Unresolved component terms

The active backend is NX2navi 0.10.1 at
`5ae55db41c7d11c4e997d2676019939a936e560b`. Its retained `LICENSE-ADDITIONS`
explicitly grants no license for its covered additions and changes and restricts
copying, modification and distribution without written permission. The owner's
earlier response stated that such permission had not been obtained; no new grant
has been supplied in this review.

The full active backend is downloaded for local staging rather than committed
here. However, `engine_overrides/dekuforge_0110/cheat_manager.patch` contains
upstream context and removed lines as well as the owner's additions. Its scoped
custom-contribution license does not grant rights to surrounding upstream code.
Do not treat that grant, the original engine's MIT base, private access or a
successful build as resolving all later code's terms.

The release-only controller artwork has terms referring specifically to NX2navi
distribution. It is not bundled in our launcher ZIP, but permission for use in
this project's build/distribution route must not be assumed. See
[THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md) for the retained provenance.

Before representing the complete project as redistributable, obtain the relevant
written grants or replace the restricted parts with independently authored or
appropriately licensed components, then review the shipped material and history.
Do not remove notices or relabel restricted material as original MIT code.

## Announcement wording

NX2navi's own handover notice says it merged into Triforce. Describe that move
rather than asserting that the project was simply abandoned. Keep the invitation
focused on DekuForge's own features, require the user's own legally obtained game
dump and do not imply affiliation, guaranteed compatibility or an available public
download before the repository/release is actually public.
