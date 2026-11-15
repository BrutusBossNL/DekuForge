import hashlib
from pathlib import Path
import struct
import tempfile
import unittest

from dekuforge.nup import Archive, ArchiveError
from dekuforge.native import prepare_archive


def fixture(path, name="hello.bin", payload=b"DekuForge test", codec=0, child=1):
    stored = payload
    if codec:
        from compression.zstd import compress
        stored = compress(payload)
    encoded = name.encode()
    pool_at = 48 + 64 + 24 + 80 + 4
    index_size = pool_at + len(encoded)
    data_at = 128 + index_size
    table = bytearray(index_size)
    struct.pack_into("<IIQQQQQ", table, 0, 0x01434F54, 1, 1, 1, pool_at, len(encoded), 0)
    struct.pack_into("<QIIII", table, 48, 0x1234, 0, 0, 0, 1)
    struct.pack_into("<IIIIQ", table, 112, 0, 0, 0, 1, 0)
    struct.pack_into("<IIQQQ32sB", table, 136, 0, len(encoded), len(payload), data_at,
                     len(stored), hashlib.sha256(payload).digest(), codec)
    struct.pack_into("<I", table, 216, child)
    table[pool_at:] = encoded
    header = bytearray(128)
    struct.pack_into("<4sHHQQ", header, 0, b"NUP\x01", 128, 1, 128, index_size)
    header[24:56] = hashlib.sha256(table).digest()
    struct.pack_into("<QQI", header, 56, data_at, data_at + len(stored), 1)
    path.write_bytes(header + table + stored)


class NupTests(unittest.TestCase):
    def test_stored_and_compressed_streams(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "test.nup"
            for codec in (0, 1):
                payload = b"a" * (3 * 1024 * 1024)
                fixture(path, payload=payload, codec=codec)
                archive = Archive(path)
                relative, member = next(archive.tree(0))
                self.assertEqual(str(relative), "hello.bin")
                self.assertEqual(b"".join(archive.chunks(member)), payload)

    def test_index_checksum_and_payload_checksum_are_separate(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "test.nup"
            fixture(path)
            contents = bytearray(path.read_bytes())
            contents[-1] ^= 1
            path.write_bytes(contents)
            archive = Archive(path)
            with self.assertRaisesRegex(ArchiveError, "checksum"):
                list(archive.chunks(archive.members[0]))
            contents[150] ^= 1
            path.write_bytes(contents)
            with self.assertRaisesRegex(ArchiveError, "index checksum"):
                Archive(path)

    def test_unsafe_names_and_directory_cycles(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "test.nup"
            for name in ("../escape", "NUL.bin", "file:stream", "bad\\path"):
                fixture(path, name=name)
                with self.assertRaises(ArchiveError):
                    Archive(path)
            fixture(path, child=0)
            archive = Archive(path)
            with self.assertRaises(ArchiveError):
                list(archive.tree(0))

    def test_native_check_and_extract_do_not_need_backend(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / "test.nup"
            fixture(path)
            messages = []
            summary = prepare_archive(path, lambda *item: messages.append(item), workspace=root)
            self.assertEqual(summary["files"], 1)
            self.assertFalse((root / "build").exists())
            output = prepare_archive(path, lambda *item: messages.append(item), extract=True, workspace=root)
            self.assertEqual(next(output.rglob("hello.bin")).read_bytes(), b"DekuForge test")
            self.assertTrue((output / "dekuforge-manifest.json").is_file())
            self.assertFalse((root / "local" / "build.lock").exists())
