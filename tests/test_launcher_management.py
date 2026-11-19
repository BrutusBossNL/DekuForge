import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import zipfile

from dekuforge.preferences import resolve_language, DEFAULTS
from dekuforge.saves import import_save, export_save
from dekuforge.releases import check_release


class ManagementTests(unittest.TestCase):
    def test_system_default_and_explicit_choice(self):
        self.assertEqual(DEFAULTS["language"], "system")
        with patch("dekuforge.preferences.system_language", return_value="de"):
            self.assertEqual(resolve_language("system"), "de")
            self.assertEqual(resolve_language("nl"), "nl")

    def test_save_roundtrip_retains_backup_and_other_slots(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            old, new = root / "old", root / "new"
            for folder, data in ((old, b"previous"), (new, b"imported")):
                (folder / "slot_00").mkdir(parents=True)
                (folder / "slot_00/progress.sav").write_bytes(data)
            (old / "slot_01").mkdir()
            (old / "slot_01/progress.sav").write_bytes(b"keep")
            export_save(new, root / "save.zip")
            backup = import_save(root / "save.zip", old)
            self.assertEqual((old / "slot_00/progress.sav").read_bytes(), b"imported")
            self.assertEqual((backup / "slot_00/progress.sav").read_bytes(), b"previous")
            self.assertEqual((old / "slot_01/progress.sav").read_bytes(), b"keep")
            self.assertEqual((new / "slot_00/progress.sav").read_bytes(), b"imported")

    def test_unsafe_zip_does_not_change_save(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            current = root / "current"
            (current / "slot_00").mkdir(parents=True)
            (current / "slot_00/progress.sav").write_bytes(b"keep")
            with zipfile.ZipFile(root / "bad.zip", "w") as archive:
                archive.writestr("../outside.sav", b"bad")
            with self.assertRaises(ValueError):
                import_save(root / "bad.zip", current)
            self.assertEqual((current / "slot_00/progress.sav").read_bytes(), b"keep")
            self.assertFalse((root / "outside.sav").exists())

    def test_import_into_existing_empty_profile(self):
        with tempfile.TemporaryDirectory() as temp:
            source, destination = Path(temp).resolve() / "source", Path(temp).resolve() / "destination"
            (source / "slot_00").mkdir(parents=True)
            (source / "slot_00/progress.sav").write_bytes(b"synthetic")
            destination.mkdir()
            backup = import_save(source, destination)
            self.assertTrue(backup.is_dir())
            self.assertEqual((destination / "slot_00/progress.sav").read_bytes(), b"synthetic")

    def test_release_channels_filter_drafts_and_preview(self):
        import json
        releases = [{"tag_name": "1", "published_at": "2026-01-01"},
                    {"tag_name": "2", "published_at": "2026-02-01", "prerelease": True},
                    {"tag_name": "3", "published_at": "2026-03-01", "draft": True}]
        from dekuforge.releases import INDEPENDENT_DESCRIPTOR
        for release in releases:
            release['assets'] = [{'name': INDEPENDENT_DESCRIPTOR}]
        with patch("dekuforge.releases.urlopen") as request, patch("dekuforge.releases.github_token", return_value=None):
            request.return_value.__enter__.return_value.read.return_value = json.dumps(releases).encode()
            self.assertEqual(check_release()["version"], "1")
            self.assertEqual(check_release(True)["version"], "2")
