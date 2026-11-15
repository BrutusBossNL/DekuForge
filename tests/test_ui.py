import os
from pathlib import Path
import tempfile
import time
import tkinter as tk
import unittest
from unittest.mock import Mock, patch

from run_launcher import prepare_tk
from dekuforge.i18n import LANGUAGES
from dekuforge.ui import Launcher


@unittest.skipUnless(os.name == "nt", "Windows desktop integration")
class LauncherWorkflowTests(unittest.TestCase):
    def setUp(self):
        prepare_tk()
        self.temporary = tempfile.TemporaryDirectory()
        self.folder = Path(self.temporary.name)
        current = self.folder / "current"
        current.mkdir()
        self.game = current / "game.exe"
        self.game.touch()
        self.settings = {"executable": str(self.game), "language": "en", "hide_playing": True}
        self.load = patch("dekuforge.ui.load_settings", return_value=self.settings)
        self.save = patch("dekuforge.ui.update_settings")
        self.project = patch("dekuforge.ui.ROOT", self.folder)
        self.load.start()
        self.save_mock = self.save.start()
        self.project.start()
        self.root = tk.Tk()
        self.root.withdraw()
        self.app = Launcher(self.root)

    def tearDown(self):
        self.root.destroy()
        self.project.stop()
        self.save.stop()
        self.load.stop()
        self.temporary.cleanup()

    def test_navigation_and_language_preserve_wizard_and_logs_in_one_window(self):
        self.app.source = str(self.folder / "own.nup")
        self.app.destination = str(self.folder / "new")
        self.app.step = 2
        self.app.log_lines = ["Keep this build log\n"]
        self.app.progress.begin()
        for language in LANGUAGES:
            self.app.set_language(language)
            for page in ("settings", "home", "build"):
                self.app.navigate(page)
                self.root.update_idletasks()
            self.assertEqual(self.app.step, 2)
            self.assertEqual(self.app.log_lines, ["Keep this build log\n"])
            self.assertIn("Keep this build log", self.app.log_widget.get("1.0", "end"))
            self.assertFalse(any(isinstance(widget, tk.Toplevel) for widget in self.root.winfo_children()))
        self.app.progress.finish()

    def test_rendered_logo_contains_project_gold_and_preserves_wide_shape(self):
        images = [child.image for child in self.app.sidebar.winfo_children() if hasattr(child, "image")]
        self.assertEqual(len(images), 1)
        logo = images[0]
        self.assertGreater(logo.width() / logo.height(), 1.8)
        colors = [logo.get(x, y) for x in range(0, logo.width(), 5) for y in range(0, logo.height(), 5)]
        self.assertTrue(any(r > 150 and g > 100 and b < 130 for r, g, b in colors))

    def test_game_launch_hides_and_restores_same_window(self):
        process = Mock()
        process.poll.return_value = None
        with patch("dekuforge.ui.launch", return_value=process) as start:
            self.app.play()
            start.assert_called_once_with(str(self.game))
            self.assertEqual(self.root.state(), "withdrawn")
            process.poll.return_value = 0
            process.returncode = 0
            self.app.tick()
            self.assertIsNone(self.app.process)
            self.assertEqual(self.root.state(), "normal")

    def test_failed_build_keeps_installation_and_records_selected_destination(self):
        source = self.folder / "own.nup"
        source.write_bytes(b"NUP\x01" + b"\0" * 124)
        destination = self.folder / "new"
        self.app.source, self.app.destination, self.app.step = str(source), str(destination), 2
        self.app.navigate("build")
        with patch("dekuforge.ui.build_independent", side_effect=RuntimeError("Known test failure")) as build:
            self.app.start_build()
            deadline = time.monotonic() + 3
            while self.app.progress.active and time.monotonic() < deadline:
                self.root.update()
                self.app.tick()
            self.assertFalse(self.app.progress.active)
            self.assertEqual(self.app.executable, str(self.game))
            self.assertIsNone(self.app.result)
            self.assertEqual(build.call_args.kwargs["destination"], destination)
            self.assertIn("Known test failure", self.app.log_path.read_text())
            self.assertFalse(destination.exists())
