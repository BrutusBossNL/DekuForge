"""Validate typed compute-image stores using synthetic Ampere instructions."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_shader_scoreboards import instruction


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--translator", type=Path, required=True)
    parser.add_argument("--tools", type=Path, required=True)
    parser.add_argument("--toolchain", type=Path, required=True)
    args = parser.parse_args()
    folder = Path(__file__).resolve().parents[1] / "build/validation-image-formats"
    folder.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["PATH"] = os.pathsep.join([str(args.tools.resolve()), str(args.toolchain.resolve()), env.get("PATH", "")])
    def run(*command):
        result = subprocess.run(list(map(str, command)), env=env, capture_output=True, timeout=60)
        if result.returncode:
            raise RuntimeError((result.stdout + result.stderr).decode(errors="replace"))
    for fmt, declaration in (("R16G16Uint", "uimage2D"), ("R16G16Sint", "iimage2D"), ("R16G16Float", "image2D")):
        key = "store-" + fmt
        source = folder / (key + ".code")
        source.write_bytes(b"".join([
            instruction(0x802, rd=0, value=0), instruction(0x802, rd=1, value=0),
            instruction(0x802, rd=2, value=0x1234), instruction(0x802, rd=3, value=0x5678),
            instruction(0xb9b, ra=0, value=2, extra=84 << 40 | 3 << 61 | 3 << 72),
            instruction(0x94d, extra=7 << 87),
        ]))
        job = dict(key=key, stage="cs", ampere=True, code=str(source), local=[1,1,1], shared=0,
                   nvn2_tex_base=304, nvn2_tex_count=4, nvn2_img_base=336, nvn2_img_count=1,
                   img={"0": {"type":"2d", "fmt":fmt}})
        jobs = folder / (key + ".json")
        jobs.write_text(json.dumps([job]))
        run(args.translator.resolve(), jobs, folder)
        module = folder / (key + ".spv")
        run(args.tools / "spirv-val.exe", "--target-env", "vulkan1.2", module)
        glsl = folder / (key + ".glsl")
        run(args.tools / "spirv-cross.exe", module, "--vulkan-semantics", "--output", glsl)
        text = glsl.read_text()
        assert " " + declaration + " " in text, text
        reflection = json.loads((folder / (key + ".res.json")).read_text())
        assert reflection["img_queried"] == [0], reflection
        if fmt.endswith("Uint"):
            assert "uvec4(4660u, 22136u" in text, text
        elif fmt.endswith("Sint"):
            assert "ivec4(4660, 22136" in text, text
    print("Unsigned, signed and float compute-image stores preserve descriptor types and integer bits.")


if __name__ == "__main__":
    main()
