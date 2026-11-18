"""Bounded save-only import/export with retained rollback directories."""
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
import os
import json
import re
import shutil
import tempfile
import uuid
import zipfile

LIMIT = 128 * 1024 * 1024


def profile_summary(folder, require_progress=True):
    files = save_files(folder, require_progress=require_progress)
    progress = [file for file, name in files if name.endswith('/progress.sav')]
    return {"folder": str(Path(folder).absolute()), "slots": [file.parent.name for file in progress],
            "modified": max((file.stat().st_mtime for file in progress), default=0),
            "files": len(files), "bytes": sum(file.stat().st_size for file, _ in files)}


def game_save_profiles(executable):
    """Only inspect committed user profiles of the selected owned game."""
    if not executable or not Path(executable).is_file():
        return []
    game = Path(executable).absolute().parent
    if (game / '.dekuforge-stable-build').is_file():
        folder = game / 'profile/save'
    elif (game / '.dekuforge-native').is_file():
        try:
            info = json.loads((game/'dekuforge-build-info.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return []
        if info.get('save_layout') != 'user/save':
            return []
        folder = game/'user/save'
    elif (game/'.dekuforge-runtime.json').is_file():
        from .open_engine_runtime import launch_options
        try:
            options = launch_options(Path(executable).absolute())
            folder = Path(options['args'][-1])/'save'
        except (OSError, ValueError, TypeError):
            return []
    else:
        return []
    if folder.resolve() != folder or not folder.is_dir():
        return []
    result = []
    try:
        with os.scandir(folder) as entries:
            children = []
            for entry in entries:
                children.append(Path(entry.path))
                if len(children) >= 128:
                    break
    except OSError:
        return []
    for child in sorted(children):
        if re.fullmatch(r'[0-9a-fA-F]{32}', child.name) and not is_link(child) and child.is_dir():
            try:
                result.append(profile_summary(child, require_progress=False))
            except (OSError, ValueError):
                continue
        if len(result) >= 32:
            break
    return result


def discover_saves(folder, max_entries=6000, max_depth=7):
    """Bounded, read-only search; never follow links or inspect game assets."""
    folder = Path(folder).absolute()
    if folder.resolve() != folder or not folder.is_dir():
        raise ValueError('save_search_folder')
    skip = {'romfs', 'exefs', 'build-cache', 'shader-cache', 'generated', 'python',
            'pydeps', 'toolchain', 'node_modules', '.git', 'save-backup', 'save-tx', 'cache'}
    pending, profiles, visited, limited = [(folder, 0)], [], 0, False
    while pending:
        current, depth = pending.pop()
        if any((current / f'slot_0{i}/progress.sav').is_file() for i in range(6)):
            try:
                profiles.append(profile_summary(current))
            except (OSError, ValueError):
                pass
            if len(profiles) >= 32:
                limited = True
                break
            continue
        if depth >= max_depth:
            limited = True
            continue
        try:
            children = []
            with os.scandir(current) as entries:
                for entry in entries:
                    visited += 1
                    if visited > max_entries:
                        limited = True
                        pending.clear()
                        break
                    path = Path(entry.path)
                    if (entry.is_dir(follow_symlinks=False) and not is_link(path)
                            and entry.name.lower() not in skip and '.backup-' not in entry.name.lower()):
                        children.append(path)
            if visited <= max_entries:
                # Visit the normal installed-game route before unrelated source trees.
                children.sort(key=lambda path: (path.name.lower() in {'play', 'profile', 'save'}, path.name.casefold()))
                pending.extend((path, depth+1) for path in children)
        except OSError:
            continue
    profiles.sort(key=lambda item: (-item['modified'], item['folder'].casefold()))
    return {"profiles": profiles, "limited": limited}


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
