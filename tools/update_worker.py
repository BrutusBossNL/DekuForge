"""Frozen, standard-library-only update helper; survives replacement of app sources."""
import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent))
from update_package import atomic_json, install, rollback, validate_launcher_health


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
        if report.stat().st_mtime_ns == before:
            raise RuntimeError("Updated launcher failed its health check")
        validate_launcher_health(proof, result['components'])
        if result.get("prepare_tools"):
            subprocess.run([str(python), "-B", str(root/"tools/prepare_installation.py")],
                           cwd=root, check=True, timeout=1800, creationflags=subprocess.CREATE_NO_WINDOW)
        pending = root / "local/pending-game-update.json"
        previous = json.loads(pending.read_text(encoding="utf-8")) if pending.is_file() and pending.stat().st_size <= 65536 else {}
        needs_game = result["requires_rebuild"] or (result["components"]["engine"].get("backend") == "independent"
            and previous.get("requires_rebuild") and previous.get("status") in {"pending", "failed"})
        atomic_json(pending, {**result, "requires_rebuild": bool(needs_game), "release": job["release"], "status": "pending"})
        atomic_json(root / "local/update-result.json", {"success": True, "release": job["release"],
            'job': job_path.parent.name, 'time': datetime.now(timezone.utc).isoformat(), **result})
    except Exception as error:
        if result:
            rollback(root, result["backup"])
        atomic_json(root / "local/update-result.json", {"success": False, "error": str(error), "release": job["release"],
            'job': job_path.parent.name, 'time': datetime.now(timezone.utc).isoformat()})
        print("Update rolled back:", error, flush=True)
    if job.get("restart", True):
        subprocess.Popen([str(root / "DekuForge.exe")], cwd=root, creationflags=subprocess.CREATE_NO_WINDOW)


if __name__ == "__main__":
    main()
