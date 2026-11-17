"""Bounded launcher packages and recoverable, data-preserving file transactions."""
import hashlib
import json
import os
import re
from pathlib import Path, PurePosixPath
import shutil
import struct
import tempfile
import uuid
import zipfile

SOURCE_DIRS = {"dekuforge", "tools", "launcher", "engine_overrides", "docs", "installer"}
SOURCE_SUFFIXES = {".py", ".ps1", ".json", ".c", ".cpp", ".h", ".patch", ".md", ".txt"}
ROOT_FILES = {"run_launcher.py", "run_builder.py", "backend_entry.py", "engine_entry.py",
              "README.md", "roadmap.md", "LICENSE", "THIRD_PARTY_NOTICES.md", "CONTRIBUTING.md"}
ARTWORK = {"logo.png", "icon.png", "launcher.ico", "background.png",
           "home-actions.png", "home-play.png", "home-update.png", "home-build.png"}
MAX_PACKAGE = 128 * 1024**2
MAX_EXPANDED = 256 * 1024**2


def allowed(name):
    p = PurePosixPath(name)
    if (not name or "\\" in name or any(char in name for char in ':<>"|?*') or p.is_absolute()
            or any(x in {"", ".", ".."} or x.endswith((".", " ")) for x in name.split("/"))
            or any(x.split(".")[0].rstrip(" ").upper() in {"CON", "PRN", "AUX", "NUL", *[f"COM{i}" for i in range(10)],
                    *[f"LPT{i}" for i in range(10)]} for x in p.parts)):
        return False
    if name == "DekuForge.exe" or name in ROOT_FILES:
        return True
    if p.parts[:2] == ("assets", "branding") and len(p.parts) == 3:
        return p.name in ARTWORK
    return len(p.parts) > 1 and p.parts[0] in SOURCE_DIRS and p.suffix in SOURCE_SUFFIXES


def checked_path(root, name):
    target = root / name
    if not allowed(name) or not target.resolve().is_relative_to(root.resolve()):
        raise ValueError("Unsafe application package path: " + name)
    for item in (target, *target.parents):
        if item.is_symlink() or getattr(item, "is_junction", lambda: False)():
            raise ValueError("Linked installation path refused")
        if item == root:
            break
    return target


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    if temporary.is_symlink():
        raise ValueError("Linked transaction temporary file refused")
    with temporary.open("w",encoding="utf-8") as output:
        output.write(json.dumps(value,indent=2)+"\n")
        output.flush();os.fsync(output.fileno())
    temporary.replace(path)


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def validate_launcher(data):
    if len(data) < 128 or len(data) > 2 * 1024**2 or data[:2] != b"MZ":
        raise ValueError("Expected a small native GUI launcher")
    offset = struct.unpack_from("<I", data, 60)[0]
    if (offset + 94 > len(data) or data[offset:offset+4] != b"PE\0\0"
            or struct.unpack_from("<H", data, offset + 24 + 68)[0] != 2
            or "DekuForge".encode("utf-16le") not in data):
        raise ValueError("Invalid DekuForge launcher executable")


def validate_package(archive):
    if archive.stat().st_size > MAX_PACKAGE:
        raise ValueError("Application package exceeds download limit")
    with zipfile.ZipFile(archive) as source:
        entries = source.infolist()
        names = [entry.filename for entry in entries]
        if (len(entries) > 10000 or len({name.casefold() for name in names}) != len(names)
                or sum(entry.file_size for entry in entries) > MAX_EXPANDED):
            raise ValueError("Application archive size or name collision")
        for entry in entries:
            if (entry.is_dir() or (entry.external_attr >> 16) & 0o170000 == 0o120000
                    or entry.filename != "launcher-package.json" and not allowed(entry.filename)):
                raise ValueError("Unexpected application member: " + entry.filename)
        if source.getinfo("launcher-package.json").file_size > 2 * 1024**2:
            raise ValueError("Oversized package inventory")
        inventory = json.loads(source.read("launcher-package.json"))
        if inventory.get("contains_game_files") is not False:
            raise ValueError("Application package must declare no game files")
        hashes = inventory["sha256"]
        if set(hashes) != set(names) - {"launcher-package.json"}:
            raise ValueError("Package inventory does not cover every member")
        required = {"DekuForge.exe", "run_launcher.py", "dekuforge/components.json", "tools/bootstrap_runtime.ps1"}
        if not required <= hashes.keys():
            raise ValueError("Application package is incomplete")
        for name, digest in hashes.items():
            data = source.read(name)
            if hashlib.sha256(data).hexdigest() != digest:
                raise ValueError("Package member checksum mismatch: " + name)
            if name == "DekuForge.exe":
                validate_launcher(data)
            elif (data.startswith((b"NSO0", b"NUP\1", b"PFS0", b"DFROMFS1", b"\x7fELF", b"MZ"))
                  or re.search(rb"(?m)^\s*(?://|/\*|\*)\s*(?:DEKUFORGE|NX2NAVI)_RECOMP_GENERATED_FROM_GAME_CODE\b",data[:8192])):
                raise ValueError("Game or unexpected executable content refused")
        if json.loads(source.read("dekuforge/components.json")) != inventory["components"]:
            raise ValueError("Component manifest differs from package inventory")
        return inventory


def build_input(name):
    return (name.startswith("engine_overrides/") or name in {
        "dekuforge/stable_engine.py", "dekuforge/stable_engine_source.json", "dekuforge/runtime_layer.py",
        "dekuforge/shader_tools.lock.json", "dekuforge/source_patch.py", "tools/build_stable_translator.py", "tools/run_stable_build.py",
        "tools/bootstrap_stable_toolchain.py", "tools/bootstrap_shader_tools.py", "assets/branding/logo.png"})


def needs_rebuild(root, inventory):
    return any(not (root / name).is_file() or sha(root / name) != digest
               for name, digest in inventory["sha256"].items() if build_input(name))


def recover(root):
    journal = root / "local/update-transaction.json"
    if not journal.is_file():
        return
    state = json.loads(journal.read_text(encoding="utf-8"))
    backup = root / "local/update-backups" / state["id"]
    if backup.resolve() != backup or len(state["id"]) != 32 or not all(c in "0123456789abcdef" for c in state["id"]):
        raise ValueError("Unsafe recovery identity")
    for item in reversed(state["changes"]):
        name = item["name"]
        target = checked_path(root, name)
        previous = backup / name
        if item["existed"]:
            if not previous.is_file():
                raise ValueError("Recovery copy is missing: " + name)
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(target.name + ".restore")
            shutil.copy2(previous, temporary)
            temporary.replace(target)
        else:
            target.unlink(missing_ok=True)
    old_inventory = backup / "installed-package.json"
    installed = root / "local/installed-package.json"
    if old_inventory.is_file():
        shutil.copy2(old_inventory, installed)
    else:
        installed.unlink(missing_ok=True)
    journal.unlink()


def install(archive, root, log=print, fail_after=None):
    """Never write build/, profiles, preferences or tools caches during app installation."""
    root = Path(root).absolute()
    if root.resolve() != root or root == Path(root.anchor):
        raise ValueError("Unsafe installation root")
    checked_path(root, "run_launcher.py")
    inventory = validate_package(Path(archive))
    if launcher_running(root):
        raise RuntimeError("Close other DekuForge launcher and build processes before installation")
    root.mkdir(parents=True, exist_ok=True)
    local = root / "local"
    if local.is_symlink() or getattr(local, "is_junction", lambda: False)():
        raise ValueError("Linked application state directory refused")
    local.mkdir(exist_ok=True)
    lock = local / "update-install.lock"
    with lock.open("a+b") as handle:
        if os.name == "nt":
            import msvcrt
            if handle.tell() == 0:
                handle.write(b"0"); handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        recover(root)
        rebuild = needs_rebuild(root, inventory)
        previous_inventory = local / "installed-package.json"
        old = json.loads(previous_inventory.read_text(encoding="utf-8")) if previous_inventory.is_file() else {"sha256": {}}
        previous_names = set(old["sha256"])
        names = set(inventory["sha256"])
        for name in names | previous_names:
            checked_path(root, name)
        identity = uuid.uuid4().hex
        backup = local / "update-backups" / identity
        backup.mkdir(parents=True)
        if previous_inventory.is_file():
            shutil.copy2(previous_inventory, backup / "installed-package.json")
        state = {"id": identity, "changes": []}
        journal = local / "update-transaction.json"
        with tempfile.TemporaryDirectory(prefix="package-", dir=local) as staging:
            stage = Path(staging)
            with zipfile.ZipFile(archive) as source:
                for name in sorted(names):
                    destination = stage / name
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with source.open(name) as stream, destination.open("wb") as output:
                        shutil.copyfileobj(stream, output)
            try:
                for name in sorted(names | previous_names):
                    target = checked_path(root, name)
                    if name in names and target.is_file() and sha(target) == inventory["sha256"][name]:
                        continue
                    existed = target.exists()
                    if existed:
                        previous = backup / name
                        previous.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(target, previous)
                    state["changes"].append({"name": name, "existed": existed})
                    atomic_json(journal, state)  # Durable undo instruction precedes every mutation.
                    if name in names:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        (stage / name).replace(target)
                    else:
                        target.unlink(missing_ok=True)
                    log("Installed: " + name)
                    if fail_after is not None and len(state["changes"]) == fail_after:
                        raise OSError("Injected installation failure")
                atomic_json(previous_inventory, inventory)
                atomic_json(backup / "undo.json", state)
                journal.unlink(missing_ok=True)
            except BaseException:
                recover(root)
                raise
    fingerprint=hashlib.sha256(json.dumps({name:digest for name,digest in inventory["sha256"].items()
        if build_input(name)},sort_keys=True).encode()).hexdigest()
    return {"requires_rebuild": rebuild, "backup": str(backup), "components": inventory["components"],
            "build_fingerprint":fingerprint}


def rollback(root, backup):
    root, backup = Path(root), Path(backup)
    if backup.parent != root / "local/update-backups":
        raise ValueError("Unknown application backup")
    atomic_json(root / "local/update-transaction.json", json.loads((backup / "undo.json").read_text(encoding="utf-8")))
    recover(root)


def launcher_running(root):
    if os.name!="nt":
        return False
    import ctypes
    from ctypes import wintypes as w
    class Entry(ctypes.Structure):
        _fields_=[("size",w.DWORD),("usage",w.DWORD),("pid",w.DWORD),("heap",ctypes.c_size_t),
                  ("module",w.DWORD),("threads",w.DWORD),("parent",w.DWORD),("priority",w.LONG),
                  ("flags",w.DWORD),("exe",w.WCHAR*260)]
    kernel=ctypes.WinDLL("kernel32",use_last_error=True)
    kernel.CreateToolhelp32Snapshot.restype=w.HANDLE
    kernel.Process32FirstW.argtypes=[w.HANDLE,ctypes.POINTER(Entry)]
    kernel.Process32NextW.argtypes=[w.HANDLE,ctypes.POINTER(Entry)]
    kernel.OpenProcess.restype=w.HANDLE
    kernel.CloseHandle.argtypes=[w.HANDLE]
    kernel.QueryFullProcessImageNameW.argtypes=[w.HANDLE,w.DWORD,w.LPWSTR,ctypes.POINTER(w.DWORD)]
    snapshot=kernel.CreateToolhelp32Snapshot(2,0)
    if snapshot==ctypes.c_void_p(-1).value:
        raise OSError("Cannot check for an active launcher")
    try:
        entry=Entry();entry.size=ctypes.sizeof(entry)
        valid=kernel.Process32FirstW(snapshot,ctypes.byref(entry))
        while valid:
            if entry.pid!=os.getpid() and entry.exe.casefold() in {"python.exe","pythonw.exe"}:
                handle=kernel.OpenProcess(0x1000,False,entry.pid)
                if handle:
                    try:
                        text=ctypes.create_unicode_buffer(32768);length=w.DWORD(32768)
                        if kernel.QueryFullProcessImageNameW(handle,0,text,ctypes.byref(length)) and text.value.casefold().startswith(str(root).casefold()+os.sep):
                            return True
                    finally:kernel.CloseHandle(handle)
            valid=kernel.Process32NextW(snapshot,ctypes.byref(entry))
        return False
    finally:kernel.CloseHandle(snapshot)
