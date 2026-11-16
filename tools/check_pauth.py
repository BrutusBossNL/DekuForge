"""Compare portable QARMA and emitted PAuth arithmetic with an independent ARM64 engine."""
import argparse
import ctypes
import json
import importlib.util
import os
from pathlib import Path
import random
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "local" / "devdeps")]
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM
from unicorn.arm64_const import UC_CPU_ARM64_MAX, UC_ARM64_REG_X0, UC_ARM64_REG_X1, UC_ARM64_REG_X2, UC_ARM64_REG_PSTATE
from unicorn import arm64_const as registers


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", type=Path, required=True)
    args = parser.parse_args()
    output = ROOT / "build" / "validation-pauth"
    output.mkdir(exist_ok=True)
    source = output / "qarma.c"
    source.write_text('#include "qarma.h"\n__declspec(dllexport) uint64_t pac(uint64_t p, uint64_t m) {'
                      'return df_qarma_computePAC(p,m,0,0) & UINT64_C(0xffffffff00000000);}\n', encoding="utf-8")
    library = output / "qarma.dll"
    env = os.environ.copy()
    env["PATH"] = str(args.compiler.parent) + os.pathsep + env.get("PATH", "")
    subprocess.run([str(args.compiler), "-O2", "-Wall", "-Wextra", "-Werror", "-shared", str(source),
                    "-I", str(ROOT / "engine_overrides"), "-o", str(library)], env=env, check=True)
    native = ctypes.CDLL(str(library))
    native.pac.argtypes, native.pac.restype = [ctypes.c_uint64, ctypes.c_uint64], ctypes.c_uint64
    oracle = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
    oracle.ctl_set_cpu_model(UC_CPU_ARM64_MAX)
    # Permit EL1 authentication instructions rather than taking EL2/EL3 traps.
    oracle.cpr_write(3, 4, 1, 1, 0, (1 << 41) | (1 << 40))
    oracle.cpr_write(3, 6, 1, 1, 0, (1 << 17) | (1 << 16))
    oracle.reg_write(UC_ARM64_REG_PSTATE, 0x3CD)
    oracle.mem_map(0x1000, 0x1000)
    oracle.mem_write(0x1000, struct.pack("<I", 0x9AC23020))  # PACGA x0,x1,x2
    rng = random.Random(8993)
    inputs = [(0, 0), (1, 0), (0, 1), ((1 << 64) - 1, (1 << 64) - 1)]
    inputs += [(rng.getrandbits(64), rng.getrandbits(64)) for _ in range(200)]
    for pointer, modifier in inputs:
        oracle.reg_write(UC_ARM64_REG_X1, pointer)
        oracle.reg_write(UC_ARM64_REG_X2, modifier)
        oracle.emu_start(0x1000, 0x1004, count=1)
        actual, expected = native.pac(pointer, modifier), oracle.reg_read(UC_ARM64_REG_X0)
        assert actual == expected, (hex(pointer), hex(modifier), hex(actual), hex(expected))
    sys.path.insert(0, str(ROOT / "engine" / "recomp"))
    spec = importlib.util.spec_from_file_location("pauth_lifter", ROOT / "engine_overrides" / "lifter.py")
    extension = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(extension)
    lifter = extension.Lifter(0x1000, simd="c")
    forms = [0x9AC23020, 0x9ADF33E0, 0x9AC13020, 0x9AC2303F,
             0xDAC10020, 0xDAC10420, 0xDAC11020, 0xDAC11420,
             0xDAC107FE, 0xDAC117FE, 0xDAC143E0, 0xDAC143FE]
    lines = [f'#include "{(ROOT / "engine/runtime/cpu.h").as_posix()}"',
             '#include "qarma.h"', '#include "pauth_profile.h"',
             '_Static_assert(sizeof(Cpu) == 1024, "CPU layout changed");']
    for index, word in enumerate(forms):
        lines.append(f"__declspec(dllexport) void f{index}(Cpu *c) {{ (void)c; {lifter.lift(word, 0x1000).code} }}")
    emitted = output / "emitted.c"
    emitted.write_text("\n".join(lines), encoding="utf-8")
    emitted_library = output / "emitted.dll"
    subprocess.run([str(args.compiler), "-O2", "-Wall", "-Wextra", "-Werror", "-shared", str(emitted),
                    "-I", str(ROOT / "engine_overrides"), "-o", str(emitted_library)], env=env, check=True)
    native_emitted = ctypes.CDLL(str(emitted_library))
    oracle.cpr_write(3, 6, 2, 0, 2, 25)  # TCR_EL3: 39-bit VA, no top-byte ignore.
    # Keep the emulator's PAuth decoding active via the unused data-key switch;
    # instruction-address keys remain disabled. Otherwise its XPACI fast path
    # assumes no signed inputs exist and optimizes away the strip operation.
    oracle.cpr_write(3, 6, 1, 0, 0, (oracle.cpr_read(3, 6, 1, 0, 0) & ~((1 << 31) | (1 << 30))) | (1 << 27))
    gprs = [getattr(registers, f"UC_ARM64_REG_X{i}") for i in range(31)]
    cases = 0
    for index, word in enumerate(forms):
        function = getattr(native_emitted, f"f{index}")
        function.argtypes, function.restype = [ctypes.c_void_p], None
        oracle.mem_write(0x1000, struct.pack("<I", word))
        for iteration in range(100):
            buffer = ctypes.create_string_buffer(1039)
            address = (ctypes.addressof(buffer) + 15) & ~15
            state = bytearray(b"\xa5" * 1024)
            for reg, identifier in enumerate(gprs):
                value = rng.getrandbits(64)
                struct.pack_into("<Q", state, reg * 8, value)
                oracle.reg_write(identifier, value)
            sp = rng.getrandbits(64) & ~15
            struct.pack_into("<Q", state, 256, sp)
            struct.pack_into("<Q", state, 272, 0xA0000000)
            oracle.reg_write(registers.UC_ARM64_REG_SP, sp)
            oracle.reg_write(registers.UC_ARM64_REG_NZCV, 0xA0000000)
            ctypes.memmove(address, bytes(state), 1024)
            oracle.emu_start(0x1000, 0x1004, count=1)
            for reg, identifier in enumerate(gprs):
                struct.pack_into("<Q", state, reg * 8, oracle.reg_read(identifier))
            function(address)
            actual_state = ctypes.string_at(address, 1024)
            assert actual_state == bytes(state), (hex(word), iteration,
                [(reg, hex(struct.unpack_from("<Q", actual_state, reg * 8)[0]),
                  hex(struct.unpack_from("<Q", state, reg * 8)[0])) for reg in range(31)
                 if actual_state[reg * 8:reg * 8 + 8] != state[reg * 8:reg * 8 + 8]])
            assert oracle.reg_read(registers.UC_ARM64_REG_NZCV) == 0xA0000000
            cases += 1
    (output / "result.json").write_text(json.dumps({"generic_cases": len(inputs), "emitted_cases": cases,
                                                    "disagreements": 0}), encoding="utf-8")
    print(f"PACGA arithmetic: {len(inputs)} native cases; emitted PAuth: {cases} cases; all match ARM64")


if __name__ == "__main__":
    main()
