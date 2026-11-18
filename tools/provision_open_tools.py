"""Fetch pinned generic tools for an explicitly experimental Windows build.

Requires an existing development Python and its requirements. Only selected
generic dependencies are extracted; runtime/lifter code is built from source.
No game, game shader/cache or NX2navi installation is downloaded.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import subprocess
import sys
from urllib.request import urlopen
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dekuforge.open_engine import stage, manifest, verify_tree
from dekuforge.open_game_build import owned
from dekuforge.mod_archives import relative_name

PINS = (
    ('llvm-mingw-20261104-ucrt-x86_64.zip', 191037046,
     '552191b5754c49a5a20723276a6fc56541ea1922c4c50b7b669022333fc1b40f',
     'https://github.com/mstorsjo/llvm-mingw/releases/download/20261104/llvm-mingw-20261104-ucrt-x86_64.zip',
     'llvm-mingw-20261104-ucrt-x86_64', 'hookshot-llvm-20261104'),
    ('HookshotBuilder-cpm-c30c77e4cf00.zip', 18641689,
     'c30c77e4cf000ebf11ec82e79ace4bef3206d3698c61146f7477baa428ea7ef0',
     'https://github.com/Z-TOON/Hookshot/releases/download/builder-parts/HookshotBuilder-cpm-c30c77e4cf00.zip',
     'HookshotBuilder/tools/cpm', 'hookshot-cpm'),
    ('HookshotBuilder-third_party-ee1cbb4068bb.zip', 30192784,
     'ee1cbb4068bbe9f4d1289a27c94356e607b5f2d59553fde1f785075668231613',
     'https://github.com/Z-TOON/Hookshot/releases/download/builder-parts/HookshotBuilder-third_party-ee1cbb4068bb.zip',
     'HookshotBuilder/tools/third_party/sdl2', 'hookshot-sdl'),
)


def archive(base, pin):
    name, size, sha, url, _, _ = pin
    path = base/name
    if not path.exists():
        temporary = base/('.download-'+uuid.uuid4().hex)
        try:
            print('Downloading pinned generic tool:', name, flush=True)
            with urlopen(url, timeout=90) as response, temporary.open('xb') as output:
                left = size+1
                while left:
                    block = response.read(min(left, 1024**2))
                    if not block:
                        break
                    output.write(block)
                    left -= len(block)
            with temporary.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            if temporary.stat().st_size != size or digest != sha:
                raise ValueError('Downloaded tool identity mismatch')
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
    if path.resolve() != path or path.stat().st_size != size:
        raise ValueError('Cached tool identity mismatch')
    with path.open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != sha:
            raise ValueError('Cached tool checksum mismatch')
    return path


def unpack(path, prefix, output):
    prefix = PurePosixPath(prefix).parts
    output = owned(output, ROOT/'local/build-tools')
    seen, total = set(), 0
    with zipfile.ZipFile(path) as bundle:
        for item in bundle.infolist():
            name = PurePosixPath(item.filename)
            if name.parts[:len(prefix)] != prefix or item.is_dir():
                continue
            if name.is_absolute() or '..' in name.parts or '\\' in item.filename or stat.S_ISLNK(item.external_attr >> 16):
                raise ValueError('Unsafe generic tool archive')
            relative = PurePosixPath(*name.parts[len(prefix):])
            relative_name(relative.as_posix())
            if relative.as_posix().casefold() in seen:
                raise ValueError('Aliased generic tool member')
            seen.add(relative.as_posix().casefold())
            total += item.file_size
            if total > 4*1024**3 or item.file_size > 512*1024**2:
                raise ValueError('Oversized generic tool extraction')
            target = output.joinpath(*relative.parts)
            if target.resolve() != target or not target.is_relative_to(output):
                raise ValueError('Generic tool output contains links')
            data = bundle.read(item)
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and target.read_bytes() != data:
                raise ValueError('Existing generic tool differs: ' + str(relative))
            if not target.exists():
                target.write_bytes(data)
    if not seen:
        raise ValueError('Generic tool prefix absent')
    print('Verified generic tools:', output, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, help='Reuse an already verified source checkout')
    parser.add_argument('--work', type=Path, default=ROOT/'build/open-engine-work')
    parser.add_argument('--configure-launcher', action='store_true', help='Explicitly opt in to experimental launcher builds')
    parser.add_argument('--jobs', type=int, default=4)
    args = parser.parse_args()
    if sys.platform != 'win32' or not 1 <= args.jobs <= 32:
        parser.error('Windows development tools require 1–32 jobs')
    from dekuforge.open_python_build import provision
    provision()
    source = owned(args.source, ROOT/'build') if args.source else stage(provider='hookshot')
    verify_tree(source, manifest('hookshot'))
    work = owned(args.work, ROOT/'build')
    base = ROOT/'local/build-tools'
    if base.resolve() != base:
        raise ValueError('Tool directory cannot contain links')
    base.mkdir(parents=True, exist_ok=True)
    for pin in PINS:
        unpack(archive(base, pin), pin[4], base/pin[5])
    compiler, deps = base/PINS[0][5], base/PINS[1][5]
    subprocess.run([sys.executable, '-B', str(ROOT/'tools/build_av1_decoder.py'), '--compiler', str(compiler),
                    '--deps', str(deps), '--jobs', str(args.jobs)], check=True)
    if args.configure_launcher:
        from dekuforge.open_game_build import CONFIG
        previous = json.loads(CONFIG.read_text(encoding='utf-8')) if CONFIG.is_file() else {}
        previous.update(source=str(source), work=str(work), toolchain=str(compiler), deps=str(deps),
                        sdl=str(base/PINS[2][5]), jobs=args.jobs, enable_launcher_build=True)
        temporary = CONFIG.with_suffix('.tmp')
        temporary.write_text(json.dumps(previous, indent=2)+'\n', encoding='utf-8')
        temporary.replace(CONFIG)
        print('Experimental launcher builds explicitly enabled; main updates/installer remain disabled.', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
