"""Explicit developer evaluation of pinned GPL source; not a production installer.

Only accepts inputs and outputs below this independent worktree's build folder.
Never imports an NX2navi backend, chooses an installed game or updates saves.
"""
import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dekuforge.open_engine import manifest, stage, verify_tree


def owned_path(path):
    path = Path(path).absolute()
    if path.resolve() != path or not path.is_relative_to(ROOT / 'build') or path == ROOT / 'build':
        raise ValueError('Evaluation paths must be regular directories below this worktree build folder')
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('fetch', 'lift', 'compile', 'shaders'))
    parser.add_argument('--provider', choices=('hookshot',), default='hookshot')
    parser.add_argument('--source', type=Path)
    parser.add_argument('--exefs', type=Path)
    parser.add_argument('--romfs', type=Path)
    parser.add_argument('--work', type=Path, default=ROOT / 'build/open-engine-evaluation/work')
    parser.add_argument('--toolchain', type=Path)
    parser.add_argument('--deps', type=Path)
    parser.add_argument('--jobs', type=int, default=4)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 32:
        parser.error('Use between 1 and 32 compiler jobs')
    record = manifest(args.provider)
    source = owned_path(args.source) if args.source else stage(provider=args.provider)
    verify_tree(source, record)
    if args.action == 'fetch':
        print(source)
        return 0
    if args.exefs is None:
        parser.error('--exefs is required for a developer evaluation')
    if args.action in ('lift','compile') and args.toolchain is None:
        parser.error('--toolchain is required; no implicit external compiler fallback')
    if args.action == 'compile' and (args.deps is None or not args.deps.is_dir()):
        parser.error('--deps must identify the explicit codec/header package')
    exefs, work = owned_path(args.exefs), owned_path(args.work)
    if work.is_relative_to(source) or source.is_relative_to(work) or exefs.is_relative_to(work):
        parser.error('Source, immutable input and generated output must be separate')
    inputs = {}
    for name in ('main', 'main.npdm', 'rtld', 'sdk', 'subsdk0'):
        path = exefs / name
        if path.resolve() != path or not path.is_file():
            raise ValueError('Missing regular module input: ' + name)
        with path.open('rb') as stream:
            inputs[name] = hashlib.file_digest(stream, 'sha256').hexdigest()
    identity = {'source_revision':record['revision'], 'input_sha256':inputs}
    marker = work / '.dekuforge-open-evaluation.json'
    if work.exists() and any(work.iterdir()):
        if not marker.is_file() or json.loads(marker.read_text(encoding='utf-8')) != identity:
            raise ValueError('Evaluation output is unowned or belongs to another source/input')
    else:
        work.mkdir(parents=True, exist_ok=True)
        marker.write_text(json.dumps(identity, indent=2)+'\n', encoding='utf-8')
    if args.toolchain:
        compiler = args.toolchain.resolve() / 'bin/clang.exe'
        if not compiler.is_file():
            raise ValueError('An explicit LLVM-MinGW toolchain is required')
        os.environ['HOOKSHOT_MINGW'] = str(args.toolchain.resolve())
        os.environ['PATH'] = str(compiler.parent) + os.pathsep + os.environ.get('PATH', '')
    if args.deps:
        os.environ['RX_CPM'] = str(args.deps.resolve())
    os.environ['OOT_WORK'] = str(work)
    os.environ['OOT_EXEFS'] = str(exefs)
    os.environ['WGPU_NATIVE'] = str(work / 'unused-webgpu')
    romfs = owned_path(args.romfs) if args.romfs else None
    if romfs:
        os.environ['OOT_ROMFS'] = str(romfs)
    sys.path.insert(0, str(source / 'nx2'))
    os.chdir(source)
    if args.action == 'shaders':
        if args.romfs is None:
            parser.error('--romfs is required for local shader enumeration')
        output = work / 'sa/build/hookshot_shaders.bin'
        output.parent.mkdir(parents=True, exist_ok=True)
        return subprocess.call([sys.executable, '-I', '-B', str(source / 'nx2/shader_census.py'),
                                str(romfs), '--out', str(output)])
    name = 'lift' if args.action == 'lift' else 'build'
    module = importlib.import_module(name)
    if Path(module.__file__).resolve().parent != source / 'nx2':
        raise ValueError('Another engine module is already loaded; use a fresh evaluation process')
    if args.action == 'compile':
        from dekuforge.open_engine_branding import configure
        configure(module, source, work)
    sys.argv = [str(source / 'nx2' / (name+'.py')), '--standalone']
    if args.action == 'lift':
        sys.argv += ['--write', '--exefs', str(exefs), '--work', str(work)]
    else:
        sys.argv += ['--jobs', str(args.jobs)]
    module.main()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
