"""Experimental source-builder composition; never selects main's backend.

An explicit local developer configuration is required until tool provisioning
and the full gameplay gates are accepted. The GPL provider supplies its complete
build pipeline; our entry applies branding and protects owned process/files.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from . import COMPONENTS
from .core import ROOT
from .open_engine import manifest, verify_tree

CONFIG = ROOT/'local/open-engine-builder.json'


def owned(value, base):
    path = Path(value)
    path = (ROOT/path).absolute() if not path.is_absolute() else path
    if path.resolve() != path or not path.is_relative_to(base) or path == base:
        raise ValueError('Independent builder path is outside its allowed workspace')
    return path


def claim(path, name, identity):
    marker = path/name
    if path.exists() and any(path.iterdir()):
        if marker.resolve() != marker or not marker.is_file() or marker.stat().st_size > 16384 or json.loads(marker.read_text()) != identity:
            raise ValueError('Existing build directory is unowned or has another identity')
    else:
        path.mkdir(parents=True, exist_ok=True)
        marker.write_text(json.dumps(identity, indent=2)+'\n')


def build(filename, notify, destination, *, config=None, romfs=None, exefs=None, prepare_gpu=True):
    config = json.loads(CONFIG.read_text(encoding='utf-8')) if config is None else config
    source = owned(config['source'], ROOT/'build')
    work = owned(config['work'], ROOT/'build')
    output = owned(destination, ROOT/'build')
    compiler = owned(config['toolchain'], ROOT/'local/build-tools')
    deps = owned(config['deps'], ROOT/'local/build-tools')
    jobs = config.get('jobs', 4)
    if type(jobs) is not int or not 1 <= jobs <= 32:
        raise ValueError('Use between 1 and 32 compiler jobs')
    for a, b in ((source, work), (source, output), (work, output)):
        if a.is_relative_to(b) or b.is_relative_to(a):
            raise ValueError('Source, work and installed output must be separate')
    record = manifest('hookshot')
    verify_tree(source, record)
    from .open_python_build import provision
    provision(lambda line: notify('log', line+'\n'))
    if not (compiler/'bin/clang.exe').is_file() or not (deps/'dav1d/1.5.4/lib/libdav1d.a').is_file():
        raise ValueError('Explicit compiler and source-built AV1 dependency are required')
    if filename is not None:
        from .nup import Archive
        archive = Archive(filename)
        if archive.path.is_relative_to(output):
            raise ValueError('The original game archive cannot be inside a build output')
        inputs = ['--nup', str(archive.path)]
        input_identity = {'nup_index_sha256': archive.index_sha256, 'nup_size': archive.size}
    else:
        romfs, exefs = owned(romfs, ROOT/'build'), owned(exefs, ROOT/'build')
        for path in (romfs, exefs):
            if not path.is_dir() or any(path.is_relative_to(p) or p.is_relative_to(path) for p in (work, output)):
                raise ValueError('Read-only extracted inputs must be separate from work/output')
        inputs = ['--romfs', str(romfs), '--exefs', str(exefs)]
        input_identity = {'developer_romfs': str(romfs), 'developer_exefs': str(exefs)}
    identity = {'provider_revision': record['revision']}
    claim(work, '.dekuforge-open-work.json', identity)
    claim(output, '.dekuforge-open-output.json', {**identity, **input_identity})
    (output/'.dekuforge-owned').touch()
    lock = work/'.dekuforge-build.lock'
    with lock.open('x'):
        pass
    try:
        env = {k: v for k, v in os.environ.items() if not k.startswith(
            ('HOS_', 'RX_', 'HOOKSHOT_', 'OOT_', 'TOTK_', 'NX2NAVI_', 'DEKUFORGE_', 'DKB_'))}
        env.update(DEKUFORGE_OPEN_SOURCE=str(source), DEKUFORGE_OPEN_WORK=str(work), DEKUFORGE_OPEN_OUTPUT=str(output),
                   HOOKSHOT_MINGW=str(compiler), RX_CPM=str(deps), WGPU_NATIVE=str(work/'unused-webgpu'),
                   HOOKSHOT_FFX_SDK=str(work/'ffx-sdk'),
                   HOOKSHOT_VERSION=COMPONENTS['engine']['version'], HOS_DISCORD='0',
                   PATH=str(compiler/'bin')+os.pathsep+env.get('PATH', ''))
        command = [sys.executable, '-B', '-u', str(ROOT/'tools/open_provider_entry.py'),
                   str(source/'nx2/make_game.py'), *inputs, '--out', str(output), '--work', str(work), '--jobs', str(jobs), '--prepare', '--fsr']
        if config.get('amd_fsr4_license_accepted') is True:
            command += ['--fetch-fsr-runtime', '--accept-amd-license']
        if not prepare_gpu:
            command += ['--no-prepare-shaders']
        phase = 'checking'
        with subprocess.Popen(command, cwd=source, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True, encoding='utf-8', errors='replace', creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)) as process:
            for line in process.stdout:
                notify('log', line)
                if line.startswith('@@stage '):
                    phase = line.split(' ', 2)[1]
                    notify('phase', {'phase': phase, 'done': 0, 'total': 0})
                elif line.startswith('@@progress '):
                    try:
                        value = float(line.split()[1])
                        if 0 <= value <= 1:
                            notify('progress', {'phase': phase, 'done': value, 'total': 1})
                    except (ValueError, IndexError):
                        pass
            if process.wait():
                raise RuntimeError('Experimental source build failed; inspect the build log')
        original = output/'hookshot.exe'
        if not original.is_file() or not (output/'image.bin').is_file() or not (output/'romfs').is_dir():
            raise RuntimeError('Provider did not produce a complete local game folder')
        prompts = output/'prompts'
        prompt_files = ['External.bfotf', 'Common.bntx', 'rsizetable.zs'] + [
            f'{face}/textures.bin' for face in ('switch', 'xbox', 'ps4', 'ps5', 'steamdeck')]
        for name in prompt_files:
            asset = prompts/name
            if not asset.is_file() or not asset.stat().st_size:
                raise RuntimeError(f'Missing controller prompt asset {name}; inspect the build log')
        executable = output/'DekuForgeGame.exe'
        original.replace(executable)
        # The public source pipeline copies controller libraries when available.
        # A developer may explicitly identify the separately verified SDL package.
        if config.get('sdl'):
            sdl = owned(config['sdl'], ROOT/'local/build-tools')
            for name in ('SDL2.dll', 'SDL3.dll'):
                shutil.copy2(sdl/name, output/name)
            if (sdl/'LICENSE.txt').is_file():
                shutil.copy2(sdl/'LICENSE.txt', output/'SDL-LICENSE.txt')
        for name in ('LICENSE',):
            shutil.copy2(source/name, output/('Hookshot-'+name+'.txt'))
        shutil.copy2(deps/'dav1d/1.5.4/COPYING', output/'dav1d-COPYING.txt')
        from .open_engine_runtime import MANIFEST
        (output/'user').mkdir(exist_ok=True)
        runtime = {'schema': 1, 'backend': 'hookshot-gpl', 'executable': executable.name,
                   'image': str(output/'image.bin'), 'romfs': str(output/'romfs'), 'user': str(output/'user')}
        temporary = output/(MANIFEST+'.tmp')
        temporary.write_text(json.dumps(runtime, indent=2)+'\n')
        temporary.replace(output/MANIFEST)
        info = {'engine_version': COMPONENTS['engine']['version'], 'game_version': '1.1.1',
                'provider_revision': record['revision'], 'experimental': True, 'gameplay_parity_accepted': False,
                'gpu_preparation_requested': prepare_gpu, 'save_layout': 'user/save'}
        (output/'dekuforge-build-info.json').write_text(json.dumps(info, indent=2)+'\n')
        if prepare_gpu:
            from .open_engine_warmup import warm
            info.update(warm(executable, work, notify))
            (output/'dekuforge-build-info.json').write_text(json.dumps(info, indent=2)+'\n')
        (output/'.dekuforge-native').touch()
        return executable
    finally:
        lock.unlink()
