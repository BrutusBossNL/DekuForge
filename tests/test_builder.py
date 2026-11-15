from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import PropertyMock, patch

from dekuforge.builder import Backend, output_directory, run_build, validate_nup
from dekuforge.core import load_settings, save_installation, update_settings


class BuilderTests(unittest.TestCase):
    def test_selection_rejects_missing_empty_or_wrong_extension(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "empty.nup"
            path.touch()
            for value in ("", str(path), str(path.with_suffix(".zip"))):
                with self.assertRaises(ValueError):
                    validate_nup(value)

    def test_settings_keep_nup_when_game_selection_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            settings = root / "settings.json"
            exe = root / "game.exe"
            exe.touch()
            update_settings({"nup": "private input.nup", "backend": "external"}, settings)
            save_installation(str(exe), settings)
            self.assertEqual(load_settings(settings)["nup"], "private input.nup")

    def test_never_reuses_unowned_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            output = root / "build" / "game"
            output.mkdir(parents=True)
            saved = output / "save.dat"
            saved.write_text("preserve me")
            with self.assertRaises(ValueError):
                output_directory(root)
            self.assertEqual(saved.read_text(), "preserve me")

    def test_backend_version_cannot_escape_installation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "app").mkdir()
            (root / "app" / "current.txt").write_text("../outside")
            with self.assertRaises(ValueError):
                _ = Backend(root).kit

    def test_check_build_and_failure_with_real_subprocess(self):
        # A tiny original test backend exercises the process boundary. It never
        # reads game contents and does not use the installed external runtime.
        with tempfile.TemporaryDirectory(prefix="deku forge ") as folder:
            root = Path(folder)
            backend = root / "external"
            tools = backend / "app" / "test" / "tools"
            tools.mkdir(parents=True)
            (backend / "app" / "current.txt").write_text("test")
            compiler = backend / "toolchain" / "msys64" / "ucrt64" / "bin"
            compiler.mkdir(parents=True)
            for name in ("clang.exe", "lld.exe", "ninja.exe"):
                (compiler / name).touch()
            script = tools / "make_game.py"
            script.write_text(
                "import pathlib,sys\n"
                "print('@@{\"step\":\"check\"}', flush=True)\n"
                "if '--check' not in sys.argv:\n"
                " out=pathlib.Path(sys.argv[sys.argv.index('--out')+1])\n"
                " (out/'ocarina.exe').write_bytes(b'test artifact')\n"
            )
            nup = root / "own game.nup"
            nup.write_bytes(b"synthetic test input")
            workspace = root / "workspace"
            workspace.mkdir()
            messages = []
            emit = lambda kind, value: messages.append((kind, value))
            with patch.object(Backend, "python", new_callable=PropertyMock, return_value=Path(sys.executable)):
                self.assertIsNone(run_build(nup, backend, emit, check=True, jobs=1, workspace=workspace))
                self.assertFalse((workspace / "build").exists())
                self.assertIn("checked", [kind for kind, _ in messages])
                with patch("dekuforge.builder.MIN_FREE_BYTES", 0):
                    exe = run_build(nup, backend, emit, jobs=1, workspace=workspace)
                self.assertEqual(exe.read_bytes(), b"test artifact")
                self.assertFalse((workspace / "local" / "build.lock").exists())
                script.write_text("raise SystemExit(7)\n")
                with self.assertRaises(RuntimeError):
                    run_build(nup, backend, emit, check=True, jobs=1, workspace=workspace)
                self.assertFalse((workspace / "local" / "build.lock").exists())
                self.assertEqual(exe.read_bytes(), b"test artifact")

    def test_duplicate_build_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            nup = root / "own.nup"
            nup.write_bytes(b"test")
            (root / "local").mkdir()
            lock = root / "local" / "build.lock"
            lock.write_text("another process")
            with patch.object(Backend, "validate"):
                with self.assertRaisesRegex(ValueError, "al een DekuForge"):
                    run_build(nup, root, lambda *_: None, check=True, jobs=1, workspace=root)
            self.assertEqual(lock.read_text(), "another process")

    def test_low_disk_space_does_not_create_game_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            nup = root / "own.nup"
            nup.write_bytes(b"test")
            with patch.object(Backend, "validate"), patch("dekuforge.builder.MIN_FREE_BYTES", 10 ** 30):
                with self.assertRaisesRegex(ValueError, "vrije ruimte"):
                    run_build(nup, root, lambda *_: None, jobs=1, workspace=root)
            self.assertFalse((root / "build").exists())
            self.assertFalse((root / "local" / "build.lock").exists())
