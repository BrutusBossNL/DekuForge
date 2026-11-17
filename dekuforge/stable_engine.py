"""Pinned 0.10.1 source backend for the DekuForge migration build."""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile
from .core import ROOT

REVISION = "5ae55db41c7d11c4e997d2676019939a936e560b"
REFERENCE = ROOT.parent / "NX2Navi/Contribute/NX2navi-cheat-manager"


def stage_stable():
    output = ROOT / "build/engine-0.10.1"
    marker = output / ".dekuforge-stable-engine"
    if output.exists() and not marker.is_file():
        raise ValueError("Stable engine workspace is not owned")
    output.mkdir(parents=True, exist_ok=True)
    archive = subprocess.check_output(["git", "-c", "safe.directory=" + REFERENCE.as_posix(),
        "-C", str(REFERENCE), "archive", "--format=zip", REVISION])
    hashes = {}
    with zipfile.ZipFile(io.BytesIO(archive)) as source:
        for item in source.infolist():
            if item.is_dir():
                continue
            relative = Path(item.filename)
            if relative.parts[0] not in {"runtime", "recomp", "tools", "docs"} and relative.name not in {
                "VERSION", "LICENSE", "LICENSE-ADDITIONS", "THIRD_PARTY_NOTICES.md", "config.example.toml"}:
                continue
            target = output / relative
            if not target.resolve().is_relative_to(output.resolve()) or target.is_symlink():
                raise ValueError("Unsafe stable engine path")
            data = source.read(item)
            hashes[relative.as_posix()] = hashlib.sha256(data).hexdigest()
            # Keep renderer behavior intact; adapt only visible application identity.
            if relative.suffix in {".c", ".cpp", ".py"}:
                text = data.decode("utf-8")
                text = text.replace('"NX2navi Recomp', '"DekuForge').replace('"NX2navi"', '"DekuForge"')
                if relative.as_posix() == "tools/make_game.py":
                    text = text.replace("'ocarina.exe'", "'DekuForgeGame.exe'")
                data = text.encode("utf-8")
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.is_file() or target.read_bytes() != data:
                target.write_bytes(data)
    icon = ROOT / "assets/branding/launcher.ico"
    if icon.is_file():
        (output / "runtime/nx2navi.ico").write_bytes(icon.read_bytes())
    marker.write_text(REVISION, encoding="utf-8")
    (output / "DEKUFORGE-SOURCE.json").write_text(json.dumps({"revision": REVISION,
        "version": "0.10.1", "files": hashes}, indent=2), encoding="utf-8")
    return output


def build_stable(filename, notify, destination):
    output = Path(destination).absolute()
    if output.resolve() != output:
        raise ValueError("Build destination must not be a link")
    marker = output / ".dekuforge-stable-build"
    if output.exists() and any(output.iterdir()) and not marker.is_file():
        raise ValueError("Build destination is not an owned stable build")
    output.mkdir(parents=True, exist_ok=True)
    marker.touch()
    source = stage_stable()
    notify("phase", {"phase":"shaders"})
    preparation = [sys.executable, str(ROOT / "tools/build_stable_translator.py")]
    with subprocess.Popen(preparation, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
            creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0)) as worker:
        for line in worker.stdout:
            notify("log",line)
        if worker.wait():
            raise RuntimeError("Stable shader translator preparation failed")
    toolchain = Path(os.environ["LOCALAPPDATA"]) / "Programs/NX2navi/toolchain/msys64/ucrt64"
    env = os.environ.copy()
    env["PATH"] = str(ROOT / "local/build-tools/shaders/ucrt64/bin") + os.pathsep + str(toolchain / "bin") + os.pathsep + env.get("PATH", "")
    command = [sys.executable, str(source / "tools/make_game.py"), "--nup", str(filename),
        "--out", str(output), "--msys", str(toolchain), "--jobs", "6", "--events"]
    notify("log", "Building pinned stable engine 0.10.1: " + REVISION + "\n")
    with subprocess.Popen(command, cwd=source, env=env, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
            creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0)) as process:
        for line in process.stdout:
            notify("log", line)
            if line.startswith("@@"):
                try:
                    event = json.loads(line[2:])
                    phases = {"check":"checking", "exefs":"prepared", "romfs":"extracting",
                              "lift":"generating", "compile":"compiling", "shaders":"shaders",
                              "prompts":"prompts", "scan":"checking"}
                    phase = phases.get(event.get("step"), "checking")
                    if event.get("ev") == "progress":
                        notify("progress", {"phase":phase,"done":event.get("done",0),"total":event.get("total",0)})
                    elif event.get("ev") == "step" and event.get("state") == "start":
                        notify("phase", {"phase":phase})
                except (ValueError, TypeError):
                    pass
        if process.wait():
            raise RuntimeError("Stable engine build failed; see build log")
    exe = output / "DekuForgeGame.exe"
    if not exe.is_file():
        raise RuntimeError("Stable build did not produce its executable")
    return exe
