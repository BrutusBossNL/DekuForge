"""Read bounded MOD0 metadata and derive local boot assertions from verified inputs."""

import hashlib
import json
from pathlib import Path
import struct

from .gameplan import FIRST_ADDRESS, inspect_nso
from .modules import normalize_module


def module_boot_metadata(payload, name):
    module = inspect_nso(name, payload, FIRST_ADDRESS)
    if any(segment["codec"] != "stored" for segment in module.segments):
        raise ValueError("Boot metadata requires normalized module segments")
    image = bytearray(module.mapped_size)
    for segment in module.segments:
        start, memory, size = (segment[key] for key in ("file_offset", "memory_offset", "size"))
        image[memory:memory + size] = payload[start:start + size]

    def read(offset, fmt):
        length = struct.calcsize(fmt)
        if offset < 0 or offset + length > len(image):
            raise ValueError("Boot metadata points outside the module")
        return struct.unpack_from(fmt, image, offset)[0]

    mod0 = read(4, "<I")
    if mod0 + 8 > len(image) or image[mod0:mod0 + 4] != b"MOD0":
        raise ValueError("Boot module has no valid MOD0 header")
    dynamic = mod0 + read(mod0 + 4, "<i")
    tags = {}
    for number in range(4096):
        tag, value = read(dynamic + 16 * number, "<Q"), read(dynamic + 16 * number + 8, "<Q")
        if tag == 0:
            break
        if tag in (12, 25, 27):
            if tag in tags:
                raise ValueError("Duplicate boot dynamic tag")
            tags[tag] = value
    else:
        raise ValueError("Unterminated boot dynamic table")
    init, array, length = tags.get(12, 0), tags.get(25, 0), tags.get(27, 0)
    text = module.segments[0]
    if not text["memory_offset"] <= init < text["memory_offset"] + text["size"] or init % 4:
        raise ValueError("DT_INIT is outside module text")
    if length % 8 or array > len(image) or length > len(image) - array:
        raise ValueError("Invalid constructor array extent")
    if length and 25 not in tags:
        raise ValueError("Constructor array size has no array address")
    return {"name": name, "build_id": module.build_id, "init": init,
            "init_array": array, "constructor_count": length // 8}


def write_boot_profile(prepared):
    prepared = Path(prepared).resolve()
    plan = json.loads((prepared / "build-plan.json").read_text(encoding="utf-8"))
    inputs = {item["name"]: item for item in plan["inputs"]}
    rows = []
    for name in ("main", "subsdk0", "sdk"):
        if name not in inputs:
            raise ValueError("The current boot profile requires main, subsdk0 and sdk")
        path = prepared / "exefs" / name
        if path.resolve() != path:
            raise ValueError("Boot input must not be a link")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != inputs[name]["sha256"]:
            raise ValueError("Boot profile input differs from the verified plan")
        rows.append(module_boot_metadata(normalize_module(raw, name), name))
    output = prepared / "host-config"
    if output.resolve() != output:
        raise ValueError("Boot profile output must not be a link")
    output.mkdir(exist_ok=True)
    header = "// Local assertions derived from verified module metadata. Do not commit.\n#pragma once\n"
    header += "#define DF_BOOT_INIT_ROWS " + ", ".join(
        '{"' + row["name"] + '", ' + str(row["constructor_count"]) + '}' for row in rows) + "\n"
    for filename, content in (("df_boot_profile.h", header),
                              ("boot-profile.json", json.dumps({"modules": rows, "playable": False}, indent=2) + "\n")):
        target = output / filename
        if target.resolve() != target:
            raise ValueError("Boot profile target must not be a link")
        temporary = target.with_suffix(target.suffix + ".tmp")
        with temporary.open("x", encoding="utf-8") as stream:
            stream.write(content)
        temporary.replace(target)
    return output
