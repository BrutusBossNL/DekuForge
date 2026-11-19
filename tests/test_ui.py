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
    def test_source_only_preview_links_to_github_without_installing(self):
        version = "v0.4.0-preview.1"
        self.app.releases = [{"version": version, "preview": True, "installable": False, "notes": "Source preview"}]
        self.app.selected_release = version
        self.app.navigate("updates")
        self.assertEqual(self.app.release_button.cget("text"), self.app.t("release_action_github"))
        self.assertIn(self.app.t("release_external_help"), self.app.release_notes.get("1.0", "end"))
        row = self.app.release_list.selection()[0]
        self.assertEqual(self.app.release_list.item(row, "values")[-1], self.app.t("release_external"))
        with (patch("dekuforge.release_ui.webbrowser.open", return_value=True) as browser,
              patch.object(self.app, "install_selected_release") as install):
            self.app.release_button.invoke()
            browser.assert_called_once_with("https://github.com/BrutusBossNL/DekuForge/releases/tag/" + version)
            install.assert_not_called()

    def test_source_only_preview_does_not_block_automatic_stable_update(self):
        self.app.preferences.update(update_channel="preview", auto_update=True)
        self.app.events.put(("release", ("preview", [
            {"version": "v0.4.0-preview.1", "installable": False},
            {"version": "v0.3.0", "installable": True},
        ])))
        with (patch("dekuforge.ui.__version__", "0.2.1"),
              patch.object(self.app, "install_selected_release") as install):
            self.app.tick()
        install.assert_called_once_with(automatic=True)
        self.assertEqual(self.app.selected_release, "v0.3.0")

    def wait_for_mods(self):
        deadline = time.monotonic() + 5
        while self.app.mods_busy and time.monotonic() < deadline:
            self.root.update()
            self.app.tick()
        self.assertFalse(self.app.mods_busy)

    def test_mod_import_toggle_and_order_in_the_single_window(self):
        import zipfile
        source = self.folder/'Test pack.zip'
        with zipfile.ZipFile(source, 'w') as archive:
            archive.writestr('Wrapper/romfs/Actor/example.txt', b'synthetic mod')
        self.app.navigate('mods')
        self.root.update_idletasks()
        self.wait_for_mods()
        with patch('dekuforge.game_updates.game_running', return_value=False):
            self.app.mods_work('import', str(source))
            self.wait_for_mods()
            self.assertEqual(len(self.app.mods_entries), 1)
            self.assertFalse(self.app.mods_entries[0].enabled)
            self.app.mod_selected = 'Test pack'
            self.app.modify_mod('toggle')
            self.wait_for_mods()
        self.assertTrue(self.app.mods_entries[0].enabled)
        self.assertIn('mods_order = Test pack', (self.game.parent/'nx2navi.ini').read_text())
        for language in LANGUAGES:
            self.app.set_language(language)
            self.app.navigate('mods')
            self.root.update_idletasks()
            self.assertEqual(self.app.mod_toggle_button.cget('text'), self.app.t('mods_disable'))
        self.assertFalse(any(isinstance(w, tk.Toplevel) for w in self.root.winfo_children()))

    def test_play_waits_for_mod_preparation_and_changed_code_prevents_launch(self):
        folder = self.game.parent/'mods/Code/exefs'
        folder.mkdir(parents=True)
        (folder/'example.pchtxt').write_text('synthetic code patch')
        with patch('dekuforge.game_updates.game_running', return_value=False), patch('dekuforge.ui.launch') as launch:
            self.app.play()
            self.wait_for_mods()
            launch.assert_not_called()
        self.assertEqual(self.app.page, 'mods')
        self.assertEqual(self.app.mods_status, self.app.t('mods_rebuild_needed'))

    def test_romfs_mod_configuration_is_ready_before_process_launch(self):
        folder = self.game.parent/'mods/Textures/romfs/Actor'
        folder.mkdir(parents=True)
        (folder/'sample.txt').write_bytes(b'synthetic asset')
        process = Mock(pid=123)
        process.poll.return_value = None
        def launch(_):
            self.assertIn('mods_order = Textures', (self.game.parent/'nx2navi.ini').read_text())
            return process
        with patch('dekuforge.game_updates.game_running', return_value=False), patch('dekuforge.ui.launch', side_effect=launch) as start:
            self.app.play()
            self.wait_for_mods()
            start.assert_called_once_with(str(self.game))
        self.assertIs(self.app.process, process)

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
        self.assertEqual(len(proof["mod_screens"]), 5)
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

    def test_update_failure_opens_prefilled_review_form_without_submitting(self):
        from dekuforge.update_package import atomic_json
        from dekuforge.update_status import pending_result
        atomic_json(self.folder/'local/update-result.json', {'success': False,
            'release': 'v0.3.0-preview.2', 'error': 'Synthetic update rollback', 'job': 'a'*32})
        self.app.update_notice = pending_result(self.folder)
        self.app.show_update_result()
        self.assertEqual(self.app.page, 'updates')
        # No collection or network work is necessary to verify the form wiring.
        with patch.object(self.app, 'prepare_report'), patch('dekuforge.reports.submit') as submit:
            self.app.report_update_failure()
            self.assertEqual(self.app.page, 'report')
            self.assertIn('v0.3.0-preview.2', self.app.report_draft['title'])
            self.assertIn('Synthetic update rollback', self.app.report_draft['details'])
            self.assertTrue(self.app.report_draft['include_logs'])
            self.assertEqual(self.app.report_incident['kind'], 'application_update')
            submit.assert_not_called()
        self.app.dismiss_update_result()
        self.assertIsNone(pending_result(self.folder))

    def test_successful_update_is_shown_before_automatic_game_rebuild(self):
        self.app.update_notice = {'success': True, 'release': 'v0.3.0-preview.2', 'id': 'test'}
        self.app.show_update_result()
        self.assertEqual(self.app.page, 'updates')
        with patch('dekuforge.ui.run_rebuild') as rebuild:
            self.app.resume_game_update()
            rebuild.assert_not_called()
        self.app.dismiss_update_result()
        self.assertIsNone(self.app.update_notice)

    def test_release_list_shows_notes_installed_status_and_contextual_actions(self):
        from dekuforge import __version__
        self.app.releases = [{'version': 'v9.0.0', 'preview': True, 'notes': '# New release\nTest details', 'installable': True},
            {'version': 'v0.2.0', 'preview': False, 'notes': 'Stable notes', 'installable': True}]
        self.app.navigate('updates')
        self.assertEqual(len(self.app.release_rows), 3)
        for version, expected, notes in (('v9.0.0','release_action_update','Test details'),
                                         ('v0.2.0','release_action_downgrade','Stable notes'),
                                         ('v'+__version__,'release_action_rebuild',self.app.t('release_notes_empty'))):
            index = next(i for i,row in enumerate(self.app.release_rows) if row['version'] == version)
            self.app.release_list.selection_set(str(index))
            self.app.select_release_row()
            self.assertEqual(self.app.selected_release, version)
            self.assertEqual(self.app.release_button.cget('text'), self.app.t(expected))
            self.assertIn(notes, self.app.release_notes.get('1.0','end'))
        values = self.app.release_list.item(str(index), 'values')
        self.assertEqual(values[-1], self.app.t('release_current'))
        with patch.object(self.app, 'install_selected_release') as install, patch.object(self.app, 'rebuild_current_release') as rebuild:
            self.app.perform_release_action()
            rebuild.assert_called_once()
            install.assert_not_called()

    def test_current_release_rebuild_queues_separate_build_identity(self):
        source = self.folder/'own.nup'
        source.write_bytes(b'synthetic input')
        self.app.source = str(source)
        with patch.object(self.app, 'resume_game_update') as rebuild:
            self.app.rebuild_current_release()
            first = json.loads((self.folder/'local/pending-game-update.json').read_text())
            self.app.rebuild_current_release()
            second = json.loads((self.folder/'local/pending-game-update.json').read_text())
        self.assertNotEqual(first['build_fingerprint'], second['build_fingerprint'])
        self.assertTrue(first['requires_rebuild'])
        rebuild.assert_called_with(manual=True)
        self.assertTrue(self.game.is_file())

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
