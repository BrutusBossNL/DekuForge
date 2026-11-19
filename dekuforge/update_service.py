"""Download verified release assets and hand app replacement to a detached worker."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import uuid
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from .core import ROOT
from .update_package import MAX_PACKAGE, validate_package, atomic_json


class AssetRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urlsplit(newurl).scheme != "https":
            raise ValueError("Insecure asset redirect refused")
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if urlsplit(newurl).hostname != urlsplit(req.full_url).hostname:
            redirected.remove_header("Authorization")
        return redirected


def github_token():
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        return token
    gh = shutil.which("gh")
    if gh:
        result = subprocess.run([gh, "auth", "token", "--hostname", "github.com"], capture_output=True,
            text=True, timeout=10, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if not result.returncode:
            return result.stdout.strip()
    return None


def github_request(url, accept="application/vnd.github+json"):
    if urlsplit(url).scheme != "https" or urlsplit(url).hostname != "api.github.com":
        raise ValueError("Release metadata must come from GitHub's API")
    headers = {"Accept": accept, "User-Agent": "DekuForge", "X-GitHub-Api-Version": "2022-11-28"}
    token = github_token()
    if token:
        headers["Authorization"] = "Bearer " + token
    return build_opener(AssetRedirect()).open(Request(url, headers=headers), timeout=60)


def download_asset(asset, target, progress=lambda done, total: None, *, accept="application/octet-stream"):
    digest = asset.get("digest", "")
    size = asset.get("size", 0)
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest) or not isinstance(size, int) or not 0 < size <= MAX_PACKAGE:
        raise ValueError("Release asset has no valid size and GitHub SHA-256 digest")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file() and target.stat().st_size == size:
        with target.open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() == digest[7:]:
                return
    partial = target.with_suffix(target.suffix + ".part")
    hasher = hashlib.sha256(); count = 0
    with github_request(asset["url"], accept) as response, partial.open("wb") as output:
        while block := response.read(1024**2):
            count += len(block)
            if count > size:
                raise ValueError("Release asset exceeds its declared size")
            output.write(block); hasher.update(block); progress(count, size)
    if count != size or hasher.hexdigest() != digest[7:]:
        partial.unlink(missing_ok=True)
        raise ValueError("Release asset checksum mismatch")
    partial.replace(target)


def prepare_release(release, progress=lambda done, total: None, root=ROOT):
    assets = {asset["name"]: asset for asset in release.get("assets", [])}
    descriptor = assets.get(release.get("descriptor", "DekuForge-release.json"))
    if not descriptor:
        raise ValueError("This release does not contain a DekuForge updater manifest")
    job = root / "local/update-jobs" / uuid.uuid4().hex
    job.mkdir(parents=True)
    manifest_path = job / "release.json"
    download_asset(descriptor, manifest_path)
    if manifest_path.stat().st_size > 1024**2:
        raise ValueError("Oversized release manifest")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != 1 or manifest.get("tag") != release["version"] or manifest.get("contains_game_files") is not False:
        raise ValueError("Release manifest identity mismatch")
    package = manifest["package"]
    asset = assets.get(package["name"])
    if not asset or asset.get("digest") != "sha256:" + package["sha256"] or asset.get("size") != package["size"]:
        raise ValueError("Release package does not match the authenticated asset inventory")
    if not re.fullmatch(r"[0-9a-f]{64}",package["sha256"]):
        raise ValueError("Invalid package digest")
    archive = root / "local/update-downloads" / (package["sha256"] + ".zip")
    download_asset(asset, archive, progress)
    inventory = validate_package(archive)
    if inventory["components"] != manifest["components"]:
        raise ValueError("Release component identities do not match")
    return prepare_job(root, job, archive, release["version"])


def prepare_job(root, job, archive, version):
    shutil.copy2(ROOT / "tools/update_worker.py", job / "worker.py")
    shutil.copy2(ROOT / "dekuforge/update_package.py", job / "update_package.py")
    atomic_json(job / "job.json", {"root": str(root), "archive": str(archive), "parent_pid": os.getpid(),
        "release": version})
    return job


def start_worker(job):
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
    with (job / "worker.log").open("w", encoding="utf-8") as log:
        return subprocess.Popen([sys.executable, str(job / "worker.py"), str(job / "job.json")],
            cwd=job, stdin=subprocess.DEVNULL, stdout=log, stderr=log, close_fds=True, creationflags=flags)


def version_key(value):
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?", value)
    if not match:
        return None
    main = tuple(map(int, match.groups()[:3]))
    suffix = match[4]
    extra = tuple((0, int(part)) if part.isdigit() else (1, part) for part in (suffix or "").split("."))
    return (*main, suffix is None, extra)


def newer_version(remote, installed):
    a, b = version_key(remote), version_key(installed)
    return a is not None and b is not None and a > b
