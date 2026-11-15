"""Reject local inputs, binaries and generated game outputs from staged source."""

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = {".nup", ".nsp", ".nsz", ".xci", ".xcz", ".nca", ".nso", ".npdm",
             ".exe", ".dll", ".keys", ".sav", ".spv", ".profdata", ".profraw"}
PREFIXES = ("local/", "build/", "generated/", "engine/build/", "engine/generated/",
            "engine/refs/", "engine/toolchain/")


def main():
    paths = subprocess.check_output(["git", "-c", f"safe.directory={ROOT.as_posix()}",
                                     "-C", str(ROOT), "diff", "--cached", "--name-only",
                                     "--diff-filter=ACMR", "-z"]).decode("utf-8").split("\0")
    bad = [path for path in paths if path and
           (path.startswith(PREFIXES) or Path(path).suffix.lower() in FORBIDDEN)]
    if bad:
        print("Local or generated content staged:\n" + "\n".join(bad), file=sys.stderr)
        return 1
    print(f"Source boundary checked: {sum(bool(path) for path in paths)} staged files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
