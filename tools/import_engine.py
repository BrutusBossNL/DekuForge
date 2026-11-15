"""Reproduce the pinned, permissively licensed engine source import.

Only the selected source roots from the fixed historical revision are exported.
The current working tree of the supplied repository is never copied.
"""

import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import zipfile

REVISION = "0478c13e4503a8c1a75155b1e277b8cc53ce149a"
ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, required=True)
    args = parser.parse_args()
    repository = args.repository.resolve()
    archive = subprocess.run(["git", "-c", f"safe.directory={repository.as_posix()}", "-C", str(repository), "archive", "--format=zip", REVISION,
                              "LICENSE", "THIRD_PARTY_NOTICES.md", "VERSION", "recomp", "runtime", "tools"],
                             check=True, stdout=subprocess.PIPE).stdout
    destination = ROOT / "engine"
    if destination.exists():
        raise SystemExit("Engine source already exists; no files overwritten")
    destination.mkdir()
    records = {}
    with zipfile.ZipFile(io.BytesIO(archive)) as source:
        for entry in source.infolist():
            if entry.is_dir():
                continue
            relative = Path(entry.filename)
            target = destination / relative
            if not target.resolve().is_relative_to(destination.resolve()):
                raise ValueError("Invalid source archive path")
            payload = source.read(entry)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
            records[relative.as_posix()] = hashlib.sha256(payload).hexdigest()
    (destination / "SOURCE.json").write_text(json.dumps({"revision": REVISION, "files": records}, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"Imported {len(records)} pinned engine source files")


if __name__ == "__main__":
    main()
