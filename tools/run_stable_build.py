"""Run the pinned builder with DekuForge's verified UI-only shader-cache carryover."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dekuforge.runtime_layer import gpu_input_signature


def require_gpu_idle():
    if os.name != "nt":
        return
    result=subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True,
        text=True, check=True, creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
    import csv
    active={row[0].casefold() for row in csv.reader(result.stdout.splitlines()) if row}
    if active & {"dekuforgegame.exe", "ocarina.exe"}:
        raise RuntimeError("Close the running game before full GPU shader preparation")


def main():
    source=ROOT/"build/engine-0.10.1"
    spec=importlib.util.spec_from_file_location("dekuforge_pinned_builder",source/"tools/make_game.py")
    driver=importlib.util.module_from_spec(spec);spec.loader.exec_module(driver)
    original=driver.step_shaders
    def prepare(out,update=False):
        signature=gpu_input_signature(source)
        try:
            proof=json.loads((out/".dekuforge-gpu-inputs.json").read_text(encoding="utf-8"))
            translator=(out/"nx2navi_xlate.id").read_text().strip()
            matches=proof["gpu_input_signature"]==signature and proof["translator_id"]==translator
        except (OSError,ValueError,KeyError):
            matches=False
        if matches and driver.prepared_from(out):
            command=[sys.executable,"-u",str(source/"tools/prepare_shaders.py"),str(out),
                "--romfs",str(out/"romfs"),"--exefs",str(out/"exefs"),"--no-list","--no-run","--exe","DekuForgeGame.exe"]
            if subprocess.run(command,check=False).returncode==0:
                was=driver.prepared_from(out)
                unchanged=all(hashlib.sha256((out/name).read_bytes()).hexdigest()==was[key]
                    for name,key in (("seed-programs.bin","programs"),("seed-answers.bin","answers")))
                if unchanged:
                    driver.refresh_pipeline_seed(out)
                    for name in ("seed-programs.bin","seed-answers.bin"):(out/name).unlink(missing_ok=True)
                    print("DekuForge: verified shader inputs, translator and release seed unchanged; prepared shaders and pipelines retained",flush=True)
                    return
        require_gpu_idle()
        original(out,update)
        proof={"gpu_input_signature":signature,"translator_id":(out/"nx2navi_xlate.id").read_text().strip()}
        (out/".dekuforge-gpu-inputs.json").write_text(json.dumps(proof,indent=2),encoding="utf-8")
    driver.step_shaders=prepare
    sys.argv=[str(source/"tools/make_game.py"),*sys.argv[1:]]
    driver.main()


if __name__=="__main__":main()
