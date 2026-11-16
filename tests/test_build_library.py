import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from dekuforge.build_library import BuildLibrary


class BuildLibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.library = BuildLibrary(self.root)
        self.folder = self.root / "build" / "one"
        self.folder.mkdir(parents=True)
        self.exe = self.folder / "game.exe"
        self.exe.write_bytes(b"synthetic")
        self.profile = self.folder / "profile" / "save" / "user" / "slot_00"
        self.profile.mkdir(parents=True)
        (self.profile / "progress.sav").write_bytes(b"keep me")

    def test_delete_preserves_profile_outside_build_and_other_installation(self):
        other = self.root / "build" / "two"
        other.mkdir()
        (other / "game.exe").write_bytes(b"other")
        second = self.library.register(other / "game.exe", owned=True)
        entry = self.library.register(self.exe, version="1.1.1", owned=True)
        backup = self.library.delete(entry["id"])
        self.assertFalse(self.folder.exists())
        self.assertEqual((backup / "save/user/slot_00/progress.sav").read_bytes(), b"keep me")
        self.assertEqual((other / "game.exe").read_bytes(), b"other")
        self.assertEqual([e["id"] for e in self.library.entries()], [second["id"]])

    def test_delete_without_retention_and_failed_backup(self):
        entry = self.library.register(self.exe, owned=True)
        with patch("dekuforge.build_library.shutil.copytree", side_effect=OSError("Disk full")):
            with self.assertRaises(OSError):
                self.library.delete(entry["id"])
        self.assertTrue(self.exe.is_file())
        self.assertEqual((self.profile / "progress.sav").read_bytes(), b"keep me")
        self.assertIsNone(self.library.delete(entry["id"], keep_saves=False))
        self.assertFalse(self.folder.exists())

    def test_external_installation_and_tampered_marker_are_protected(self):
        entry = self.library.register(self.exe)
        with self.assertRaises(ValueError):
            self.library.delete(entry["id"])
        self.library.write([])
        entry = self.library.register(self.exe, owned=True)
        (self.folder / ".dekuforge-build.json").write_text(json.dumps({"id": "other", "executable": "game.exe"}))
        with self.assertRaises(ValueError):
            self.library.delete(entry["id"])
        self.assertTrue(self.exe.is_file())

    def test_protects_dump_nested_build_and_project(self):
        entry = self.library.register(self.exe, dump=str(self.folder / "own.nup"), owned=True)
        with self.assertRaises(ValueError):
            self.library.delete(entry["id"])
        self.library.write([{**entry, "dump": ""}])
        nested = self.folder / "nested"
        nested.mkdir()
        (nested / "game.exe").touch()
        self.library.register(nested / "game.exe", owned=True)
        with self.assertRaises(ValueError):
            self.library.delete(entry["id"])
        for path in (self.root, self.root.parent, self.root / "local" / "test"):
            with self.assertRaises(ValueError):
                self.library.check_root(path)
        self.assertTrue(self.exe.is_file())
