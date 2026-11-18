import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from dekuforge.build_library import BuildLibrary


class BuildLibraryTests(unittest.TestCase):
    def test_already_removed_owned_build_is_unregistered_without_marker_access(self):
        entry=self.library.register(self.exe,owned=True)
        import shutil
        shutil.rmtree(self.folder)
        self.assertIsNone(self.library.delete(entry["id"]))
        self.assertEqual(self.library.entries(),[])

    def test_refresh_prunes_removed_owned_builds_and_keeps_external_records(self):
        owned=self.library.register(self.exe,owned=True)
        import shutil
        shutil.rmtree(self.folder)
        external={**owned,"id":"external","owned":False}
        self.library.write([owned,external])
        self.assertEqual(self.library.prune_missing(),[external])

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

    def test_independent_user_and_legacy_profiles_both_survive_retention(self):
        user = self.folder/'user/save'/('f'*32)/'slot_00'
        user.mkdir(parents=True)
        (user/'progress.sav').write_bytes(b'independent save')
        entry = self.library.register(self.exe, owned=True)
        backup = self.library.delete(entry['id'], keep_saves=True)
        self.assertEqual((backup/'profile/save/user/slot_00/progress.sav').read_bytes(), b'keep me')
        self.assertEqual((backup/'user/save'/('f'*32)/'slot_00/progress.sav').read_bytes(), b'independent save')

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

    def test_completed_stable_build_is_discovered_without_selecting_or_changing_saves(self):
        stable = self.root / "build" / "stable"
        stable.mkdir()
        executable = stable / "DekuForgeGame.exe"
        executable.write_bytes(b"synthetic")
        (stable / ".dekuforge-stable-build").touch()
        (stable / "dekuforge-build-info.json").write_text(json.dumps({
            "engine_version":"0.10.1", "game_version":"1.1.1"}),encoding="utf-8")
        entries = self.library.discover()
        self.assertEqual(len(entries),1)
        self.assertEqual(entries[0]["version"],"0.10.1 / 1.1.1")
        self.assertTrue(entries[0]["owned"])
        self.assertEqual((self.profile / "progress.sav").read_bytes(),b"keep me")
        self.assertFalse((self.root / "local/settings.json").exists())
