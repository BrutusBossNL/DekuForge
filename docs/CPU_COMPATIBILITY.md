# Instruction compatibility

> Historical validation of the experimental `engine/` extensions. These results
> do not describe the active stable 0.10.1 generator or establish its compatibility.
> The current build route is documented in [building.md](building.md). The
> synthetic checks remain useful development tools; their local game-generation
> counts below are recorded observations, not shipped game content.

The immutable engine baseline is composed with original extensions in an owned,
ignored engine workspace. Both the parent generator and its child workers import
the same extension. The source import and hash inventory remain unchanged.

The first extension recognizes RETAA and RETAB as returns in the static runtime's
unsigned guest-address model. It does not implement pointer signing or signed
pointer authentication. Unknown neighboring encodings still fail. Tests compare
valid return targets with Unicorn 2.1.4 using its maximum-feature ARM64 model.
They do not establish complete PAuth emulation or game compatibility.

LDAPR byte, halfword, word and doubleword forms now emit host acquire loads.
This ordering is stronger than RCpc. Compiled C fragments have been checked
against ARM64 execution for 96 cases, including SP addressing, zero-register
destinations, zero extension, flag preservation and unchanged memory.

Full SDK generation now covers 45,907 functions in 57 chunks with zero
unsupported instructions. The remaining 58 PACGA and ten address-authentication
sites have been implemented for the explicit static guest profile below.

The static profile uses 39-bit virtual addresses, no instruction top-byte ignore,
disabled instruction-address signing (SCTLR.EnIA/EnIB=0), and a zero generic key.
This makes the existing hint and return behavior consistent with address-key
PAC/AUT forms. XPACI restores the canonical address. PACGA remains active and
computes actual QARMA authentication arithmetic. This is not a claim of hardware
key secrecy or enabled address authentication. Compiled emitted instructions
matched ARM64 in 1,200 complete-state cases; QARMA separately matched 204 PACGA
cases. The test oracle's privilege and PAuth activation settings are explicit in
`tools/check_pauth.py`; its inactive-XPACI optimization is avoided.

FP16 vector FNEG now flips each halfword's sign bit without changing NaN payloads,
flags or other lanes. Compiled emitted C matched the ARM64 oracle in 528 cases,
including 4H/8H widths, aliased registers, NaNs and different FPCR modes.

The full main-module pass exposed byte-vector dot products. Original portable
SDOT/UDOT lowering has now matched ARM64 execution in 1,600 compiled-C cases,
covering signed/unsigned bytes, 64/128-bit widths, all operand-alias patterns,
accumulation overflow and unchanged CPU state. Indexed dot products remain
outside this extension. Full main generation has now been repeated across all
249,960 functions and reports zero unsupported instructions.
The separate subsdk0 movie module has 1,547 functions and zero unsupported sites.

The dot-product encodings were cross-checked with LLVM's instruction tests:
https://github.com/llvm/llvm-project/blob/main/llvm/test/MC/AArch64/armv8.2a-dotprod.s .

Instruction encodings were checked against the LLVM project's AArch64 tests:
https://lists.llvm.org/pipermail/llvm-commits/Week-of-Mon-20181203/607432.html .
The test oracle is an optional development dependency, not part of the game runtime.
