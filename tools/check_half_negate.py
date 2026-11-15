"""Compare compiled vector statements with ARM64, including every unchanged state byte."""

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
sys.path.insert(0, str(ROOT / "local" / "devdeps"))
sys.path.insert(0, str(ROOT / "engine" / "recomp"))
sys.path.insert(0, str(ROOT))
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM
from unicorn.arm64_const import (UC_CPU_ARM64_MAX, UC_ARM64_REG_Q0, UC_ARM64_REG_FPSR,
                                UC_ARM64_REG_FPCR, UC_ARM64_REG_NZCV)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", type=Path, required=True)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("native_half_lifter", ROOT / "engine_overrides" / "lifter.py")
    extension = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(extension)
    lifter = extension.Lifter(0x1000, simd="c")
    forms = [(wide, source, target, 0x2EF8F800 | (int(wide) << 30) | (source << 5) | target)
             for wide in (False, True) for source, target in ((2, 2), (1, 0))]
    output = ROOT / "build" / "validation-half-negate"
    output.mkdir(parents=True, exist_ok=True)
    source = output / "emitted.c"
    lines = [f'#include "{(ROOT / "engine" / "runtime" / "cpu.h").as_posix()}"',
             f'#include "{(ROOT / "engine_overrides" / "half_negate.h").as_posix()}"',
             '_Static_assert(sizeof(Cpu) == 1024, "unexpected CPU size");']
    for number, (_, _, _, word) in enumerate(forms):
        lines.append(f"__declspec(dllexport) void f{number}(Cpu *c) {{ {lifter.lift(word, 0x1000).code} }}")
    source.write_text("\n".join(lines), encoding="utf-8")
    library = output / "emitted.dll"
    environment = os.environ.copy()
    environment["PATH"] = str(args.compiler.parent) + os.pathsep + environment.get("PATH", "")
    subprocess.run([str(args.compiler), "-shared", "-O2", "-Wall", "-Wextra", "-Werror", "-msse4.2",
                    str(source), "-o", str(library)], check=True, env=environment)
    native = ctypes.CDLL(str(library))
    cpu = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
    cpu.ctl_set_cpu_model(UC_CPU_ARM64_MAX)
    cpu.mem_map(0x1000, 0x1000)
    edges = (0, 0x8000, 1, 0x3C00, 0x7C00, 0xFC00, 0x7E00, 0x7D00, 0xFFFF)
    patterns = [sum(value << (16 * lane) for lane in range(8)) for value in edges]
    rng = random.Random(2411)
    patterns.extend(rng.getrandbits(128) for _ in range(24))
    cases = 0
    for number, (wide, rn, rd, word) in enumerate(forms):
        fn = getattr(native, f"f{number}")
        fn.argtypes, fn.restype = [ctypes.c_void_p], None
        cpu.mem_write(0x1000, struct.pack("<I", word))
        for control in (0, 1 << 19, 1 << 25, 1 << 26):
            for pattern in patterns:
                buffer = ctypes.create_string_buffer(1024 + 15)
                address = (ctypes.addressof(buffer) + 15) & ~15
                ctypes.memset(address, 0xA5, 1024)
                ctypes.memmove(address + 512 + 16 * rn, pattern.to_bytes(16, "little"), 16)
                ctypes.c_uint64.from_address(address + 272).value = 0xA0000000
                ctypes.c_uint64.from_address(address + 320).value = control
                ctypes.c_uint64.from_address(address + 328).value = 0x0800001F
                before = bytearray(ctypes.string_at(address, 1024))
                cpu.reg_write(UC_ARM64_REG_Q0 + rd, int.from_bytes(before[512 + 16 * rd:528 + 16 * rd], "little"))
                cpu.reg_write(UC_ARM64_REG_Q0 + rn, pattern)
                cpu.reg_write(UC_ARM64_REG_FPCR, control)
                cpu.reg_write(UC_ARM64_REG_FPSR, 0x0800001F)
                cpu.reg_write(UC_ARM64_REG_NZCV, 0xA0000000)
                cpu.emu_start(0x1000, 0x1004, count=1)
                expected = cpu.reg_read(UC_ARM64_REG_Q0 + rd)
                before[512 + 16 * rd:528 + 16 * rd] = expected.to_bytes(16, "little")
                fn(address)
                assert ctypes.string_at(address, 1024) == bytes(before), (wide, rn, rd, control, pattern)
                cases += 1
    (output / "result.json").write_text(json.dumps({"cases": cases, "disagreements": 0}), encoding="utf-8")
    print(f"Half-vector emitted C validation: {cases} cases, 0 disagreements")


if __name__ == "__main__":
    main()
