from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from dekuforge.engine import build_independent


class IndependentBuildFailureTests(unittest.TestCase):
    def test_unsupported_sdk_stops_before_creating_or_selecting_installation(self):
        with tempfile.TemporaryDirectory() as folder:
            workspace = Path(folder)
            current = workspace / "current"
            current.mkdir()
            game = current / "game.exe"
            game.write_bytes(b"unchanged working game")
            target = workspace / "new"
            prepared = workspace / "prepared"
            with (patch("dekuforge.engine.load_installation", return_value=str(game)),
                  patch("dekuforge.engine.prepare_game", return_value=prepared),
                  patch("dekuforge.engine.normalize_prepared"),
                  patch("dekuforge.engine.generate_prepared", side_effect=RuntimeError("unsupported SDK instruction")) as generator):
                with self.assertRaisesRegex(RuntimeError, "unsupported SDK"):
                    build_independent("own.nup", Mock(), workspace=workspace, destination=target)
                self.assertEqual(generator.call_count, 1)
                self.assertEqual(generator.call_args.kwargs["modules"], "sdk")
            self.assertEqual(game.read_bytes(), b"unchanged working game")
            self.assertFalse(target.exists())
