import json
import io
import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from dekuforge import stable_engine


class StableEngineTests(unittest.TestCase):
    def test_interrupted_child_is_reported_without_misclassifying_shader_errors(self):
        self.assertEqual(stable_engine.build_failure_message(1,
            "CalledProcessError: glslc returned non-zero exit status 3221225786."), "build_interrupted")
        self.assertEqual(stable_engine.build_failure_message(-1073741510), "build_interrupted")
        self.assertNotEqual(stable_engine.build_failure_message(1, "Shader syntax error"), "build_interrupted")

    def test_native_build_worker_hides_console_without_discarding_process_flags(self):
        from tools import run_stable_build
        calls = []
        class Process:
            def __init__(self, *args, **kwargs): calls.append(kwargs)
        with patch.object(run_stable_build.os, "name", "nt"), patch.object(run_stable_build.subprocess, "Popen", Process), patch.object(run_stable_build.subprocess, "CREATE_NO_WINDOW", 0x08000000, create=True):
            run_stable_build.hide_build_windows()
            run_stable_build.subprocess.Popen(["synthetic-tool"], creationflags=512)
        self.assertEqual(calls[0]["creationflags"], 0x08000000 | 512)

    def test_verified_source_archive_is_cached_and_restores_pristine_inputs(self):
        archive=io.BytesIO()
        with zipfile.ZipFile(archive,"w") as z:z.writestr("upstream/VERSION","0.10.1")
        expected={"VERSION":hashlib.sha256(b"0.10.1").hexdigest()}
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(stable_engine,"ROOT",Path(folder).resolve()), patch.object(stable_engine,"REFERENCE") as reference, patch.object(stable_engine,"source_manifest",return_value=expected), patch.object(stable_engine,"urlopen") as network:
                reference.is_dir.return_value=False
                network.return_value.__enter__.return_value.read.return_value=archive.getvalue()
                source=stable_engine.stage_stable()
                (source/"VERSION").write_text("temporary layer version",encoding="utf-8")
                stable_engine.stage_stable()
                self.assertEqual(network.call_count,1)
                self.assertEqual((source/"VERSION").read_text(),"0.10.1")

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
            with zipfile.ZipFile(io.BytesIO(archive.getvalue())) as fixture:
                expected={name:hashlib.sha256(fixture.read(name)).hexdigest()
                          for name in fixture.namelist() if not name.startswith("generated/")}
            with patch.object(stable_engine,"source_manifest",return_value=expected), patch.object(stable_engine,"ROOT",root), patch.object(stable_engine,"REFERENCE"), patch.object(stable_engine.subprocess,"check_output",return_value=archive.getvalue()) as git:
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

    def test_modified_source_is_rejected_before_it_can_be_used(self):
        archive=io.BytesIO()
        with zipfile.ZipFile(archive,"w") as z:
            z.writestr("runtime/main.c","unexpected source")
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve()
            with patch.object(stable_engine,"ROOT",root), patch.object(stable_engine,"REFERENCE"), patch.object(stable_engine,"source_manifest",return_value={"runtime/main.c":"0"*64}), patch.object(stable_engine.subprocess,"check_output",return_value=archive.getvalue()):
                with self.assertRaisesRegex(ValueError,"hash mismatch"):
                    stable_engine.stage_stable()
                self.assertFalse((root/"build/engine-0.10.1/runtime/main.c").exists())

    def test_rebuild_reuses_only_the_same_completed_archive_extraction(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve()
            source=root/"own.nup";source.write_bytes(b"synthetic input")
            output=root/"game";cache=output/"build-cache";cache.mkdir(parents=True)
            stat=source.stat()
            state={"version":2,"input":f"nup {source} {stat.st_size} {int(stat.st_mtime)}",
                   "steps":{"exefs":"complete","romfs":"complete"}}
            record=cache/"state.json"
            record.write_text(json.dumps(state),encoding="utf-8")
            self.assertEqual(stable_engine.build_input_arguments(source,output),["--rebuild"])
            source.write_bytes(b"replaced input with a different size")
            self.assertEqual(stable_engine.build_input_arguments(source,output),["--nup",str(source)])
            source.write_bytes(b"synthetic input")
            state["steps"].pop("romfs")
            record.write_text(json.dumps(state),encoding="utf-8")
            self.assertEqual(stable_engine.build_input_arguments(source,output),["--nup",str(source)])

    def test_verified_release_data_includes_pipeline_art_and_notices_but_no_runtime_binary(self):
        package=io.BytesIO()
        with zipfile.ZipFile(package,"w") as z:
            z.writestr("tools/data/pipeline_list.bin",b"synthetic metadata")
            z.writestr("prompt-art/pad/button.png",b"synthetic art")
            z.writestr("THIRD_PARTY_NOTICES.md","retained release credit")
            z.writestr("bin/runtime.dll",b"must not be extracted")
        data=package.getvalue()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();source=root/"source";source.mkdir()
            archive=root/"local/build-tools/NX2navi-app-0.10.1.zip"
            archive.parent.mkdir(parents=True);archive.write_bytes(data)
            with patch.object(stable_engine,"ROOT",root),patch.object(stable_engine,"RELEASE_SIZE",len(data)),patch.object(stable_engine,"RELEASE_SHA256",hashlib.sha256(data).hexdigest()),patch.object(stable_engine,"urlopen") as download:
                stable_engine.prepare_release_data(source,lambda *args:None)
                download.assert_not_called()
            self.assertEqual((source/"tools/data/pipeline_list.bin").read_bytes(),b"synthetic metadata")
            self.assertEqual((source/"RELEASE-NOTICES.md").read_text(),"retained release credit")
            self.assertFalse((source/"bin").exists())

    def test_changed_release_reprepares_shaders_without_discarding_native_or_extracted_work(self):
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder).resolve();cache=output/"build-cache";cache.mkdir()
            path=cache/"state.json"
            state={"steps":{"exefs":"kept","romfs":"kept","compile":"kept","shaders":"old"}}
            path.write_text(json.dumps(state),encoding="utf-8")
            self.assertTrue(stable_engine.release_preparation_changed(output))
            updated=json.loads(path.read_text())
            self.assertEqual(updated["steps"],{"exefs":"kept","romfs":"kept","compile":"kept"})
            (output/".dekuforge-release-data").write_text(stable_engine.RELEASE_SHA256,encoding="ascii")
            self.assertFalse(stable_engine.release_preparation_changed(output))

    def test_new_build_carries_only_matching_preferences_and_preserves_existing_destination(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();old=root/"active";new=root/"new"
            old.mkdir();new.mkdir();exe=old/"game.exe";exe.touch()
            info=old/"dekuforge-build-info.json"
            info.write_text(json.dumps({"engine_revision":"other"}),encoding="utf-8")
            (old/"nx2navi.ini").write_text("dlss=quality\n",encoding="utf-8")
            self.assertFalse(stable_engine.carry_active_configuration(new,str(exe)))
            info.write_text(json.dumps({"engine_revision":stable_engine.REVISION}),encoding="utf-8")
            self.assertTrue(stable_engine.carry_active_configuration(new,str(exe)))
            self.assertEqual((new/"nx2navi.ini").read_text(),"dlss=quality\n")
            (old/"nx2navi.ini").write_text("dlss=performance\n",encoding="utf-8")
            self.assertFalse(stable_engine.carry_active_configuration(new,str(exe)))
            self.assertEqual((new/"nx2navi.ini").read_text(),"dlss=quality\n")
