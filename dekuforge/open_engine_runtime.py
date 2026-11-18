"""Explicit launch metadata for locally generated independent game folders."""
import json
import os
from pathlib import Path

from .core import ROOT

MANIFEST = '.dekuforge-runtime.json'


def launch_options(executable, root=ROOT):
    executable, root = Path(executable).absolute(), Path(root).resolve()
    marker = executable.parent / MANIFEST
    if not marker.exists():
        return None
    if marker.resolve() != marker or not marker.is_file():
        raise ValueError('Independent runtime metadata must be a regular file')
    if marker.stat().st_size > 16384:
        raise ValueError('Oversized independent runtime metadata')
    data = json.loads(marker.read_text(encoding='utf-8'))
    if data.get('schema') != 1 or data.get('backend') != 'hookshot-gpl' or data.get('executable') != executable.name:
        raise ValueError('Unsupported independent runtime metadata')
    paths = {}
    for name in ('image', 'romfs', 'user'):
        value = data.get(name)
        if not isinstance(value, str) or not Path(value).is_absolute():
            raise ValueError('Independent resource paths must be explicit absolute paths')
        path = Path(value)
        if path.resolve() != path or not path.is_relative_to(root / 'build'):
            raise ValueError('Independent resources must stay inside this worktree build folder')
        if name == 'image' and not path.is_file():
            raise ValueError('Generated game image is missing')
        if name != 'image' and not path.is_dir():
            raise ValueError('Independent game resource directory is missing: ' + name)
        paths[name] = path
    if executable.resolve() != executable or not executable.is_relative_to(root / 'build'):
        raise ValueError('Independent executable must stay inside this worktree build folder')
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(('HOS_', 'RX_', 'TOTK_', 'NX2NAVI_', 'DEKUFORGE_', 'OOT_', 'DKB_'))}
    env.update(RX_BACKEND='vulkan', HOS_DISCORD='0')
    return {'args': [str(executable), str(paths['image']), '--romfs', str(paths['romfs']), '--user', str(paths['user'])],
            'env': env}
