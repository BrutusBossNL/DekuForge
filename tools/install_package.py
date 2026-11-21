"""Install a verified launcher package and provision tools.

The native setup creates the Start Menu shortcut and Installed apps entry afterwards."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

SOURCE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(SOURCE))
from dekuforge.update_package import install, atomic_json, rollback, validate_launcher_health


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package",type=Path,required=True)
    parser.add_argument("--root",type=Path,required=True)
    parser.add_argument("--skip-tools",action="store_true")
    parser.add_argument("--no-launch",action="store_true")
    args=parser.parse_args();root=args.root.absolute()
    settings=root/"local/settings.json"
    previous=json.loads(settings.read_text(encoding="utf-8")) if settings.is_file() else {}
    has_game=bool(previous.get("executable")) and Path(previous["executable"]).is_file()
    result=install(args.package,root,log=lambda line:print(line,flush=True))
    try:
        pin=result["components"]["python"]["id"]
        destination=root/"python"/pin
        if not destination.exists():
            destination.parent.mkdir(parents=True,exist_ok=True)
            stage=destination.with_name(pin+".install")
            if stage.exists():
                raise ValueError("A runtime installation is already pending")
            shutil.copytree(Path(sys.executable).parent,stage)
            stage.replace(destination)
        python=destination/"python.exe"
        atomic_json(root/"local/installation.json",{"kind":"DekuForge","components":result["components"]})
        if not args.skip_tools:
            print("Preparing pinned build tools; this can take several minutes...",flush=True)
            subprocess.run([str(python),str(root/"tools/prepare_installation.py")],cwd=root,check=True)
        report=root/"local/launcher-selftest.json"
        before = report.stat().st_mtime_ns if report.is_file() else 0
        subprocess.run([str(python),str(root/"run_launcher.py"),"--self-test"],cwd=root,check=True,timeout=90)
        proof=json.loads(report.read_text(encoding="utf-8"))
        if report.stat().st_mtime_ns == before:
            raise RuntimeError("Installed launcher failed its health check")
        validate_launcher_health(proof, result["components"])
        atomic_json(root/"local/setup-result.json",{"success":True,"components":result["components"],"tools_prepared":not args.skip_tools})
        if has_game and result["requires_rebuild"]:
            atomic_json(root/"local/pending-game-update.json",{**result,"status":"pending",
                "release":"v"+result["components"]["launcher"]["version"]})
    except Exception:
        rollback(root,result["backup"])
        raise
    if not args.no_launch:
        subprocess.Popen([str(root/"DekuForge.exe")],cwd=root,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))


if __name__=="__main__":main()
