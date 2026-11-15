"""Bounded, read-only parser for the unencrypted NUP v1 container format.

This implementation validates offsets and names before exposing archive members.
Game bytes are read only on request and never placed in project source files.
"""

from dataclasses import dataclass
from contextlib import nullcontext
import hashlib
from pathlib import Path
import struct


class ArchiveError(ValueError):
    pass


@dataclass(frozen=True)
class Member:
    name: str
    length: int
    offset: int
    stored: int
    digest: bytes
    codec: int


@dataclass(frozen=True)
class Package:
    title: int
    root: int
    exefs: int
    romfs: int
    version: int
    kind: int


def safe_name(value):
    reserved = {"CON", "PRN", "AUX", "NUL"} | {f"{prefix}{i}" for prefix in ("COM", "LPT") for i in range(1, 10)}
    if (not value or value in (".", "..") or value[-1] in " ." or
            any(ord(char) < 32 or char in '/\\:<>"|?*' for char in value) or
            value.split(".")[0].upper() in reserved):
        raise ArchiveError("Unsafe archive member name")
    return value


class Archive:
    def __init__(self, filename):
        self.path = Path(filename).resolve()
        self.size = self.path.stat().st_size
        with self.path.open("rb") as stream:
            header = stream.read(128)
            if len(header) != 128 or header[:4] != b"NUP\x01":
                raise ArchiveError("Not a NUP v1 archive")
            if struct.unpack_from("<HH", header, 4) != (128, 1):
                raise ArchiveError("Unsupported NUP header version")
            offset, length = struct.unpack_from("<QQ", header, 8)
            if offset < 128 or not 48 <= length <= 256 * 1024 ** 2 or offset + length > self.size:
                raise ArchiveError("Invalid archive index range")
            stream.seek(offset)
            index = stream.read(length)
        if hashlib.sha256(index).digest() != header[24:56]:
            raise ArchiveError("Archive index checksum mismatch")
        self.index_sha256 = header[24:56].hex()
        self._index_end = offset + length
        self._decode(index, struct.unpack_from("<I", header, 72)[0])

    def _decode(self, data, package_count):
        signature, packages, directories, files, names_at, names_size, _ = struct.unpack_from("<IIQQQQQ", data)
        records_end = 48 + 64 * packages + 24 * directories + 80 * files
        if (signature != 0x01434F54 or packages != package_count or records_end > names_at or
                names_at + names_size > len(data) or (names_at - records_end) % 4):
            raise ArchiveError("Malformed archive index layout")
        names = data[names_at:names_at + names_size]

        def name(at):
            start, length = struct.unpack_from("<II", data, at)
            if start + length > len(names):
                raise ArchiveError("Archive name exceeds name pool")
            try:
                return names[start:start + length].decode("utf-8")
            except UnicodeDecodeError as error:
                raise ArchiveError("Archive names must be UTF-8") from error

        self.packages = []
        for number in range(packages):
            at = 48 + number * 64
            title, root, exefs, romfs, version = struct.unpack_from("<QIIII", data, at)
            for directory in (root, exefs, romfs):
                if directory != 0xFFFFFFFF and directory >= directories:
                    raise ArchiveError("Package references an absent directory")
            self.packages.append(Package(title, root, exefs, romfs, version, data[at + 24]))
        self.directories = []
        child_count = (names_at - records_end) // 4
        for number in range(directories):
            at = 48 + packages * 64 + number * 24
            first, count = struct.unpack_from("<II", data, at + 8)
            if first + count > child_count:
                raise ArchiveError("Directory references an absent child")
            self.directories.append((name(at), first, count))
        self.members = []
        for number in range(files):
            at = 48 + packages * 64 + directories * 24 + number * 80
            length, offset, stored = struct.unpack_from("<QQQ", data, at + 8)
            codec = data[at + 64]
            if offset < self._index_end or offset + stored > self.size or codec not in (0, 1):
                raise ArchiveError("Invalid file data range or compression codec")
            if codec == 0 and length != stored:
                raise ArchiveError("Uncompressed member has inconsistent lengths")
            self.members.append(Member(safe_name(name(at)), length, offset, stored, data[at + 32:at + 64], codec))
        self.children = [entry[0] for entry in struct.iter_unpack("<I", data[records_end:names_at])]
        if any(child >= directories + files for child in self.children):
            raise ArchiveError("Directory references an absent entry")

    def tree(self, directory):
        if directory == 0xFFFFFFFF:
            return
        if not 0 <= directory < len(self.directories):
            raise ArchiveError("Invalid directory selection")
        pending = [(directory, Path())]
        visited, destinations = set(), set()
        while pending:
            number, prefix = pending.pop()
            if number in visited:
                raise ArchiveError("Repeated or cyclic directory reference")
            visited.add(number)
            _, first, count = self.directories[number]
            for entry in self.children[first:first + count]:
                if entry < len(self.directories):
                    relative = prefix / safe_name(self.directories[entry][0])
                    next_directory = entry
                else:
                    next_directory = None
                    entry -= len(self.directories)
                    relative = prefix / self.members[entry].name
                key = relative.as_posix().casefold()
                if key in destinations:
                    raise ArchiveError("Duplicate archive destination")
                destinations.add(key)
                if next_directory is None:
                    yield relative, self.members[entry]
                else:
                    pending.append((next_directory, relative))

    def chunks(self, member, chunk_size=1024 * 1024, *, stream=None):
        decoder = None
        compression_error = ValueError
        if member.codec:
            try:
                from compression.zstd import ZstdDecompressor, ZstdError
            except ImportError as error:
                raise ArchiveError("Compressed NUP members require Python 3.14 or newer") from error
            decoder = ZstdDecompressor()
            compression_error = ZstdError
        digest = hashlib.sha256()
        total = 0
        # A sequential packer can reuse its own handle. Callers must not share
        # that handle between threads; each member is still checked independently.
        context = self.path.open("rb") if stream is None else nullcontext(stream)
        with context as stream:
            stream.seek(member.offset)
            left = member.stored
            while left:
                block = stream.read(min(chunk_size, left))
                if not block:
                    raise ArchiveError("Truncated archive payload")
                left -= len(block)
                while True:
                    try:
                        output = decoder.decompress(block, chunk_size) if decoder else block
                    except (ValueError, EOFError, compression_error) as error:
                        raise ArchiveError("Invalid compressed payload") from error
                    total += len(output)
                    if total > member.length:
                        raise ArchiveError("Payload exceeds declared size")
                    digest.update(output)
                    if output:
                        yield output
                    if not decoder or decoder.needs_input or decoder.eof:
                        break
                    block = b""
                if decoder and decoder.eof and (left or decoder.unused_data):
                    raise ArchiveError("Trailing compressed payload data")
        if decoder and not decoder.eof:
            raise ArchiveError("Incomplete compressed payload")
        if total != member.length or digest.digest() != member.digest:
            raise ArchiveError("Payload checksum or size mismatch")

    def summary(self):
        return {"packages": [{"title_id": f"{p.title:016X}", "version": p.version, "kind": p.kind}
                             for p in self.packages], "files": len(self.members),
                "expanded_bytes": sum(member.length for member in self.members)}
