from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from dekuforge.engine import build_independent
from dekuforge import COMPONENTS


class IndependentBuildFailureTests(unittest.TestCase):
    def test_stable_build_failure_preserves_active_installation_and_releases_lock(self):
        with tempfile.TemporaryDirectory() as folder:
            workspace = Path(folder).resolve()
            current = workspace / "current"
            current.mkdir()
            game = current / "game.exe"
            game.write_bytes(b"unchanged working game")
            target = workspace / "new"
            with (patch.dict(COMPONENTS['engine'], {'backend':'stable'}),
                  patch("dekuforge.engine.load_installation", return_value=str(game)),
                  patch("dekuforge.stable_engine.build_stable", side_effect=RuntimeError("stable compile failed")) as build):
                with self.assertRaisesRegex(RuntimeError, "stable compile failed"):
                    build_independent("own.nup", Mock(), workspace=workspace, destination=target)
                self.assertEqual(build.call_args.args[2], target)
            self.assertEqual(game.read_bytes(), b"unchanged working game")
            self.assertFalse(target.exists())
            self.assertFalse((workspace / "local/build.lock").exists())
