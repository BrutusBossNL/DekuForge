"""Local build inventory and bounded deletion of owned installations."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import uuid


class BuildLibrary:
    def __init__(self, project):
        self.project = Path(project).resolve()
        self.path = self.project / "local" / "builds.json"

    def entries(self):
        if not self.path.exists():
            return []
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError("Invalid build inventory")
        return data

    def write(self, entries):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(entries, indent=2), encoding="utf-8")
        temp.replace(self.path)

    def register(self, executable, dump="", version="", owned=False):
        exe = Path(executable).absolute()
        if not exe.is_file():
            raise ValueError("Build executable is missing")
        entries = self.entries()
        existing = next((e for e in entries if Path(e["executable"]) == exe), None)
        if existing:
            if version and existing.get("version") != version:
                existing["version"] = version
                self.write(entries)
            return existing
        folder = exe.parent
        marker = folder / ".dekuforge-build.json"
        identity = uuid.uuid4().hex
        if owned:
            self.check_root(folder)
            if marker.exists():
                identity = json.loads(marker.read_text(encoding="utf-8"))["id"]
            else:
                marker.write_text(json.dumps({"id": identity, "executable": exe.name}), encoding="utf-8")
        entry = {"id": identity, "executable": str(exe), "dump": str(dump),
                 "version": version, "owned": owned,
                 "created": datetime.now(timezone.utc).isoformat()}
        entries.append(entry)
        self.write(entries)
        return entry

    def discover(self, selected="", dump=""):
        build = self.project / "build"
        if build.is_dir():
            for folder in build.iterdir():
                exe = folder / "DekuForgeGame.exe"
                if (folder / ".dekuforge-native").is_file() and exe.is_file():
                    info = folder / "dekuforge-build-info.json"
                    version = json.loads(info.read_text(encoding="utf-8")).get("game_version", "") if info.is_file() else ""
                    self.register(exe, dump if str(exe) == selected else "", version=version, owned=True)
        if selected and Path(selected).is_file():
            self.register(selected, dump)
        return self.entries()

    def check_root(self, folder):
        folder = Path(folder).absolute()
        if folder != folder.resolve() or folder == Path(folder.anchor) or folder == self.project or self.project.is_relative_to(folder):
            raise ValueError("Unsafe build directory")
        for protected in ("assets", "local", "engine", "dekuforge", "tools", ".git"):
            if folder.is_relative_to(self.project / protected):
                raise ValueError("Build directory overlaps project files")
        for parent in (folder, *folder.parents):
            if parent.is_symlink() or getattr(parent, "is_junction", lambda: False)():
                raise ValueError("Linked build directories cannot be deleted")
        return folder

    def deletion_target(self, identity):
        entries = self.entries()
        entry = next(e for e in entries if e["id"] == identity)
        if not entry["owned"]:
            raise ValueError("Only owned builds can be deleted")
        folder = self.check_root(Path(entry["executable"]).parent)
        marker = folder / ".dekuforge-build.json"
        if marker.is_symlink():
            raise ValueError("Invalid ownership marker")
        record = json.loads(marker.read_text(encoding="utf-8"))
        if record.get("id") != identity or record.get("executable") != Path(entry["executable"]).name:
            raise ValueError("Build ownership does not match")
        if entry.get("dump") and Path(entry["dump"]).resolve().is_relative_to(folder):
            raise ValueError("The game dump is inside this build; move it before deletion")
        for other in entries:
            if other["id"] != identity and Path(other["executable"]).resolve().is_relative_to(folder):
                raise ValueError("Another build is inside this directory")
        for base, dirs, files in os.walk(folder, followlinks=False):
            for name in dirs + files:
                path = Path(base) / name
                if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
                    raise ValueError("Build contains links; automatic deletion refused")
        return entry, folder

    def delete(self, identity, keep_saves=True):
        entry, folder = self.deletion_target(identity)
        backup = None
        profile = folder / "profile"
        if keep_saves and profile.is_dir():
            backup = self.project / "local" / "retained-saves" / (identity + "-" + uuid.uuid4().hex[:8])
            backup.parent.mkdir(parents=True, exist_ok=True)
            # Keep all profile data, including saves whose format is not yet known.
            shutil.copytree(profile, backup)
        # Revalidate the exact absolute target immediately before recursive removal.
        _, checked = self.deletion_target(identity)
        if checked != folder:
            raise ValueError("Build path changed during deletion")
        shutil.rmtree(checked)
        self.write([e for e in self.entries() if e["id"] != identity])
        return backup
