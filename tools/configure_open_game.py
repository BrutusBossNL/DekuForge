"""Register an existing locally compiled experimental game with this launcher.

This does not build a game or grant gameplay acceptance. All inputs must already
exist inside this independent worktree. No existing metadata is overwritten.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dekuforge.core import save_installation
from dekuforge.open_engine_runtime import MANIFEST, launch_options
from dekuforge.build_library import BuildLibrary
from dekuforge import COMPONENTS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--executable', type=Path, required=True)
    parser.add_argument('--image', type=Path, required=True)
    parser.add_argument('--romfs', type=Path, required=True)
    parser.add_argument('--user', type=Path, required=True)
    parser.add_argument('--activate', action='store_true')
    args = parser.parse_args()
    executable = args.executable.absolute()
    if not executable.is_file() or executable.resolve() != executable or not executable.is_relative_to(ROOT/'build'):
        parser.error('Select a regular existing compiled game inside this worktree build folder')
    marker = executable.parent / MANIFEST
    record = {'schema': 1, 'backend': 'hookshot-gpl', 'executable': executable.name,
              **{name: str(getattr(args, name).absolute()) for name in ('image', 'romfs', 'user')}}
    # Exclusive creation protects an earlier selected image/profile from replacement.
    with marker.open('x', encoding='utf-8') as output:
        json.dump(record, output, indent=2)
    try:
        launch_options(executable)
    except Exception:
        marker.unlink()
        raise
    # Experimental output shares separately managed generated caches. Do not grant
    # the build-library delete operation ownership of that entire source workspace.
    BuildLibrary(ROOT).register(executable, version=COMPONENTS['engine']['version']+' (experimental)', owned=False)
    if args.activate:
        save_installation(str(executable))
    print('Configured experimental local game:', executable)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
