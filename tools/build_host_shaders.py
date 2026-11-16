"""Rebuild stale host-owned GLSL shaders without changing the pinned engine import."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dekuforge.engine_workspace import stage_engine


def build_host_shaders(engine, toolchain):
    sys.path.insert(0, str(engine / "tools"))
    import build_shaders
    tools = ROOT / "local" / "build-tools" / "shaders" / "ucrt64" / "bin"
    environment = os.environ.copy()
    environment["PATH"] = str(tools) + os.pathsep + str(toolchain.resolve()) + os.pathsep + environment.get("PATH", "")
    for source in build_shaders.stale(engine / "runtime"):
        digest = build_shaders.source_hash(source)
        output = ROOT / "build" / "host-shaders" / digest
        output.mkdir(parents=True, exist_ok=True)
        binary = output / (source.stem + ".spv")
        subprocess.run([str(tools / "glslc.exe"), "-O", "--target-env=vulkan1.1",
                        "-fshader-stage=" + build_shaders.STAGES[source.suffix], "-o", str(binary), str(source)],
                       env=environment, check=True)
        subprocess.run([str(tools / "spirv-val.exe"), "--target-env", "vulkan1.1", str(binary)], env=environment, check=True)
        payload = binary.read_bytes()
        words = [int.from_bytes(payload[index:index + 4], "little") for index in range(0, len(payload), 4)]
        header = output / (source.stem + "_spv.h")
        header.write_text(build_shaders.header_of(source, words), encoding="utf-8")
        shutil.copyfile(header, build_shaders.header_path(source))
        print("Rebuilt and validated host shader:", source.name, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--toolchain", type=Path, required=True)
    args = parser.parse_args()
    build_host_shaders(stage_engine(), args.toolchain)


if __name__ == "__main__":
    main()
