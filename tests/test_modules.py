import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest

from dekuforge.engine import verify_engine_sources
from dekuforge.gameplan import FIRST_ADDRESS, TITLE, inspect_nso, prepare_game
from dekuforge.modules import normalize_module, normalize_prepared
from dekuforge.nup import ArchiveError


def executable(compress=False):
    header = bytearray(256)
    header[:4] = b"NSO0"
    header[64:96] = bytes(range(32))
    flags = 0x38 | (7 if compress else 0)
    struct.pack_into("<I", header, 12, flags)
    struct.pack_into("<I", header, 60, 8)
    result = bytearray(header)
    for number in range(3):
        content = bytes([number + 1]) * 16
        packed = content
        if compress:
            from lz4.block import compress as lz4_compress
            packed = lz4_compress(content, store_size=False)
        struct.pack_into("<III", result, 16 + 16 * number, len(result), number * 4096, len(content))
        struct.pack_into("<I", result, 96 + 4 * number, len(packed))
        result[160 + 32 * number:192 + 32 * number] = hashlib.sha256(content).digest()
        result.extend(packed)
    return bytes(result)


def game_archive(path):
    entries = {"main": executable(), "sdk": executable(), "main.npdm": b"META" + b"\0" * 252}
    count = len(entries)
    pool = b"".join(name.encode() for name in entries)
    pool_offset = 48 + 64 + 24 + 80 * count + 4 * count
    toc = bytearray(pool_offset + len(pool))
    struct.pack_into("<IIQQQQQ", toc, 0, 0x01434F54, 1, 1, count, pool_offset, len(pool), 0)
    struct.pack_into("<QIIII", toc, 48, TITLE, 0, 0, 0, 1)
    struct.pack_into("<IIIIQ", toc, 112, 0, 0, 0, count, 0)
    data_offset = 128 + len(toc)
    payload = bytearray()
    name_offset = 0
    for index, (name, content) in enumerate(entries.items()):
        struct.pack_into("<IIQQQ32sB", toc, 136 + 80 * index, name_offset, len(name), len(content),
                         data_offset + len(payload), len(content), hashlib.sha256(content).digest(), 0)
        struct.pack_into("<I", toc, 136 + 80 * count + 4 * index, index + 1)
        payload.extend(content)
        name_offset += len(name)
    toc[pool_offset:] = pool
    header = bytearray(128)
    struct.pack_into("<4sHHQQ", header, 0, b"NUP\x01", 128, 1, 128, len(toc))
    header[24:56] = hashlib.sha256(toc).digest()
    struct.pack_into("<QQI", header, 56, data_offset, data_offset + len(payload), 1)
    path.write_bytes(header + toc + payload)


class ModuleTests(unittest.TestCase):
    def test_segment_normalization_checks_hashes_and_layout(self):
        for compress in (False, True):
            raw = executable(compress)
            before = inspect_nso("test", raw, FIRST_ADDRESS)
            normalized = normalize_module(raw)
            after = inspect_nso("test", normalized, FIRST_ADDRESS)
            self.assertEqual(before.build_id, after.build_id)
            self.assertEqual(before.mapped_size, after.mapped_size)
            self.assertTrue(all(item["codec"] == "stored" for item in after.segments))
            corrupted = bytearray(raw)
            corrupted[160] ^= 1
            with self.assertRaisesRegex(ArchiveError, "checksum"):
                normalize_module(bytes(corrupted))

    def test_module_ranges_are_validated(self):
        raw = bytearray(executable())
        struct.pack_into("<I", raw, 16, len(raw) + 1)
        with self.assertRaises(ArchiveError):
            inspect_nso("test", raw, FIRST_ADDRESS)

    def test_independent_preparation_is_repeatable_and_detects_modified_input(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            archive = root / "synthetic.nup"
            game_archive(archive)
            prepared = prepare_game(archive, lambda *_: None, root)
            plan = json.loads((prepared / "build-plan.json").read_text())
            self.assertEqual([module["name"] for module in plan["modules"]], ["main", "sdk"])
            self.assertEqual(plan["status"], "prepared-not-playable")
            self.assertFalse(plan["capabilities"]["native_game_link"])
            self.assertEqual(prepare_game(archive, lambda *_: None, root), prepared)
            normalized = normalize_prepared(prepared)
            self.assertTrue((normalized / "sdk").is_file())
            (prepared / "exefs" / "main").write_bytes(b"modified")
            with self.assertRaises(ValueError):
                prepare_game(archive, lambda *_: None, root)
            self.assertFalse((root / "local" / "build.lock").exists())

    def test_imported_source_matches_pinned_hash_inventory(self):
        self.assertEqual(verify_engine_sources(), 671)
