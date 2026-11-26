import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from dekuforge import recomplauncher as managed
from dekuforge.core import ROOT


class RecompLauncherTests(unittest.TestCase):
    def test_managed_setup_reuses_the_same_copy_and_writes_receipt_only_after_success(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(managed, "ROOT", Path(folder).resolve()):
            receipt = managed.ROOT / "ready.json"
            archive = SimpleNamespace(index_sha256="a" * 64, path=managed.ROOT / "local-copy.nup", size=123)
            with (patch.object(managed, "input_archive", return_value=archive),
                  patch.object(managed.subprocess, "run") as tools,
                  patch("dekuforge.independent_engine.build", side_effect=RuntimeError("build failed")) as build):
                with self.assertRaisesRegex(RuntimeError, "build failed"):
                    managed.prepare(archive.path, receipt)
                self.assertFalse(receipt.exists())
                build.side_effect = None
                managed.prepare(archive.path, receipt)
                self.assertTrue(receipt.is_file())
                with patch.object(managed, "prepared_game", return_value=archive.path):
                    managed.prepare(archive.path, receipt)
                self.assertEqual(build.call_count, 2)
                self.assertEqual(tools.call_count, 2)

    def test_manifest_uses_the_same_executable_and_supported_nup(self):
        config = json.loads((ROOT / "recomplauncher.json").read_text(encoding="utf-8"))
        self.assertEqual(config["prepare"]["program"], ["DekuForge.exe"])
        self.assertEqual(config["start"]["program"], config["prepare"]["program"])
        self.assertEqual(config["prepare"]["args"], ["--recomp-prepare", "--game={input:game}"])
        self.assertEqual(config["start"]["args"], ["--recomp-play"])
        self.assertEqual(config["inputs"][0]["formats"], [{"type": "file", "extensions": ["nup"]}])
        self.assertIn(config["inputs"][0]["check"]["nup_build_id"],
                      (ROOT / "dekuforge/boot_profile.py").read_text(encoding="utf-8"))
        self.assertEqual(config["prepare"]["done"], ["{data}/dekuforge-ready.json"])
        self.assertEqual(config["config"][0]["file"], [{"path": "{data}/hookshot_options.ini"}])
