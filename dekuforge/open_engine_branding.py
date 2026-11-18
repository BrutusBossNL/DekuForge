# SPDX-License-Identifier: GPL-3.0-or-later
"""Recorded UI adaptations of the pinned GPL provider; no renderer changes.

Original provider files stay immutable. Only the affected translation units use
generated, attributed copies, so unrelated CPU/renderer objects remain reusable.
"""
import hashlib
import json
import os
from pathlib import Path

from .core import ROOT


def _replace(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Pinned UI adaptation anchor changed: ' + old[:65])
    return text.replace(old, new, 1)


def prepare(source, output):
    source, output = Path(source).resolve(), Path(output).absolute()
    if output.resolve() != output or not output.is_relative_to(ROOT / 'build'):
        raise ValueError('Adapted source must remain in the independent build folder')
    output.mkdir(parents=True, exist_ok=True)
    palette = (source / 'gpu/vk/vk_ui.h').read_text(encoding='utf-8')
    for old, new in (
        ('kGold = rgba(222, 152, 40)', 'kGold = rgba(233, 185, 73)'),
        ('kGoldHi = rgba(238, 168, 52)', 'kGoldHi = rgba(250, 207, 105)'),
        ('kCellDark = rgba(30, 25, 19, 246)', 'kCellDark = rgba(11, 28, 19, 246)'),
        ('kCellName = rgba(60, 47, 32, 240)', 'kCellName = rgba(29, 53, 35, 240)'),
        ('kCellNameSel = rgba(92, 70, 42, 248)', 'kCellNameSel = rgba(55, 78, 40, 248)'),
        ('kColumn = rgba(34, 26, 17, 228)', 'kColumn = rgba(12, 30, 20, 238)'),
        ('kBox = rgba(36, 28, 19, 248)', 'kBox = rgba(15, 33, 23, 248)'),
        ('kBar = rgba(22, 17, 11, 232)', 'kBar = rgba(8, 22, 15, 240)'),
    ):
        palette = _replace(palette, old, new)
    files = {'vk_ui.h': palette}
    menu = (source / 'gpu/vk/vk_menu.cpp').read_text(encoding='utf-8')
    menu = _replace(menu, '#include "vk_ui.h"', '#include "' + (output / 'vk_ui.h').as_posix() + '"')
    menu = _replace(menu, 'std::string("Hookshot ")', 'std::string("DekuForge ")')
    menu = _replace(menu, '"HOOKSHOT", 6 * k', '"DEKUFORGE", 6 * k')
    menu = _replace(menu, 'ui::rgba(14, 10, 6)', 'ui::rgba(7, 21, 13)')
    menu = menu.replace('github.com/NotRexed/Hookshot/issues/2034', 'github.com/BrutusBossNL/DekuForge/issues')
    menu = menu.replace('github.com/NotRexed/Hookshot/issues', 'github.com/BrutusBossNL/DekuForge/issues')
    files['vk_menu.cpp'] = menu
    display = (source / 'host/display.c').read_text(encoding='utf-8')
    display = _replace(display, '#include "hos.h"', '#include "hos.h"\n#undef HOS_GAME_TITLE\n#define HOS_GAME_TITLE "DekuForge"')
    files['display.c'] = display
    mapping, records = {}, {}
    origins = {'vk_ui.h': 'gpu/vk/vk_ui.h', 'vk_menu.cpp': 'gpu/vk/vk_menu.cpp', 'display.c': 'host/display.c'}
    for name, text in files.items():
        path = output / name
        if path.exists() and (path.is_symlink() or getattr(path, 'is_junction', lambda: False)()):
            raise ValueError('Adapted source cannot be a link')
        data = ('// DekuForge UI adaptation of Hookshot; GPL-3.0-or-later.\n' + text).encode('utf-8')
        if not path.is_file() or path.read_bytes() != data:
            path.write_bytes(data)
        original = source / origins[name]
        mapping[str(original)] = str(path)
        records[origins[name]] = {'original_sha256': hashlib.sha256(original.read_bytes()).hexdigest(),
                                'adapted_sha256': hashlib.sha256(data).hexdigest()}
    (output / 'adaptations.json').write_text(json.dumps(records, indent=2)+'\n', encoding='utf-8')
    return mapping


def configure(module, source, work):
    """Install once in a fresh provider compiler process before calling main()."""
    if getattr(module, '_dekuforge_branded', False):
        raise ValueError('Provider branding already installed')
    source = Path(source).resolve()
    mapping = prepare(source, Path(work) / 'dekuforge-ui')
    version = json.loads((ROOT / 'dekuforge/components.json').read_text(encoding='utf-8'))['engine']['version']
    os.environ['HOOKSHOT_VERSION'] = version
    logo_write = module.logo_rgba.write
    module.logo_rgba.write = lambda path: logo_write(path, str(ROOT / 'assets/branding/logo.png'))
    original_compile, original_key = module.compile_one, module.object_key

    def adapted_job(job):
        cc, src, obj, flags, deps = job
        replacement = mapping.get(str(Path(src).resolve()))
        if replacement:
            # Quoted provider includes formerly resolved beside the original file.
            flags = [*flags, '-I' + str(Path(src).parent)]
            deps += Path(mapping[str(source / 'gpu/vk/vk_ui.h')]).read_bytes()
            src = replacement
        return cc, src, obj, flags, deps

    def key(src, flags, deps):
        _, src, _, flags, deps = adapted_job((None, src, None, flags, deps))
        return original_key(src, flags, deps)

    module.object_key = key
    module.compile_one = lambda job: original_compile(adapted_job(job))
    module._dekuforge_branded = True
