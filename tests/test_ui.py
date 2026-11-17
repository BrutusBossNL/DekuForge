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
        self.addCleanup(self.temporary.cleanup)
        for dialog in ("showerror", "showwarning", "showinfo", "askyesno"):
            guard = patch("dekuforge.ui.messagebox." + dialog,
                          side_effect=AssertionError("Unexpected modal dialog: " + dialog))
            guard.start()
            self.addCleanup(guard.stop)
        self.folder = Path(self.temporary.name).resolve()
        current = self.folder / "current"
        current.mkdir()
        self.game = current / "game.exe"
        self.game.touch()
        self.settings = {"executable": str(self.game), "language": "en", "hide_playing": True, "check_updates": False}
        self.load = patch("dekuforge.ui.load_settings", return_value=self.settings)
        self.save = patch("dekuforge.ui.update_settings")
        self.project = patch("dekuforge.ui.ROOT", self.folder)
        self.load.start()
        self.addCleanup(self.load.stop)
        self.save_mock = self.save.start()
        self.addCleanup(self.save.stop)
        self.project.start()
        self.addCleanup(self.project.stop)
        self.root = tk.Tk()
        self.addCleanup(self.root.destroy)
        self.root.withdraw()
        self.app = Launcher(self.root)

    def test_navigation_and_language_preserve_wizard_and_logs_in_one_window(self):
        self.app.source = str(self.folder / "own.nup")
        self.app.destination = str(self.folder / "new")
        self.app.step = 2
        self.app.log_lines = ["Keep this build log\n"]
        self.app.progress.begin()
        for language in LANGUAGES:
            self.app.set_language(language)
            for page in ("settings", "updates", "saves", "home", "build"):
                self.app.navigate(page)
                self.root.update_idletasks()
            self.assertEqual(self.app.step, 2)
            self.assertEqual(self.app.log_lines, ["Keep this build log\n"])
            self.assertIn("Keep this build log", self.app.log_widget.get("1.0", "end"))
            self.assertFalse(any(isinstance(widget, tk.Toplevel) for widget in self.root.winfo_children()))
        self.app.progress.finish()

    def test_automatic_install_is_opt_in_and_failed_release_does_not_loop(self):
        import json
        self.assertFalse(self.app.preferences["auto_update"])
        self.app.toggle_auto_update()
        self.assertTrue(self.app.preferences["auto_update"])
        self.save_mock.assert_called_with({"auto_update":True})
        path=self.folder/"local/update-result.json";path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps({"success":False,"release":"v0.3.0"}),encoding="utf-8")
        self.assertFalse(self.app.automatic_update_allowed({"version":"v0.3.0"}))
        self.assertTrue(self.app.automatic_update_allowed({"version":"v0.3.1"}))

    def test_management_controls_fit_minimum_window(self):
        self.root.geometry("960x700")
        self.root.deiconify()
        def buttons(widget):
            for child in widget.winfo_children():
                if isinstance(child, tk.Button):
                    yield child
                yield from buttons(child)
        for language in LANGUAGES:
            self.app.set_language(language)
            for page in ("settings", "updates", "saves", "home"):
                self.app.navigate(page)
                self.root.update_idletasks()
                for button in buttons(self.app.content):
                    self.assertLessEqual(button.winfo_rooty() + button.winfo_height(),
                                         self.root.winfo_rooty() + self.root.winfo_height(),
                                         (language, page, button.cget("text")))

    def test_rendered_logo_contains_project_gold_and_preserves_wide_shape(self):
        images = [child.image for child in self.app.sidebar.winfo_children() if hasattr(child, "image")]
        self.assertEqual(len(images), 1)
        logo = images[0]
        self.assertGreater(logo.width() / logo.height(), 1.8)
        colors = [logo.get(x, y) for x in range(0, logo.width(), 5) for y in range(0, logo.height(), 5)]
        self.assertTrue(any(r > 150 and g > 100 and b < 130 for r, g, b in colors))

    def test_action_cards_pointer_keyboard_and_disabled_play(self):
        from dekuforge.theme import GOLD, BORDER
        self.root.deiconify()
        self.root.update()
        play, update, build = self.app.home_cards
        play.event_generate("<Enter>")
        self.assertEqual(play.cget("highlightbackground"), GOLD)
        play.event_generate("<Leave>")
        self.assertEqual(play.cget("highlightbackground"), BORDER)
        play.focus_force()
        self.root.update()
        self.assertEqual(play.cget("highlightbackground"), GOLD)
        update.focus_force()
        self.root.update()
        update.event_generate("<Return>")
        self.assertEqual(self.app.page, "updates")
        self.app.executable = ""
        self.app.navigate("home")
        with patch("dekuforge.ui.launch") as start:
            self.app.home_cards[0].activate()
            start.assert_not_called()
        self.app.home_cards[2].activate()
        self.assertEqual(self.app.page, "build")

    def test_intro_cancel_restores_layout_and_home_cards(self):
        from dekuforge.home_cards import animate_intro
        animate_intro(self.app)
        self.assertIsNotNone(self.app.intro_cover)
        self.assertEqual(self.app.intro_cover.reveal, 0)
        backdrop = self.app.intro_cover._image
        self.assertGreater(backdrop.get(backdrop.width()//2, backdrop.height()//2)[1], backdrop.get(0, 0)[1])
        frames = self.app.intro_cover._logo_frames
        self.assertEqual(frames[0].width(), round(self.app.logo_label.image.width() * 1.35))
        self.assertEqual(frames[-1].width(), self.app.logo_label.image.width())
        self.assertNotEqual(self.app.logo_label.cget("image"), str(self.app.logo_label.image))
        self.app.navigate("settings")
        self.assertIsNone(self.app.intro_cover)
        self.assertEqual(self.app.logo_label.cget("image"), str(self.app.logo_label.image))
        self.assertEqual(self.app.sidebar.winfo_manager(), "grid")
        self.app.navigate("home")
        self.app.animate_cards()
        self.app.navigate("saves")
        self.assertIsNone(self.app.card_job)

    def test_popdown_and_navigation_use_brand_colors(self):
        from tkinter import ttk
        from dekuforge.theme import PANEL, GOLD, TEXT
        self.app.navigate("settings")
        self.root.deiconify()
        self.root.update()
        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)
        combo = next(w for w in descendants(self.app.content) if isinstance(w, ttk.Combobox))
        popup = self.root.tk.call("ttk::combobox::PopdownWindow", str(combo))
        listing = str(popup) + ".f.l"
        self.assertEqual(self.root.tk.call(listing, "cget", "-background"), PANEL)
        self.assertEqual(self.root.tk.call(listing, "cget", "-foreground"), TEXT)
        self.assertEqual(self.root.tk.call(listing, "cget", "-selectbackground"), GOLD)
        button = next(w for w in self.app.sidebar.winfo_children() if isinstance(w, tk.Button))
        normal = button.cget("background")
        button.event_generate("<Enter>")
        self.assertNotEqual(button.cget("background"), normal)
        button.event_generate("<Leave>")
        self.assertEqual(button.cget("background"), normal)

    def test_delete_cancel_leaves_build_and_activation_selects_executable(self):
        self.app.open_library()
        with patch("dekuforge.ui.save_installation", return_value=self.game) as select:
            self.app.activate_build()
            select.assert_called_once_with(str(self.game))
        with patch("dekuforge.ui.messagebox.askyesno", return_value=False), patch.object(self.app.library, "delete") as delete:
            self.app.delete_build()
            delete.assert_not_called()
        self.assertTrue(self.game.exists())

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
