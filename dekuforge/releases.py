"""List eligible releases and their authenticated API asset identities."""
import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from .update_service import github_token

REPOSITORY = "BrutusBossNL/DekuForge"


def list_releases(preview=False):
    headers={"Accept": "application/vnd.github+json", "User-Agent": "DekuForge"}
    token=github_token()
    if token:
        headers["Authorization"]="Bearer " + token
    request = Request(f"https://api.github.com/repos/{REPOSITORY}/releases?per_page=100", headers=headers)
    try:
        with urlopen(request, timeout=15) as response:
            raw = response.read(2_000_001)
    except HTTPError as error:
        if error.code == 404:
            return []  # A private repository is deliberately not exposed.
        raise
    if len(raw) > 2_000_000:
        raise ValueError("Release response exceeds size limit")
    releases = json.loads(raw)
    if not isinstance(releases, list):
        raise ValueError("Unexpected release response")
    candidates = [r for r in releases if not r.get("draft") and (preview or not r.get("prerelease"))]
    candidates.sort(key=lambda r: r.get("published_at") or "", reverse=True)
    return [{"version": str(r["tag_name"]), "date": str(r.get("published_at", "")),
             "preview": bool(r.get("prerelease")), "assets": r.get("assets", []),
             "installable": any(a.get("name")=="DekuForge-release.json" for a in r.get("assets", []))}
            for r in candidates]


def check_release(preview=False):
    releases = list_releases(preview)
    return releases[0] if releases else None
