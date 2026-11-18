"""Compose launcher asset-mod order into the GPL runtime's public mod interface.

Never writes through a game asset/hard link. Runtime snapshots contain only the
chosen local mod files; disabled mods never reach the engine's automatic loader.
Code patches/cheats remain gated pending an independent implementation.
"""
import hashlib
import json
from pathlib import Path
import shutil
import uuid

from .core import ROOT
from .mod_archives import regular, relative_name
from .mods import ModLibrary, digest

LIMIT = 2 * 1024**3


def prepare_mods(executable, options, root=ROOT):
    game = Path(executable).absolute().parent
    if game.resolve() != game or not game.is_relative_to(Path(root).resolve()/'build'):
        raise ValueError('mods_external_dir')
    library = ModLibrary(executable, running=lambda: False)
    mods = library.scan()
    if any(mod.enabled and mod.problem for mod in mods):
        raise ValueError('mods_blocked')
    if any(mod.enabled and mod.code for mod in mods):
        raise ValueError('independent_backend_incomplete')
    winners = {}
    for mod in mods:  # Launcher priority: the first enabled provider wins.
        if mod.enabled:
            for key, file in mod.romfs.items():
                winners.setdefault(key, (file, file.relative_to(mod.parts['romfs']).as_posix()))
    cache = game/'.dfmods'
    if cache.resolve() != cache:
        raise ValueError('mods_external_dir')
    env = dict(options['env'])
    env['HOS_MODS'] = str(cache/'disabled')
    result = {**options, 'env': env}
    if not winners:
        return result
    records, total = [], 0
    for key, (file, relative) in sorted(winners.items()):
        relative_name(relative)
        if not regular(file) or not file.is_file():
            raise ValueError('mods_unsafe_archive')
        size = file.stat().st_size
        total += size
        if total > LIMIT or len(records) >= 100000:
            raise ValueError('mods_import_limit')
        records.append({'path': relative, 'size': size, 'sha256': digest(file), 'source': str(file)})
    identity = hashlib.sha256(json.dumps(records, sort_keys=True).encode()).hexdigest()
    # Keep the engine's Win32 mod paths short; the full receipt is still verified.
    snapshot = cache/identity[:20]
    if snapshot.resolve() != snapshot:
        raise ValueError('mods_unsafe_archive')
    if any(len(str(snapshot/'DekuForge/romfs'/record['path']).encode('utf-8')) >= 260 for record in records):
        raise ValueError('mods_path_too_long')
    if snapshot.exists():
        receipt = snapshot/'snapshot.json'
        if not regular(receipt) or not receipt.is_file() or receipt.stat().st_size > 32*1024**2:
            raise ValueError('mods_unsafe_archive')
        if json.loads(receipt.read_text()) != records:
            raise ValueError('mods_unsafe_archive')
        for record in records:
            file = snapshot/'DekuForge/romfs'/record['path']
            if not regular(file) or not file.is_file() or file.stat().st_size != record['size'] or digest(file) != record['sha256']:
                raise ValueError('mods_unsafe_archive')
    else:
        cache.mkdir(exist_ok=True)
        if shutil.disk_usage(cache).free < total+128*1024**2:
            raise OSError('Insufficient space for the selected asset mods')
        staged = cache/('.staging-'+uuid.uuid4().hex)
        staged.mkdir()
        try:
            for record in records:
                target = staged/'DekuForge/romfs'/record['path']
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(record['source'], target)
                if target.stat().st_size != record['size'] or digest(target) != record['sha256']:
                    raise ValueError('mods_unsafe_archive')
            (staged/'snapshot.json').write_text(json.dumps(records, indent=2)+'\n')
            staged.rename(snapshot)
        finally:
            # Only this invocation's freshly created, checked temporary tree.
            if staged.exists():
                if staged.resolve() != staged or not staged.is_relative_to(cache):
                    raise ValueError('mods_unsafe_archive')
                if any(not regular(child) for child in staged.rglob('*')):
                    raise ValueError('mods_unsafe_archive')
                shutil.rmtree(staged)
    env['HOS_MODS'] = str(snapshot)
    return result
