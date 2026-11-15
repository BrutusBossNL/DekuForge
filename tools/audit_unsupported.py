"""Summarize unsupported instruction encodings without exporting game functions."""

import argparse
from collections import Counter, defaultdict
import importlib.util
import json
from pathlib import Path
import re
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine" / "recomp"))
from nso import Nso


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--module", choices=["main", "sdk", "subsdk0"], default="sdk")
    args = parser.parse_args()
    generated = args.prepared / "generated" / args.module
    manifest = json.loads((generated / "manifest.json").read_text(encoding="utf-8"))
    base = int(manifest["base"], 16)
    module = Nso(str(args.prepared / "normalized-exefs" / args.module))
    found = defaultdict(Counter)
    pattern = re.compile(r"rt_udf\(c,\s*(0x[0-9a-f]+)(?:ull)?\);\s*/\*\s*(.*?)\s*\*/")
    for chunk in manifest["chunks"]:
        with (generated / chunk).open(encoding="utf-8") as source:
            for line in source:
                match = pattern.search(line)
                if not match:
                    continue
                offset = int(match[1], 16) - base
                if not 0 <= offset <= len(module.image) - 4:
                    raise ValueError("Unsupported-instruction address outside the module")
                instruction = struct.unpack_from("<I", module.image, offset)[0]
                found[match[2]][f"{instruction:08x}"] += 1
    print(json.dumps({reason: dict(words) for reason, words in found.items()}, indent=2))


if __name__ == "__main__":
    main()
