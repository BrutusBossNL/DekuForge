"""Check descriptor cleanup with real SPIR-V tools and synthetic shader inputs."""
import argparse
import os
import re
from pathlib import Path
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from mesh_shader_worker import validate_resource_bindings
from dekuforge.mesh_stage import vulkan_stage


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tools", type=Path, required=True)
    parser.add_argument("--toolchain", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    folder = root / "build/validation-mesh-resources"
    folder.mkdir(parents=True, exist_ok=True)
    source = folder / "synthetic.comp"
    source.write_text('''#version 460
layout(local_size_x=1) in;
layout(binding=1) uniform LiveInput { uint value; } live_input;
layout(binding=2) uniform Unused { uint value; } unused_buffer;
layout(binding=3) buffer Output { uint value; } result_buffer;
void main() { result_buffer.value = live_input.value; }
''', encoding="utf-8")
    environment = dict(os.environ)
    environment["PATH"] = str(args.tools.resolve()) + os.pathsep + str(args.toolchain.resolve()) + os.pathsep + environment.get("PATH", "")
    def run(name, *arguments):
        result = subprocess.run([str(args.tools / (name + ".exe")), *map(str, arguments)], env=environment, capture_output=True)
        if result.returncode:
            raise RuntimeError((result.stdout + result.stderr).decode("utf-8", errors="replace"))
    raw, cleaned = folder / "raw.spv", folder / "clean.spv"
    run("glslang", "-V", "--target-env", "vulkan1.2", source, "-o", raw)
    reflection = {"cbufs": [{"binding": 1}], "sbufs": [{"binding": 3}]}
    try:
        validate_resource_bindings(raw, reflection)
    except ValueError as error:
        assert "binding 2" in str(error)
    else:
        raise AssertionError("Fixture did not retain the unused declaration")
    run("spirv-opt", "--remove-unused-interface-variables", "--eliminate-dead-variables", raw, "-o", cleaned)
    run("spirv-val", "--target-env", "vulkan1.2", cleaned)
    validate_resource_bindings(cleaned, reflection)
    for missing in (1, 3):
        incomplete = {k: [x for x in values if x["binding"] != missing] for k, values in reflection.items()}
        try:
            validate_resource_bindings(cleaned, incomplete)
        except ValueError as error:
            assert f"binding {missing}" in str(error)
        else:
            raise AssertionError("Cleanup removed a live resource")
    print("Native shader resources: unused declaration removed, live read/write resources preserved")
    for kind in ("task", "mesh"):
        facts = dict(kind=kind, threads=32, payload=32, shared=1024,
                     stage_memory=[0, 16, 48, 768], task=True, vertices=3,
                     primitives=1, topology=3,
                     vertex=[("position", i) for i in range(4)], primitive=[], primitive_system=0)
        kernel = "#version 450\nlayout(local_size_x=32) in;\nshared uint stage_words[256];\nvoid main() {}\n"
        source = folder / ("checked." + kind)
        source.write_text(vulkan_stage(kernel, facts, 1), encoding="utf-8")
        compiled = folder / (kind + ".spv")
        run("glslang", "-V", "--target-env", "vulkan1.2", "-S", kind, source, "-o", compiled)
        run("spirv-val", "--target-env", "vulkan1.2", compiled)
        validate_resource_bindings(compiled, {"sbufs": [{"binding": 1}]})
        if kind == "mesh":
            assembly = folder / "mesh.spvasm"
            run("spirv-dis", compiled, "-o", assembly)
            text = assembly.read_text()
            position = re.search(r"OpMemberDecorate (\S+) (\d+) BuiltIn Position", text)
            if not position or f"OpMemberDecorate {position[1]} {position[2]} Invariant" not in text:
                raise AssertionError("Native mesh output lost position invariance")
    print("Task/mesh bounds-feedback shaders compiled and SPIR-V validated")


if __name__ == "__main__":
    main()
