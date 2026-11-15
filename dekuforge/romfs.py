"""Independent, resumable image assembly with a validated binary file index."""

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import struct
import time

from .gameplan import TITLE
from .nup import Archive, ArchiveError, safe_name

MAGIC = b"DFROMFS1"
HEADER = struct.Struct("<8sQQ")
ROW = struct.Struct("<QQII")
RESERVE = 2 * 1024 ** 3


def safe_path(value):
    path = PurePosixPath(value)
    if (not value or value.startswith("/") or "\\" in value or "\0" in value or
            any(part in ("", ".", "..") for part in value.split("/")) or str(path) != value):
        raise ArchiveError("Invalid RomFS path")
    for part in value.split("/"):
        safe_name(part)
    return value.encode("utf-8")


def encode_index(records, image_size):
    strings, rows = bytearray(), bytearray()
    previous = None
    for item in records:
        name = safe_path(item["path"])
        if previous is not None and name <= previous:
            raise ArchiveError("RomFS index is not uniquely sorted")
        offset, size = item["offset"], item["size"]
        if offset < 0 or size < 0 or offset + size > image_size:
            raise ArchiveError("RomFS file exceeds the image")
        rows.extend(ROW.pack(offset, size, len(strings), len(name) + 1))
        strings.extend(name + b"\0")
        previous = name
    return HEADER.pack(MAGIC, len(records), HEADER.size + len(rows)) + rows + strings


def decode_index(data, image_size):
    if len(data) < HEADER.size:
        raise ArchiveError("Truncated RomFS index")
    magic, count, names_at = HEADER.unpack_from(data)
    if magic != MAGIC or names_at != HEADER.size + count * ROW.size or names_at > len(data):
        raise ArchiveError("Invalid RomFS index layout")
    records = []
    previous = None
    for number in range(count):
        offset, size, start, length = ROW.unpack_from(data, HEADER.size + number * ROW.size)
        if not length or names_at + start + length > len(data) or offset + size > image_size:
            raise ArchiveError("RomFS index entry exceeds its bounds")
        raw = data[names_at + start:names_at + start + length]
        if raw[-1] != 0 or b"\0" in raw[:-1]:
            raise ArchiveError("Invalid RomFS index name")
        try:
            path = raw[:-1].decode("utf-8")
        except UnicodeDecodeError as error:
            raise ArchiveError("Invalid RomFS name encoding") from error
        name = safe_path(path)
        if previous is not None and name <= previous:
            raise ArchiveError("RomFS index is not uniquely sorted")
        previous = name
        records.append({"path": path, "offset": offset, "size": size})
    return records


def _atomic_json(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _hash_prefix(path, length):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        left = length
        while left:
            block = stream.read(min(left, 4 * 1024 * 1024))
            if not block:
                raise ArchiveError("Truncated partial RomFS image")
            digest.update(block)
            left -= len(block)
    return digest


def select_snapshot(archive):
    # This stage requires an export with complete per-version RomFS snapshots.
    # Never union base/update paths: removed files must not be resurrected.
    packages = [package for package in archive.packages
                if (package.title == TITLE and package.kind == 0) or
                (package.title == TITLE + 0x800 and package.kind == 1)]
    if not any(package.kind == 0 for package in packages):
        raise ArchiveError("Expected base game is absent")
    packages.sort(key=lambda item: (item.kind == 1, item.version), reverse=True)
    for package in packages:
        entries = sorted(archive.tree(package.romfs), key=lambda item: item[0].as_posix().encode("utf-8"))
        if entries:
            return package, entries
    raise ArchiveError("No RomFS tree found")


def build_romfs(filename, output, notify, checkpoint_every=64):
    archive = Archive(filename)
    package, entries = select_snapshot(archive)
    records, position = [], 0
    for relative, member in entries:
        position = (position + 15) // 16 * 16
        records.append({"path": relative.as_posix(), "offset": position, "size": member.length})
        position += member.length
    if position >= 1 << 63 or checkpoint_every < 1:
        raise ArchiveError("Invalid image size or checkpoint interval")
    index = encode_index(records, position)
    output = Path(output).expanduser().absolute()
    if output.resolve() != output:
        raise ValueError("RomFS output must not be a link")
    if output.exists() and any(output.iterdir()) and not (output / ".dekuforge-romfs").is_file():
        raise ValueError("RomFS output is not owned by DekuForge")
    output.mkdir(parents=True, exist_ok=True)
    for item in output.iterdir():
        if item.is_symlink() or getattr(item, "is_junction", lambda: False)():
            raise ValueError("RomFS output contains a link")
    (output / ".dekuforge-romfs").touch()
    lock = output / ".romfs.lock"
    try:
        owner = lock.open("x", encoding="utf-8")
    except FileExistsError:
        raise ValueError("A RomFS build is already active") from None
    try:
        with owner:
            owner.write(str(os.getpid()))
            owner.flush()
            identity = {"input_index": archive.index_sha256, "package": f"{package.title:016X}",
                        "version": package.version, "size": position, "index_sha256": hashlib.sha256(index).hexdigest()}
            manifest_path = output / "index.json"
            image = output / "romfs.bin"
            partial = output / "romfs.partial"
            checkpoint_path = output / "checkpoint.json"
            if manifest_path.is_file():
                existing = json.loads(manifest_path.read_text(encoding="utf-8"))
                if existing.get("identity") != identity:
                    raise ValueError("Existing image belongs to different input; no files overwritten")
                if existing.get("status") != "ok" or existing.get("romfs_size") != position or existing.get("files") != records:
                    raise ArchiveError("Existing RomFS manifest no longer matches its layout")
                if not image.is_file() or image.stat().st_size != position or _hash_prefix(image, position).hexdigest() != existing["romfs_sha256"]:
                    raise ArchiveError("Existing RomFS image no longer matches its checksum")
                if not (output / "romfs-index.bin").is_file() or (output / "romfs-index.bin").read_bytes() != index:
                    raise ArchiveError("Existing RomFS index no longer matches")
                notify("checked", "Verified existing RomFS image")
                return output
            done, cursor, digest = 0, 0, hashlib.sha256()
            if checkpoint_path.is_file():
                checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
                if checkpoint.get("identity") != identity:
                    raise ValueError("Checkpoint belongs to different input")
                done, cursor = checkpoint["files"], checkpoint["position"]
                if not isinstance(done, int) or not 0 <= done <= len(entries):
                    raise ArchiveError("Invalid RomFS checkpoint count")
                expected = records[done - 1]["offset"] + records[done - 1]["size"] if done else 0
                if cursor != expected:
                    raise ArchiveError("Invalid RomFS checkpoint position")
                source = partial if partial.exists() else image
                digest = _hash_prefix(source, cursor)
                if digest.hexdigest() != checkpoint["sha256"]:
                    raise ArchiveError("RomFS checkpoint checksum mismatch")
                if source == image and done != len(entries):
                    raise ArchiveError("Incomplete image was prematurely committed")
                if source == image and image.stat().st_size != position:
                    raise ArchiveError("Committed image has unexpected trailing data")
            elif image.exists():
                raise ArchiveError("Finished image has no verified manifest or checkpoint")
            if shutil.disk_usage(output).free < position - cursor + RESERVE:
                raise ValueError("Not enough disk space for the remaining image and reserve")

            def save_checkpoint():
                _atomic_json(checkpoint_path, {"identity": identity, "files": done, "position": cursor,
                                               "sha256": digest.hexdigest()})
            last_progress = 0
            if not image.exists():
                with partial.open("r+b" if partial.exists() else "w+b") as sink, archive.path.open("rb") as source:
                    sink.truncate(cursor)
                    sink.seek(cursor)
                    for number in range(done, len(entries)):
                        member = entries[number][1]
                        padding = records[number]["offset"] - cursor
                        if padding:
                            sink.write(b"\0" * padding)
                            digest.update(b"\0" * padding)
                            cursor += padding
                        for block in archive.chunks(member, stream=source):
                            sink.write(block)
                            digest.update(block)
                            cursor += len(block)
                            now = time.monotonic()
                            if now - last_progress >= 0.25:
                                notify("progress", {"phase": "game_data", "done": cursor, "total": position})
                                last_progress = now
                        done = number + 1
                        if done % checkpoint_every == 0 or done == len(entries):
                            sink.flush()
                            os.fsync(sink.fileno())
                            save_checkpoint()
                    sink.flush()
                    os.fsync(sink.fileno())
                if cursor != position:
                    raise ArchiveError("Built image has unexpected length")
                partial.replace(image)
            manifest = {"status": "ok", "identity": identity, "romfs_size": position,
                        "romfs_sha256": digest.hexdigest(), "files": records}
            binary_temp = output / "romfs-index.tmp"
            binary_temp.write_bytes(index)
            binary_temp.replace(output / "romfs-index.bin")
            _atomic_json(manifest_path, manifest)
            notify("progress", {"phase": "game_data", "done": position, "total": position})
            notify("checked", "RomFS image and index assembled and verified; not a playable executable")
            return output
    finally:
        lock.unlink(missing_ok=True)
