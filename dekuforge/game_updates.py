"""Rebuild an updated engine separately and activate only its successful result."""
import json
from pathlib import Path
import shutil
import subprocess
import os
import csv
from .core import ROOT, load_settings, save_installation
from .stable_engine import build_stable
from .update_package import atomic_json
from . import COMPONENTS


def check_backend():
    if COMPONENTS['engine'].get('backend') == 'independent':
        raise RuntimeError('Main-channel engine rebuilds are disabled on the independent branch')


def game_running():
    if os.name != "nt":
        return False
    result=subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True,
        check=True, creationflags=subprocess.CREATE_NO_WINDOW)
    return any(row and row[0].casefold() in {"ocarina.exe", "dekuforgegame.exe"}
               for row in csv.reader(result.stdout.splitlines()))


def rebuild_pending(notify, root=ROOT):
    check_backend()
    pending=root/"local/pending-game-update.json"
    state=json.loads(pending.read_text(encoding="utf-8"))
    settings=load_settings(root/"local/settings.json")
    if game_running():
        raise ValueError("Close the running game before rebuilding the updated engine")
    source=Path(settings.get("nup", ""))
    if not source.is_file():
        raise ValueError("Select your own game archive in Build game before rebuilding")
    active=Path(settings.get("executable", ""))
    identity=state["components"]["engine"]["version"]
    # No version/tag supplied by a server is used as a filesystem path.
    import hashlib
    key=hashlib.sha256(json.dumps([state["components"],state.get("build_fingerprint")],sort_keys=True).encode()).hexdigest()[:12]
    destination=root/"build"/("release-"+key)
    if destination.resolve()!=destination:
        raise ValueError("Linked build destination refused")
    if active.is_file() and active.parent==destination:
        raise ValueError("The active game is already this build; choose another build before rebuilding it")
    lock=root/"local/build.lock"
    owner=lock.open("x",encoding="utf-8")
    try:
        with owner:
            owner.write(str(os.getpid()));owner.flush()
            if active.is_file() and active.parent != destination and not destination.exists():
                previous=active.parent
                owned=(previous/".dekuforge-stable-build").is_file()
                dirs=[p for p in previous.iterdir() if p.is_dir() and
                      (p.name=="profile" or owned and (p.name in {"romfs","exefs","build-cache","shader-cache"}
                       or p.name.startswith("romfs-patches-")))]
                for folder in dirs:
                    if folder.is_symlink() or getattr(folder,"is_junction",lambda:False)():
                        raise ValueError("Linked cache directories cannot be copied for an update")
                required=sum(p.stat().st_size for folder in dirs for p in folder.rglob("*") if p.is_file())
                if shutil.disk_usage(root).free < required + 4*1024**3:
                    raise ValueError("Insufficient space for a separate game build and rollback copy")
                staging=destination.with_name(destination.name+".copying")
                if staging.resolve()!=staging or staging.exists() and not (staging/".dekuforge-update-copy").is_file():
                    raise ValueError("Unowned cache-copy directory")
                staging.mkdir(parents=True,exist_ok=True)
                (staging/".dekuforge-update-copy").touch()
                notify("log","Copying reusable build cache and a separate save profile; previous installation retained\n")
                for folder in dirs:
                    shutil.copytree(folder,staging/folder.name,dirs_exist_ok=True)
                if owned:
                    for path in previous.iterdir():
                        if path.is_file() and (path.suffix in {".dll",".bin",".id"}
                            or path.name in {"nx2navi_xlate.exe","nx2navi.ini","nvngx_dlss-NOTICE.txt",
                                "romfs-check.json",".dekuforge-gpu-inputs.json",".dekuforge-release-data"}):
                            shutil.copy2(path,staging/path.name)
                (staging/".dekuforge-owned").write_text("DekuForge update build\n",encoding="utf-8")
                (staging/".dekuforge-stable-build").touch()
                staging.replace(destination)
            result=build_stable(source,notify,destination)
            if not Path(result).is_file():
                raise RuntimeError("Updated game executable is missing")
            if game_running():
                raise ValueError("The updated build is ready; close the running game before activating it")
            if active.is_file() and active.parent != destination and (active.parent/"profile").is_dir():
                shutil.copytree(active.parent/"profile",destination/"profile",dirs_exist_ok=True)
            save_installation(result,root/"local/settings.json")
            state.update(status="complete",previous_executable=str(active),executable=str(result),engine_version=identity)
            atomic_json(pending,state)
            return result
    finally:
        lock.unlink(missing_ok=True)



def run_rebuild(notify, root=ROOT):
    check_backend()
    try:
        return rebuild_pending(notify,root)
    except Exception:
        pending=root/"local/pending-game-update.json"
        if pending.is_file():
            state=json.loads(pending.read_text(encoding="utf-8"));state["status"]="failed"
            atomic_json(pending,state)
        raise
