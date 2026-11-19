"""Run the native installer in an isolated folder without a game archive."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from dekuforge import COMPONENTS
    from dekuforge.update_package import validate_launcher_health

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--with-tools", action="store_true")
    args = parser.parse_args()
    setup = ROOT/"build/releases/DekuForge-Setup.exe"
    target = ROOT/"build"/f"independent-setup-{uuid.uuid4().hex[:8]}"
    flags = [] if args.with_tools else ["/SKIPTOOLS"]
    started = time.time()
    try:
        subprocess.run([str(setup), "/SILENT", "/NOLAUNCH", "/NOSHORTCUT", f"/DIR={target}", *flags],
                       check=True, timeout=1800 if args.with_tools else 600)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        logs = Path(tempfile.gettempdir()).glob("DekuForge-setup-*/setup.log")
        for log in logs:
            if log.stat().st_mtime >= started - 1:
                print(log.read_text(encoding="utf-8", errors="replace"), file=sys.stderr, flush=True)
                runtime_log = log.parent / "application/local/runtime-bootstrap.log"
                if runtime_log.is_file():
                    print(runtime_log.read_text(encoding="utf-8-sig", errors="replace"), file=sys.stderr, flush=True)
        raise
    meta = json.loads((target/"local/setup-result.json").read_text(encoding="utf-8"))
    assert meta["success"] and meta["components"] == COMPONENTS and meta["tools_prepared"] == args.with_tools
    proof = json.loads((target/"local/launcher-selftest.json").read_text(encoding="utf-8"))
    validate_launcher_health(proof, COMPONENTS)
    assert (target/"DekuForge.exe").is_file() and (target/"DekuForge-Uninstall.exe").is_file()
    assert not (target/"dekuforge/stable_engine.py").exists()
    assert not list(target.rglob("DekuForgeGame.exe"))
    if args.with_tools:
        config = json.loads((target/"local/open-engine-builder.json").read_text(encoding="utf-8"))
        assert config["enable_launcher_build"] and Path(config["toolchain"]).is_relative_to(target)
    print("Independent native setup accepted:", target, flush=True)


if __name__ == "__main__":
    main()
