"""Copy the validated local installation into an isolated candidate; never share writable files."""
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dekuforge.runtime_layer import ENGINE_VERSION


def main():
    source=ROOT/"build/stable-windows-game"
    target=ROOT/"build"/f"windows-{ENGINE_VERSION}"
    if source.resolve()!=source or target.resolve()!=target or not (source/".dekuforge-stable-build").is_file():
        raise ValueError("Use only owned local version directories")
    validation=json.loads((source/"dekuforge-validation.json").read_text(encoding="utf-8"))
    with (source/"DekuForgeGame.exe").open("rb") as executable:
        identity=hashlib.file_digest(executable,"sha256").hexdigest()
    if not validation.get("visually_verified") or validation.get("runtime_sha256")!=identity:
        raise ValueError("The baseline has no matching visual validation")
    marker=target/".dekuforge-candidate-copy"
    if target.exists() and (not marker.is_file() or (target/"DekuForgeGame.exe").exists()):
        raise ValueError("Candidate destination is already in use")
    if shutil.disk_usage(ROOT).free < 34*1024**3:
        raise ValueError("The isolated copy needs 34 GiB free space")
    target.mkdir(parents=True,exist_ok=True)
    marker.write_text(identity,encoding="ascii")
    for name in ("exefs","romfs","build-cache","shader-cache","profile"):
        print("Copying",name,flush=True)
        shutil.copytree(source/name,target/name,dirs_exist_ok=True)
    for directory in source.glob("romfs-patches-*"):
        if directory.is_dir():shutil.copytree(directory,target/directory.name,dirs_exist_ok=True)
    for p in source.iterdir():
        if p.is_file() and (p.suffix in {".dll",".id"} or p.name in {
            "nx2navi_xlate.exe","nx2navi.ini","nvngx_dlss-NOTICE.txt","romfs-check.json",
            ".dekuforge-stable-build",".dekuforge-owned",".dekuforge-release-data"}
            or p.name.endswith(".bin")):
            shutil.copy2(p,target/p.name)
    proof=json.loads((ROOT/"local/validated-base-gpu-inputs.json").read_text(encoding="utf-8"))
    proof["source_runtime_sha256"]=identity
    proof["translator_id"]=(target/"nx2navi_xlate.id").read_text().strip()
    (target/".dekuforge-gpu-inputs.json").write_text(json.dumps(proof,indent=2),encoding="utf-8")
    print("Candidate ready:",target,flush=True)


if __name__=="__main__":main()
