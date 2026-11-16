"""Translate synthetic Ampere programs and check deferred writes across joins."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess


def instruction(opcode, *, pred=7, rd=0, ra=0, value=0, extra=0, barrier=7):
    return (opcode | pred << 12 | rd << 16 | ra << 24 | value << 32 |
            extra | barrier << 110).to_bytes(16, "little")


def fixture(value, predicate):
    # P0 is constant true/false, with the complementary result discarded (PT).
    compare = (7 if predicate else 0) << 76 | 7 << 84 | 7 << 87
    return b"".join([
        instruction(0x20c, ra=255, value=255, extra=compare),
        # An untaken branch creates a join after the predicated instruction.
        instruction(0x947, pred=15, value=48, extra=7 << 87),
        instruction(0x802, rd=7, value=value),
        instruction(0x309, rd=7, value=7, barrier=1),
        instruction(0x802, pred=0, rd=9, value=123),
        # The pending POPC result must reach this store on BOTH predicate paths.
        instruction(0x388, ra=255, value=7, extra=4 << 73),
        instruction(0x94d, extra=7 << 87),
    ])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--translator", type=Path, required=True)
    parser.add_argument("--tools", type=Path, required=True)
    parser.add_argument("--toolchain", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    folder = root / "build/validation-shader-scoreboards"
    folder.mkdir(parents=True, exist_ok=True)
    environment = dict(os.environ)
    environment["PATH"] = os.pathsep.join([str(args.tools.resolve()),
        str(args.toolchain.resolve()), environment.get("PATH", "")])
    def run(*command):
        result = subprocess.run(list(map(str, command)), env=environment,
                                capture_output=True, timeout=60)
        if result.returncode:
            raise RuntimeError((result.stdout + result.stderr).decode(errors="replace"))
    for predicate in (False, True):
        for value in (0, 5, 0xffffffff, 0x80000000):
            key = f"predicate-{int(predicate)}-value-{value:x}"
            source = folder / (key + ".code")
            source.write_bytes(fixture(value, predicate))
            jobs = folder / (key + ".json")
            jobs.write_text(json.dumps([dict(key=key, stage="cs", ampere=True,
                code=str(source), local=[1, 1, 1], shared=4)]), encoding="utf-8")
            run(args.translator.resolve(), jobs, folder)
            module = folder / (key + ".spv")
            run(args.tools / "spirv-val.exe", "--target-env", "vulkan1.2", module)
            glsl = folder / (key + ".glsl")
            run(args.tools / "spirv-cross.exe", module, "--vulkan-semantics", "--output", glsl)
            text = glsl.read_text()
            shared_name = re.search(r"shared uint (\w+)\[1\];", text).group(1)
            stores = re.findall(re.escape(shared_name) + r"\[0\] = (\d+)u?;", text)
            expected = value.bit_count()
            if stores != [str(expected)]:
                raise AssertionError(f"{key}: expected shared[0]={expected}, got {stores}; see {glsl}")
    print("Eight synthetic deferred-write paths match independent population counts.")


if __name__ == "__main__":
    main()
