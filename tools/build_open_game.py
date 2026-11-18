"""Run the complete pinned GPL pipeline in explicitly owned developer folders."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dekuforge.open_game_build import build


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=ROOT/'local/open-engine-builder.json')
    parser.add_argument('--nup', type=Path)
    parser.add_argument('--romfs', type=Path)
    parser.add_argument('--exefs', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--no-prepare-shaders', action='store_true', help='Developer diagnostic only; does not claim shader preparation')
    args = parser.parse_args()
    if bool(args.nup) == bool(args.romfs or args.exefs) or (not args.nup and not (args.romfs and args.exefs)):
        parser.error('Choose --nup, or both --romfs and --exefs')
    result = build(args.nup, lambda kind, value: print(value, end='' if kind == 'log' else '\n', flush=True),
                   args.out, config=json.loads(args.config.read_text(encoding='utf-8')),
                   romfs=args.romfs, exefs=args.exefs, prepare_gpu=not args.no_prepare_shaders)
    print('Experimental game:', result)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
