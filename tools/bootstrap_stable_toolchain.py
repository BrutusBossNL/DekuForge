"""Install the stable release's verified native packages into an owned workspace."""
import argparse
import hashlib
import importlib
import os
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", action="store_true", help="Validate and describe the pinned packages without installing")
    args = parser.parse_args()
    source = ROOT / "build/engine-0.10.1"
    if not (source / ".dekuforge-stable-engine").is_file():
        raise ValueError("Prepare the pinned stable source first")
    sys.path.insert(0, str(source))
    package = importlib.import_module("launcher")
    package.NAME = "DekuForge"
    tools = importlib.import_module("launcher.toolchain")
    target = ROOT / "local/build-tools/native"
    if target.resolve() != target:
        raise ValueError("Native tool workspace must not be linked")
    layout = SimpleNamespace(toolchain=target, msys_root=target / "msys64",
        msys=target / "msys64/ucrt64", pkgs=target / "packages",
        lock_file=source / "toolchain.lock.json", app=source, dev=True)
    lock = tools.load_lock(layout, version="0.10.1")
    print(f"Stable native tools: {len(lock['packages'])} pinned packages, {sum(p['csize'] for p in lock['packages']) / 1e6:.0f} MB", flush=True)
    if args.plan:
        return
    target.mkdir(parents=True, exist_ok=True)
    if tools.is_current(layout, lock):
        print("Native toolchain matches the stable release", flush=True)
        return
    # Reuse independently verified package archives, never another installation's mutable tools.
    reuse = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/NX2navi/toolchain/pkgs"
    layout.pkgs.mkdir(parents=True, exist_ok=True)
    for entry in lock["packages"]:
        old = reuse / entry["filename"]
        new = layout.pkgs / entry["filename"]
        if not new.exists() and old.is_file() and old.stat().st_size == entry["csize"]:
            with old.open("rb") as stream:
                correct = hashlib.file_digest(stream, "sha256").hexdigest() == entry["sha256"]
            if correct:
                shutil.copy2(old, new)
    def progress(phase, done, total):
        print(f"Native tools {phase}: {done} / {total}", flush=True)
    tools.install(layout, lock, progress=progress, log=lambda line: print(line, flush=True), version="0.10.1")
    if tools.missing_files(layout.msys):
        raise RuntimeError("Stable native toolchain installation is incomplete")


if __name__ == "__main__":
    main()
