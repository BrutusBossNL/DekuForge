"""Original build orchestration for an explicitly external NX2navi backend.

The backend is neither bundled nor relicensed. This adapter uses its documented
make_game command-line interface. It does not implement recompilation itself.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from .core import ROOT

MIN_FREE_BYTES = 40 * 1024 ** 3


@dataclass(frozen=True)
class Backend:
    root: Path

    @property
    def python(self):
        return self.root / "python" / "python.exe"

    @property
    def kit(self):
        version = (self.root / "app" / "current.txt").read_text(encoding="utf-8").strip()
        if not version or Path(version).name != version or "/" in version or "\\" in version or version in (".", ".."):
            raise ValueError("Ongeldige versie in de externe builder-installatie.")
        return self.root / "app" / version

    @property
    def compiler_root(self):
        return self.root / "toolchain" / "msys64" / "ucrt64"

    def validate(self, compiling=False):
        required = [self.python, self.kit / "tools" / "make_game.py"]
        if compiling:
            required += [self.compiler_root / "bin" / name for name in ("clang.exe", "lld.exe", "ninja.exe")]
        missing = [str(path) for path in required if not path.is_file()]
        if missing:
            raise ValueError("Externe builder onvolledig: " + ", ".join(missing))

    def command(self, nup, output, check=False, jobs=4):
        # A script entry point avoids relying on PATH or PYTHONPATH, which isolated
        # Windows Python intentionally ignores. Paths remain separate argv values.
        entry = ROOT / "backend_entry.py"
        args = [str(self.python), "-I", str(entry), str(self.kit / "tools" / "make_game.py"),
                str(self.root / "pydeps"), "--nup", str(nup), "--events"]
        if check:
            return args + ["--check"]
        return args + ["--out", str(output), "--msys", str(self.compiler_root), "--jobs", str(jobs)]


def default_backend():
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Programs" / "NX2navi"


def validate_nup(value):
    if not value:
        raise ValueError("Kies eerst je eigen NUP-bestand.")
    path = Path(value).expanduser().resolve()
    if path.suffix.lower() != ".nup" or not path.is_file():
        raise ValueError("Kies een bestaand .nup-bestand.")
    if path.stat().st_size == 0:
        raise ValueError("Het NUP-bestand is leeg.")
    return path


def output_directory(workspace=ROOT):
    workspace = workspace.resolve()
    build = workspace / "build"
    output = build / "game"
    if build.is_symlink() or build.resolve() != build or output.is_symlink() or output.resolve() != output:
        raise ValueError("De buildmap mag geen koppeling naar een andere installatie zijn.")
    if output.exists() and not (output / ".dekuforge-owned").is_file():
        raise ValueError("De doelmap bevat geen DekuForge-eigendomsmarkering; kies een lege project-buildmap.")
    # Reject junctions/symlinks inside an earlier output before the backend writes.
    if output.exists():
        for directory, folders, files in os.walk(output, followlinks=False):
            for name in folders + files:
                path = Path(directory) / name
                if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
                    raise ValueError("De buildmap bevat een bestandskoppeling; bouwen is gestopt.")
    return output


def run_build(nup_value, backend_value, notify, check=False, jobs=4, workspace=ROOT):
    """Run synchronously on a worker thread; emit (kind, value) to the UI queue.

    A project-wide exclusive lock covers checks and builds. Failed builds never
    replace the currently selected installation. No existing output is deleted.
    """
    nup = validate_nup(nup_value)
    backend = Backend(Path(backend_value).expanduser().resolve())
    backend.validate(compiling=not check)
    if not isinstance(jobs, int) or not 1 <= jobs <= (os.cpu_count() or 1):
        raise ValueError("Ongeldig aantal buildworkers.")
    output = output_directory(workspace)
    workspace = workspace.resolve()
    local = workspace / "local"
    local.mkdir(exist_ok=True)
    lock = local / "build.lock"
    try:
        handle = lock.open("x", encoding="utf-8")
    except FileExistsError:
        raise ValueError("Er loopt al een DekuForge-build of controle. Controleer dit voordat je local/build.lock verwijdert.") from None
    try:
        with handle:
            handle.write(str(os.getpid()))
            handle.flush()
            if not check:
                if shutil.disk_usage(workspace).free < MIN_FREE_BYTES:
                    raise ValueError("Minimaal 40 GiB vrije ruimte nodig voor een aparte gamebuild.")
                output.mkdir(parents=True, exist_ok=True)
                (output / ".dekuforge-owned").touch()
            logs = local / "logs"
            logs.mkdir(exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            log_path = logs / f"{'check' if check else 'build'}-{stamp}.log"
            environment = os.environ.copy()
            environment["PYTHONUNBUFFERED"] = "1"
            environment["PATH"] = str(backend.compiler_root / "bin") + os.pathsep + environment.get("PATH", "")
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            notify("log", "Externe NX2navi-backend; geen zelfstandige DekuForge-runtime.\n")
            notify("log", f"Logbestand: {log_path}\n")
            with log_path.open("w", encoding="utf-8") as log:
                with subprocess.Popen(backend.command(nup, output, check, jobs), cwd=str(backend.kit),
                                      env=environment, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                      text=True, encoding="utf-8", errors="replace", creationflags=flags) as process:
                    for line in process.stdout:
                        log.write(line)
                        log.flush()
                        if line.startswith("@@"):
                            try:
                                notify("progress", json.loads(line[2:]))
                            except ValueError:
                                notify("log", line)
                        else:
                            notify("log", line)
                    code = process.wait()
            if code:
                raise RuntimeError(f"Externe builder gestopt met code {code}. Zie {log_path}")
            if check:
                notify("checked", "NUP-controle geslaagd bij de externe backend.")
                return None
            executable = output / "ocarina.exe"
            if not executable.is_file() or executable.stat().st_size == 0:
                raise RuntimeError("Backend meldde succes maar leverde geen game-executable op.")
            notify("built", str(executable))
            return executable
    finally:
        lock.unlink(missing_ok=True)
