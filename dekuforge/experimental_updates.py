"""Update from checked builds on the first-party independent branch."""
import json
import re
import shutil
import uuid
import zipfile

from .core import ROOT
from .releases import REPOSITORY
from .update_package import MAX_PACKAGE, validate_package
from .update_service import download_asset, github_request, github_token, prepare_job, version_key


API = f"https://api.github.com/repos/{REPOSITORY}"
ARTIFACT = re.compile(r"dekuforge-windows-([0-9]+\.[0-9]+\.[0-9]+-experimental\.[0-9]+\.[0-9]+)-([a-f0-9]{40})")


def read_response(url):
    with github_request(url) as response:
        data = response.read(2_000_001)
    if len(data) > 2_000_000:
        raise ValueError("GitHub Actions response exceeds size limit")
    return json.loads(data)


def list_builds():
    if not github_token():
        raise ValueError("experimental_sign_in")
    runs = read_response(f"{API}/actions/workflows/independent-windows.yml/runs"
                         "?branch=independent&event=push&status=success&per_page=20")["workflow_runs"]
    rows = {}
    for run in runs:
        if (run.get("head_branch") != "independent" or run.get("conclusion") != "success"
                or (run.get("head_repository") or {}).get("full_name", "").casefold() != REPOSITORY.casefold()
                or type(run.get("id")) is not int):
            continue
        assets = read_response(f"{API}/actions/runs/{run['id']}/artifacts")["artifacts"]
        for asset in assets:
            match = ARTIFACT.fullmatch(asset.get("name", ""))
            if not match or match[2] != run.get("head_sha") or asset.get("expired") or type(asset.get("id")) is not int:
                continue
            version = "v" + match[1]
            rows[version] = {"version": version, "preview": True, "experimental": True, "installable": True,
                             "commit": match[2], "notes": f"{run.get('display_title', '')}\n\nCommit {match[2]}",
                             "artifact": {"url": f"{API}/actions/artifacts/{asset['id']}/zip",
                                          "digest": asset.get("digest"), "size": asset.get("size_in_bytes")}}
    return sorted(rows.values(), key=lambda row: version_key(row["version"]), reverse=True)


def prepare_build(row, progress, root=ROOT):
    job = root / "local/update-jobs" / uuid.uuid4().hex
    job.mkdir(parents=True)
    source = job / "artifact.zip"
    download_asset(row["artifact"], source, progress, accept="application/vnd.github+json")
    version = row["version"].removeprefix("v")
    filename = f"DekuForge-launcher-{version}-windows.zip"
    package = job / "package.zip"
    with zipfile.ZipFile(source) as outer:
        entries = outer.infolist()
        if len(entries) != 1 or entries[0].filename != filename or entries[0].file_size > MAX_PACKAGE:
            raise ValueError("Unexpected experimental artifact contents")
        with outer.open(entries[0]) as origin, package.open("xb") as target:
            shutil.copyfileobj(origin, target)
    components = validate_package(package)["components"]
    if (components["engine"].get("backend") != "independent"
            or components["launcher"].get("commit") != row["commit"]
            or components["launcher"]["version"] != version):
        raise ValueError("Experimental package does not match the selected commit")
    source.unlink()
    return prepare_job(root, job, package, row["version"])
