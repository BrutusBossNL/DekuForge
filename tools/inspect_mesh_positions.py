"""Summarize bounded GPU position traces without interpreting them as visual proof."""
import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import re
import struct


PATTERN = re.compile(
    r"Mesh position bits: shader ([0-9a-f]{8}) group (\d+) first (\d+) "
    r"primitives (\d+) xyzw " + r"([0-9a-f]{8}) " * 3 + r"([0-9a-f]{8})"
)


def inspect(text):
    shaders = Counter()
    positions = defaultdict(set)
    invalid = 0
    total = 0
    for match in PATTERN.finditer(text):
        shader, group, first, primitives, *words = match.groups()
        bits = tuple(int(word, 16) for word in words)
        values = struct.unpack("<4f", struct.pack("<4I", *bits))
        total += 1
        shaders[shader] += 1
        invalid += not all(math.isfinite(value) for value in values)
        positions[bits].add(shader)
    shared = [sorted(programs) for programs in positions.values() if len(programs) > 1]
    batches = [(int(a), int(b)) for a, b in re.findall(
        r"Mesh position batch: (\d+) captured, (\d+) requested", text)]
    return {
        "records": total,
        "shaders": dict(shaders),
        "nonfinite_positions": invalid,
        "unique_position_bit_patterns": len(positions),
        "positions_shared_by_different_shaders": len(shared),
        "shared_shader_sets": dict(Counter(",".join(group) for group in shared)),
        "batches": len(batches),
        "truncated_records": sum(requested - captured for captured, requested in batches),
        "limitation": "Samples have no vertex identity across draws; equality alone does not establish pass correctness.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.log.read_text(encoding="utf-8", errors="replace")), indent=2))
