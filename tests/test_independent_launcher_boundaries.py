"""Main's owned UI must never reactivate its excluded build/update backend."""
import unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from dekuforge import COMPONENTS
from dekuforge.mods import rebuild_code
from dekuforge.release_ui import ReleaseListUI
from dekuforge.ui import Launcher


class IndependentLauncherBoundaries(unittest.TestCase):
    def test_direct_legacy_update_api_cannot_bypass_ui_guard_or_rewrite_pending_state(self):
        from dekuforge.game_updates import run_rebuild, rebuild_pending
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve()
            pending=root/'local/pending-game-update.json'
            pending.parent.mkdir()
            pending.write_bytes(b'{"status":"pending"}')
            with patch('dekuforge.game_updates.build_stable') as excluded:
                for entry in (run_rebuild,rebuild_pending):
                    with self.assertRaisesRegex(RuntimeError,'disabled on the independent branch'):
                        entry(Mock(),root)
                excluded.assert_not_called()
            self.assertEqual(pending.read_bytes(),b'{"status":"pending"}')
            self.assertFalse((root/'local/build.lock').exists())

    def fake(self):
        return SimpleNamespace(page='home', t=lambda key: key, render=Mock())

    def test_branch_identity_keeps_updates_disabled(self):
        self.assertEqual(COMPONENTS['engine']['backend'], 'independent')
        self.assertFalse(COMPONENTS['launcher']['updates'])
        self.assertFalse(COMPONENTS['engine']['playable'])

    def test_update_actions_return_before_network_worker_or_install(self):
        app = self.fake()
        with patch('dekuforge.ui.list_releases') as fetch, patch('dekuforge.ui.prepare_release') as install:
            Launcher.check_updates(app)
            Launcher.install_selected_release(app)
        fetch.assert_not_called()
        install.assert_not_called()
        self.assertEqual(app.release_status, 'independent_updates_disabled')

    def test_pending_main_rebuild_is_not_resumed(self):
        app = self.fake()
        with patch('dekuforge.ui.run_rebuild') as rebuild:
            Launcher.resume_game_update(app, manual=True)
        rebuild.assert_not_called()
        app.render.assert_not_called()

    def test_release_rebuild_cannot_use_old_backend(self):
        app = self.fake()
        app.rebuild_independent_installation = Mock()
        app.resume_game_update = Mock()
        ReleaseListUI.rebuild_current_release(app)
        app.rebuild_independent_installation.assert_called_once_with()
        app.resume_game_update.assert_not_called()

    def test_code_mod_rebuild_rejects_before_accessing_library(self):
        with self.assertRaisesRegex(ValueError, 'independent_backend_incomplete'):
            rebuild_code(None, None, None)
