"""DekuForge instruction extensions over the unchanged pinned engine lifter.

The static runtime uses unsigned guest addresses. Authenticated return forms
therefore have the ordinary return's control-flow semantics in this model.
This does not implement pointer signing or authentication of signed pointers.
"""

import importlib.util
from pathlib import Path
import sys

_project = next(parent for parent in Path(__file__).resolve().parents
                if (parent / "engine" / "SOURCE.json").is_file())
_spec = importlib.util.spec_from_file_location("_dekuforge_base_lifter", _project / "engine" / "recomp" / "lifter.py")
_base = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _base
_spec.loader.exec_module(_base)
globals().update({name: value for name, value in vars(_base).items() if not name.startswith("__")})
sys.path.insert(0, str(_project))
from dekuforge.arm64_models import decode_half_negate, decode_byte_dot


class Lifter(_base.Lifter):
    def dp_reg(self, word, pc):
        # The static guest profile has SCTLR.EnIA/EnIB disabled, matching its
        # existing unsigned returns and hint forms. PACGA is independent of
        # those switches and still computes a real generic authentication code.
        if word & 0xFFE0FC00 == 0x9AC03000:
            rd, rn, rm = word & 31, (word >> 5) & 31, (word >> 16) & 31
            expression = f"(df_qarma_computePAC({X(rn)}, {XS(rm)}, 0, 0) & UINT64_C(0xffffffff00000000))"
            return Insn("op", set_reg(1, rd, expression))
        if word & 0xFFFFFC00 in (0xDAC10000, 0xDAC10400, 0xDAC11000, 0xDAC11400):
            return Insn("op", "/* PAC/AUT: address-key signing disabled by the static guest profile. */")
        if word & 0xFFFFFFE0 == 0xDAC143E0:
            rd = word & 31
            return Insn("op", set_reg(1, rd, f"df_strip_instruction_pac({X(rd)})"))
        return super().dp_reg(word, pc)

    def branch_sys(self, word, pc):
        if word in (0xD65F0BFF, 0xD65F0FFF):
            return Insn("ret")
        return super().branch_sys(word, pc)

    def atomic(self, word):
        # LDAPRB/H/W/X use an acquire load. The host's full acquire ordering is
        # stronger than RCpc; no weaker ordering is introduced on x86-64.
        if word & 0x3FFFFC00 == 0x38BFC000:
            width = 8 << ((word >> 30) & 3)
            rn, rt = (word >> 5) & 31, word & 31
            expression = f"__atomic_load_n((uint{width}_t *)(uintptr_t)({XS(rn)}), __ATOMIC_ACQUIRE)"
            code = f"(void){expression};" if rt == 31 else set_reg(width == 64, rt, expression)
            return Insn("op", code)
        return super().atomic(word)

    def fp_simd(self, word, pc):
        dot = decode_byte_dot(word) if self.sc is not None else None
        if dot is not None:
            destination, left, right, wide, unsigned = dot
            return Insn("op", f"c->v[{destination}] = df_dot_bytes(c->v[{destination}], c->v[{left}], "
                        f"c->v[{right}], {int(wide)}, {int(unsigned)});")
        decoded = decode_half_negate(word) if self.sc is not None else None
        if decoded is not None:
            destination, source, wide = decoded
            return Insn("op", f"c->v[{destination}] = df_negate_half_vector(c->v[{source}], {int(wide)});")
        return super().fp_simd(word, pc)
