"""Verified, resumable NUP-to-directory extraction for a direct-file runtime.

The archive is read only. A partial output is never advertised as complete, and
existing files are hashed before reuse. Metadata stays outside the game tree.
"""
import hashlib
from contextlib import contextmanager
import json
from pathlib import Path
import shutil
import uuid

from .nup import Archive, ArchiveError
from .romfs import safe_path, select_snapshot

RESERVE = 2 * 1024**3


@contextmanager
def _lock(path):
    with path.open('x', encoding='utf-8'):
        pass
    try:
        yield
    finally:
        path.unlink()


def _regular(path):
    if path.resolve() != path or path.is_symlink() or getattr(path, 'is_junction', lambda: False)():
        raise ValueError('Extraction paths cannot contain links')


def _write_json(path, value):
    temporary = path.with_suffix('.tmp')
    _regular(temporary)
    temporary.write_text(json.dumps(value, indent=2)+'\n', encoding='utf-8')
    temporary.replace(path)


def extract_directory(filename, output, notify=lambda *_: None):
    archive = Archive(filename)
    package, entries = select_snapshot(archive)
    aliases, total = {}, 0
    for relative, member in entries:
        name = relative.as_posix()
        safe_path(name)
        for prefix in (Path(*relative.parts[:n]).as_posix() for n in range(1, len(relative.parts)+1)):
            previous = aliases.setdefault(prefix.casefold(), prefix)
            if previous != prefix:
                raise ArchiveError('Case-colliding RomFS paths')
        total += member.length
    identity = {'schema': 1, 'archive_index_sha256': archive.index_sha256,
                'archive_size': archive.size, 'title': package.title,
                'version': package.version, 'files': len(entries), 'bytes': total}
    output = Path(output).expanduser().absolute()
    _regular(output)
    marker = output / '.dekuforge-directory.json'
    if output.exists() and any(output.iterdir()):
        _regular(marker)
        if not marker.is_file() or json.loads(marker.read_text(encoding='utf-8')) != identity:
            raise ValueError('Extraction directory is unowned or belongs to another input')
    else:
        output.mkdir(parents=True, exist_ok=True)
        _write_json(marker, identity)
    lock = output / '.extract.lock'
    _regular(lock)
    with _lock(lock):
        tree = output / 'romfs'
        _regular(tree)
        tree.mkdir(exist_ok=True)
        completion = output / 'complete.json'
        _regular(completion)
        completion.unlink(missing_ok=True)
        done = 0
        with archive.path.open('rb') as stream:
            for index, (relative, member) in enumerate(entries):
                target = tree / relative
                _regular(target)
                for parent in reversed(target.parents):
                    if parent.is_relative_to(tree):
                        _regular(parent)
                        parent.mkdir(exist_ok=True)
                reusable = False
                if target.is_file() and target.stat().st_size == member.length:
                    with target.open('rb') as existing:
                        reusable = hashlib.file_digest(existing, 'sha256').digest() == member.digest
                if not reusable:
                    if shutil.disk_usage(output).free < member.length + RESERVE:
                        raise OSError('Insufficient free space for the next game file and reserve')
                    temporary = output / ('.extract-' + uuid.uuid4().hex + '.part')
                    try:
                        with temporary.open('xb') as destination:
                            for block in archive.chunks(member, stream=stream):
                                destination.write(block)
                        temporary.replace(target)
                    finally:
                        temporary.unlink(missing_ok=True)
                done += member.length
                if index % 64 == 0 or index + 1 == len(entries):
                    notify('progress', {'stage': 'romfs', 'current': done, 'total': total,
                                        'files': index+1, 'file_count': len(entries)})
        _write_json(completion, identity)
        return tree
