"""Command-line access to the DekuForge external build adapter."""

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dekuforge.builder import default_backend, run_build
from dekuforge.native import prepare_archive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nup", required=True)
    parser.add_argument("--backend", default=str(default_backend()))
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--extract", action="store_true")
    parser.add_argument("--jobs", type=int, default=1)
    args = parser.parse_args()
    try:
        emit = lambda kind, data: print(f"{kind}: {data}", flush=True)
        if args.check or args.extract:
            prepare_archive(args.nup, emit, extract=args.extract)
        else:
            run_build(args.nup, args.backend, emit, jobs=args.jobs)
    except (OSError, ValueError, RuntimeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
