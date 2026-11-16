"""Inventory local NVN2 shaders and prepare them before starting the game.

Outputs contain game-derived data and must remain in the owned local build.
Driver preparation covers compute pipelines and graphics stage libraries;
complete graphics pipeline combinations are learned during play.
"""
import argparse
import compression.zstd as zstd
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_game_shaders import shaders, sarc

STAGES = {"vs": 0, "ps": 4, "cs": 5, "ts": 6, "ms": 7}
NVN_STAGES = {"vs": 0, "ps": 1, "cs": 5, "ts": 3, "ms": 4}


def seed(stage, control, code, constants):
    if len(control) < 0xd8 or not 0 < constants <= len(code) <= 16 << 20:
        raise ValueError("Invalid shader bounds")
    normalized = bytearray(0x880)
    normalized[:0xd8] = control[:0xd8]
    struct.pack_into("<II", normalized, 0x700, constants, len(code))
    struct.pack_into("<I", normalized, 0x714, NVN_STAGES[stage])
    local = (0, 0, 0)
    shared = 0
    if stage == "cs":
        normalized[0x748:0x758] = control[0x58:0x68]
        local = struct.unpack_from("<III", control, 0x58)
        shared = struct.unpack_from("<I", control, 0x64)[0]
        if any(not 0 < n <= 1024 for n in local):
            raise ValueError("Invalid compute workgroup")
    elif stage in ("ts", "ms"):
        local = (1, 1, 1)  # Runtime answers; the stage wrapper supplies its actual workgroup.
    c1 = code[constants:]
    number = STAGES[stage]
    digest = hashlib.sha256(struct.pack("<I", number) + normalized +
                            struct.pack("<Q", len(code)) + code + struct.pack("<I", len(c1)) + c1).digest()
    program = struct.pack("<III", number, len(code), len(c1)) + digest + normalized + code + c1
    answers = bytes([4] * 32) + bytes(32 * 3 + 8) + struct.pack("<HHHIB", *local, shared, 0)
    assert len(answers) == 147
    variant = struct.pack("<I", number) + digest + bytes(32) + answers + bytes([2])
    return digest, program, variant


def prepare(romfs, output, limit=0):
    if output.resolve() != output.absolute() or not (output / ".dekuforge-native").is_file():
        raise ValueError("Shader preparation requires an owned native build")
    rows = json.loads((romfs / "index.json").read_text(encoding="utf-8"))["files"]
    entries = {row["path"]: row for row in rows}
    seen, counts = set(), {}
    programs = output / "seed-programs.bin.tmp"
    answers = output / "seed-answers.bin.tmp"
    with (romfs / "romfs.bin").open("rb") as archive, programs.open("wb") as pf, answers.open("wb") as af:
        def read(name):
            row = entries[name]
            if not 0 <= row["size"] <= 512 << 20 or row["offset"] < 0:
                raise ValueError("Shader resource exceeds bounds")
            archive.seek(row["offset"])
            data = archive.read(row["size"])
            if len(data) != row["size"]:
                raise ValueError("Truncated shader resource")
            return data
        dictionaries = {}
        if "Pack/ZsDic.pack.zs" in entries:
            for raw in sarc(zstd.decompress(read("Pack/ZsDic.pack.zs"))).values():
                dictionary = zstd.ZstdDict(raw)
                dictionaries[dictionary.dict_id] = dictionary
        # The native RecHeader stores exactly eight magic bytes, followed by
        # two little-endian words (the descriptive C literals are longer).
        pf.write(b"NX2NAVIS" + struct.pack("<II", 1, 0))
        af.write(b"NX2NAVIS" + struct.pack("<II", 1, 216))
        names = sorted(n for n in entries if n.endswith(".bfsha.zs") or
                       ("Nin_Ounce_NVN2" in n and n.endswith(".sarc.zs")))
        for index, name in enumerate(names):
            raw = read(name)
            info = zstd.get_frame_info(raw)
            if info.decompressed_size is None or info.decompressed_size > 512 << 20:
                raise ValueError("Unbounded shader resource")
            data = zstd.decompress(raw, zstd_dict=dictionaries[info.dictionary_id] if info.dictionary_id else None)
            for stage, control, code, constants in shaders(data):
                digest, program, variant = seed(stage, control, code, constants)
                if digest in seen:
                    continue
                seen.add(digest)
                pf.write(program)
                af.write(variant)
                counts[stage] = counts.get(stage, 0) + 1
                if limit and len(seen) >= limit:
                    break
            print(f"Shader inventory {index + 1}/{len(names)}: {len(seen)} unique", flush=True)
            if limit and len(seen) >= limit:
                break
    if not seen:
        raise ValueError("No supported shaders found")
    programs.replace(output / "seed-programs.bin")
    answers.replace(output / "seed-answers.bin")
    (output / "shader-inventory.json").write_text(json.dumps({"stages": counts, "limited": bool(limit)}, indent=2))
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--romfs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--no-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0, help="Diagnostic inventory limit; zero means all")
    args = parser.parse_args()
    if args.limit < 0:
        parser.error("Limit must be nonnegative")
    output = args.output.absolute()
    print(json.dumps(prepare(args.romfs, output, args.limit)), flush=True)
    if not args.no_run:
        env = dict(os.environ, NX2NAVI_GPU="vulkan")
        with (output / "shader-preparation.log").open("w", encoding="utf-8") as log:
            result = subprocess.run([str(output / "DekuForgeGame.exe"), "--prepare-shaders"], cwd=output,
                                    env=env, stdout=log, stderr=subprocess.STDOUT,
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if result.returncode:
            raise RuntimeError(f"Shader preparation failed ({result.returncode}); see {output / 'shader-preparation.log'}")


if __name__ == "__main__":
    main()
