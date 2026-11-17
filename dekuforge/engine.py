"""Inventory the source engine and its readiness for the selected game variant."""

import hashlib
import importlib.util
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys

from .core import ROOT, load_installation
from .gameplan import prepare_game
from .modules import normalize_prepared


def engine_report(root=ROOT):
    engine = root / "engine"
    components = {"arm64_lifter": "recomp/lifter.py", "code_generator": "recomp/gen.py",
                  "host_runtime": "runtime/boot.c", "vulkan_renderer": "runtime/vk_device.c",
                  "shader_translator": "tools/xlate/Program.cs", "native_linker_driver": "tools/build_game.py"}
    return {"source_components": {name: (engine / relative).is_file() for name, relative in components.items()},
            "python_dependencies": {name: importlib.util.find_spec(name) is not None
                                    for name in ("numpy", "lz4", "zbic")},
            "tools": {name: shutil.which(name) is not None for name in ("clang", "ninja", "dotnet")},
            "interpreter": f"{sys.version_info.major}.{sys.version_info.minor}",
            "game_1_1_1_port_validated": False,
            "playable_build_available": False}


def verify_engine_sources(root=ROOT):
    engine = root / "engine"
    record = json.loads((engine / "SOURCE.json").read_text(encoding="utf-8"))
    for relative, expected in record["files"].items():
        source = engine / relative
        if not source.resolve().is_relative_to(engine.resolve()) or not source.is_file():
            raise ValueError("Missing engine source: " + relative)
        if hashlib.sha256(source.read_bytes()).hexdigest() != expected:
            raise ValueError("Pinned engine source differs: " + relative)
    return len(record["files"])


def build_independent(filename, notify, workspace=ROOT, destination=None):
    from .workflow import validate_destination
    target = validate_destination(destination or workspace / "build" / "game", load_installation())
    notify("phase", {"phase": "prepared"})
    prepared = prepare_game(filename, notify, workspace)
    notify("phase", {"phase": "normalizing"})
    normalize_prepared(prepared, notify)
    report = engine_report()
    notify("log", json.dumps(report, indent=2) + "\n")
    notify("log", f"Requested installation: {target}\n")
    # Validate the SDK before spending time on the larger game module. Failed
    # generation never advances to a native link or selects an installation.
    notify("phase", {"phase": "generating"})
    generate_prepared(prepared, notify, modules="sdk", jobs=1)
    generate_prepared(prepared, notify, modules="main,subsdk0", jobs=1)
    if not report["game_1_1_1_port_validated"]:
        raise RuntimeError("CPU generation finished, but the game 1.1.1 host, NVN2 renderer and shader integration "
                           "are not validated. Native linking is blocked; no playable executable was produced.")
    raise RuntimeError("Native game linking is not implemented")


def generate_prepared(prepared, notify, modules="main,subsdk0,sdk", limit=0, jobs=1):
    prepared = Path(prepared).resolve()
    if not prepared.is_relative_to((ROOT / "build").resolve()):
        raise ValueError("Generation input must be in the project build directory")
    lock = ROOT / "local" / "build.lock"
    lock.parent.mkdir(exist_ok=True)
    try:
        owner = lock.open("x", encoding="utf-8")
    except FileExistsError:
        raise ValueError("Er loopt al een build of controle.") from None
    try:
        with owner:
            owner.write(str(os.getpid()))
            owner.flush()
            return _generate_prepared(prepared, notify, modules, limit, jobs)
    finally:
        lock.unlink(missing_ok=True)


def _generate_prepared(prepared, notify, modules, limit, jobs):
    if not (prepared / "build-plan.json").is_file():
        raise ValueError("Select an independently prepared build directory")
    selected = modules.split(",")
    if not selected or any(name not in ["main", "sdk", *[f"subsdk{i}" for i in range(10)]] for name in selected):
        raise ValueError("Invalid generation module selection")
    if limit < 0 or jobs < 1:
        raise ValueError("Invalid generation limits")
    notify("phase", {"phase": "generating", "done": 0, "total": 0})
    exefs = normalize_prepared(prepared)
    output = prepared / ("generated-smoke" if limit else "generated")
    if output.resolve() != output:
        raise ValueError("Generated output must not be a link")
    args = [sys.executable, "-I", str(ROOT / "engine_entry.py"), "recomp/gen.py",
            "--exefs", str(exefs), "--out", str(output), "--modules", modules,
            "--jobs", str(jobs), "--limit", str(limit),
            "--patches", str(ROOT / "engine_overrides/frame_timing_v111.txt")]
    with subprocess.Popen(args, cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, encoding="utf-8", errors="replace",
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)) as process:
        for line in process.stdout:
            notify("log", line)
            match = re.search(r"emitted\s+(\d+)/(\d+)\s+chunks", line)
            if match:
                notify("progress", {"phase": "generating", "done": int(match[1]), "total": int(match[2])})
        code = process.wait()
    if code:
        raise RuntimeError(f"Independent code generation failed with code {code}")
    unsupported = {}
    for module in selected:
        manifest = json.loads((output / module / "manifest.json").read_text(encoding="utf-8"))
        if manifest.get("stats", {}).get("unsupported", 0):
            unsupported[module] = manifest.get("unsupported_census", {})
    if unsupported:
        raise RuntimeError("Code gegenereerd met niet-ondersteunde instructies: " + json.dumps(unsupported) +
                           ". Deze uitvoer mag nog niet als game worden gebouwd.")
    notify("checked", f"Codegeneratie voltooid: {output}. Nog niet gelinkt of speelbaar.")
    return output
