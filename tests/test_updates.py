import hashlib
import json
from pathlib import Path
import shutil
import struct
import tempfile
import unittest
from unittest.mock import patch
from urllib.request import Request
import zipfile

from dekuforge import COMPONENTS
from dekuforge.update_package import install, validate_package, rollback, recover, allowed, needs_rebuild, atomic_json
from dekuforge.update_service import AssetRedirect, newer_version, prepare_release, download_asset
from dekuforge.source_patch import apply_patch
from dekuforge.game_updates import run_rebuild


def fixture_package(path, text="new", extra=None):
    exe=bytearray(512);exe[:2]=b"MZ";struct.pack_into("<I",exe,60,128)
    exe[128:132]=b"PE\0\0";struct.pack_into("<H",exe,128+24+68,2)
    exe[300:318]="DekuForge".encode("utf-16le")
    files={"DekuForge.exe":bytes(exe),"DekuForge-Uninstall.exe":bytes(exe),"run_launcher.py":text.encode(),
           "dekuforge/components.json":json.dumps(COMPONENTS).encode(),
           "tools/bootstrap_runtime.ps1":b"# synthetic bootstrap",
           "dekuforge/runtime_layer.py":b"# same engine"}
    files.update(extra or {})
    inventory={"components":COMPONENTS,"contains_game_files":False,
               "sha256":{name:hashlib.sha256(data).hexdigest() for name,data in files.items()}}
    with zipfile.ZipFile(path,"w") as z:
        for name,data in files.items():z.writestr(name,data)
        z.writestr("launcher-package.json",json.dumps(inventory))
    return inventory


class UpdateTests(unittest.TestCase):
    def test_pinned_text_patches_need_no_git_and_check_every_context_before_writing(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();(root/"first.c").write_text("before\n",encoding="utf-8")
            (root/"second.c").write_text("preserve\n",encoding="utf-8")
            patch_text="--- a/first.c\n+++ b/first.c\n@@ -1 +1 @@\n-before\n+after\n--- a/second.c\n+++ b/second.c\n@@ -1 +1 @@\n-wrong\n+after\n"
            with self.assertRaises(ValueError):apply_patch(root,patch_text)
            self.assertEqual((root/"first.c").read_text(),"before\n")
            apply_patch(root,patch_text.replace("-wrong\n","-preserve\n"))
            self.assertEqual((root/"first.c").read_text(),"after\n")
            self.assertEqual((root/"second.c").read_text(),"after\n")

    def test_failed_engine_build_keeps_active_game_and_save(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();active=root/"working/game.exe";active.parent.mkdir();active.write_bytes(b"working")
            profile=active.parent/"profile";profile.mkdir();(profile/"progress.sav").write_bytes(b"original save")
            source=root/"own.nup";source.write_bytes(b"synthetic")
            atomic_json(root/"local/settings.json",{"executable":str(active),"nup":str(source)})
            atomic_json(root/"local/pending-game-update.json",{"components":COMPONENTS,"requires_rebuild":True,"status":"pending"})
            with patch("dekuforge.game_updates.game_running",return_value=False), patch("dekuforge.game_updates.build_stable",side_effect=RuntimeError("compile failed")):
                with self.assertRaises(RuntimeError):run_rebuild(lambda *args:None,root)
            self.assertEqual(json.loads((root/"local/settings.json").read_text())["executable"],str(active))
            self.assertEqual((profile/"progress.sav").read_bytes(),b"original save")
            self.assertFalse((root/"local/build.lock").exists())

    def test_new_engine_is_activated_only_after_success_with_separate_profile(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();active=root/"working/game.exe";active.parent.mkdir();active.write_bytes(b"working")
            profile=active.parent/"profile";profile.mkdir();(profile/"progress.sav").write_bytes(b"save")
            source=root/"own.nup";source.write_bytes(b"synthetic")
            atomic_json(root/"local/settings.json",{"executable":str(active),"nup":str(source)})
            atomic_json(root/"local/pending-game-update.json",{"components":COMPONENTS,"requires_rebuild":True,"status":"pending"})
            def build(source,notify,destination):
                self.assertEqual(json.loads((root/"local/settings.json").read_text())["executable"],str(active))
                exe=destination/"DekuForgeGame.exe";exe.write_bytes(b"new build");return exe
            with patch("dekuforge.game_updates.game_running",return_value=False), patch("dekuforge.game_updates.build_stable",side_effect=build):
                result=run_rebuild(lambda *args:None,root)
            self.assertNotEqual(result.parent,active.parent)
            self.assertEqual((result.parent/"profile/progress.sav").read_bytes(),b"save")
            self.assertEqual((profile/"progress.sav").read_bytes(),b"save")
            self.assertEqual(json.loads((root/"local/settings.json").read_text())["executable"],str(result))

    def test_install_and_downgrade_preserve_game_settings_and_saves(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve()/"app";archive=Path(folder).resolve()/"release.zip"
            for name in ("local/settings.json","build/game/profile/slot_00/progress.sav","build/game/DekuForgeGame.exe"):
                p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b"keep")
            fixture_package(archive,"old");install(archive,root,log=lambda _:None)
            fixture_package(archive,"new");result=install(archive,root,log=lambda _:None)
            self.assertFalse(result["requires_rebuild"])
            self.assertEqual((root/"run_launcher.py").read_text(),"new")
            rollback(root,result["backup"])
            self.assertEqual((root/"run_launcher.py").read_text(),"old")
            for name in ("local/settings.json","build/game/profile/slot_00/progress.sav","build/game/DekuForgeGame.exe"):
                self.assertEqual((root/name).read_bytes(),b"keep")

    def test_mid_install_failure_restores_original_and_removes_new_members(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve()/"app";archive=Path(folder).resolve()/"release.zip"
            fixture_package(archive,"old");install(archive,root,log=lambda _:None)
            fixture_package(archive,"new",{"docs/new.md":b"new file"})
            with self.assertRaises(OSError):install(archive,root,log=lambda _:None,fail_after=2)
            self.assertEqual((root/"run_launcher.py").read_text(),"old")
            self.assertFalse((root/"docs/new.md").exists())
            self.assertFalse((root/"local/update-transaction.json").exists())

    def test_interrupted_transaction_is_recovered_before_next_install(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve()/"app";identity="a"*32
            backup=root/"local/update-backups"/identity;backup.mkdir(parents=True)
            (backup/"run_launcher.py").write_text("before",encoding="utf-8")
            (root/"run_launcher.py").write_text("partially replaced",encoding="utf-8")
            atomic_json(root/"local/update-transaction.json",{"id":identity,"changes":[{"name":"run_launcher.py","existed":True}]})
            recover(root)
            self.assertEqual((root/"run_launcher.py").read_text(),"before")

    def test_tampered_member_is_rejected_before_existing_app_is_changed(self):
        with tempfile.TemporaryDirectory() as folder:
            archive=Path(folder).resolve()/"bad.zip";fixture_package(archive)
            with zipfile.ZipFile(archive,"a") as z:z.writestr("run_launcher.py",b"tampered")
            with self.assertRaises(ValueError):validate_package(archive)

    def test_forbidden_members_and_windows_path_aliases(self):
        for name in ("../README.md","/README.md","tools/../../save.py","tools\\file.py",
                     "local/settings.json","build/romfs.bin","DekuForgeGame.exe","tools/CON.py",
                     "tools/thing.py:payload","tools./app.py","tools/file.py ","tools//file.py"):
            self.assertFalse(allowed(name),name)
        with tempfile.TemporaryDirectory() as folder:
            archive=Path(folder).resolve()/"bad.zip";fixture_package(archive,extra={"build/game.py":b"no"})
            with self.assertRaises(ValueError):validate_package(archive)

    def test_build_inputs_control_rebuild_instead_of_launcher_version(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve()/"app";archive=Path(folder).resolve()/"release.zip"
            fixture_package(archive);install(archive,root,log=lambda _:None)
            inventory=fixture_package(archive,"new launcher",{"README.md":b"new documentation"})
            self.assertFalse(needs_rebuild(root,inventory))
            inventory=fixture_package(archive,extra={"dekuforge/runtime_layer.py":b"changed engine"})
            self.assertTrue(needs_rebuild(root,inventory))

    def test_linked_destination_does_not_write_outside_installation(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder).resolve();root=base/"app";root.mkdir();outside=base/"outside";outside.mkdir()
            try:(root/"dekuforge").symlink_to(outside,target_is_directory=True)
            except OSError:self.skipTest("Symlinks unavailable")
            archive=base/"app.zip";fixture_package(archive)
            with self.assertRaises(ValueError):install(archive,root,log=lambda _:None)
            self.assertEqual(list(outside.iterdir()),[])

    def test_automatic_updates_only_take_newer_semantic_versions(self):
        self.assertTrue(newer_version("v0.2.0","0.2.0-preview.1"))
        self.assertTrue(newer_version("v0.2.0-preview.10","0.2.0-preview.2"))
        self.assertFalse(newer_version("v0.1.0","0.2.0"))
        self.assertFalse(newer_version("v0.3.0-unknown","bad-version"))

    def test_github_credentials_are_removed_on_asset_redirect(self):
        request=Request("https://api.github.com/repos/owner/repo/releases/assets/1",headers={"Authorization":"Bearer private"})
        redirected=AssetRedirect().redirect_request(request,None,302,"Found",{},"https://release-assets.githubusercontent.com/file")
        self.assertFalse(redirected.has_header("Authorization"))

    def test_unsigned_asset_metadata_is_refused_before_network_access(self):
        with tempfile.TemporaryDirectory() as folder, patch("dekuforge.update_service.github_request") as network:
            with self.assertRaises(ValueError):download_asset({"size":10,"url":"https://evil.test"},Path(folder).resolve()/"app.zip")
            network.assert_not_called()

    def test_release_descriptor_and_package_are_bound_to_the_selected_tag(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();(root/"tools").mkdir();(root/"dekuforge").mkdir()
            (root/"tools/update_worker.py").write_text("# worker",encoding="utf-8")
            (root/"dekuforge/update_package.py").write_text("# verifier",encoding="utf-8")
            archive=root/"fixture.zip";fixture_package(archive)
            digest=hashlib.sha256(archive.read_bytes()).hexdigest()
            tag="v"+COMPONENTS["launcher"]["version"]
            manifest={"schema":1,"tag":tag,"contains_game_files":False,"components":COMPONENTS,
                      "package":{"name":"app.zip","size":archive.stat().st_size,"sha256":digest}}
            descriptor={"name":"DekuForge-release.json"};asset={"name":"app.zip","digest":"sha256:"+digest,"size":archive.stat().st_size}
            release={"version":tag,"assets":[descriptor,asset]}
            def download(item,target,*args):
                target.parent.mkdir(parents=True,exist_ok=True)
                if item is descriptor:target.write_text(json.dumps(manifest),encoding="utf-8")
                else:shutil.copy2(archive,target)
            with patch("dekuforge.update_service.download_asset",side_effect=download):
                job=prepare_release(release,root=root)
                self.assertTrue((job/"job.json").is_file())
                release["version"]="v9.9.9"
                with self.assertRaises(ValueError):prepare_release(release,root=root)
