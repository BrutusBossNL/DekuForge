"""Verified source staging for the explicitly experimental GPL engine candidate.

This stages licensed source only. It neither installs an application update nor
downloads a game, compiled game code or shader/pipeline cache.
"""
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import stat
import tempfile
from urllib.request import urlopen
import zipfile

from .core import ROOT

MAX_ARCHIVE = 64 * 1024**2
MAX_SOURCE = 64 * 1024**2


def manifest(provider='ocarina'):
    names = {'ocarina':'open_engine_source.json', 'hookshot':'hookshot_source.json'}
    if provider not in names:
        raise ValueError('Unknown experimental engine provider')
    return json.loads(Path(__file__).with_name(names[provider]).read_text(encoding='utf-8'))


def _name(name):
    path = PurePosixPath(name)
    if (not name or path.is_absolute() or '\\' in name or ':' in name or
            any(part in ('', '.', '..') for part in name.split('/'))):
        raise ValueError('Unsafe engine source path')
    return path


def verified_files(data, record):
    """Validate the complete archive before exposing any source to a builder."""
    if len(data) > MAX_ARCHIVE or hashlib.sha256(data).hexdigest() != record['archive_sha256']:
        raise ValueError('Engine archive identity mismatch')
    expected = record['files']
    if not expected or sum(item['size'] for item in expected.values()) > MAX_SOURCE:
        raise ValueError('Invalid engine source manifest')
    files, folded, prefix, total = {}, set(), None, 0
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        if len(archive.infolist()) > len(expected) * 3 + 100:
            raise ValueError('Too many engine archive members')
        for member in archive.infolist():
            path = _name(member.filename.rstrip('/') if member.is_dir() else member.filename)
            mode = member.external_attr >> 16
            if stat.S_ISLNK(mode) or member.flag_bits & 1:
                raise ValueError('Linked or encrypted engine source')
            if prefix is None:
                prefix = path.parts[0]
            if path.parts[0] != prefix:
                raise ValueError('Mixed engine archive roots')
            if member.is_dir():
                continue
            name = '/'.join(path.parts[1:])
            if name not in expected or name.casefold() in folded:
                raise ValueError('Unexpected or duplicate engine source')
            folded.add(name.casefold())
            total += member.file_size
            if total > MAX_SOURCE or member.file_size > expected[name]['size'] * 2 + 2:
                raise ValueError('Engine source exceeds bounded size')
            content = archive.read(member)
            # These are the pinned repository's explicit checkout EOL attributes.
            if Path(name).suffix.lower() in ('.ps1', '.bat', '.cmd'):
                content = content.replace(b'\r\n', b'\n')
            header = b'blob ' + str(len(content)).encode('ascii') + b'\0'
            if (len(content) != expected[name]['size'] or
                    hashlib.sha1(header + content).hexdigest() != expected[name]['sha1']):
                raise ValueError('Engine source blob mismatch: ' + name)
            files[name] = content
    if files.keys() != expected.keys():
        raise ValueError('Incomplete engine source archive')
    return files


def verify_tree(target, record):
    """Check original source blobs without rejecting local compiler outputs."""
    target = Path(target).absolute()
    if target.resolve() != target or not target.is_dir():
        raise ValueError('Engine source directory must be a regular owned directory')
    for name, item in record['files'].items():
        path = target.joinpath(*_name(name).parts)
        if not path.resolve().is_relative_to(target) or path.is_symlink():
            raise ValueError('Engine source contains a link')
        if path.stat().st_size != item['size']:
            raise ValueError('Engine source changed: '+name)
        content = path.read_bytes()
        if hashlib.sha1(b'blob '+str(len(content)).encode('ascii')+b'\0'+content).hexdigest() != item['sha1']:
            raise ValueError('Engine source changed: '+name)
    return target


def stage(root=ROOT, notify=lambda message: None, provider='ocarina'):
    """Populate a new owned source directory; never overwrite a previous tree."""
    root = Path(root).resolve()
    record = manifest(provider)
    target = root / 'build' / ('open-engine-source-' + record['revision'])
    if provider == 'hookshot' and not target.exists():
        target = root / 'build' / ('hs-' + record['revision'][:12])
    cache = root / 'local/build-tools' / ('open-engine-' + record['revision'] + '.zip')
    marker = target / '.dekuforge-open-engine-source.json'
    for path in (target, cache):
        if not path.resolve().is_relative_to(root):
            raise ValueError('Engine staging path escapes workspace')
    if target.exists():
        if target.is_symlink() or not marker.is_file():
            raise ValueError('Engine source directory is not owned')
        identity = json.loads(marker.read_text(encoding='utf-8'))
        if identity != {key: record[key] for key in ('revision', 'archive_sha256')}:
            raise ValueError('Engine source marker mismatch')
        return verify_tree(target, record)
    cache.parent.mkdir(parents=True, exist_ok=True)
    if not cache.is_file():
        notify('Downloading pinned GPL engine source')
        with urlopen(record['url'], timeout=60) as response:
            data = response.read(MAX_ARCHIVE+1)
        files = verified_files(data, record)
        # Only persist a fully verified archive; no interrupted cache is reused.
        with tempfile.NamedTemporaryFile(dir=cache.parent, delete=False) as temporary:
            temporary.write(data)
            temporary_path = Path(temporary.name)
        temporary_path.replace(cache)
    else:
        if cache.stat().st_size > MAX_ARCHIVE:
            raise ValueError('Engine archive cache exceeds bounded size')
        files = verified_files(cache.read_bytes(), record)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=target.parent, prefix='s-') as folder:
        staging = Path(folder)
        for name, content in files.items():
            path = staging.joinpath(*_name(name).parts)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        (staging/marker.name).write_text(json.dumps({key: record[key] for key in ('revision', 'archive_sha256')}),
                                        encoding='utf-8')
        staging.replace(target)
    return target
