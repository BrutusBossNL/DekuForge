"""Derive imported-call return sites from the player's module, without exporting code."""
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine" / "recomp"))
import numpy as np
from nso import Nso


def callsites(payload_path, symbol):
    module = Nso(str(payload_path))
    slots = {offset for offset, kind, index, _ in module.relocs
             if kind == 1026 and module.syms[index][0] == symbol}
    start, length = module.text
    words = np.frombuffer(module.image, dtype="<u4", count=length // 4, offset=start)
    candidates = np.flatnonzero((words & 0x9F00001F) == 0x90000010)
    stubs = []
    for index in candidates:
        index = int(index)
        if index + 3 >= len(words):
            continue
        page, load, branch = int(words[index]), int(words[index + 1]), int(words[index + 3])
        if load & 0xFFC003FF != 0xF9400211 or branch != 0xD61F0220:
            continue
        immediate = ((page >> 29) & 3) | (((page >> 5) & 0x7FFFF) << 2)
        immediate = (immediate ^ (1 << 20)) - (1 << 20)
        address = start + index * 4
        slot = (address & ~4095) + immediate * 4096 + ((load >> 10) & 4095) * 8
        if slot in slots:
            stubs.append(address)
    indices = np.flatnonzero((words & 0xFC000000) == 0x94000000)
    immediate = (words[indices] & 0x3FFFFFF).astype(np.int64)
    immediate = (immediate ^ (1 << 25)) - (1 << 25)
    offsets = start + indices.astype(np.int64) * 4
    return (offsets[np.isin(offsets + immediate * 4, stubs)] + 4).tolist()


