from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from dekuforge.core import launch, load_installation, save_installation


class InstallationTests(unittest.TestCase):
    def test_corrupt_settings_do_not_prevent_startup(self):
        with tempfile.TemporaryDirectory() as folder:
            settings = Path(folder).resolve() / "settings.json"
            for data in ("broken", "[]", '{"executable":42}'):
                settings.write_text(data)
                self.assertEqual(load_installation(settings), "")

    def test_persistence_and_launch_preserve_installation_directory(self):
        with tempfile.TemporaryDirectory(prefix="deku forge ") as folder:
            executable = Path(folder).resolve() / "game with spaces.exe"
            executable.touch()
            settings = Path(folder).resolve() / "local" / "settings.json"
            save_installation(str(executable), settings)
            self.assertEqual(load_installation(settings), str(executable.resolve()))
            with patch("dekuforge.core.subprocess.Popen") as popen:
                launch(load_installation(settings))
                popen.assert_called_once_with([str(executable.resolve())],
                                              cwd=str(executable.parent.resolve()), shell=False)
            self.assertEqual(executable.read_bytes(), b"")

    def test_invalid_installation_is_not_saved_or_launched(self):
        with tempfile.TemporaryDirectory() as folder:
            settings = Path(folder).resolve() / "settings.json"
            with self.assertRaises(ValueError):
                save_installation(str(Path(folder).resolve() / "missing.exe"), settings)
            self.assertFalse(settings.exists())
            with patch("dekuforge.core.subprocess.Popen") as popen:
                with self.assertRaises(ValueError):
                    launch("")
                popen.assert_not_called()
