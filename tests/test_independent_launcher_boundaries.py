"""Main's owned UI must never reactivate its excluded build/update backend."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from dekuforge import COMPONENTS
from dekuforge.mods import rebuild_code
from dekuforge.release_ui import ReleaseListUI
from dekuforge.ui import Launcher


class IndependentLauncherBoundaries(unittest.TestCase):
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
        self.assertEqual(app.release_status, 'independent_backend_incomplete')

    def test_release_rebuild_cannot_use_old_backend(self):
        app = self.fake()
        ReleaseListUI.rebuild_current_release(app)
        self.assertEqual(app.release_status, 'independent_backend_incomplete')

    def test_code_mod_rebuild_rejects_before_accessing_library(self):
        with self.assertRaisesRegex(ValueError, 'independent_backend_incomplete'):
            rebuild_code(None, None, None)
