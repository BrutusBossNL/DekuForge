import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from dekuforge import stable_engine


class StableEngineTests(unittest.TestCase):
    def test_snapshot_retains_terms_and_source_identity_and_omits_game_outputs(self):
        archive = io.BytesIO()
        with zipfile.ZipFile(archive,"w") as z:
            z.writestr("VERSION","0.10.1")
            z.writestr("LICENSE-ADDITIONS","retained source terms")
            z.writestr("runtime/gfx_window_win.c",'const char *title="NX2navi Recomp";')
            z.writestr("tools/make_game.py", "EXE_NAME = 'ocarina.exe'\n")
            z.writestr("generated/main.c","must never be staged")
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            with patch.object(stable_engine,"ROOT",root), patch.object(stable_engine.subprocess,"check_output",return_value=archive.getvalue()) as git:
                result=stable_engine.stage_stable()
            self.assertIn(stable_engine.REVISION,git.call_args.args[0])
            self.assertEqual((result/"VERSION").read_text(),"0.10.1")
            self.assertEqual((result/"LICENSE-ADDITIONS").read_text(),"retained source terms")
            self.assertIn("DekuForge",(result/"runtime/gfx_window_win.c").read_text())
            self.assertFalse((result/"generated").exists())

    def test_nonowned_build_destination_is_refused_before_source_access(self):
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder).resolve()
            keep=output/"save.dat";keep.write_bytes(b"preserve")
            with patch.object(stable_engine,"stage_stable") as source:
                with self.assertRaises(ValueError):
                    stable_engine.build_stable("own.nup",lambda *args:None,output)
                source.assert_not_called()
            self.assertEqual(keep.read_bytes(),b"preserve")
