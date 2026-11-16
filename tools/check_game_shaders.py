"""Translate a bounded sample of local NVN2 shaders and validate SPIR-V without running a GPU."""
import argparse
import compression.zstd as zstd
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine" / "tools"))
sys.path.insert(0, str(ROOT))
from shader_census import sarc
from dekuforge.mesh_stage import metadata


def shaders(data):
    if data[:4] == b"SARC":
        for member in sarc(data).values():
            yield from shaders(member)
        return
    if data[:4] == b"BAHS" and len(data) >= 32:
        start, pool_size, pool = struct.unpack_from("<III", data, 20)
        if not 32 <= start <= pool <= len(data) or pool_size > len(data) - pool:
            raise ValueError("BAHS code pool outside its image")
        for control_size in (0xd8, 0xe0):
            at = start
            while (at := data.find(struct.pack("<I", control_size), at, pool)) >= 0:
                record, at = at - 8, at + 4
                if record < start or record % 4 or record + 16 > pool:
                    continue
                code_offset = struct.unpack_from("<Q", data, record)[0]
                control_at = record + struct.unpack_from("<i", data, record + 12)[0]
                if not start <= control_at <= pool - control_size or code_offset >= pool_size:
                    continue
                ctl = data[control_at:control_at + control_size]
                if ctl[:8] != struct.pack("<II", 0x98761234, 0xc9):
                    continue
                c1, length = struct.unpack_from("<II", ctl, 0x40)
                if not 0 < c1 <= length <= pool_size - code_offset:
                    continue
                body = data[pool + code_offset:pool + code_offset + length]
                stage = {5: "cs", 6: "ts", 7: "ms"}.get(ctl[0x56]) or {0: "vs", 1: "vs", 5: "ps"}.get((struct.unpack_from("<I", body)[0] >> 10) & 15)
                if stage:
                    yield stage, ctl, body, c1
        return
    # NVN2 GLSLC containers also occur inside BAHS and archive members.
    position = data.find(b"\x91\x68\x86\x19")
    while position >= 0:
        if position + 0x68 <= len(data):
            total, offset = struct.unpack_from("<II", data, position + 0x5c)
            if 0x60 <= offset and offset + 0xd8 <= total <= len(data) - position:
                at = position + offset
                if data[at:at+8] == struct.pack("<II", 0x98761234, 0xc9):
                    size = struct.unpack_from("<I", data, at + 0x30)[0]
                    c1, length = struct.unpack_from("<II", data, at + 0x40)
                    if 0xd8 <= size <= 65536 and 0 < c1 <= length <= 16 << 20 and offset + size + length <= total:
                        ctl = data[at:at+size]
                        body = data[at+size:at+size+length]
                        stage = {5: "cs", 6: "ts", 7: "ms"}.get(ctl[0x56])
                        if stage:
                            yield stage, ctl, body, c1
        position = data.find(b"\x91\x68\x86\x19", position + 4)
    for position in range(len(data)):
        if data[position:position + 8] != b"BNSH\0\0\0\0":
            continue
        if position + 0x88 > len(data):
            raise ValueError("Truncated BNSH header")
        size = struct.unpack_from("<I", data, position + 28)[0]
        count, table = struct.unpack_from("<IQ", data, position + 124)
        if size > len(data) - position or table + count * 64 > size:
            raise ValueError("BNSH table outside its image")
        for number in range(count):
            program = struct.unpack_from("<Q", data, position + table + number * 64 + 16)[0]
            if not program:
                continue
            if program + 56 > size:
                raise ValueError("BNSH program outside its image")
            for stage_offset in (8, 16, 24, 32, 40, 48):
                record = struct.unpack_from("<Q", data, position + program + stage_offset)[0]
                if not record:
                    continue
                if record + 32 > size:
                    raise ValueError("BNSH stage outside its image")
                control, code, length, control_size = struct.unpack_from("<QQII", data, position + record + 8)
                if control + control_size > size or code + length > size or control_size < 0x68:
                    raise ValueError("BNSH shader range outside its image")
                ctl, body = data[position + control:position + control + control_size], data[position + code:position + code + length]
                if ctl[:8] != struct.pack("<II", 0x98761234, 0xC9):
                    continue
                declared = struct.unpack_from("<I", ctl, 0x44)[0]
                c1 = struct.unpack_from("<I", ctl, 0x40)[0]
                if not 0 < c1 <= declared <= length:
                    raise ValueError("NVN2 code range differs from BNSH")
                stage = {5: "cs", 6: "ts", 7: "ms"}.get(ctl[0x56]) or {0: "vs", 1: "vs", 5: "ps"}.get((struct.unpack_from("<I", body)[0] >> 10) & 15)
                if stage:
                    yield stage, ctl, body[:declared], c1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--romfs", type=Path, required=True)
    parser.add_argument("--toolchain", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=16)
    parser.add_argument("--mesh", action="store_true", help="Validate task/mesh stage-memory translation separately")
    args = parser.parse_args()
    manifest = json.loads((args.romfs / "index.json").read_text(encoding="utf-8"))
    entries = {row["path"]: row for row in manifest["files"]}
    with (args.romfs / "romfs.bin").open("rb") as stream:
        def read(name):
            row = entries[name]
            stream.seek(row["offset"])
            data = stream.read(row["size"])
            if len(data) != row["size"]:
                raise ValueError("Short shader resource read")
            return data
        dictionaries = {}
        if "Pack/ZsDic.pack.zs" in entries:
            for raw in sarc(zstd.decompress(read("Pack/ZsDic.pack.zs"))).values():
                dictionary = zstd.ZstdDict(raw)
                dictionaries[dictionary.dict_id] = dictionary
        def decode(raw):
            if raw[:4] != b"\x28\xb5\x2f\xfd":
                return raw
            info = zstd.get_frame_info(raw)
            if info.decompressed_size is None or info.decompressed_size > 512 << 20:
                raise ValueError("Unbounded shader package")
            return zstd.decompress(raw, zstd_dict=dictionaries[info.dictionary_id] if info.dictionary_id else None)
        output = ROOT / "build" / ("validation-game-mesh-shaders" if args.mesh else "validation-game-shaders")
        output.mkdir(exist_ok=True)
        selected = []
        seen = set()
        for name in sorted(entries):
            if not (name.endswith(".bfsha.zs") or (args.mesh and "Nin_Ounce_NVN2" in name and name.endswith(".sarc.zs"))) or len(selected) >= args.limit:
                continue
            for stage, control, code, c1 in shaders(decode(read(name))):
                if (stage in ("ts", "ms")) != args.mesh:
                    continue
                key = hashlib.sha256(control + code).hexdigest()
                if key in seen:
                    continue
                seen.add(key)
                path = output / (key + ".code")
                path.write_bytes(code)
                job = {"key": key, "stage": stage, "code": str(path), "c1": code[c1:].hex(),
                       "ampere": True, "debug": False}
                if stage == "cs":
                    job["local"] = list(struct.unpack_from("<III", control, 0x58))
                    job["shared"] = struct.unpack_from("<I", control, 0x64)[0]
                if args.mesh:
                    facts = metadata(control, code)
                    (output / (key + ".mesh.json")).write_text(json.dumps(facts, indent=2), encoding="utf-8")
                    path.write_bytes(code[0x80:facts["instructions"]])
                    job.update(stage="cs", stage_memory=facts["stage_memory"], local=[facts["threads"], 1, 1], shared=facts["shared"])
                selected.append(job)
                if len(selected) >= args.limit:
                    break
    if not selected:
        raise ValueError("No NVN2 shaders were found")
    jobs = output / "jobs.json"
    jobs.write_text(json.dumps(selected), encoding="utf-8")
    active = json.loads((ROOT / "build/shader-compiler/active.json").read_text())
    translator = ROOT / active["executable"]
    result = subprocess.run([str(translator), str(jobs), str(output)], capture_output=True, text=True, encoding="utf-8", errors="replace")
    (output / "translation.log").write_text(result.stdout + result.stderr, encoding="utf-8")
    if result.returncode:
        raise RuntimeError("Shader sample translation failed:\n" + result.stderr[-4000:])
    validator = ROOT / "local/build-tools/shaders/ucrt64/bin/spirv-val.exe"
    env = os.environ.copy()
    env["PATH"] = str(validator.parent) + os.pathsep + str(args.toolchain.resolve()) + os.pathsep + env.get("PATH", "")
    for job in selected:
        subprocess.run([str(validator), "--target-env", "vulkan1.1", str(output / (job["key"] + ".spv"))], env=env, check=True)
    print(f"Validated {len(selected)} real NVN2 shader translations; no GPU execution")


if __name__ == "__main__":
    main()
