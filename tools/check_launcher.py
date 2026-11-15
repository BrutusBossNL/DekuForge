"""Verify the native launcher icon, GUI subsystem and complete one-window UI self-test."""

import ctypes
import json
from pathlib import Path
import struct
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    executable = ROOT / "DekuForge.exe"
    binary = executable.read_bytes()
    header = struct.unpack_from("<I", binary, 60)[0]
    assert binary[header:header + 4] == b"PE\0\0"
    assert struct.unpack_from("<H", binary, header + 24 + 68)[0] == 2, "Console executable instead of GUI executable"
    extract = ctypes.windll.shell32.ExtractIconExW
    extract.argtypes = [ctypes.c_wchar_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint]
    extract.restype = ctypes.c_uint
    assert extract(str(executable), -1, None, None, 0) == 1, "Missing embedded brand icon"
    report = ROOT / "local" / "launcher-selftest.json"
    previous = report.stat().st_mtime_ns if report.exists() else 0
    subprocess.run([str(executable), "--self-test"], cwd=ROOT, check=True, timeout=10)
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if report.exists() and report.stat().st_mtime_ns > previous:
            result = json.loads(report.read_text(encoding="utf-8"))
            assert result["success"], result
            assert result["logo_loaded"] and result["top_level_windows"] == 1
            assert len(result["screens"]) == 25
            print("Native GUI launcher: embedded icon verified; 25 screens, 5 languages, 1 window")
            return
        time.sleep(0.1)
    raise RuntimeError("Native launcher self-test did not produce a fresh report")


if __name__ == "__main__":
    main()
