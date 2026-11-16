"""Compile and link independently generated game modules with the permitted host runtime.

The resulting executable is experimental until its isolated boot/play tests pass.
This command never selects an installation or changes saves.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import shutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dekuforge.engine import verify_engine_sources
from dekuforge.engine_workspace import stage_engine
from dekuforge.boot_profile import write_boot_profile
from dekuforge.modules import normalize_prepared


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--romfs", type=Path, required=True)
    parser.add_argument("--toolchain", type=Path, required=True, help="MSYS2 UCRT64 bin directory")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    prepared = args.prepared.resolve()
    if not prepared.is_relative_to((ROOT / "build").resolve()):
        parser.error("Use a prepared input inside the project build directory")
    output = args.out.absolute()
    if not output.is_relative_to((ROOT / "build").resolve()) or output.resolve() != output:
        parser.error("Experimental native output must be inside the owned project build directory")
    marker = output / ".dekuforge-native"
    if output.exists() and any(output.iterdir()) and not marker.is_file():
        parser.error("Native output is not an owned build directory")
    output.mkdir(parents=True, exist_ok=True)
    marker.touch()
    verify_engine_sources()
    exefs = normalize_prepared(prepared)
    generated = prepared / "generated"
    for name in ("main", "subsdk0", "sdk"):
        manifest = json.loads((generated / name / "manifest.json").read_text(encoding="utf-8"))
        if manifest["stats"].get("unsupported", 1) or not manifest.get("function_count"):
            raise RuntimeError(f"{name}: complete supported CPU generation is required before linking")
        for chunk in manifest["chunks"] + [manifest["table"]]:
            path = generated / name / chunk
            if path.resolve() != path or path.parent != generated / name or not path.is_file():
                raise ValueError("Invalid generated chunk path")
    boot = write_boot_profile(prepared)
    engine = stage_engine()
    from tools.build_host_shaders import build_host_shaders
    build_host_shaders(engine, args.toolchain)
    sys.path[:0] = [str(engine / "tools"), str(engine / "recomp")]
    spec = importlib.util.spec_from_file_location("df_native_driver", engine / "tools" / "build_game.py")
    driver = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(driver)
    tools = args.toolchain.resolve()
    driver.UCRT = tools
    driver.CLANG, driver.AR, driver.WINDRES = tools / "clang.exe", tools / "ar.exe", tools / "windres.exe"
    driver.NINJA = ROOT / "local" / "build-tools" / "ninja-1.13.2" / "ninja.exe"
    driver.SDL3_DLLS = [tools / name for name in ("SDL3.dll", "libiconv-2.dll", "libopus-0.dll")]
    driver.VMA_INCLUDE = tools.parent / "include" / "vma"
    driver.EXE = "DekuForgeGame.exe"
    driver.DISPLAY_VERSIONS["v111"] = "1.1.1"
    driver.RT_FLAGS.extend(["-I", driver.cmd_path(boot)])
    linker = ROOT / "local" / "build-tools" / "shaders" / "ucrt64" / "bin" / "ld.lld.exe"
    if not linker.is_file():
        raise ValueError("The portable LLD linker is missing; provision the build tools first")
    driver.LINK_FLAGS[0] = "-fuse-ld=" + driver.cmd_path(linker)
    driver.LINK_LIBS.append("-l:libdav1d.a")
    expected = output / "expected-inputs.json"
    expected.write_text(json.dumps({"exefs_sha256": {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                                                    for path in exefs.iterdir() if path.is_file()}}, indent=2), encoding="utf-8")
    previous = sys.argv
    try:
        sys.argv = [str(engine / "tools" / "build_game.py"), "--version", "v111", "--gen", str(generated),
                    "--out", str(output), "--exefs", str(exefs), "--romfs", str(args.romfs.resolve()),
                    "--profile", str(output / "profile"), "--expected", str(expected), "--jobs", str(args.jobs),
                    "--full-build"]
        driver.main()
    finally:
        sys.argv = previous
    active = ROOT / "build" / "shader-compiler" / "active.json"
    if active.is_file():
        record = json.loads(active.read_text(encoding="utf-8"))
        translator = ROOT / record["executable"]
        if not translator.resolve().is_relative_to((ROOT / "build" / "shader-compiler").resolve()):
            raise ValueError("Shader executable points outside its owned build directory")
        if hashlib.sha256(translator.read_bytes()).hexdigest() != record["sha256"]:
            raise ValueError("Shader executable differs from its build record")
        for path in translator.parent.iterdir():
            if path.is_file() and path.suffix != ".pdb":
                shutil.copy2(path, output / path.name)
    from dekuforge import __version__
    from dekuforge.build_library import BuildLibrary
    info = output / "dekuforge-build-info.json"
    temporary = info.with_suffix(".tmp")
    temporary.write_text(json.dumps({"game_version": "1.1.1", "launcher_version": __version__,
                                     "experimental": True}, indent=2), encoding="utf-8")
    temporary.replace(info)
    BuildLibrary(ROOT).register(output / "DekuForgeGame.exe", version="1.1.1", owned=True)
    (output / "DekuForgeMesh.json").write_text(json.dumps({"python": sys.executable,
        "worker": str(ROOT / "tools/mesh_shader_worker.py"),
        "tools": str(ROOT / "local/build-tools/shaders/ucrt64/bin"), "toolchain": str(tools)}, indent=2), encoding="utf-8")
    print("Linked experimental game executable:", output / "DekuForgeGame.exe")


if __name__ == "__main__":
    main()
