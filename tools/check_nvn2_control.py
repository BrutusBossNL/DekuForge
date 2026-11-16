"""Compile and verify short NVN2 control adaptation with synthetic records."""
import argparse
import ctypes
import os
from pathlib import Path
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", type=Path, required=True)
    args = parser.parse_args()
    folder = ROOT / "build" / "validation-nvn2-control"
    folder.mkdir(exist_ok=True)
    source = folder / "test.c"
    source.write_text('#include "nvn2_control.h"\n__declspec(dllexport) int normalize(uint8_t *o, const uint8_t *c, '
                      'size_t n, const uint8_t *p, size_t s) {return df_nvn2_normalize(o,c,n,p,s);}', encoding="utf-8")
    library = folder / "test.dll"
    env = os.environ.copy()
    env["PATH"] = str(args.compiler.parent) + os.pathsep + env.get("PATH", "")
    subprocess.run([str(args.compiler), "-shared", "-O2", "-Wall", "-Wextra", "-Werror", str(source), "-I",
                    str(ROOT / "engine_overrides"), "-o", str(library)], env=env, check=True)
    native = ctypes.CDLL(str(library))
    fn = native.normalize
    fn.argtypes, fn.restype = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t], ctypes.c_int
    count = 0
    for stage, native_stage in ((1, 0), (5, 1), (0, 5), (1, 6), (3, 7)):
        compute = native_stage == 5
        control, code = bytearray(0xD8), bytearray(0x200)
        struct.pack_into("<II", control, 0, 0x98761234, 0xC9)
        for offset, value in ((0x38, 0x80), (0x40, 0x100), (0x44, 0x200)):
            struct.pack_into("<I", control, offset, value)
        struct.pack_into("<I", code, 0, 4 | stage << 10)
        control[0x56] = native_stage
        if compute:
            control[0x56] = 5
            struct.pack_into("<IIII", control, 0x58, 32, 2, 1, 4096)
        inputs, instructions = ctypes.create_string_buffer(bytes(control)), ctypes.create_string_buffer(bytes(code))
        output = ctypes.create_string_buffer(b"\xa5" * (0x880 + 16))
        assert fn(output, inputs, len(control), instructions, len(code)) == 1
        actual = output.raw
        assert actual[0x880:0x890] == b"\xa5" * 16
        assert actual[:0xD8] == control
        assert struct.unpack_from("<II", actual, 0x700) == (0x100, 0x200)
        assert struct.unpack_from("<I", actual, 0x714)[0] == {0: 0, 1: 1, 5: 5, 6: 3, 7: 4}[native_stage]
        if compute:
            assert struct.unpack_from("<IIII", actual, 0x748) == (32, 2, 1, 4096)
        for length, code_size in ((7, len(code)), (0xD7, len(code)), (len(control), 0x100)):
            assert fn(output, inputs, length, instructions, code_size) != 1
        assert inputs.raw[:-1] == control
        count += 4
    print(f"NVN2 control adaptation: {count} native cases passed")


if __name__ == "__main__":
    main()
