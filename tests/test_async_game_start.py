from queue import Queue
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from dekuforge.ui import Launcher as App


class AsyncGameStartTests(unittest.TestCase):
    def app(self):
        return SimpleNamespace(executable='chosen.exe', mods_busy=False, events=Queue(),
                               t=lambda key: key, render=Mock(), show_error=Mock(), root=Mock())

    def test_game_and_mod_preparation_run_outside_ui_callback(self):
        app = self.app()
        with patch('dekuforge.ui.threading.Thread') as thread, patch('dekuforge.ui.launch') as launch:
            App.launch_ready(app)
            self.assertTrue(app.mods_busy)
            launch.assert_not_called()
            thread.return_value.start.assert_called_once()
            app.executable = 'another.exe'
            thread.call_args.kwargs['target']()
            launch.assert_called_once_with('chosen.exe')
            kind, payload = app.events.get_nowait()
            self.assertEqual(kind, 'game_started')
            self.assertEqual(payload[1], 'chosen.exe')
            app.root.withdraw.assert_not_called()

    def test_worker_failure_is_queued_for_main_thread(self):
        app = self.app()
        with patch('dekuforge.ui.threading.Thread') as thread, patch('dekuforge.ui.launch', side_effect=OSError('snapshot failed')):
            App.launch_ready(app)
            thread.call_args.kwargs['target']()
            kind, error = app.events.get_nowait()
            self.assertEqual(kind, 'game_start_failed')
            self.assertIsInstance(error, OSError)
            app.show_error.assert_not_called()
