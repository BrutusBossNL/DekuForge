"""Compile the constructor decoder and check synthetic bounds and local module prologues."""
import argparse
import ctypes
import os
from pathlib import Path
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "engine" / "recomp"))
from nso import Nso


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", type=Path, required=True)
    parser.add_argument("--prepared", type=Path, required=True)
    args = parser.parse_args()
    output = ROOT / "build" / "constructor-check"
    output.mkdir(exist_ok=True)
    source = output / "check.c"
    source.write_text('#include "constructor_flag.h"\n__declspec(dllexport) uint64_t check(const uint8_t *p, '
                      'uint64_t n, uint64_t d, uint64_t t, uint64_t i) {'
                      'return df_ctor_flag_offset(p,n,d,t,i);}\n', encoding="utf-8")
    dll = output / "check.dll"
    environment = os.environ.copy()
    environment["PATH"] = str(args.compiler.parent) + os.pathsep + environment.get("PATH", "")
    subprocess.run([str(args.compiler), "-O2", "-Wall", "-Wextra", "-Werror", "-shared", str(source),
                    "-I", str(ROOT / "engine_overrides"), "-o", str(dll)], env=environment, check=True)
    library = ctypes.CDLL(str(dll))
    function = library.check
    function.argtypes = [ctypes.c_void_p, *([ctypes.c_uint64] * 4)]
    function.restype = ctypes.c_uint64
    cases = 0
    for pac in (False, True):
        for page_offset in (-1, 0, 1):
            image = bytearray(0x8000)
            init = 0x2000
            position = init + (20 if pac else 16)
            struct.pack_into("<I", image, init, 0xD503237F if pac else 0xA9BF7BFD)
            immediate = page_offset & 0x1FFFFF
            adrp = 0x90000013 | ((immediate & 3) << 29) | ((immediate >> 2) << 5)
            struct.pack_into("<II", image, position, adrp, 0xB9400268 | (32 << 10))
            buffer = ctypes.create_string_buffer(bytes(image))
            expected = 0x2000 + page_offset * 4096 + 128
            assert function(buffer, len(image), 0, 0x4000, init) == expected
            for size, data, text, start in ((16, 0, 16, init), (len(image), expected + 1, 0x4000, init),
                                            (len(image), 0, init + 28, init), (len(image), 0, 0x4000, len(image))):
                assert function(buffer, size, data, text, start) == 0
            cases += 5
    for name in ("main", "subsdk0", "sdk"):
        module = Nso(str(args.prepared / "normalized-exefs" / name))
        buffer = ctypes.create_string_buffer(bytes(module.image))
        value = function(buffer, len(module.image), module.data[0], sum(module.text), module.dyn[12])
        assert module.data[0] <= value <= len(module.image) - 4, name
        print(f"{name}: constructor state located in data; offset {value:#x}")
        cases += 1
    print(f"Constructor decoder: {cases} native cases passed; no game execution.")


if __name__ == "__main__":
    main()
