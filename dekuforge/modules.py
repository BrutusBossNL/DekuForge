"""Verified NSO segment decoding for the independent engine input format."""

import hashlib
from pathlib import Path
import struct

from .gameplan import FIRST_ADDRESS, inspect_nso
from .nup import ArchiveError


def normalize_module(payload, name="module"):
    metadata = inspect_nso(name, payload, FIRST_ADDRESS)
    flags = struct.unpack_from("<I", payload, 12)[0]
    header = bytearray(payload[:256])
    struct.pack_into("<I", header, 12, flags & ~0x87)
    output = bytearray(header)
    for number, segment in enumerate(metadata.segments):
        offset = segment["file_offset"]
        data = payload[offset:offset + segment["stored_size"]]
        codec = segment["codec"]
        if codec == "lz4":
            try:
                from lz4.block import decompress
            except ImportError as error:
                raise RuntimeError("Install the lz4 engine dependency") from error
            data = decompress(data, uncompressed_size=segment["size"])
        elif codec == "zbic":
            try:
                from zbic import decompress
            except ImportError as error:
                raise RuntimeError("Install the zbic engine dependency") from error
            data = decompress(data)
        if len(data) != segment["size"]:
            raise ArchiveError(f"{name}: decoded segment size mismatch")
        if flags & (1 << (number + 3)):
            expected = payload[160 + 32 * number:192 + 32 * number]
            if hashlib.sha256(data).digest() != expected:
                raise ArchiveError(f"{name}: decoded segment checksum mismatch")
        output.extend(b"\0" * (-len(output) % 16))
        struct.pack_into("<I", output, 16 + 16 * number, len(output))
        struct.pack_into("<I", output, 96 + 4 * number, len(data))
        output.extend(data)
    return bytes(output)


def normalize_prepared(prepared, notify=None):
    source = prepared / "exefs"
    destination = prepared / "normalized-exefs"
    if destination.exists() and destination.resolve() != destination:
        raise ValueError("Normalized module directory must not be a link")
    destination.mkdir(exist_ok=True)
    inputs = list(source.iterdir())
    for number, path in enumerate(inputs, 1):
        if not path.is_file() or path.resolve() != path:
            raise ValueError("Prepared input must be a regular file")
        payload = path.read_bytes()
        normalized = normalize_module(payload, path.name) if payload[:4] == b"NSO0" else payload
        target = destination / path.name
        if target.exists():
            if target.resolve() != target or target.read_bytes() != normalized:
                raise ValueError("Existing normalized input differs; no files overwritten")
        else:
            with target.open("xb") as output:
                output.write(normalized)
        if notify is not None:
            notify("progress", {"phase": "normalizing", "done": number, "total": len(inputs)})
    return destination
