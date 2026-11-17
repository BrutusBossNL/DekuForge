"""Install MSYS2 shader tools from the official package index into an owned folder."""
import hashlib
import argparse
import json
from pathlib import Path
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
HOST = "https://ftp.nluug.nl/pub/os/windows/msys2/builds/mingw/ucrt64/"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validation", action="store_true", help="Include local Vulkan validation layers")
    args = parser.parse_args()
    output = ROOT / "local" / "build-tools" / "shaders"
    output.mkdir(parents=True, exist_ok=True)
    pins = json.loads((ROOT / "dekuforge/shader_tools.lock.json").read_text(encoding="utf-8"))
    packages = {name: {"FILENAME": [pin["package"]], "SHA256SUM": [pin["sha256"]]}
                for name, pin in pins.items()}
    if args.validation:
        raise ValueError("Validation-layer installation is a separate developer setup")
    for name, record in sorted(packages.items()):
        filename, expected = record["FILENAME"][0], record["SHA256SUM"][0]
        if Path(filename).name != filename:
            raise ValueError("Invalid package filename")
        marker = output / (name + ".json")
        if marker.is_file():
            installed = json.loads(marker.read_text(encoding="utf-8"))
            if installed.get("package") == filename and installed.get("sha256") == expected:
                print("Available (pinned):", name, flush=True)
                continue
        archive = output / filename
        if not archive.is_file():
            with urllib.request.urlopen(HOST + filename, timeout=120) as response:
                archive.write_bytes(response.read(128 * 1024 * 1024))
        with archive.open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != expected:
                raise ValueError("Shader package checksum mismatch")
        with tarfile.open(archive, "r:zst") as source:
            members = [member for member in source if member.name.startswith("ucrt64/")]
            for member in members:
                target = output / member.name
                local_link = (member.islnk() and member.linkname.startswith("ucrt64/")
                              and (output / member.linkname).resolve().is_relative_to(output.resolve()))
                if not target.resolve().is_relative_to(output.resolve()) or not (member.isfile() or member.isdir() or local_link):
                    raise ValueError("Unsafe shader package entry")
            source.extractall(output, members=members, filter="data")
        marker.write_text(json.dumps({"package": filename, "sha256": expected}) + "\n", encoding="utf-8")
        print("Installed:", name, flush=True)


if __name__ == "__main__":
    main()
