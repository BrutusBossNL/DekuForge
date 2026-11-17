import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from dekuforge.build_library import BuildLibrary


@unittest.skipUnless(os.name=="nt","Windows uninstaller")
class UninstallTests(unittest.TestCase):
    def fixture(self,base):
        root=base/"app";local=root/"local";local.mkdir(parents=True)
        (root/"DekuForge.exe").write_bytes(b"synthetic launcher")
        (local/"installation.json").write_text(json.dumps({"kind":"DekuForge"}),encoding="utf-8")
        (local/"installed-package.json").write_text(json.dumps({"sha256":{"DekuForge.exe":"fixture"}}),encoding="utf-8")
        game=root/"build/game";game.mkdir(parents=True);exe=game/"DekuForgeGame.exe";exe.write_bytes(b"synthetic game")
        (game/".dekuforge-stable-build").touch()
        profile=game/"profile/user/slot_00";profile.mkdir(parents=True);(profile/"progress.sav").write_bytes(b"save me")
        own=profile/"user-input.dat";own.write_bytes(b"NUP\1 original renamed input")
        archive=game/"original.nup";archive.write_bytes(b"NUP\1 original archive")
        external=base/"external-game";external.mkdir();(external/"game.exe").write_bytes(b"external keep")
        library=BuildLibrary(root);library.register(exe,dump=str(own),owned=True);library.register(external/"game.exe")
        (local/"settings.json").write_text(json.dumps({"nup":str(own)}),encoding="utf-8")
        tools=local/"build-tools";tools.mkdir();(tools/"compiler.exe").write_bytes(b"tool")
        return root,own,archive,external

    def run_uninstall(self,root,*args):
        script=Path(__file__).resolve().parents[1]/"installer/uninstall.ps1"
        return subprocess.run(["powershell.exe","-NoProfile","-NonInteractive","-ExecutionPolicy","Bypass","-File",str(script),
            "-Root",str(root),"-Silent","-Confirm","-NoShellCleanup",*map(str,args)],capture_output=True,text=True,timeout=45,
            creationflags=subprocess.CREATE_NO_WINDOW)

    def test_preserves_original_inputs_and_verified_save_backup_while_removing_owned_tools(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder).resolve();root,own,archive,external=self.fixture(base)
            originals={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in (own,archive)}
            backup=base/"save-backup";result=self.run_uninstall(root,"-Backup",backup)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            for path,digest in originals.items():self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),digest)
            self.assertFalse((root/"DekuForge.exe").exists())
            self.assertFalse((root/"local/build-tools/compiler.exe").exists())
            self.assertFalse((root/"build/game/DekuForgeGame.exe").exists())
            self.assertEqual(next(backup.rglob("progress.sav")).read_bytes(),b"save me")
            self.assertFalse(list(backup.rglob("user-input.dat")))
            self.assertEqual((external/"game.exe").read_bytes(),b"external keep")

    def test_removing_saves_still_never_removes_the_game_dump(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder).resolve();root,own,archive,external=self.fixture(base)
            result=self.run_uninstall(root,"-RemoveSaves")
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertTrue(own.exists());self.assertTrue(archive.exists())
            self.assertFalse(list((root/"build").rglob("*.sav")))
            self.assertTrue((external/"game.exe").exists())

    def test_bad_ownership_and_backup_inside_removed_root_are_refused_before_deletion(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder).resolve();root,own,archive,external=self.fixture(base)
            result=self.run_uninstall(root,"-Backup",root/"bad-backup")
            self.assertNotEqual(result.returncode,0)
            self.assertTrue((root/"DekuForge.exe").exists())
            (root/"build/game/.dekuforge-build.json").write_text('{"id":"wrong"}',encoding="utf-8")
            result=self.run_uninstall(root,"-RemoveSaves")
            self.assertNotEqual(result.returncode,0)
            self.assertTrue((root/"build/game/DekuForgeGame.exe").exists())
