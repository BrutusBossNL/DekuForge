"""Differentially test compiled emitted dot-product instructions against ARM64."""
import argparse
import ctypes
import importlib.util
import json
import os
from pathlib import Path
import random
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "local" / "devdeps"), str(ROOT / "engine" / "recomp")]
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM
from unicorn.arm64_const import UC_CPU_ARM64_MAX, UC_ARM64_REG_Q0, UC_ARM64_REG_NZCV, UC_ARM64_REG_FPSR
from dekuforge.arm64_models import decode_byte_dot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", type=Path, required=True)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("dot_lifter", ROOT / "engine_overrides" / "lifter.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    lifter = module.Lifter(0x1000, simd="c")
    forms = [(wide, unsigned, rd, rn, rm, 0x0E809400 | wide << 30 | unsigned << 29 | rm << 16 | rn << 5 | rd)
             for wide in (0, 1) for unsigned in (0, 1)
             for rd, rn, rm in ((0, 1, 2), (1, 1, 2), (2, 1, 2), (1, 1, 1))]
    assert decode_byte_dot(0x6E839404) == (4, 0, 3, True, True)
    assert decode_byte_dot(0x6E839422) == (2, 1, 3, True, True)
    assert decode_byte_dot(0x6E839804) is None
    assert decode_byte_dot(0x6F83E004) is None  # Indexed form is not covered by this extension.
    output = ROOT / "build" / "validation-dot-product"
    output.mkdir(exist_ok=True)
    lines = [f'#include "{(ROOT / "engine/runtime/cpu.h").as_posix()}"',
             f'#include "{(ROOT / "engine_overrides/dot_product.h").as_posix()}"',
             '_Static_assert(sizeof(Cpu) == 1024, "CPU state layout changed");']
    for index, (*_, word) in enumerate(forms):
        lines.append(f"__declspec(dllexport) void f{index}(Cpu *c) {{ {lifter.lift(word, 0x1000).code} }}")
    source = output / "emitted.c"
    source.write_text("\n".join(lines), encoding="utf-8")
    library_path = output / "emitted.dll"
    environment = os.environ.copy()
    environment["PATH"] = str(args.compiler.parent) + os.pathsep + environment.get("PATH", "")
    subprocess.run([str(args.compiler), "-O2", "-shared", "-Wall", "-Wextra", "-Werror", str(source),
                    "-o", str(library_path)], env=environment, check=True)
    native = ctypes.CDLL(str(library_path))
    oracle = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
    oracle.ctl_set_cpu_model(UC_CPU_ARM64_MAX)
    oracle.mem_map(0x1000, 0x1000)
    rng = random.Random(3519)
    values = [int.from_bytes(bytes([byte]) * 16, "little") for byte in (0, 1, 127, 128, 255)]
    cases = 0
    for index, (wide, unsigned, rd, rn, rm, word) in enumerate(forms):
        function = getattr(native, f"f{index}")
        function.argtypes, function.restype = [ctypes.c_void_p], None
        oracle.mem_write(0x1000, struct.pack("<I", word))
        for iteration in range(100):
            buffer = ctypes.create_string_buffer(1039)
            address = (ctypes.addressof(buffer) + 15) & ~15
            before = bytearray(b"\xa5" * 1024)
            for reg in {rd, rn, rm}:
                value = values[(iteration + reg) % len(values)] if iteration < 25 else rng.getrandbits(128)
                before[512 + reg * 16:528 + reg * 16] = value.to_bytes(16, "little")
                oracle.reg_write(UC_ARM64_REG_Q0 + reg, value)
            struct.pack_into("<Q", before, 272, 0xA0000000)
            struct.pack_into("<Q", before, 328, 0x0800001F)
            oracle.reg_write(UC_ARM64_REG_NZCV, 0xA0000000)
            oracle.reg_write(UC_ARM64_REG_FPSR, 0x0800001F)
            ctypes.memmove(address, bytes(before), 1024)
            oracle.emu_start(0x1000, 0x1004, count=1)
            before[512 + rd * 16:528 + rd * 16] = oracle.reg_read(UC_ARM64_REG_Q0 + rd).to_bytes(16, "little")
            function(address)
            assert ctypes.string_at(address, 1024) == bytes(before), (index, iteration, wide, unsigned)
            assert oracle.reg_read(UC_ARM64_REG_NZCV) == 0xA0000000
            assert oracle.reg_read(UC_ARM64_REG_FPSR) == 0x0800001F
            cases += 1
    (output / "result.json").write_text(json.dumps({"cases": cases, "disagreements": 0}), encoding="utf-8")
    print(f"Dot-product emitted C validation: {cases} cases, 0 disagreements")


if __name__ == "__main__":
    main()
