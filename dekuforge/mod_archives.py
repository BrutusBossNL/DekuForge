"""Original bounded mod import. Never execute files supplied by a mod."""
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import struct
import subprocess
import zipfile

MAX_FILES = 50000
MAX_BYTES = 8 * 1024**3
MAX_FILE = 2 * 1024**3
ARCHIVES = {'.zip', '.7z', '.rar'}


def regular(path):
    return not path.is_symlink() and not getattr(path, 'is_junction', lambda: False)() and path.resolve() == path.absolute()


def relative_name(name):
    if not isinstance(name, str) or '\\' in name or any(ord(c) < 32 for c in name):
        raise ValueError('mods_unsafe_archive')
    path = PurePosixPath(name)
    parts = name.rstrip('/').split('/')
    reserved = {'con', 'prn', 'aux', 'nul', *('com'+str(i) for i in range(1,10)), *('lpt'+str(i) for i in range(1,10))}
    if (path.is_absolute() or not parts or len(parts) > 32 or
            any(not part or part in {'.', '..'} or part.endswith((' ', '.')) or
                any(c in part for c in ':<>"|?*') or part.split('.')[0].casefold() in reserved for part in parts)):
        raise ValueError('mods_unsafe_archive')
    return Path(*parts)


def tree_files(directory):
    directory = Path(directory).absolute()
    if not regular(directory) or not directory.is_dir():
        raise ValueError('mods_unsafe_archive')
    pending, files, total, visited = [(directory, 0)], [], 0, 0
    while pending:
        parent, depth = pending.pop()
        with os.scandir(parent) as entries:
            for entry in entries:
                visited += 1
                if visited > MAX_FILES:
                    raise ValueError('mods_import_limit')
                path = Path(entry.path)
                relative_name(path.relative_to(directory).as_posix())
                if not regular(path):
                    raise ValueError('mods_unsafe_archive')
                if entry.is_dir(follow_symlinks=False):
                    if depth >= 31:
                        raise ValueError('mods_unsafe_archive')
                    pending.append((path, depth + 1))
                elif entry.is_file(follow_symlinks=False):
                    size = entry.stat(follow_symlinks=False).st_size
                    total += size
                    if len(files) >= MAX_FILES or size > MAX_FILE or total > MAX_BYTES:
                        raise ValueError('mods_import_limit')
                    files.append((path, path.relative_to(directory), size))
                else:
                    raise ValueError('mods_unsafe_archive')
    check_names([(relative, size, False) for _, relative, size in files])
    return files


def check_names(entries):
    seen, files, total = set(), set(), 0
    if len(entries) > MAX_FILES:
        raise ValueError('mods_import_limit')
    for relative, size, directory in entries:
        name = relative_name(relative.as_posix()).as_posix().casefold()
        if name in seen:
            raise ValueError('mods_unsafe_archive')
        seen.add(name)
        if not directory:
            files.add(name)
            total += size
            if size < 0 or size > MAX_FILE or total > MAX_BYTES:
                raise ValueError('mods_import_limit')
    for name in seen:
        if any(parent.as_posix() in files for parent in PurePosixPath(name).parents if str(parent) != '.'):
            raise ValueError('mods_unsafe_archive')
    return total


def validate_library(directory):
    """Validate each mod independently before copying an entire library."""
    count = 0
    for path in Path(directory).iterdir():
        count += 1
        if count > MAX_FILES or not regular(path):
            raise ValueError('mods_unsafe_archive')
        if path.is_dir():
            tree_files(path)
        elif not path.is_file() or path.stat().st_size > MAX_BYTES:
            raise ValueError('mods_import_limit')


def seven_zip():
    candidates = [shutil.which('7z'), shutil.which('7zz')]
    if os.name == 'nt':
        candidates += [str(Path(os.environ.get('ProgramFiles', r'C:\Program Files')) / '7-Zip/7z.exe')]
    return next((str(Path(p).resolve()) for p in candidates if p and Path(p).is_file()), None)


def _seven_entries(source, tool):
    # Listing is bounded on disk before it is parsed; paths and links are checked
    # before the external extractor ever receives a destination directory.
    import tempfile
    with tempfile.TemporaryFile() as listing:
        result = subprocess.run([tool, 'l', '-slt', '-ba', '-sccUTF-8', '--', str(source)],
                                stdout=listing, stderr=subprocess.DEVNULL, timeout=90,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if result.returncode or listing.tell() > 16 * 1024**2:
            raise ValueError('mods_unsafe_archive')
        listing.seek(0)
        text = listing.read().decode('utf-8-sig')
    entries = []
    for block in text.replace('\r\n', '\n').split('\n\n'):
        fields = dict(line.split(' = ', 1) for line in block.splitlines() if ' = ' in line)
        if 'Path' not in fields:
            continue
        if any('link' in key.casefold() and value for key, value in fields.items()):
            raise ValueError('mods_unsafe_archive')
        attributes = fields.get('Attributes', '')
        if 'l' in attributes or fields.get('Encrypted') == '+':
            raise ValueError('mods_unsafe_archive')
        name = fields['Path'].replace('\\', '/')
        directory = fields.get('Folder') == '+' or 'D' in attributes
        entries.append((relative_name(name), int(fields.get('Size', '0')), directory))
    check_names(entries)
    return entries


def _zip_directory_bounds(source):
    # Check ZIP/ZIP64 footer counts before ZipFile allocates its member objects.
    with source.open('rb') as stream:
        stream.seek(0, 2)
        length = stream.tell()
        tail_size = min(length, 65557)
        stream.seek(length - tail_size)
        tail = stream.read(tail_size)
        offset = tail.rfind(b'PK\x05\x06')
        if offset < 0 or offset + 22 > len(tail):
            raise ValueError('mods_unsafe_archive')
        fields = struct.unpack_from('<4s4H2LH', tail, offset)
        if fields[1] or fields[2]:
            raise ValueError('mods_unsafe_archive')
        count, directory_size = fields[4], fields[5]
        if count == 65535 or directory_size == 0xffffffff or fields[6] == 0xffffffff:
            end = length - tail_size + offset
            if end < 20:
                raise ValueError('mods_unsafe_archive')
            stream.seek(end - 20)
            locator = struct.unpack('<4sLQL', stream.read(20))
            if locator[0] != b'PK\x06\x07' or locator[1] or locator[3] != 1 or locator[2] > end - 56:
                raise ValueError('mods_unsafe_archive')
            stream.seek(locator[2])
            data = stream.read(56)
            if len(data) != 56:
                raise ValueError('mods_unsafe_archive')
            large = struct.unpack('<4sQ2H2L4Q', data)
            if large[0] != b'PK\x06\x06' or large[4] or large[5]:
                raise ValueError('mods_unsafe_archive')
            count, directory_size = large[7], large[8]
        if count > MAX_FILES or directory_size > 64 * 1024**2:
            raise ValueError('mods_import_limit')


def extract_archive(source, target):
    """Extract only into a new, private staging directory; originals remain intact."""
    source, target = Path(source).absolute(), Path(target).absolute()
    if not regular(source) or not source.is_file() or source.stat().st_size > MAX_BYTES:
        raise ValueError('mods_unsafe_archive')
    if not regular(target) or not target.is_dir() or any(target.iterdir()):
        raise ValueError('mods_unsafe_archive')
    if source.suffix.casefold() == '.zip':
        _zip_directory_bounds(source)
        with zipfile.ZipFile(source) as archive:
            members = archive.infolist()
            entries = []
            for item in members:
                mode = item.external_attr >> 16
                if (item.flag_bits & 1 or stat.S_ISLNK(mode) or
                        stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR)):
                    raise ValueError('mods_unsafe_archive')
                entries.append((relative_name(item.orig_filename), item.file_size, item.is_dir()))
            required = check_names(entries)
            if shutil.disk_usage(target).free < required + 64 * 1024**2:
                raise ValueError('mods_disk_space')
            for item, (relative, size, directory) in zip(members, entries):
                path = target / relative
                if directory:
                    path.mkdir(parents=True, exist_ok=True)
                    continue
                path.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(item) as stream, path.open('xb') as output:
                    remaining = size
                    while remaining:
                        chunk = stream.read(min(1024**2, remaining))
                        if not chunk:
                            raise ValueError('mods_unsafe_archive')
                        output.write(chunk)
                        remaining -= len(chunk)
                    if stream.read(1):
                        raise ValueError('mods_import_limit')
    elif source.suffix.casefold() in {'.7z', '.rar'}:
        tool = seven_zip()
        if not tool:
            raise ValueError('mods_need_7zip')
        entries = _seven_entries(source, tool)
        required = check_names(entries)
        if shutil.disk_usage(target).free < required + 64 * 1024**2:
            raise ValueError('mods_disk_space')
        result = subprocess.run([tool, 'x', '-y', '-bd', '-bso0', '-bse0', '-spd', '-o'+str(target), '--', str(source)],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=600,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if result.returncode:
            raise ValueError('mods_unsafe_archive')
        actual = {rel.as_posix().casefold(): size for _, rel, size in tree_files(target)}
        expected = {rel.as_posix().casefold(): size for rel, size, directory in entries if not directory}
        if actual != expected:
            raise ValueError('mods_unsafe_archive')
    else:
        raise ValueError('mods_archive_type')
