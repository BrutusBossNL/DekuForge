"""Frozen, standard-library-only update helper; survives replacement of app sources."""
import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from update_package import atomic_json, install, rollback


def main():
    job_path = Path(sys.argv[1]).resolve()
    job = json.loads(job_path.read_text(encoding="utf-8"))
    root = Path(job["root"])
    ctypes.windll.kernel32.OpenProcess.restype=ctypes.c_void_p
    ctypes.windll.kernel32.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_ulong]
    ctypes.windll.kernel32.CloseHandle.argtypes=[ctypes.c_void_p]
    parent = ctypes.windll.kernel32.OpenProcess(0x100000, False, job["parent_pid"])
    if parent:
        try:
            if ctypes.windll.kernel32.WaitForSingleObject(parent, 60000) != 0:
                raise RuntimeError("The launcher did not exit; update cancelled")
        finally:
            ctypes.windll.kernel32.CloseHandle(parent)
    result = None
    try:
        result = install(Path(job["archive"]), root, log=lambda line: print(line, flush=True))
        subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File",
            str(root / "tools/bootstrap_runtime.ps1"), "-Root", str(root)], check=True, timeout=600,
            creationflags=subprocess.CREATE_NO_WINDOW)
        pin = result["components"]["python"]["id"]
        python = root / "python" / pin / "python.exe"
        report = root / "local/launcher-selftest.json"
        before = report.stat().st_mtime_ns if report.exists() else 0
        subprocess.run([str(python), str(root / "run_launcher.py"), "--self-test"], cwd=root,
            check=True, timeout=90, creationflags=subprocess.CREATE_NO_WINDOW)
        proof = json.loads(report.read_text(encoding="utf-8"))
        if report.stat().st_mtime_ns == before or not proof["success"] or len(proof["screens"]) != 40:
            raise RuntimeError("Updated launcher failed its health check")
        if result["components"]["launcher"].get("bug_reports") and len(proof.get("report_screens",[]))!=5:
            raise RuntimeError("Updated launcher failed its report-form checks")
        atomic_json(root / "local/pending-game-update.json", {**result, "release": job["release"], "status": "pending"})
        atomic_json(root / "local/update-result.json", {"success": True, "release": job["release"], **result})
    except Exception as error:
        if result:
            rollback(root, result["backup"])
        atomic_json(root / "local/update-result.json", {"success": False, "error": str(error), "release": job["release"]})
        print("Update rolled back:", error, flush=True)
    if job.get("restart", True):
        subprocess.Popen([str(root / "DekuForge.exe")], cwd=root, creationflags=subprocess.CREATE_NO_WINDOW)


if __name__ == "__main__":
    main()
