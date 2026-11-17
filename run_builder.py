"""DekuForge independent preparation and build entry point."""

import argparse
from pathlib import Path
import sys
import subprocess

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dekuforge.builder import default_backend, run_build
from dekuforge.native import prepare_archive
from dekuforge.gameplan import prepare_game
from dekuforge.engine import build_independent, engine_report, generate_prepared
from dekuforge.romfs import build_romfs
from dekuforge import COMPONENTS
import json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nup")
    parser.add_argument("--backend", default="" if COMPONENTS['engine'].get('backend') == 'independent' else str(default_backend()))
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--check", action="store_true")
    action.add_argument("--extract", action="store_true")
    action.add_argument("--romfs", action="store_true", help="assemble a verified RomFS image from a complete NUP snapshot")
    action.add_argument("--prepare", action="store_true")
    action.add_argument("--doctor", action="store_true")
    action.add_argument("--compat", action="store_true", help="explicitly use a separately installed compatibility backend")
    action.add_argument("--generate", type=Path, metavar="PREPARED", help="generate C from prepared modules; does not link a game")
    action.add_argument("--runtime", type=Path, metavar="PREPARED", help="compile the Windows host runtime; does not link a game")
    parser.add_argument("--toolchain", type=Path, help="MSYS2 UCRT64 compiler bin directory for --runtime")
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--modules", default="main,subsdk0,sdk")
    parser.add_argument("--limit", type=int, default=0, help="function limit for generation smoke checks")
    parser.add_argument("--out", type=Path, help="independent installation destination, or image directory with --romfs")
    args = parser.parse_args()
    if COMPONENTS['engine'].get('backend') == 'independent' and (args.compat or args.generate or args.runtime):
        parser.error('Legacy backend generation/runtime routes are reference-only in this branch. Use --doctor for the independent status.')
    if args.doctor:
        print(json.dumps(engine_report(), indent=2))
        return 0
    if not args.nup and not args.generate and not args.runtime:
        parser.error("--nup is required for this action")
    if args.runtime and not args.toolchain:
        parser.error("--runtime requires --toolchain")
    if args.romfs and not args.out:
        parser.error("--romfs requires an explicit --out directory")
    if args.compat and args.out:
        parser.error("--out is supported only by independent stages")
    try:
        emit = lambda kind, data: print(f"{kind}: {data}", flush=True)
        if args.runtime:
            return subprocess.call([sys.executable, str(Path(__file__).resolve().parent / "tools" / "build_runtime.py"),
                                    "--prepared", str(args.runtime), "--toolchain", str(args.toolchain)])
        elif args.generate:
            generate_prepared(args.generate.resolve(), emit, args.modules, args.limit, args.jobs)
        elif args.romfs:
            build_romfs(args.nup, args.out, emit)
        elif args.check or args.extract:
            prepare_archive(args.nup, emit, extract=args.extract)
        elif args.prepare:
            prepare_game(args.nup, emit)
        elif args.compat:
            run_build(args.nup, args.backend, emit, jobs=args.jobs)
        else:
            build_independent(args.nup, emit, destination=args.out)
    except (OSError, ValueError, RuntimeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
