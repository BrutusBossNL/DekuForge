"""Bounded save-only import/export with retained rollback directories."""
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
import uuid
import zipfile

LIMIT = 128 * 1024 * 1024


def is_link(path):
    return path.is_symlink() or getattr(path, "is_junction", lambda: False)()


def save_files(folder, require_progress=True):
    folder = Path(folder)
    if not folder.is_dir():
        raise ValueError("Select an existing user save folder")
    if is_link(folder):
        raise ValueError("Save folders must not be links")
    result, total = [], 0
    for file in folder.rglob("*"):
        if is_link(file):
            raise ValueError("Save folders must not contain links")
        if not file.is_file():
            continue
        relative = file.relative_to(folder).as_posix()
        if not re.fullmatch(r"(?:account|option)\.sav|slot_0[0-5]/[A-Za-z0-9_-]+\.sav", relative):
            raise ValueError("Select the user save folder containing slot_00, not the installation folder")
        total += file.stat().st_size
        if total > LIMIT or len(result) >= 256:
            raise ValueError("Save data exceeds the import limit")
        result.append((file, relative))
    if require_progress and not any(name.endswith("/progress.sav") for _, name in result):
        raise ValueError("No supported progress.sav found")
    return result


def export_save(folder, archive):
    files = save_files(folder)
    archive = Path(archive)
    if archive.resolve().is_relative_to(Path(folder).resolve()):
        raise ValueError("Export outside the current save folder")
    temporary = archive.with_name(archive.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as output:
            for file, name in files:
                output.write(file, name)
        temporary.replace(archive)
    finally:
        temporary.unlink(missing_ok=True)


def import_save(source, destination):
    destination = Path(destination).absolute()
    save_files(destination, require_progress=False)  # Existing profile may not have been played yet.
    with tempfile.TemporaryDirectory(prefix="dekuforge-save-") as temporary:
        source = Path(source)
        if source.resolve().is_relative_to(destination.resolve()) or destination.resolve().is_relative_to(source.resolve()):
            raise ValueError("Import from a separate save folder or ZIP")
        if source.is_file():
            extracted = Path(temporary)
            with zipfile.ZipFile(source) as archive:
                members = archive.infolist()
                if len(members) > 300 or sum(i.file_size for i in members) > LIMIT:
                    raise ValueError("Save archive exceeds the import limit")
                seen = set()
                for item in members:
                    path = PurePosixPath(item.filename)
                    if (path.is_absolute() or ".." in path.parts or "\\" in item.filename
                            or ":" in item.filename or (item.external_attr >> 16) & 0o170000 == 0o120000):
                        raise ValueError("Unsafe save archive path")
                    if item.is_dir():
                        continue
                    if item.filename.casefold() in seen:
                        raise ValueError("Duplicate save archive path")
                    seen.add(item.filename.casefold())
                    target = extracted.joinpath(*path.parts)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(item) as reader, target.open("wb") as writer:
                        shutil.copyfileobj(reader, writer)
            source = extracted
        files = save_files(source)
        # Inherit the profile directory's Windows ACL. mkdtemp uses an owner-only
        # ACL, which can make the installed save unreadable to the game process.
        stage = destination.parent / (".dekuforge-import-" + uuid.uuid4().hex)
        stage.mkdir()
        try:
            # Preserve slots absent from the import.
            for file, name in save_files(destination, require_progress=False):
                target = stage / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file, target)
            for file, name in files:
                target = stage / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file, target)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            backup = destination.with_name(destination.name + ".backup-" + stamp + "-" + uuid.uuid4().hex[:8])
            destination.rename(backup)
            try:
                stage.rename(destination)
            except OSError:
                backup.rename(destination)
                raise
            return backup
        finally:
            if stage.exists():
                shutil.rmtree(stage)
