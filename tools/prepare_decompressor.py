"""Provision the pinned open-source NUP decompressor, without any game input."""
import importlib
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]


def main():
    source=ROOT/"build/engine-0.10.1"
    if not (source/".dekuforge-stable-engine").is_file():
        raise ValueError("Prepare the verified source first")
    target=ROOT/"pydeps"
    if target.resolve()!=target:
        raise ValueError("Decompressor directory must not be linked")
    sys.path.insert(0,str(source))
    package=importlib.import_module("launcher");package.NAME="DekuForge"
    tools=importlib.import_module("launcher.toolchain")
    downloads=ROOT/"local/downloads";downloads.mkdir(parents=True,exist_ok=True)
    layout=SimpleNamespace(pydeps=target,downloads=downloads,python_for_builds=lambda:sys.executable)
    tools.ensure_zbic(layout,log=lambda value:print(value,flush=True),version="buildkit-0.1.0")


if __name__=="__main__":main()
