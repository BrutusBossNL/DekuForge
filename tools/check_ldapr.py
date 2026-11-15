"""Compile emitted acquire loads and compare their state changes with ARM64 execution."""

import argparse
import ctypes
import importlib.util
import json
import os
from pathlib import Path
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "local" / "devdeps"))
sys.path.insert(0, str(ROOT / "engine" / "recomp"))
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM
from unicorn.arm64_const import (UC_CPU_ARM64_MAX, UC_ARM64_REG_PC, UC_ARM64_REG_SP,
                                UC_ARM64_REG_NZCV, UC_ARM64_REG_X0, UC_ARM64_REG_X1)


class Cpu(ctypes.Structure):
    _fields_ = [("x", ctypes.c_uint64 * 32), ("sp", ctypes.c_uint64), ("nzcv", ctypes.c_uint64)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", type=Path, required=True)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("validation_lifter", ROOT / "engine_overrides" / "lifter.py")
    extension = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(extension)
    lifter = extension.Lifter(0x1000)
    forms = [(size, rn, rt, 0x38BFC000 | (size << 30) | (rn << 5) | rt)
             for size in range(4) for rn in (1, 31) for rt in (0, 1, 31)]
    output = ROOT / "build" / "validation-ldapr"
    output.mkdir(parents=True, exist_ok=True)
    source = output / "emitted.c"
    lines = ["#include <stdint.h>", "typedef struct { uint64_t x[32], sp, nzcv; } Cpu;"]
    for number, (_, _, _, instruction) in enumerate(forms):
        code = lifter.lift(instruction, 0x1000).code
        lines.append(f"__declspec(dllexport) void f{number}(Cpu *c) {{ {code} }}")
    source.write_text("\n".join(lines), encoding="utf-8")
    library = output / "emitted.dll"
    environment = os.environ.copy()
    environment["PATH"] = str(args.compiler.parent) + os.pathsep + environment.get("PATH", "")
    subprocess.run([str(args.compiler), "-shared", "-O2", "-Wall", "-Wextra", "-Werror",
                    str(source), "-o", str(library)], check=True, env=environment)
    native = ctypes.CDLL(str(library))
    checked = 0
    for number, (size, rn, rt, instruction) in enumerate(forms):
        fn = getattr(native, f"f{number}")
        fn.argtypes = [ctypes.POINTER(Cpu)]
        fn.restype = None
        for value in (0, 1, 0x80, 0xFEDCBA9876543210):
            buffer = ctypes.c_uint64(value)
            host_address = ctypes.addressof(buffer)
            context = Cpu()
            context.x[0] = 0x99887766
            context.x[1] = host_address if rn == 1 else 0x88776655
            context.x[31] = 0xDEADBEEF
            context.sp = host_address if rn == 31 else 0x3000
            context.nzcv = 0xA0000000
            cpu = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
            cpu.ctl_set_cpu_model(UC_CPU_ARM64_MAX)
            cpu.mem_map(0x1000, 0x1000)
            cpu.mem_map(0x2000, 0x1000)
            cpu.mem_write(0x1000, struct.pack("<I", instruction))
            cpu.mem_write(0x2000, struct.pack("<Q", value))
            cpu.reg_write(UC_ARM64_REG_X0, 0x99887766)
            cpu.reg_write(UC_ARM64_REG_X1, 0x2000 if rn == 1 else 0x88776655)
            cpu.reg_write(UC_ARM64_REG_SP, 0x2000 if rn == 31 else 0x3000)
            cpu.reg_write(UC_ARM64_REG_NZCV, context.nzcv)
            cpu.emu_start(0x1000, 0x1004, count=1)
            fn(ctypes.byref(context))
            for register, constant in ((0, UC_ARM64_REG_X0), (1, UC_ARM64_REG_X1)):
                actual = context.x[register]
                if register == rn and register != rt:
                    actual = 0x2000 if actual == host_address else actual
                assert actual == cpu.reg_read(constant), (size, rn, rt, value, register)
            actual_sp = 0x2000 if context.sp == host_address else context.sp
            assert actual_sp == cpu.reg_read(UC_ARM64_REG_SP)
            assert context.nzcv == cpu.reg_read(UC_ARM64_REG_NZCV)
            assert context.x[31] == 0xDEADBEEF
            assert buffer.value == value
            assert cpu.reg_read(UC_ARM64_REG_PC) == 0x1004
            checked += 1
    (output / "result.json").write_text(json.dumps({"cases": checked, "disagreements": 0}), encoding="utf-8")
    print(f"LDAPR differential validation: {checked} cases, 0 disagreements")


if __name__ == "__main__":
    main()
