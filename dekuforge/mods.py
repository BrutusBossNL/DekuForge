"""Original DekuForge mod library and adapter to the game's configuration interface.

No upstream launcher implementation is imported. Mod payloads stay local.
"""
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile

from .mod_archives import ARCHIVES, regular, tree_files, extract_archive, relative_name
from .update_package import atomic_json
from . import COMPONENTS

TITLE = '0400486024dec000'
PARTS = ('romfs', 'romfslite', 'exefs', 'cheats')
MAX_MODS = 256


def digest(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def fnv(data):
    value = 2166136261
    for byte in data:
        value = ((value ^ byte) * 16777619) & 0xffffffff
    return f'{value:08X}'


def _small_record(path):
    if not path.exists():
        return {}
    if not regular(path) or not path.is_file() or path.stat().st_size > 8 * 1024**2:
        raise ValueError('mods_unsafe_archive')
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as error:
        raise ValueError('mods_unsafe_archive') from error
    if not isinstance(value, dict):
        raise ValueError('mods_unsafe_archive')
    return value


def _config(path):
    if not path.exists():
        return '', {}
    if not regular(path) or path.stat().st_size > 512 * 1024:
        raise ValueError('mods_unsafe_archive')
    text = path.read_text(encoding='utf-8-sig')
    values = {}
    for line in text.splitlines():
        match = re.match(r'\s*(?:NX2NAVI_)?(MODS_(?:DIR|ORDER|DISABLED|REBUILD))\s*=\s*(.*?)\s*$', line, re.I)
        if match:
            values[match[1].upper()] = match[2].strip('"')
    return text, values


def _parts(folder):
    """Recognize wrappers plus documented emulator/Atmosphere directory layouts."""
    candidates, pending = {}, [(folder, 0)]
    while pending:
        base, depth = pending.pop(0)
        found = {}
        for form in (base, base/'atmosphere/contents'/TITLE, base/'contents'/TITLE, base/TITLE):
            if not form.is_dir() and form.parent.is_dir():
                form = next((p for p in form.parent.iterdir() if p.name.casefold() == form.name.casefold()), form)
            for part in PARTS:
                path = form / part
                if path.is_dir():
                    found.setdefault('romfs' if part == 'romfslite' else part, path)
        patches = base / 'atmosphere/exefs_patches'
        if patches.is_dir():
            found['atmosphere/exefs_patches'] = patches
        if found:
            candidates[tuple(sorted(str(p) for p in found.values()))] = found
        if base.name.casefold() in PARTS and base == folder:
            candidates[(str(base),)] = {'romfs' if base.name.casefold() == 'romfslite' else base.name.casefold(): base}
        if depth < 2:
            for child in base.iterdir():
                if child.is_dir() and child.name.casefold() not in {*PARTS, 'atmosphere', 'contents', TITLE, 'metadata'}:
                    if not regular(child):
                        raise ValueError('mods_unsafe_archive')
                    pending.append((child, depth + 1))
    if len(candidates) != 1:
        raise ValueError('mods_layout')
    return next(iter(candidates.values()))


@dataclass
class Mod:
    name: str
    enabled: bool
    folder: Path
    description: str = ''
    romfs: dict = field(default_factory=dict)
    code: dict = field(default_factory=dict)
    problem: str = ''
    needs_layout: bool = False
    parts: dict = field(default_factory=dict)
    conflicts: list = field(default_factory=list)
    conflict_peers: dict = field(default_factory=dict)


class ModLibrary:
    def __init__(self, executable, running=None):
        self.executable = Path(executable).absolute()
        if not executable or not regular(self.executable) or not self.executable.is_file():
            raise ValueError('mods_no_game')
        self.game = self.executable.parent
        self.ini = self.game / ('dekuforge-mods.ini' if (self.game/'.dekuforge-runtime.json').is_file() else 'nx2navi.ini')
        _, config = _config(self.ini)
        configured = Path(config.get('MODS_DIR') or 'mods')
        self.folder = (configured if configured.is_absolute() else self.game / configured).absolute()
        protected = {'profile', 'user', 'romfs', 'exefs', 'build-cache', 'shader-cache', '.git', 'local', 'python', '.dfmods'}
        if (not self.folder.is_relative_to(self.game) or self.folder == self.game or not regular(self.folder)
                or self.folder.relative_to(self.game).parts[0].casefold() in protected):
            raise ValueError('mods_external_dir')
        if self.folder.exists() and not self.folder.is_dir():
            raise ValueError('mods_unsafe_archive')
        if running is None:
            from .game_updates import game_running
            running = game_running
        self.running = running

    def _closed(self):
        if self.running():
            raise ValueError('mods_close_game')

    def scan(self):
        _, config = _config(self.ini)
        build_id = ''
        main = self.game/'exefs/main'
        if main.is_file() and regular(main):
            with main.open('rb') as source:
                header = source.read(96)
            if len(header) == 96 and header[:4] == b'NSO0':
                build_id = header[64:96].hex()
        order = config.get('MODS_ORDER', '').split('|')
        disabled = set(config.get('MODS_DISABLED', '').split('|'))
        if not self.folder.exists():
            return []
        folders = [p for p in self.folder.iterdir() if p.is_dir()]
        if len(folders) > MAX_MODS:
            raise ValueError('mods_import_limit')
        folders.sort(key=lambda p: (order.index(p.name) if p.name in order else len(order), p.name))
        mods = []
        for folder in folders:
            mod = Mod(folder.name, folder.name not in disabled, folder)
            other_version = False
            try:
                relative_name(folder.name)
                if len(folder.name.encode('utf-8')) > 240:
                    raise ValueError('mods_import_limit')
                files = tree_files(folder)
                mod.parts = _parts(folder)
                mod.needs_layout = any(path != folder / part for part, path in mod.parts.items())
                metadata = folder / 'mod.json'
                if metadata.is_file() and metadata.stat().st_size <= 16384:
                    value = json.loads(metadata.read_text(encoding='utf-8-sig'))
                    mod.description = str(value.get('description', ''))[:1500] if isinstance(value, dict) else ''
                for path, relative, _ in files:
                    for part, root in mod.parts.items():
                        if not path.is_relative_to(root):
                            continue
                        if part == 'romfs':
                            key = path.relative_to(root).as_posix().casefold()
                            mod.romfs[key] = path
                        elif part == 'exefs' and path.suffix.casefold() in {'.ips', '.pchtxt'} or part == 'cheats' and path.suffix.casefold() == '.txt' or part == 'atmosphere/exefs_patches' and path.suffix.casefold() in {'.ips', '.pchtxt'}:
                            if path.stat().st_size > 64 * 1024**2:
                                raise ValueError('mods_import_limit')
                            if part == 'cheats' and not re.fullmatch(r'[0-9a-fA-F]{16,64}', path.stem):
                                continue
                            target_id = ''
                            if part == 'cheats':
                                target_id = path.stem.lower()
                            elif path.suffix.casefold() == '.ips' and re.fullmatch(r'[0-9a-fA-F]{1,64}', path.stem):
                                target_id = path.stem.lower().ljust(64, '0')
                            elif path.suffix.casefold() == '.pchtxt':
                                for line in path.read_text(encoding='utf-8-sig').splitlines():
                                    line = line.split('//', 1)[0].strip()
                                    if line.startswith('@stop'):
                                        break
                                    match = re.fullmatch(r'@nsobid-([0-9a-fA-F]{1,64})', line)
                                    if match:
                                        target_id = match[1].lower().ljust(64, '0')
                            if build_id and target_id and target_id != (build_id[:16] if part == 'cheats' else build_id):
                                other_version = True
                                continue
                            mod.code[folder.name + '/' + relative.as_posix()] = path
                        elif part == 'exefs' and (path.name.casefold() == 'main' or path.name.casefold().startswith('subsdk') or path.suffix.casefold() in {'.nso', '.dll', '.so', '.exe', '.nro', '.elf', '.asi', '.dylib'}):
                            mod.problem = 'mods_plugin'
                if not mod.problem and not mod.romfs and not mod.code:
                    mod.problem = 'mods_other_version' if other_version else 'mods_layout'
            except (ValueError, OSError) as error:
                mod.problem = str(error) if str(error).startswith('mods_') else 'mods_unsafe_archive'
            mods.append(mod)
        owners = {}
        for mod in mods:
            if not mod.enabled or mod.problem:
                continue
            for path in mod.romfs:
                owners.setdefault(path, []).append(mod)
        for path, providers in owners.items():
            if len(providers) > 1:
                for mod in providers:
                    mod.conflicts.append((path, providers[0].name))
                    mod.conflict_peers[path] = [other.name for other in providers if other is not mod]
        return mods

    def _write(self, mods):
        self._closed()
        for mod in mods:
            relative_name(mod.name)
        text, _ = _config(self.ini)
        wanted = {'MODS_DIR': self.folder.relative_to(self.game).as_posix(),
                  'MODS_ORDER': '|'.join(m.name for m in mods),
                  'MODS_DISABLED': '|'.join(m.name for m in mods if not m.enabled),
                  'MODS_REBUILD': 'off'}
        wanted = {key: '"'+value+'"' if value.strip() != value else value for key, value in wanted.items()}
        lines, written = [], set()
        for line in text.splitlines(keepends=True):
            match = re.match(r'\s*(?:NX2NAVI_)?(MODS_(?:DIR|ORDER|DISABLED|REBUILD))\s*=', line, re.I)
            if match:
                key = match[1].upper()
                if key not in written:
                    lines.append(key.lower()+' = '+wanted[key]+'\n')
                    written.add(key)
            else:
                lines.append(line)
        if lines and not lines[-1].endswith('\n'):
            lines[-1] += '\n'
        missing = [key for key in wanted if key not in written]
        if missing:
            lines += ['\n[mods]\n'] + [key.lower()+' = '+wanted[key]+'\n' for key in missing]
        if ''.join(lines) == text:
            return
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=self.game, prefix='.dekuforge-mod-settings-', delete=False) as target:
            temporary = Path(target.name)
            try:
                target.write(''.join(lines))
            except Exception:
                target.close()
                temporary.unlink(missing_ok=True)
                raise
        try:
            temporary.replace(self.ini)
        finally:
            temporary.unlink(missing_ok=True)

    def toggle(self, name):
        mods = self.scan()
        mod = next(m for m in mods if m.name == name)
        if mod.problem and not mod.enabled:
            raise ValueError(mod.problem)
        mod.enabled = not mod.enabled
        self._write(mods)

    def move(self, name, delta):
        if delta not in (-1, 1):
            raise ValueError('mods_layout')
        mods = self.scan()
        index = next(i for i, mod in enumerate(mods) if mod.name == name)
        target = index + delta
        if 0 <= target < len(mods):
            mods[index], mods[target] = mods[target], mods[index]
            self._write(mods)

    def import_mod(self, source):
        self._closed()
        source = Path(source).absolute()
        if not regular(source) or not source.exists():
            raise ValueError('mods_unsafe_archive')
        name = source.stem if source.is_file() else source.name
        if source.is_dir() and name.casefold() in PARTS:
            name = source.parent.name
        relative_name(name)
        if len(name.encode('utf-8')) > 240:
            raise ValueError('mods_import_limit')
        self.folder.mkdir(parents=True, exist_ok=True)
        target = self.folder / name
        if any(p.name.casefold() == name.casefold() for p in self.folder.iterdir() if p.is_dir()):
            raise ValueError('mods_exists')
        if source == self.game or self.game.is_relative_to(source) or source == self.folder or self.folder.is_relative_to(source):
            raise ValueError('mods_unsafe_archive')
        if len(self.scan()) >= MAX_MODS:
            raise ValueError('mods_import_limit')
        with tempfile.TemporaryDirectory(prefix='.dekuforge-mod-', dir=self.game) as temporary:
            stage = Path(temporary)
            raw = stage / 'raw'
            raw.mkdir()
            if source.is_dir():
                inputs = tree_files(source)
                needed = sum(size for _, _, size in inputs)
                if shutil.disk_usage(stage).free < needed + 64 * 1024**2:
                    raise ValueError('mods_disk_space')
                # Selecting a romfs/exefs/cheats folder is accepted directly.
                base = raw / source.name if source.name.casefold() in PARTS else raw
                for path, relative, _ in inputs:
                    destination = base / relative
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(path, destination)
            else:
                extract_archive(source, raw)
            staged_files = tree_files(raw)
            parts = _parts(raw)
            normalized = stage / 'mod'
            normalized.mkdir()
            for part, path in parts.items():
                destination = normalized / part
                destination.parent.mkdir(parents=True, exist_ok=True)
                path.rename(destination)
            metadata = next((path for path in (raw/'mod.json', *[p.parent/'mod.json' for p in parts.values()]) if path.is_file()), None)
            if metadata and regular(metadata) and metadata.stat().st_size <= 16384:
                shutil.copyfile(metadata, normalized/'mod.json')
            for path, relative, _ in staged_files:
                if (not any(path.is_relative_to(part) for part in parts.values()) and path.is_file()
                        and (path.name.casefold().startswith(('readme', 'license', 'copying', 'notice', 'changelog'))
                             or path.suffix.casefold() == '.md')):
                    target_metadata = normalized/'metadata'/relative
                    target_metadata.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(path, target_metadata)
            if source.is_file():
                atomic_json(normalized/'.dekuforge-import.json', {'source_name':source.name, 'archive_sha256':digest(source)})
            tree_files(normalized)
            self._closed()
            normalized.rename(target)
            try:
                # A new import is disabled until the user explicitly turns it on.
                mods = self.scan()
                next(m for m in mods if m.name == name).enabled = False
                self._write(mods)
            except Exception:
                target.rename(normalized)
                raise
        return name

    def prepare(self):
        self._closed()
        self.folder.mkdir(parents=True, exist_ok=True)
        imports_path = self.game / '.dekuforge-mod-imports.json'
        previous = _small_record(imports_path)
        for archive in sorted(self.folder.iterdir()):
            if archive.is_file() and archive.suffix.casefold() in ARCHIVES:
                if not regular(archive):
                    raise ValueError('mods_unsafe_archive')
                if archive.stat().st_size > 8 * 1024**3:
                    raise ValueError('mods_import_limit')
                old = previous.get(archive.name, {})
                if not isinstance(old, dict):
                    raise ValueError('mods_unsafe_archive')
                if old.get('mod'):
                    relative_name(old['mod'])
                    if len(Path(old['mod']).parts) != 1:
                        raise ValueError('mods_unsafe_archive')
                stat = archive.stat()
                if (old.get('size') == stat.st_size and old.get('mtime_ns') == stat.st_mtime_ns
                        and (self.folder/old.get('mod', '')).is_dir()):
                    continue
                fingerprint = digest(archive)
                if old.get('sha256') == fingerprint and (self.folder / old.get('mod', '')).is_dir():
                    old.update(size=stat.st_size, mtime_ns=stat.st_mtime_ns)
                    atomic_json(imports_path, previous)
                    continue
                receipt = self.folder / archive.stem / '.dekuforge-import.json'
                if receipt.is_file() and regular(receipt) and receipt.stat().st_size < 4096:
                    imported = _small_record(receipt)
                    if imported.get('archive_sha256') == fingerprint:
                        previous[archive.name] = {'sha256':fingerprint, 'mod':archive.stem,
                                                 'size':stat.st_size, 'mtime_ns':stat.st_mtime_ns}
                        atomic_json(imports_path, previous)
                        continue
                name = self.import_mod(archive)
                previous[archive.name] = {'sha256': fingerprint, 'mod': name,
                                         'size':stat.st_size, 'mtime_ns':stat.st_mtime_ns}
                atomic_json(imports_path, previous)
        mods = self.scan()
        changed_layout = False
        for mod in mods:
            if mod.needs_layout and not mod.problem:
                moved = []
                try:
                    for part, path in mod.parts.items():
                        target = mod.folder / part
                        if path != target:
                            if target.exists():
                                raise ValueError('mods_layout')
                            target.parent.mkdir(parents=True, exist_ok=True)
                            path.rename(target)
                            changed_layout = True
                            moved.append((path, target))
                except Exception:
                    for original, target in reversed(moved):
                        target.rename(original)
                    raise
        if changed_layout:
            mods = self.scan()
        if any(m.enabled and m.problem for m in mods):
            raise ValueError('mods_blocked')
        self._write(mods)
        return mods

    def pending_code(self, mods=None):
        mods = self.scan() if mods is None else mods
        record_path = self.game / 'build-cache/mod-code.json'
        try:
            record = json.loads(record_path.read_text()) if regular(record_path) and record_path.stat().st_size < 8 * 1024**2 else {}
        except (OSError, ValueError):
            record = {}
        if not isinstance(record, dict):
            record = {}
        pending = {}
        for mod in mods:
            if mod.enabled and not mod.problem:
                for name, path in mod.code.items():
                    fingerprint = digest(path)
                    if record.get(name) != fingerprint:
                        pending[name] = fingerprint
        return pending

    def check_code_status(self, mods=None):
        """Read the builder's public TSV receipt, not its patch implementation."""
        for mod in self.scan() if mods is None else mods:
            if not mod.enabled or mod.problem:
                continue
            for name, path in mod.code.items():
                if path.suffix.casefold() == '.txt':
                    status = self.game / 'build-cache/cheats.status'
                    if not regular(status) or not status.is_file() or status.stat().st_size > 8 * 1024**2:
                        raise ValueError('mods_rebuild_needed')
                    rows = [line.split('\t', 4) for line in status.read_text(encoding='utf-8').splitlines()]
                    names = {}
                    for title in re.findall(r'^\s*[\[{]([^\]}]+)[\]}]\s*$', path.read_text(encoding='utf-8-sig'), re.M):
                        names[title] = names.get(title, 0) + 1
                        suffix = '#' + str(names[title]) if names[title] > 1 else ''
                        key = fnv((mod.name + '/' + title + suffix).encode())
                        found = next((r for r in rows if len(r) == 5 and r[0].upper() == key), None)
                        if not found or found[2] not in {'code', 'data', 'key', 'master', 'restore', 'heading'}:
                            raise ValueError('mods_code_rejected')
                    continue
                if path.suffix.casefold() not in {'.ips', '.pchtxt'}:
                    continue
                status = self.game / 'build-cache/exefs.status'
                if not regular(status) or not status.is_file() or status.stat().st_size > 8 * 1024**2:
                    raise ValueError('mods_rebuild_needed')
                key, content = fnv(name.encode()), fnv(path.read_bytes())
                rows = [line.split('\t', 4) for line in status.read_text(encoding='utf-8').splitlines()]
                found = next((r for r in rows if len(r) == 5 and r[0].upper() == key and r[1].upper() == content), None)
                if not found or found[2] not in {'code', 'empty'}:
                    raise ValueError('mods_code_rejected')


def rebuild_code(library, source, notify):
    """Use the existing builder with rollback of executable/configuration receipts.

    No source archive, save profile or mod payload is removed or replaced here.
    The old executable is restored if compilation or patch acceptance fails.
    """
    if COMPONENTS['engine'].get('backend') == 'independent':
        raise ValueError('independent_backend_incomplete')
    library._closed()
    if (not (library.game / '.dekuforge-stable-build').is_file() or not Path(source).is_file()
            or library.executable.name.casefold() != 'dekuforgegame.exe'
            or library.folder != library.game / 'mods'):
        raise ValueError('mods_rebuild_source')
    from .stable_engine import build_stable
    cache = library.game / 'build-cache'
    paths = [p for p in library.game.iterdir() if p.is_file() and
             (p.suffix.casefold() in {'.exe', '.dll'} or p.name in {'nx2navi.ini', 'dekuforge-build-info.json'})]
    paths += [cache / name for name in ('mod-code.json', 'cheats.status', 'exefs.status', 'state.json')]
    required = sum(p.stat().st_size for p in paths if p.is_file())
    if required > 512 * 1024**2 or shutil.disk_usage(library.game).free < required + 64 * 1024**2:
        raise ValueError('mods_disk_space')
    lock = library.game / '.dekuforge-mod-build.lock'
    owner = lock.open('x')
    owner.close()
    try:
        with tempfile.TemporaryDirectory(prefix='.dekuforge-mod-rollback-', dir=library.game) as temporary:
            backup = Path(temporary)
            originals = {}
            for index, path in enumerate(paths):
                if path.exists():
                    if not regular(path):
                        raise ValueError('mods_unsafe_archive')
                    copy = backup / str(index)
                    shutil.copyfile(path, copy)
                    originals[path] = copy
                else:
                    originals[path] = None
            try:
                library._closed()
                result = build_stable(Path(source), notify, library.game)
                if result is None or Path(result).absolute() != library.executable or not Path(result).is_file():
                    raise ValueError('mods_code_rejected')
                if library.pending_code():
                    raise ValueError('mods_code_rejected')
                try:
                    library.check_code_status()
                except ValueError as error:
                    if str(error) == 'mods_rebuild_needed':
                        raise ValueError('mods_code_rejected') from error
                    raise
                return result
            except Exception:
                for path, copy in originals.items():
                    if copy is None:
                        path.unlink(missing_ok=True)
                    else:
                        shutil.copyfile(copy, path)
                raise
    finally:
        lock.unlink(missing_ok=True)
