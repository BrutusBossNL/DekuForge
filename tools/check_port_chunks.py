"""Regenerate unsupported chunks into a separate validation folder and compile them.

The complete generation manifest is left unchanged. This is a focused extension
check, not permission to link a partially regenerated game.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dekuforge.engine_workspace import stage_engine


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--module", choices=("main", "subsdk0", "sdk"), default="main")
    parser.add_argument("--compiler", type=Path, required=True)
    args = parser.parse_args()
    prepared = args.prepared.resolve()
    if not prepared.is_relative_to((ROOT / "build").resolve()):
        parser.error("Use an owned prepared input inside the project build directory")
    generated = prepared / "generated"
    manifest_path = generated / args.module / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["stats"]["patched_sites"]:
        parser.error("This focused check currently supports unpatched generation only")
    engine = stage_engine()
    sys.path[:0] = [str(engine / "recomp"), str(engine / "tools")]
    import gen
    from module import Module
    module = Module(args.module, prepared / "normalized-exefs" / args.module, int(manifest["base"], 16))
    starts, _ = gen.discover(module)
    addresses = (module.lo + starts * 4).tolist()
    ends = dict(zip(addresses, addresses[1:] + [module.hi]))
    output = prepared / "validation-chunks" / args.module
    if output.resolve() != output:
        parser.error("Validation output must not be a link")
    output.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment["PATH"] = str(args.compiler.parent) + os.pathsep + environment.get("PATH", "")
    report = {"complete_generation_unchanged": True, "playable": False, "chunks": []}
    for name in manifest["chunks"]:
        if not re.fullmatch(args.module + r"_[0-9]{4}\.c", name):
            raise ValueError("Unexpected generated chunk name")
        text = (generated / args.module / name).read_text(encoding="utf-8")
        if not re.search(r'rt_udf\(c,.*?/\*', text):
            continue
        functions = [int(value, 16) for value in re.findall(r'^void f_([0-9a-f]+)\(Cpu \*c\) \{', text, re.MULTILINE)]
        if not functions or any(address not in ends for address in functions):
            raise ValueError("Generated function boundaries differ from discovery")
        emitter = gen.Emitter(module, set(addresses))
        number = int(name.rsplit("_", 1)[1][:-2])
        candidate = gen.chunk_text(args.module, number, emitter, [(address, ends[address]) for address in functions])
        if emitter.stats["unsupported"]:
            raise RuntimeError(f"{name}: still unsupported: {dict(emitter.unsupported)}")
        source, obj = output / name, output / (name + ".o")
        source.write_text(candidate, encoding="utf-8")
        subprocess.run([str(args.compiler), "-O1", "-fno-strict-aliasing", "-Wno-return-type", "-Wno-unused-label",
                        "-march=x86-64-v3", "-I", str(engine / "runtime"), "-I", str(generated),
                        "-c", str(source), "-o", str(obj)], env=environment, check=True)
        report["chunks"].append({"name": name, "functions": len(functions), "unsupported": 0,
                                  "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest()})
        print(f"{name}: {len(functions)} functions regenerated and compiled, 0 unsupported", flush=True)
    if not report["chunks"]:
        raise ValueError("No unsupported chunks were available to validate")
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
