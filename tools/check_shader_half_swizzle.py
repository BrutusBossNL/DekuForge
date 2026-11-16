"""Check synthetic half arithmetic's scalar and uniform lane selection."""
import argparse
import json
import os
import re
from pathlib import Path
import subprocess
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_shader_scoreboards import instruction


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--translator", type=Path, required=True)
    parser.add_argument("--tools", type=Path, required=True)
    parser.add_argument("--toolchain", type=Path, required=True)
    args = parser.parse_args()
    folder = Path(__file__).resolve().parents[1] / "build/validation-half-swizzle"
    folder.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["PATH"] = os.pathsep.join([str(args.tools.resolve()), str(args.toolchain.resolve()), env.get("PATH", "")])
    def run(*command):
        result = subprocess.run(list(map(str, command)), env=env, capture_output=True, timeout=60)
        if result.returncode:
            raise RuntimeError((result.stdout + result.stderr).decode(errors="replace"))
    # HADD2 R2, R0.F32, RZ: the whole 1.5f value must reach both half lanes.
    source = folder / "scalar.code"
    source.write_bytes(b"".join([
        instruction(0x802, rd=0, value=struct.unpack('<I', struct.pack('<f', 1.5))[0]),
        instruction(0x230, rd=2, ra=0, value=255, extra=1 << 74),
        instruction(0x388, ra=255, value=2, extra=4 << 73),
        instruction(0x94d, extra=7 << 87),
    ]))
    jobs = folder / "scalar.json"
    jobs.write_text(json.dumps([dict(key="scalar", stage="cs", ampere=True,
        code=str(source), local=[1, 1, 1], shared=4)]))
    run(args.translator.resolve(), jobs, folder)
    module = folder / "scalar.spv"
    run(args.tools / "spirv-val.exe", "--target-env", "vulkan1.2", module)
    glsl = folder / "scalar.glsl"
    run(args.tools / "spirv-cross.exe", module, "--vulkan-semantics", "--output", glsl)
    output = glsl.read_text()
    if "vec2(1.5)" not in output and "vec2(1.5, 1.5)" not in output and "1040203264u" not in output:
        raise AssertionError("Scalar half arithmetic did not preserve 1.5 in both lanes; inspect " + str(glsl))
    for swizzle, component in ((2, "x"), (3, "y")):
        key = f"uniform-{component}"
        source = folder / (key + ".code")
        source.write_bytes(b"".join([
            instruction(0xa30, rd=2, ra=255, value=0, extra=swizzle << 60),
            instruction(0x388, ra=255, value=2, extra=4 << 73),
            instruction(0x94d, extra=7 << 87),
        ]))
        jobs = folder / (key + ".json")
        jobs.write_text(json.dumps([dict(key=key, stage="cs", ampere=True,
            code=str(source), local=[1, 1, 1], shared=4)]))
        run(args.translator.resolve(), jobs, folder)
        module = folder / (key + ".spv")
        run(args.tools / "spirv-val.exe", "--target-env", "vulkan1.2", module)
        glsl = folder / (key + ".glsl")
        run(args.tools / "spirv-cross.exe", module, "--vulkan-semantics", "--output", glsl)
        lanes = re.findall(r"unpackHalf2x16\(.*?\)\.([xy])", glsl.read_text())
        if not lanes or any(lane != component for lane in lanes):
            raise AssertionError(f"{key}: wrong uniform lane selection {lanes}; see {glsl}")
    print("Scalar 1.5 and both uniform half-lane broadcasts pass; all synthetic modules validate.")


if __name__ == "__main__":
    main()
