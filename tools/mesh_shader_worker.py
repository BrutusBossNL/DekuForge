"""Translate an NVN2 task/mesh request to a native Vulkan stage, locally only."""
import json
import os
from pathlib import Path
import subprocess
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dekuforge.mesh_stage import metadata, vulkan_stage


def preserve_fused_arithmetic(module):
    """Keep native FFMA's single rounding across the GLSL stage-wrapper round trip.

    glslang preserves precise add/multiply operations but drops NoContraction
    from GLSL.std.450 Fma, even when its GLSL result is precise. Without that
    decoration a driver may use separately rounded multiply/add operations.
    """
    path = Path(module)
    data = path.read_bytes()
    if len(data) < 20 or len(data) % 4:
        raise ValueError("Truncated native shader module")
    words = list(struct.unpack(f"<{len(data)//4}I", data))
    if words[0] != 0x07230203:
        raise ValueError("Invalid native shader module magic")
    imports, precise, fused = set(), set(), set()
    offset, types = 5, None
    while offset < len(words):
        count, opcode = words[offset] >> 16, words[offset] & 0xffff
        if not count or offset + count > len(words):
            raise ValueError("Malformed native shader instruction")
        operands = words[offset+1:offset+count]
        if opcode == 11 and count >= 3:
            name = struct.pack(f"<{len(operands)-1}I", *operands[1:]).split(b"\0", 1)[0]
            if name == b"GLSL.std.450":
                imports.add(operands[0])
        elif opcode == 71 and count == 3 and operands[1] == 42:
            precise.add(operands[0])
        elif opcode == 12 and count >= 5 and operands[2] in imports and operands[3] == 50:
            fused.add(operands[1])
        if types is None and 19 <= opcode <= 39:
            types = offset
        offset += count
    missing = sorted(fused - precise)
    if missing:
        if types is None:
            raise ValueError("Native shader module has no type section")
        decorations = [word for result in missing for word in ((3 << 16) | 71, result, 42)]
        words[types:types] = decorations
        path.write_bytes(struct.pack(f"<{len(words)}I", *words))
    return len(missing)


def validate_resource_bindings(module, resources):
    """Reject native modules whose declared descriptors lack host reflection."""
    data = Path(module).read_bytes()
    if len(data) < 20 or len(data) % 4:
        raise ValueError("Truncated native shader module")
    words = struct.unpack(f"<{len(data)//4}I", data)
    known = {0} | {item["binding"] for kind in ("cbufs", "sbufs", "textures", "images")
                   for item in resources.get(kind, [])}
    offset = 5
    while offset < len(words):
        count, opcode = words[offset] >> 16, words[offset] & 0xffff
        if not count or offset + count > len(words):
            raise ValueError("Malformed native shader instruction")
        if opcode == 71 and count >= 4 and words[offset+2] == 33:
            binding = words[offset+3]
            if binding not in known:
                raise ValueError(f"Native shader binding {binding} lacks resource reflection")
        offset += count


def compile_stage(job, output, translator, tools, toolchain):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    key = job["key"]
    if not isinstance(key, str) or len(key) != 64 or any(c not in "0123456789abcdef" for c in key):
        raise ValueError("Invalid shader key")
    destination = output
    output = destination / (key + ".mesh-work")
    if output.resolve() != output:
        raise ValueError("Shader workspace must not be a link")
    output.mkdir(exist_ok=True)
    control = bytes.fromhex(job["mesh_control"])
    code = Path(job["code"]).read_bytes()
    facts = metadata(control, code)
    facts["diagnostic_tag"] = int(key[:8], 16)
    original = output / (key + ".kernel.code")
    original.write_bytes(code[0x80:facts["instructions"]])
    kernel = dict(job)
    kernel.pop("mesh_control")
    kernel.pop("emit_glsl", None)
    kernel.update(stage="cs", code=str(original), ampere=True, stage_memory=facts["stage_memory"],
                  local=[facts["threads"], 1, 1], shared=facts["shared"])
    jobs = output / (key + ".kernel.json")
    jobs.write_text(json.dumps([kernel]), encoding="utf-8")
    env = os.environ.copy()
    env["PATH"] = str(tools) + os.pathsep + str(toolchain) + os.pathsep + env.get("PATH", "")
    def run(arguments):
        result = subprocess.run([str(x) for x in arguments], env=env, capture_output=True, timeout=120)
        if result.returncode:
            raise RuntimeError((result.stderr + result.stdout).decode("utf-8", errors="replace")[-6000:])
    run([translator, jobs, output])
    module = output / (key + ".spv")
    glsl = output / (key + ".kernel.glsl")
    run([tools / "spirv-cross.exe", module, "--vulkan-semantics", "--output", glsl])
    reflection = output / (key + ".res.json")
    resources = json.loads(reflection.read_text(encoding="utf-8"))
    checks_binding = max([0] + [item["binding"] + max(1, item.get("array", 1)) - 1
                              for kind in ("cbufs", "sbufs", "textures", "images")
                              for item in resources.get(kind, [])]) + 1
    resources.setdefault("sbufs", []).append({"binding": checks_binding, "slot": 0,
                                             "cb_slot": 254, "cb_offset": 0, "flags": 1})
    stage = "task" if facts["kind"] == "task" else "mesh"
    source = output / (key + "." + stage)
    source.write_text(vulkan_stage(glsl.read_text(encoding="utf-8"), facts, checks_binding), encoding="utf-8")
    compiled = output / (key + ".native.spv")
    run([tools / "glslang.exe", "-V", "--target-env", "vulkan1.2", "-S", stage, source, "-o", compiled])
    # The GLSL round trip retains declarations removed from translator reflection.
    # Remove only unreachable interface variables, then their dead declarations.
    cleaned = output / (key + ".clean.spv")
    run([tools / "spirv-opt.exe", "--remove-unused-interface-variables", "--eliminate-dead-variables",
         compiled, "-o", cleaned])
    cleaned.replace(compiled)
    preserve_fused_arithmetic(compiled)
    run([tools / "spirv-val.exe", "--target-env", "vulkan1.2", compiled])
    validate_resource_bindings(compiled, resources)
    resources["stage"] = "ts" if stage == "task" else "ms"
    resources["mesh"] = facts
    # Native artifacts replace the intermediate kernel only after validation.
    reflection.write_text(json.dumps(resources), encoding="utf-8")
    compiled.replace(destination / module.name)
    reflection.replace(destination / reflection.name)


def main():
    request, output, translator, tools, toolchain = map(Path, sys.argv[1:])
    job = json.loads(request.read_text(encoding="utf-8"))
    compile_stage(job, output, translator, tools, toolchain)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
