# Instruction compatibility

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

Full SDK generation was exercised: 45,907 functions, 57 chunks. After these
extensions, 68 unsupported instructions remain: 58 in the two-source register
class and 10 in the one-source extension class (pointer authentication). This
remains a build failure, not a playable SDK. No unsupported instruction is
silently replaced with zero or a no-op.

FP16 vector FNEG now flips each halfword's sign bit without changing NaN payloads,
flags or other lanes. Compiled emitted C matched the ARM64 oracle in 528 cases,
including 4H/8H widths, aliased registers, NaNs and different FPCR modes.

The full main-module pass exposed byte-vector dot products. Original portable
SDOT/UDOT lowering has now matched ARM64 execution in 1,600 compiled-C cases,
covering signed/unsigned bytes, 64/128-bit widths, all operand-alias patterns,
accumulation overflow and unchanged CPU state. Indexed dot products remain
outside this extension. The full main pass contains 249,960 functions and reports
four unsupported sites, all these UDOT forms. The affected chunk (657 functions)
has subsequently been regenerated and compiled with zero unsupported sites in a
separate validation folder. The original full-generation manifest is preserved;
the complete main output still needs a fresh generation before production linking.
The separate subsdk0 movie module has 1,547 functions and zero unsupported sites.

The dot-product encodings were cross-checked with LLVM's instruction tests:
https://github.com/llvm/llvm-project/blob/main/llvm/test/MC/AArch64/armv8.2a-dotprod.s .

Instruction encodings were checked against the LLVM project's AArch64 tests:
https://lists.llvm.org/pipermail/llvm-commits/Week-of-Mon-20181203/607432.html .
The test oracle is an optional development dependency, not part of the game runtime.
