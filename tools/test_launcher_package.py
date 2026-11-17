"""Test the native package bootstrap in a new folder without installed runtimes."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dekuforge import COMPONENTS


def main():
    package = ROOT / "build/releases" / ("DekuForge-launcher-" + COMPONENTS["launcher"]["version"] + "-windows.zip")
    target = ROOT / "build" / ("launcher-install-smoke-" + uuid.uuid4().hex[:8])
    target.mkdir()
    with zipfile.ZipFile(package) as archive:
        for name in archive.namelist():
            if not (target / name).resolve().is_relative_to(target):
                raise ValueError("Unsafe package path")
        archive.extractall(target)
    inventory = json.loads((target / "launcher-package.json").read_text(encoding="utf-8"))
    for name, digest in inventory["sha256"].items():
        assert hashlib.sha256((target / name).read_bytes()).hexdigest() == digest, name
    assert not (target / "python").exists()
    assert not (target / "local").exists()
    subprocess.run([str(target / "DekuForge.exe"), "--self-test"], cwd=target, check=True, timeout=180)
    report = target / "local/launcher-selftest.json"
    deadline = time.monotonic() + 45
    while not report.is_file() and time.monotonic() < deadline:
        time.sleep(.2)
    result = json.loads(report.read_text(encoding="utf-8"))
    assert result["success"] and len(result["screens"]) == 40, result
    assert result["logo_loaded"] and result["native_icon_verified"]
    runtime = target / "python" / COMPONENTS["python"]["id"]
    assert (runtime / "python.exe").is_file()
    print("Fresh package: downloaded and verified its own runtime; 40 screens passed:", target)


if __name__ == "__main__":
    main()
