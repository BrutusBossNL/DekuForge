import os
import json
import subprocess
import sys
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
    def test_save_import_finds_old_installation_and_requires_confirmation(self):
        active = self.game.parent
        (active/'.dekuforge-stable-build').touch()
        destination = active/'profile/save'/('a'*32)
        destination.mkdir(parents=True)
        source = self.folder/'NX2navi/Play/profile/save'/('b'*32)
        (source/'slot_00').mkdir(parents=True)
        (source/'slot_00/progress.sav').write_bytes(b'synthetic old save')
        self.app.navigate('saves')
        self.assertEqual(self.app.save_folder,str(destination))
        with patch('dekuforge.ui.filedialog.askdirectory',return_value=str(self.folder/'NX2navi')):
            self.app.search_save_folder()
        deadline=time.monotonic()+3
        while self.app.save_busy and time.monotonic()<deadline:
            self.root.update();self.app.tick()
        self.assertEqual(self.app.save_source,str(source))
        self.assertFalse((destination/'slot_00').exists())
        with patch('dekuforge.ui.game_running',return_value=False), patch('dekuforge.ui.messagebox.askyesno',return_value=False), patch('dekuforge.ui.import_save') as copy:
            self.app.save_action('selected')
            copy.assert_not_called()
        with patch('dekuforge.ui.game_running',return_value=True), patch('dekuforge.ui.messagebox.askyesno') as confirm:
            self.app.save_action('selected')
            confirm.assert_not_called()
            self.assertEqual(self.app.save_status,self.app.t('save_close_game'))
        with patch('dekuforge.ui.game_running',return_value=False), patch('dekuforge.ui.messagebox.askyesno',return_value=True):
            self.app.save_action('selected')
            deadline=time.monotonic()+3
            while self.app.save_busy and time.monotonic()<deadline:
                self.root.update();self.app.tick()
        self.assertEqual((destination/'slot_00/progress.sav').read_bytes(),b'synthetic old save')
        self.assertEqual((source/'slot_00/progress.sav').read_bytes(),b'synthetic old save')
        self.assertEqual(len(list(destination.parent.glob(destination.name+'.backup-*'))),1)

    def test_setup_health_check_visits_all_languages_without_showing_a_window(self):
        source = Path(__file__).resolve().parents[1]
        script = """import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from run_launcher import prepare_tk
prepare_tk()
from dekuforge import ui
ui.ROOT = Path(sys.argv[2])
ui.load_settings = lambda: {'language':'en', 'check_updates':False}
sys.argv = ['run_launcher.py', '--self-test']
ui.main()
"""
        result = subprocess.run([sys.executable, "-c", script, str(source), str(self.folder)],
            capture_output=True, text=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        proof = json.loads((self.folder/"local/launcher-selftest.json").read_text())
        self.assertTrue(proof["success"])
        self.assertFalse(proof["window_was_mapped"])
        self.assertEqual(len(proof["screens"]), 40)
        self.assertEqual(len(proof["report_screens"]), 5)

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

    def test_page_panel_preserves_tk_root_method_and_releases_destroyed_images(self):
        self.app.navigate('settings')
        panel = self.app.page_panel
        self.assertTrue(callable(panel._root))
        self.assertIs(panel._root(), self.root)
        body = panel.body
        self.root.update_idletasks()
        self.app.navigate('home')
        self.assertIsNone(body._image)

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
            self.app.report_context={"metadata":{"system":{"os":"Windows 11 build test","cpu":"Intel Test CPU with 16 logical processors","ram_gib":32,"gpus":[{"model":"NVIDIA Test GPU","driver":"123.45"}]}},"logs":[]}
            for page in ("settings", "updates", "saves", "home", "report"):
                self.app.navigate(page)
                self.root.update_idletasks()
                for button in buttons(self.app.content):
                    if self.app.page_panel:
                        self.app.page_panel.reveal(button)
                        self.assertLessEqual(button.winfo_rootx()+button.winfo_width(),
                            self.app.page_panel.viewport.winfo_rootx()+self.app.page_panel.viewport.winfo_width(),
                            (language, page, button.cget("text")))
                    self.assertLessEqual(button.winfo_rooty() + button.winfo_height(),
                                         self.root.winfo_rooty() + self.root.winfo_height(),
                                         (language, page, button.cget("text")))

    def test_crashed_game_opens_report_without_submitting_anything(self):
        process=Mock(pid=123);process.poll.return_value=None
        with patch("dekuforge.ui.launch",return_value=process),patch("dekuforge.ui.reports.submit") as submit:
            self.app.play()
            self.app.report_context={"metadata":{},"logs":[]}
            process.poll.return_value=3221225477;process.returncode=3221225477
            self.app.tick()
            self.assertEqual(self.app.page,"report")
            self.assertEqual(self.app.report_incident["exit_code"],3221225477)
            self.assertIsNone(self.app.process)
            submit.assert_not_called()

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

    def test_navigation_keeps_background_viewport_and_readable_text(self):
        from dekuforge.theme import ArtworkLabel
        self.root.deiconify()
        self.root.update()
        expected = (self.app.backdrop.winfo_width(), self.app.backdrop.winfo_height())
        self.assertEqual(expected, (self.root.winfo_width(), self.root.winfo_height()))
        for page in ("settings", "saves", "build", "updates", "home"):
            self.app.navigate(page)
            self.root.update_idletasks()
            self.assertEqual((self.app.backdrop.winfo_width(), self.app.backdrop.winfo_height()), expected)
            text = self.app.label(self.app.content, "Readable status")
            if page != "home":
                self.assertIsNotNone(self.app.page_panel)
                self.assertEqual(self.app.content._opacity, .15)
            self.assertIsInstance(text, ArtworkLabel)
            text.destroy()

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

    def test_long_panel_scrolls_and_keyboard_focus_reveals_bottom_action(self):
        self.app.navigate("build")
        self.root.deiconify()
        self.root.update()
        panel = self.app.page_panel
        for i in range(25):
            self.app.label(self.app.content, f"Long page section {i}").pack(pady=8)
        action = self.app.button(self.app.content, "Last action", lambda: None)
        action.pack(pady=8)
        self.root.update()
        self.assertTrue(panel.scroll.winfo_manager())
        start = panel.viewport.yview()[0]
        panel.body.event_generate("<MouseWheel>", delta=-120)
        self.root.update()
        self.assertGreater(panel.viewport.yview()[0], start)
        panel.reveal(action)
        self.root.update_idletasks()
        self.assertGreaterEqual(action.winfo_rooty(), panel.viewport.winfo_rooty())
        self.assertLessEqual(action.winfo_rooty()+action.winfo_height(),
                             panel.viewport.winfo_rooty()+panel.viewport.winfo_height())

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
