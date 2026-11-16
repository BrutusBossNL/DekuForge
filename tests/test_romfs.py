import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from dekuforge.nup import Archive, ArchiveError
from dekuforge.romfs import build_romfs, decode_index, encode_index
from test_modules import game_archive


class RomfsTests(unittest.TestCase):
    def test_binary_index_rejects_bad_names_order_and_bounds(self):
        records = [{"path": "a/file.bin", "offset": 0, "size": 4},
                   {"path": "z.bin", "offset": 16, "size": 2}]
        encoded = encode_index(records, 18)
        self.assertEqual(decode_index(encoded, 18), records)
        for path in ("../escape", "/absolute", "bad\\name", "a//b", "C:stream", "bad\nname"):
            with self.assertRaises(ArchiveError):
                encode_index([{"path": path, "offset": 0, "size": 1}], 1)
        with self.assertRaises(ArchiveError):
            encode_index(list(reversed(records)), 18)
        with self.assertRaises(ArchiveError):
            decode_index(encoded, 3)
        with self.assertRaises(ArchiveError):
            decode_index(encoded[:-1], 18)

    def test_build_verify_and_reuse(self):
        with tempfile.TemporaryDirectory() as folder, patch("dekuforge.romfs.RESERVE", 0):
            root = Path(folder).resolve()
            source = root / "own.nup"
            game_archive(source)
            output = root / "image"
            build_romfs(source, output, lambda *_: None)
            manifest = json.loads((output / "index.json").read_text())
            image = (output / "romfs.bin").read_bytes()
            records = decode_index((output / "romfs-index.bin").read_bytes(), len(image))
            self.assertEqual(records, manifest["files"])
            self.assertEqual(hashlib.sha256(image).hexdigest(), manifest["romfs_sha256"])
            archive = Archive(source)
            package = archive.packages[0]
            members = dict(archive.tree(package.romfs))
            for record in records:
                expected = b"".join(archive.chunks(members[Path(record["path"])]))
                self.assertEqual(image[record["offset"]:record["offset"] + record["size"]], expected)
                self.assertEqual(record["offset"] % 16, 0)
            with patch.object(Archive, "chunks", side_effect=AssertionError("Do not extract completed input again")):
                self.assertEqual(build_romfs(source, output, lambda *_: None), output)
            self.assertFalse((output / ".romfs.lock").exists())

    def test_verified_checkpoint_survives_interruption(self):
        with tempfile.TemporaryDirectory() as folder, patch("dekuforge.romfs.RESERVE", 0):
            root = Path(folder).resolve()
            source = root / "own.nup"
            game_archive(source)
            output = root / "image"
            original = Archive.chunks
            def interrupted(archive, member, *args, **kwargs):
                if member.name == "main.npdm":
                    raise RuntimeError("Simulated interruption")
                yield from original(archive, member, *args, **kwargs)
            with patch.object(Archive, "chunks", interrupted):
                with self.assertRaisesRegex(RuntimeError, "Simulated"):
                    build_romfs(source, output, lambda *_: None, checkpoint_every=1)
            checkpoint = json.loads((output / "checkpoint.json").read_text())
            self.assertEqual(checkpoint["files"], 1)
            self.assertFalse((output / "index.json").exists())
            self.assertFalse((output / ".romfs.lock").exists())
            build_romfs(source, output, lambda *_: None, checkpoint_every=1)
            self.assertTrue((output / "index.json").is_file())

    def test_completed_image_recovers_manifest_after_interruption(self):
        with tempfile.TemporaryDirectory() as folder, patch("dekuforge.romfs.RESERVE", 0):
            root = Path(folder).resolve()
            source = root / "own.nup"
            game_archive(source)
            output = root / "image"
            build_romfs(source, output, lambda *_: None)
            image = output / "romfs.bin"
            before = image.stat().st_mtime_ns
            (output / "index.json").unlink()
            with patch.object(Archive, "chunks", side_effect=AssertionError("Image already assembled")):
                build_romfs(source, output, lambda *_: None)
            self.assertEqual(image.stat().st_mtime_ns, before)
            self.assertTrue((output / "index.json").is_file())

    def test_corrupt_source_cannot_be_committed_as_complete_image(self):
        with tempfile.TemporaryDirectory() as folder, patch("dekuforge.romfs.RESERVE", 0):
            root = Path(folder).resolve()
            source = root / "own.nup"
            game_archive(source)
            payload = bytearray(source.read_bytes())
            payload[-1] ^= 1
            source.write_bytes(payload)
            output = root / "image"
            with self.assertRaises(ArchiveError):
                build_romfs(source, output, lambda *_: None)
            self.assertFalse((output / "romfs.bin").exists())
            self.assertFalse((output / "index.json").exists())

    def test_existing_user_directory_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            source = root / "own.nup"
            game_archive(source)
            output = root / "existing"
            output.mkdir()
            saved = output / "save.dat"
            saved.write_bytes(b"preserve")
            with self.assertRaises(ValueError):
                build_romfs(source, output, lambda *_: None)
            self.assertEqual(saved.read_bytes(), b"preserve")
