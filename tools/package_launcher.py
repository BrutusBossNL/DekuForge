"""Build a launcher-only archive from an explicit source and branding allowlist."""
import hashlib
import json
from pathlib import Path
import struct
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.check_source import forbidden

from dekuforge.update_package import SOURCE_DIRS as DIRECTORIES, ROOT_FILES, SOURCE_SUFFIXES, allowed, validate_package


def included(path):
    path = Path(path)
    name = path.as_posix()
    if name in {"DekuForge.exe", "dekuforge/stable_engine.py", "dekuforge/stable_engine_source.json",
                "dekuforge/shader_tools.lock.json", "dekuforge/runtime_layer.py"}:
        return False
    return (allowed(name) and "__pycache__" not in path.parts
            and (path.parts[0] != "engine_overrides" or path.parts[1] == "independent"))


def package(root=ROOT):
    pins = json.loads((root / "dekuforge/components.json").read_text(encoding="utf-8"))
    launcher = (root / "DekuForge.exe").read_bytes()
    header = struct.unpack_from("<I", launcher, 60)[0]
    if (len(launcher) > 2 * 1024 * 1024 or launcher[header:header+4] != b"PE\0\0"
            or struct.unpack_from("<H", launcher, header + 24 + 68)[0] != 2
            or b"D\0e\0k\0u\0F\0o\0r\0g\0e\0" not in launcher):
        raise ValueError("Expected the small native DekuForge GUI bootstrap")
    files = {"DekuForge.exe": launcher}
    uninstaller=root/"DekuForge-Uninstall.exe"
    if uninstaller.is_file():
        from dekuforge.update_package import validate_launcher
        content=uninstaller.read_bytes();validate_launcher(content)
        files[uninstaller.name]=content
    candidates = [root / name for name in ROOT_FILES]
    for name in DIRECTORIES | {"assets/branding"}:
        candidates.extend((root / name).rglob("*"))
    for path in sorted(candidates):
        relative = path.relative_to(root)
        if not included(relative) or not path.is_file():
            continue
        if path.is_symlink() or path.resolve() != path.absolute():
            raise ValueError("Linked package source refused: " + relative.as_posix())
        data = path.read_bytes()
        if path.suffix in SOURCE_SUFFIXES:
            data = data.replace(b"\r\n", b"\n")
        if forbidden(relative.as_posix(), data[:8192]):
            raise ValueError("Forbidden launcher package content: " + relative.as_posix())
        files[relative.as_posix()] = data
    inventory = {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}
    files["launcher-package.json"] = json.dumps({"components": pins, "sha256": inventory,
        "contains_game_files": False}, indent=2).encode("utf-8")
    output = root / "build/releases" / ("DekuForge-launcher-" + pins["launcher"]["version"] + "-windows.zip")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".zip.part")
    with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    validate_package(temporary)
    temporary.replace(output)
    print(f"Launcher package: {output} ({output.stat().st_size / 1048576:.2f} MiB, {len(files)} files)")
    return output


if __name__ == "__main__":
    package()
