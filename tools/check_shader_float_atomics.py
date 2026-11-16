"""Check synthetic floating-point reductions and their emitted CAS loops."""
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
    parser.add_argument("--assembly", type=Path)
    parser.add_argument("--dotnet", default="dotnet")
    args = parser.parse_args()
    folder = Path(__file__).resolve().parents[1] / "build/validation-float-atomics"
    folder.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["PATH"] = os.pathsep.join([str(args.tools.resolve()), str(args.toolchain.resolve()), env.get("PATH", "")])
    def run(*command):
        result = subprocess.run(list(map(str, command)), env=env, capture_output=True, timeout=60)
        output = (result.stdout + result.stderr).decode(errors="replace")
        if result.returncode or "Invalid reduction type" in output:
            raise RuntimeError(output)
    for name, opcode in (("global-reduce", 0x98e), ("global-return", 0x9a8), ("shared-return", 0x38c)):
        source = folder / (name + ".code")
        source.write_bytes(b"".join([
            instruction(0x802, rd=0, value=0),
            instruction(0x802, rd=2, value=0x3fc00000),  # 1.5f
            instruction(opcode, rd=4, ra=0, value=2, extra=3 << 73),
            instruction(0x388, ra=255, value=4, extra=4 << 73),
            instruction(0x94d, extra=7 << 87),
        ]))
        jobs = folder / (name + ".json")
        jobs.write_text(json.dumps([dict(key=name, stage="cs", ampere=True,
            code=str(source), local=[32, 1, 1], shared=8)]))
        run(args.translator.resolve(), jobs, folder)
        module = folder / (name + ".spv")
        run(args.tools / "spirv-val.exe", "--target-env", "vulkan1.2", module)
        glsl = folder / (name + ".glsl")
        run(args.tools / "spirv-cross.exe", module, "--vulkan-semantics", "--output", glsl)
        text = glsl.read_text()
        if "atomicCompSwap" not in text or "1.5" not in text:
            raise AssertionError(f"{name}: floating addition or atomic update missing")
    print("Global reductions, returned atomics and shared atomics retain float addition and CAS; modules validate.")
    if args.assembly:
        import shutil
        shutil.copyfile(Path(__file__).with_name("shader_atomic_ir_check.cs"), folder / "Program.cs")
        project = folder / "Check.csproj"
        project.write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType>'
                           '<TargetFramework>net10.0</TargetFramework></PropertyGroup></Project>')
        env.update(DOTNET_CLI_TELEMETRY_OPTOUT="1", DOTNET_GENERATE_ASPNET_CERTIFICATE="false",
                   DOTNET_CLI_HOME=str(folder))
        subprocess.run([args.dotnet, "run", "--project", str(project), "--configuration", "Release",
                        "--", str(args.assembly.resolve())], env=env, check=True)


if __name__ == "__main__":
    main()
