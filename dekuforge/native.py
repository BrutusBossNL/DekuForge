"""DekuForge's own archive inspection and verified extraction stages."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil

from .core import ROOT
from .nup import Archive, ArchiveError


def prepare_archive(filename, notify, extract=False, workspace=ROOT):
    workspace = workspace.resolve()
    local = workspace / "local"
    local.mkdir(exist_ok=True)
    lock = local / "build.lock"
    try:
        handle = lock.open("x", encoding="utf-8")
    except FileExistsError:
        raise ValueError("Er loopt al een build of archiefcontrole.") from None
    try:
        with handle:
            handle.write(str(os.getpid()))
            handle.flush()
            notify("log", "DekuForge NUP-lezer: geen externe builder nodig.\n")
            archive = Archive(filename)
            summary = archive.summary()
            for package in archive.packages:
                # Walk all entries before any extraction so cycles, collisions
                # and unsafe names cannot cause a partially planned installation.
                for _ in archive.tree(package.root):
                    pass
            notify("log", f"{len(archive.packages)} pakketten, {summary['files']} bestanden, "
                   f"{summary['expanded_bytes'] / 1024 ** 3:.1f} GiB uitgepakt.\n")
            if not extract:
                notify("checked", "NUP-index, checksum en mappenstructuur gecontroleerd door DekuForge. "
                       "Payloads en uitvoerbare gameversie zijn nog niet gecontroleerd.")
                return summary
            if shutil.disk_usage(workspace).free < summary["expanded_bytes"] + 2 * 1024 ** 3:
                raise ValueError("Te weinig vrije ruimte voor volledige extractie plus 2 GiB reserve.")
            build = workspace / "build"
            if build.resolve() != build:
                raise ValueError("De buildmap mag niet naar een andere locatie verwijzen.")
            build.mkdir(exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            destination = build / f"extracted-{stamp}"
            destination.mkdir()
            (destination / ".dekuforge-owned").touch()
            completed = 0
            for number, package in enumerate(archive.packages):
                package_root = destination / f"{number:02d}-{package.title:016X}-{package.version}"
                for relative, member in archive.tree(package.root):
                    target = package_root / relative
                    if not target.resolve().is_relative_to(destination):
                        raise ArchiveError("Extraction destination escaped its workspace")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    # Exclusive creation and a fresh directory prevent accidental
                    # replacement of user files. Failure leaves an identifiable
                    # partial output, with no finished manifest.
                    with target.open("xb") as stream:
                        for block in archive.chunks(member):
                            stream.write(block)
                    completed += 1
                    if completed % 500 == 0:
                        notify("progress", {"stage": "extract", "files": completed, "total": summary["files"]})
            (destination / "dekuforge-manifest.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
            notify("checked", f"Extractie en SHA-256-controle voltooid: {destination}. "
                   "Dit zijn bronbestanden, nog geen speelbare gamebuild.")
            return destination
    finally:
        lock.unlink(missing_ok=True)
