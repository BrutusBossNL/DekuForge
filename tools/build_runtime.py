"""Compile the pinned Windows host runtime separately from game-derived code.

This is a development build, not an executable or a compatibility claim. Game-
specific installation sources and the resource file are deliberately separate.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dekuforge.engine import verify_engine_sources
from dekuforge.engine_workspace import stage_engine
from dekuforge.boot_profile import write_boot_profile

INSTALL_SOURCES = {"romfs.c", "patches.c", "ov_zstd.c", "mouse_direct.c"}


def sources(runtime):
    patterns = ("*.c", "*.cpp", "platform/*.c", "ui/*.cpp",
                "third_party/imgui/*.cpp", "third_party/imgui/backends/*.cpp")
    return sorted(path for pattern in patterns for path in runtime.glob(pattern)
                  if path.name not in INSTALL_SOURCES and path.name != "linux.c"
                  and not path.stem.endswith("_sdl"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--toolchain", type=Path, required=True, help="MSYS2 UCRT64 bin directory")
    parser.add_argument("--prepared", type=Path, required=True)
    args = parser.parse_args()
    if os.name != "nt":
        parser.error("This development stage currently targets Windows")
    tools = args.toolchain.resolve()
    compiler, archiver = tools / "clang.exe", tools / "ar.exe"
    if not compiler.is_file() or not archiver.is_file():
        parser.error("The toolchain must contain clang.exe and ar.exe")
    prepared = args.prepared.resolve()
    if not prepared.is_relative_to((ROOT / "build").resolve()):
        parser.error("Prepared modules must be inside the project build directory")
    generated = prepared / "generated"
    if not (generated / "layout.h").is_file():
        parser.error("Generate a module first to establish its authoritative layout")
    verify_engine_sources()
    boot_config = write_boot_profile(prepared)
    engine = stage_engine()
    runtime = engine / "runtime"
    output = ROOT / "build" / "windows-runtime"
    if output.resolve() != output:
        parser.error("Runtime output must not be a link")
    output.mkdir(exist_ok=True)
    environment = os.environ.copy()
    environment["PATH"] = str(tools) + os.pathsep + environment.get("PATH", "")
    flags = ["-O2", "-g", "-Wall", "-Wextra", "-Wno-unused-parameter", "-Wno-missing-field-initializers",
             "-fno-strict-aliasing", "-march=x86-64-v3", "-D_WIN32_WINNT=0x0A00"]
    includes = [runtime, generated, boot_config, output, tools.parent / "include" / "vma",
                runtime / "third_party" / "imgui"]
    for include in includes:
        flags.extend(["-I", str(include)])
    report = {"stage": "host-runtime-compilation", "playable": False,
              "game_1_1_1_validated": False, "objects": [], "failures": []}
    started = time.monotonic()
    inputs = sources(runtime)
    for index, source in enumerate(inputs, 1):
        relative = source.relative_to(runtime)
        target = output / "obj" / relative.with_suffix(".o")
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.resolve() != target:
            raise ValueError("Runtime object path must not be a link")
        print(f"[{index}/{len(inputs)}] {relative.as_posix()}", flush=True)
        command = [str(compiler), *flags, "-c", str(source), "-o", str(target)]
        result = subprocess.run(command, env=environment, capture_output=True, text=True, errors="replace")
        log = output / "logs" / relative.with_suffix(".txt")
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(result.stdout + result.stderr, encoding="utf-8")
        if result.returncode:
            report["failures"].append({"source": relative.as_posix(), "log": str(log.relative_to(ROOT))})
            print(result.stderr[-4000:], flush=True)
        else:
            report["objects"].append({"path": str(target.relative_to(output)),
                                      "sha256": hashlib.sha256(target.read_bytes()).hexdigest()})
    report["seconds"] = round(time.monotonic() - started, 2)
    report["compiler"] = subprocess.check_output([str(compiler), "--version"], env=environment, text=True).splitlines()[0]
    report["layout_sha256"] = hashlib.sha256((generated / "layout.h").read_bytes()).hexdigest()
    if not report["failures"]:
        archive = output / "libdekuforge-runtime.a"
        # Start from a fresh archive so removed sources cannot leave stale members.
        temporary = output / "libdekuforge-runtime.pending.a"
        temporary.unlink(missing_ok=True)
        response = output / "archive.rsp"
        response.write_text("\n".join('"' + (output / entry["path"]).as_posix() + '"'
                                      for entry in report["objects"]), encoding="utf-8")
        subprocess.run([str(archiver), "rcs", str(temporary), "@" + str(response)], env=environment, check=True)
        temporary.replace(archive)
        report["archive"] = str(archive.relative_to(ROOT))
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Compiled {len(report['objects'])}/{len(inputs)} runtime sources; {len(report['failures'])} failures.")
    return bool(report["failures"])


if __name__ == "__main__":
    raise SystemExit(main())
