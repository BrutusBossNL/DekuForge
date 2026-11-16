"""Provision verified portable build tools inside the ignored project workspace."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def install_zip(name, url, expected, algorithm):
    root = ROOT / "local" / "build-tools"
    root.mkdir(parents=True, exist_ok=True)
    destination = root / name
    marker = destination / ".dekuforge-tool.json"
    identity = {"url": url, "hash": expected, "algorithm": algorithm}
    if marker.is_file():
        if json.loads(marker.read_text()) != identity:
            raise ValueError("Installed tool identity differs")
        print("Available:", destination, flush=True)
        return destination
    if destination.exists():
        raise ValueError("Incomplete tool installation exists")
    archive = root / (name + ".zip")
    if not archive.is_file() or hashlib.file_digest(archive.open("rb"), algorithm).hexdigest() != expected:
        partial = root / (name + ".download")
        digest = hashlib.new(algorithm)
        with urllib.request.urlopen(url, timeout=120) as response, partial.open("wb") as output:
            count = 0
            while block := response.read(1024 * 1024):
                count += len(block)
                if count > 1024 * 1024 * 1024:
                    raise ValueError("Tool download exceeds its size limit")
                output.write(block)
                digest.update(block)
        if digest.hexdigest() != expected:
            raise ValueError("Tool archive checksum mismatch")
        partial.replace(archive)
    with zipfile.ZipFile(archive) as source:
        entries = source.infolist()
        if len(entries) > 100000 or sum(entry.file_size for entry in entries) > 4 * 1024**3:
            raise ValueError("Tool archive expands beyond its limit")
        if shutil.disk_usage(root).free < sum(entry.file_size for entry in entries) + 2 * 1024**3:
            raise ValueError("Not enough free space for the tool")
        for entry in entries:
            target = (destination / entry.filename).resolve()
            if not target.is_relative_to(destination.resolve()) or (entry.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError("Unsafe tool archive entry")
        destination.mkdir()
        source.extractall(destination)
    marker.write_text(json.dumps(identity, indent=2) + "\n", encoding="utf-8")
    print("Installed:", destination, flush=True)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dotnet", action="store_true")
    parser.add_argument("--ninja", action="store_true")
    args = parser.parse_args()
    if args.dotnet:
        metadata_url = "https://builds.dotnet.microsoft.com/dotnet/release-metadata/10.0/releases.json"
        with urllib.request.urlopen(metadata_url, timeout=60) as response:
            metadata = json.load(response)
        sdk = next(sdk for release in metadata["releases"] for sdk in release.get("sdks", [release["sdk"]])
                   if sdk["version"] == "10.0.404")
        asset = next(file for file in sdk["files"] if file["rid"] == "win-x64" and file["url"].endswith(".zip"))
        if not asset["url"].startswith("https://builds.dotnet.microsoft.com/dotnet/Sdk/"):
            raise ValueError("SDK download points outside the official host")
        install_zip("dotnet-10.0.404", asset["url"], asset["hash"], "sha512")
    if args.ninja:
        install_zip("ninja-1.13.2", "https://github.com/ninja-build/ninja/releases/download/v1.13.2/ninja-win.zip",
                    "07fc8261b42b20e71d1720b39068c2e14ffcee6396b76fb7a795fb460b78dc65", "sha256")


if __name__ == "__main__":
    main()
