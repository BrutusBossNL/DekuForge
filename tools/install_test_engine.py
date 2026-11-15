"""Install the pinned ARM64 test oracle into the ignored project-local test folder."""

import hashlib
import io
import json
from pathlib import Path
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = "2.1.4"


def main():
    with urllib.request.urlopen(f"https://pypi.org/pypi/unicorn/{VERSION}/json", timeout=30) as response:
        metadata = json.load(response)
    choices = [item for item in metadata["urls"] if item["filename"].endswith("-cp37-abi3-win_amd64.whl")]
    if len(choices) != 1:
        raise RuntimeError("Expected one pinned Windows x64 test-engine wheel")
    wheel = choices[0]
    if not wheel["url"].startswith("https://files.pythonhosted.org/"):
        raise RuntimeError("Unexpected wheel host")
    with urllib.request.urlopen(wheel["url"], timeout=30) as response:
        payload = response.read(100 * 1024 * 1024)
    if hashlib.sha256(payload).hexdigest() != wheel["digests"]["sha256"]:
        raise RuntimeError("Wheel checksum mismatch")
    target = ROOT / "local" / "devdeps"
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        for member in archive.infolist():
            if not (target / member.filename).resolve().is_relative_to(target.resolve()):
                raise RuntimeError("Unsafe wheel entry")
        archive.extractall(target)
    print(f"Installed test-only Unicorn {VERSION} in local/devdeps")


if __name__ == "__main__":
    main()
