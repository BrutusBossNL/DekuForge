"""Build the BSD-licensed AV1 decoder needed by the independent Windows engine.

No Store codec, game bytes or precompiled game engine is used. Generic build
tools and VideoLAN source are downloaded at fixed identities into local/.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import sys
import tarfile
from urllib.request import urlopen
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PINS = (
    ('meson.whl', 'https://files.pythonhosted.org/packages/9c/07/b48592d325cb86682829f05216e4efb2dc881762b8f1bafb48b57442307a/meson-1.9.1-py3-none-any.whl',
     'f824ab770c041a202f532f69e114c971918ed2daff7ea56583d80642564598d0'),
    ('ninja.whl', 'https://files.pythonhosted.org/packages/29/45/c0adfbfb0b5895aa18cec400c535b4f7ff3e52536e0403602fc1a23f7de9/ninja-1.13.0-py3-none-win_amd64.whl',
     'fb8ee8719f8af47fed145cced4a85f0755dd55d45b2bddaf7431fa89803c5f3e'),
    ('nasm.zip', 'https://www.nasm.us/pub/nasm/releasebuilds/2.16.03/win64/nasm-2.16.03-win64.zip',
     '3ee4782247bcb874378d02f7eab4e294a84d3d15f3f6ee2de2f47a46aa7226e6'),
    ('dav1d.tar.gz', 'https://codeload.github.com/videolan/dav1d/tar.gz/refs/tags/1.5.4',
     'a1d5b63d2d38ec9bd03acf643caa51fa22edd1e89c5a109c4807717216bbec07'),
)
TREE = '01ecdd01d24e9946c5ad67837390620bc943ef521c661cebebd1d7e4263d61ea'
LIMIT = 64 * 1024**2


def checked_path(value):
    path = Path(value).absolute()
    if path.resolve() != path or not path.is_relative_to(ROOT / 'local/build-tools'):
        raise ValueError('Decoder tools must stay in this worktree local/build-tools')
    return path


def put(directory, name, data):
    relative = PurePosixPath(name)
    if relative.is_absolute() or '..' in relative.parts or '\\' in name or ':' in name:
        raise ValueError('Unsafe tool member')
    target = directory.joinpath(*relative.parts)
    if target.resolve() != target or not target.is_relative_to(directory):
        raise ValueError('Tool output cannot contain links')
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.read_bytes() != data:
        raise ValueError('Existing tool file differs: ' + name)
    if not target.exists():
        target.write_bytes(data)


def fetch(base, pin):
    name, url, digest = pin
    cache = base / name
    if cache.is_file():
        data = cache.read_bytes()
    else:
        print('Downloading pinned decoder tool:', name, flush=True)
        with urlopen(url, timeout=90) as response:
            data = response.read(LIMIT+1)
    if len(data) > LIMIT or hashlib.sha256(data).hexdigest() != digest:
        raise ValueError('Decoder tool identity mismatch: ' + name)
    if not cache.exists():
        cache.write_bytes(data)
    return data


def unpack_zip(data, output):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        seen, total = set(), 0
        for member in archive.infolist():
            if member.is_dir():
                continue
            if stat.S_ISLNK(member.external_attr >> 16) or member.filename.casefold() in seen:
                raise ValueError('Linked or duplicated tool member')
            seen.add(member.filename.casefold())
            total += member.file_size
            if total > LIMIT:
                raise ValueError('Oversized decoder tool extraction')
            put(output, member.filename, archive.read(member))


def meson_build_path(base, output, cross_config):
    # Meson embeds absolute source, interpreter, compiler and install paths.
    identity = hashlib.sha256(os.fsencode(output) + b'\0' + os.fsencode(sys.executable)
                              + b'\0' + cross_config.encode('utf-8')).hexdigest()[:16]
    return checked_path(base / f'build-{identity}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', required=True, type=Path)
    parser.add_argument('--deps', required=True, type=Path)
    parser.add_argument('--jobs', type=int, default=4)
    args = parser.parse_args()
    if os.name != 'nt' or not 1 <= args.jobs <= 32:
        parser.error('This command builds the Windows decoder with 1–32 jobs')
    compiler, deps = checked_path(args.compiler), checked_path(args.deps)
    if not (compiler / 'bin/clang.exe').is_file():
        parser.error('An explicit LLVM-MinGW compiler is required')
    base = checked_path(ROOT / 'local/build-tools/dav1d-dev')
    base.mkdir(parents=True, exist_ok=True)
    for pin in PINS[:2]:
        unpack_zip(fetch(base, pin), base / 'python')
    unpack_zip(fetch(base, PINS[2]), base / 'nasm')
    rows = []
    with tarfile.open(fileobj=io.BytesIO(fetch(base, PINS[3])), mode='r:gz') as archive:
        total = 0
        for member in archive:
            if member.isdir():
                continue
            if not member.isfile():
                raise ValueError('Nonregular decoder source member')
            total += member.size
            if total > LIMIT:
                raise ValueError('Oversized decoder source')
            name = PurePosixPath(member.name)
            if name.parts[0] != 'dav1d-1.5.4':
                raise ValueError('Unexpected decoder source prefix')
            name = PurePosixPath(*name.parts[1:]).as_posix()
            data = archive.extractfile(member).read()
            rows.append((name, hashlib.sha256(data).hexdigest()))
            put(base / 'source', name, data)
    tree = hashlib.sha256(''.join(f'{digest}  ./{name}\n' for name, digest in sorted(rows)).encode()).hexdigest()
    if tree != TREE:
        raise ValueError('Decoder source tree identity mismatch')
    wrapper = base / 'meson.py'
    text = "import sys\nfrom pathlib import Path\nsys.path.insert(0,str(Path(__file__).resolve().parent/'python'))\nfrom mesonbuild.mesonmain import main\nraise SystemExit(main())\n"
    put(base, 'meson.py', text.encode())
    output, llvm = deps / 'dav1d/1.5.4', compiler / 'bin'
    nasm = base / 'nasm/nasm-2.16.03'
    ninja = base / 'python/ninja-1.13.0.data/scripts/ninja.exe'
    cross = base / 'cross.txt'
    binaries = {'c': llvm/'clang.exe', 'ar': llvm/'llvm-ar.exe', 'strip': llvm/'llvm-strip.exe',
                'windres': llvm/'x86_64-w64-mingw32-windres.exe', 'nasm': nasm/'nasm.exe'}
    cross_config = '[binaries]\n'+''.join(f"{key} = '{path.as_posix()}'\n" for key, path in binaries.items())+(
        "[built-in options]\nc_args = ['-mno-incremental-linker-compatible']\n[host_machine]\nsystem = 'windows'\n"
        "cpu_family = 'x86_64'\ncpu = 'x86_64'\nendian = 'little'\n")
    cross.write_text(cross_config, encoding='utf-8')
    build = meson_build_path(base, output, cross_config)
    env = {**os.environ, 'PATH': os.pathsep.join((str(llvm), str(nasm), str(ninja.parent), os.environ.get('PATH', '')))}
    setup = [sys.executable, '-B', str(wrapper), 'setup', str(build), str(base/'source'),
             '--cross-file', str(cross), '--prefix', str(output), '--libdir=lib', '--buildtype=release',
             '--default-library=static', '-Denable_tools=false', '-Denable_tests=false', '-Denable_examples=false', '-Db_ndebug=true']
    if (build / 'meson-private/coredata.dat').exists():
        setup += ['--reconfigure']
    for command in (setup, [str(ninja), '-C', str(build), '-j'+str(args.jobs)],
                    [sys.executable, '-B', str(wrapper), 'install', '-C', str(build), '--no-rebuild']):
        subprocess.run(command, env=env, check=True)
    shutil.copyfile(base/'source/COPYING', output/'COPYING')
    library = output/'lib/libdav1d.a'
    (output/'dekuforge-decoder.json').write_text(json.dumps({'version': '1.5.4', 'source_tree_sha256': TREE,
        'library_sha256': hashlib.sha256(library.read_bytes()).hexdigest(), 'license': 'BSD-2-Clause'}, indent=2)+'\n')
    print('AV1 decoder ready:', output, flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
