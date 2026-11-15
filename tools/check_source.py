"""Reject local inputs, binaries and generated game outputs from staged source."""

from pathlib import Path
import argparse
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = {".nup", ".nsp", ".nsz", ".xci", ".xcz", ".nca", ".nso", ".npdm",
             ".exe", ".dll", ".keys", ".sav", ".spv", ".profdata", ".profraw",
             ".rom", ".z64", ".n64", ".v64", ".ncz", ".tik", ".nro",
             ".o", ".obj", ".a", ".lib", ".zip", ".7z", ".rar", ".bin"}
PREFIXES = ("local/", "build/", "generated/", "engine/build/", "engine/generated/",
            "engine/refs/", "engine/toolchain/")
GENERATED = re.compile(rb"(?m)^\s*(?://|/\*|\*)\s*(?:DEKUFORGE|NX2NAVI)_RECOMP_GENERATED_FROM_GAME_CODE\b")


def forbidden(path, data=b""):
    lowered = path.casefold()
    name = Path(lowered)
    if lowered.startswith(PREFIXES) or name.suffix in FORBIDDEN:
        return True
    if name.name in {"main", "sdk", "rtld", *[f"subsdk{i}" for i in range(10)]}:
        return True
    if data.startswith((b"NUP\x01", b"NSO0", b"PFS0", b"DFROMFS1", b"\x7fELF", b"MZ")):
        return True
    return GENERATED.search(data) is not None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tracked", action="store_true", help="check the full checkout in CI")
    args = parser.parse_args()
    git = ["git", "-c", f"safe.directory={ROOT.as_posix()}", "-C", str(ROOT)]
    selection = ["ls-files", "-z"] if args.tracked else ["diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"]
    paths = [path for path in subprocess.check_output(git + selection).decode("utf-8").split("\0") if path]
    bad = []
    for path in paths:
        if args.tracked:
            target = ROOT / path
            if target.is_symlink() or not target.resolve().is_relative_to(ROOT.resolve()):
                bad.append(path)
                continue
            with target.open("rb") as source:
                data = source.read(8192)
        else:
            data = subprocess.check_output(git + ["show", ":" + path])[:8192]
        if forbidden(path, data):
            bad.append(path)
    if bad:
        print("Local or generated content staged:\n" + "\n".join(bad), file=sys.stderr)
        return 1
    print(f"Source boundary checked: {len(paths)} {'tracked' if args.tracked else 'staged'} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
