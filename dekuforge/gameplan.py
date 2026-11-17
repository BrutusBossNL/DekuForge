"""Independent selection and reproducible preparation of a Switch game build.

Preparation produces verified input modules and a build plan. It cannot compile
a playable game until the CPU, OS and graphics backends are implemented.
"""

from dataclasses import dataclass, asdict
import hashlib
import json
import os
from pathlib import Path
import struct

from .core import ROOT
from .nup import Archive, ArchiveError

TITLE = 0x0400486024DEC000
MODULE_ORDER = ["main", *[f"subsdk{i}" for i in range(10)], "sdk"]
FIRST_ADDRESS = 0x7000000000
MODULE_ALIGNMENT = 2 * 1024 * 1024
ADDRESS_LIMIT = 1 << 39
MAX_MODULE_SIZE = 512 * 1024 * 1024


@dataclass(frozen=True)
class Segment:
    file_offset: int
    memory_offset: int
    size: int
    stored_size: int
    codec: str


@dataclass(frozen=True)
class Module:
    name: str
    build_id: str
    base: int
    mapped_size: int
    bss_size: int
    sha256: str
    segments: list


def inspect_nso(name, payload, base):
    if type(base) is not int or not 0 <= base < ADDRESS_LIMIT or base % 4096:
        raise ArchiveError(f"{name}: invalid module base")
    if len(payload) < 256 or payload[:4] != b"NSO0":
        raise ArchiveError(f"{name}: expected an NSO executable module")
    version, _, flags = struct.unpack_from("<III", payload, 4)
    if version != 0:
        raise ArchiveError(f"{name}: unsupported NSO version {version}")
    segments = []
    ranges = []
    for number in range(3):
        offset, memory, size = struct.unpack_from("<III", payload, 16 + 16 * number)
        compressed = bool(flags & (1 << number))
        stored = struct.unpack_from("<I", payload, 96 + number * 4)[0] if compressed else size
        if size > MAX_MODULE_SIZE or memory + size > MAX_MODULE_SIZE:
            raise ArchiveError(f"{name}: oversized module segment")
        if size and (offset < 256 or offset + stored > len(payload) or stored == 0):
            raise ArchiveError(f"{name}: segment exceeds module data")
        codec = ("zbic" if flags & 128 else "lz4") if compressed else "stored"
        segments.append(Segment(offset, memory, size, stored, codec))
        if size:
            for start, end in ranges:
                if memory < end and memory + size > start:
                    raise ArchiveError(f"{name}: overlapping module memory segments")
            ranges.append((memory, memory + size))
    bss = struct.unpack_from("<I", payload, 60)[0]
    mapped = max((segment.memory_offset + segment.size for segment in segments), default=0)
    mapped = max(mapped, segments[2].memory_offset + segments[2].size + bss)
    if mapped > MAX_MODULE_SIZE:
        raise ArchiveError(f"{name}: module mapping exceeds limit")
    mapped = (mapped + 4095) // 4096 * 4096
    if base + mapped > ADDRESS_LIMIT:
        raise ArchiveError("Module layout exceeds the guest address space")
    return Module(name, payload[64:96].hex(), base, mapped, bss,
                  hashlib.sha256(payload).hexdigest(), [asdict(segment) for segment in segments])


def capabilities():
    return {"nup_reader": True, "verified_extraction": True, "package_selection": True,
            "nso_metadata": True, "module_layout": True, "nso_segment_decoding": True,
            "module_linking": False, "arm64_translation": False, "switch_host": False,
            "vulkan_renderer": False, "shader_translation": False, "native_game_link": False}


def _read_module(archive, member):
    if member.length > MAX_MODULE_SIZE:
        raise ArchiveError("Executable module exceeds the preparation size limit")
    return b"".join(archive.chunks(member))


def prepare_game(filename, notify, workspace=ROOT):
    workspace = workspace.resolve()
    local = workspace / "local"
    local.mkdir(exist_ok=True)
    lock = local / "build.lock"
    try:
        owner = lock.open("x", encoding="utf-8")
    except FileExistsError:
        raise ValueError("Er loopt al een build of controle.") from None
    try:
        with owner:
            owner.write(str(os.getpid()))
            owner.flush()
            archive = Archive(filename)
            candidates = [package for package in archive.packages
                          if (package.title == TITLE and package.kind == 0) or
                          (package.title == TITLE + 0x800 and package.kind == 1)]
            if not any(package.kind == 0 for package in candidates):
                raise ArchiveError("The archive does not contain the expected base game")
            candidates.sort(key=lambda package: (package.kind == 1, package.version), reverse=True)
            sources = [(package, dict(archive.tree(package.exefs))) for package in candidates]
            selected, base = [], FIRST_ADDRESS
            for name in ["main.npdm", "rtld", *MODULE_ORDER]:
                for package, entries in sources:
                    member = entries.get(Path(name))
                    if member is None:
                        continue
                    # Updates may contain placeholders. Only a full executable or
                    # process descriptor is selected; verify the entire member.
                    payload = _read_module(archive, member)
                    magic = b"META" if name.endswith(".npdm") else b"NSO0"
                    if len(payload) < 256 or payload[:4] != magic:
                        continue
                    metadata = None
                    if name in MODULE_ORDER:
                        metadata = inspect_nso(name, payload, base)
                        base = (base + metadata.mapped_size + MODULE_ALIGNMENT - 1) // MODULE_ALIGNMENT * MODULE_ALIGNMENT
                    selected.append((name, payload, package, metadata))
                    notify("progress", {"stage": "module", "name": name,
                                        "package": f"{package.title:016X}", "version": package.version})
                    break
            absent = {"main.npdm", "main", "sdk"} - {name for name, *_ in selected}
            if absent:
                raise ArchiveError("Required modules missing: " + ", ".join(sorted(absent)))
            # The chosen RomFS is a complete package tree. A sparse update needs
            # explicit composition; do not silently invent file-deletion behavior.
            romfs_package = None
            romfs_files = 0
            for package in candidates:
                count = sum(1 for _ in archive.tree(package.romfs))
                if count:
                    romfs_package, romfs_files = package, count
                    break
            if romfs_package is None:
                raise ArchiveError("No RomFS tree found")
            modules = [asdict(metadata) for *_, metadata in selected if metadata is not None]
            identity = hashlib.sha256((archive.index_sha256 + json.dumps(modules, sort_keys=True) +
                                       json.dumps(capabilities(), sort_keys=True)).encode()).hexdigest()[:20]
            build = workspace / "build"
            if build.resolve() != build:
                raise ValueError("De buildmap mag geen koppeling zijn.")
            build.mkdir(exist_ok=True)
            destination = build / f"prepared-{identity}"
            # Build preparation is immutable and content-addressed. A previous
            # completed plan can be reused only after all bytes verify again.
            plan = {"schema": 1, "status": "prepared-not-playable", "modules": modules,
                    "container_index_sha256": archive.index_sha256,
                    "inputs": [{"name": name, "sha256": hashlib.sha256(payload).hexdigest(),
                                "package": f"{package.title:016X}", "version": package.version}
                               for name, payload, package, _ in selected],
                    "romfs": {"package": f"{romfs_package.title:016X}", "version": romfs_package.version,
                              "files": romfs_files, "composition": "requires-validation"},
                    "capabilities": capabilities()}
            encoded = json.dumps(plan, sort_keys=True, indent=2) + "\n"
            if destination.exists():
                if destination.is_symlink() or destination.resolve() != destination:
                    raise ValueError("De voorbereidingsmap mag geen koppeling zijn.")
                manifest = destination / "build-plan.json"
                if not manifest.is_file() or manifest.read_text(encoding="utf-8") != encoded:
                    raise ValueError("Bestaande voorbereiding is onvolledig of wijkt af; geen bestanden overschreven.")
                for name, payload, *_ in selected:
                    existing = destination / "exefs" / name
                    if existing.resolve() != existing or not existing.is_file() or hashlib.sha256(existing.read_bytes()).digest() != hashlib.sha256(payload).digest():
                        raise ValueError("Een voorbereid modulebestand is gewijzigd; geen bestanden overschreven.")
            else:
                destination.mkdir()
                (destination / ".dekuforge-owned").touch()
                exefs = destination / "exefs"
                exefs.mkdir()
                for name, payload, *_ in selected:
                    (exefs / name).write_bytes(payload)
                temporary = destination / "build-plan.tmp"
                temporary.write_text(encoded, encoding="utf-8")
                temporary.replace(destination / "build-plan.json")
            missing = [name for name, ready in capabilities().items() if not ready]
            notify("checked", "Zelfstandige buildvoorbereiding gereed; nog niet speelbaar. "
                   "Ontbrekend: " + ", ".join(missing))
            return destination
    finally:
        lock.unlink(missing_ok=True)
