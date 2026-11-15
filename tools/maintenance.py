"""Read-only daily repository triage and a source-check summary. No comments or merges."""

from datetime import datetime, timezone
import html
import json
import os
from pathlib import Path
import re
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def make_report(repository, issues, pulls, source_result="unknown"):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("Invalid repository name")
    def item(value):
        return {"number": int(value["number"]), "title": value["title"],
                "updated_at": value.get("updated_at"),
                "labels": [label["name"] for label in value.get("labels", [])]}
    report = {"repository": repository, "checked_at": datetime.now(timezone.utc).isoformat(),
              "source_checks": source_result, "issues": [item(value) for value in issues if "pull_request" not in value],
              "pull_requests": [], "game_validation": "not established by this workflow"}
    for value in pulls:
        pull = item(value)
        pull.update(draft=bool(value.get("draft")), mergeable=value.get("mergeable"),
                    mergeable_state=value.get("mergeable_state", "unknown"))
        report["pull_requests"].append(pull)
    return report


def summary(report):
    lines = ["# DekuForge daily check", "", f"Source checks: **{report['source_checks']}**", "",
             "Source checks do not establish a working game build or platform parity.", ""]
    for group, title, kind in (("issues", "Open issues", "issues"), ("pull_requests", "Open pull requests", "pull")):
        lines += [f"## {title}: {len(report[group])}", ""]
        for item in report[group]:
            text = html.escape(str(item["title"]).replace("\n", " ").replace("\r", " ")[:180])
            for char in ("[", "]", "*", "`", "_"):
                text = text.replace(char, "\\" + char)
            number = item["number"]
            url = f"https://github.com/{report['repository']}/{kind}/{number}"
            state = ""
            if group == "pull_requests":
                state = f" — {'draft, ' if item['draft'] else ''}mergeability: {item['mergeable_state']}"
            lines.append(f"- [#{number}]({url}) {text}{state}")
        lines.append("")
    lines += ["Read-only report. No issue comments, PR merges or code changes were performed.", ""]
    return "\n".join(lines)


def main():
    repository = os.environ.get("GITHUB_REPOSITORY", "BrutusBossNL/DekuForge")
    token = os.environ.get("GITHUB_TOKEN")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository) or not token:
        raise RuntimeError("A valid GITHUB_REPOSITORY and read-only GITHUB_TOKEN are required")
    def get(resource):
        request = urllib.request.Request(f"https://api.github.com/repos/{repository}/{resource}",
                                         headers={"Authorization": f"Bearer {token}",
                                                  "Accept": "application/vnd.github+json",
                                                  "User-Agent": "DekuForge-maintenance"})
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    def pages(resource):
        collected = []
        for page in range(1, 11):
            values = get(f"{resource}?state=open&per_page=100&page={page}")
            collected.extend(values)
            if len(values) < 100:
                return collected
        raise RuntimeError("Repository report exceeds the configured pagination limit")
    issues = pages("issues")
    pulls = [get(f"pulls/{item['number']}") for item in pages("pulls")]
    report = make_report(repository, issues, pulls, os.environ.get("SOURCE_CHECK_RESULT", "unknown"))
    folder = ROOT / "local" / "maintenance"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "latest.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    text = summary(report)
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with Path(path).open("a", encoding="utf-8") as output:
            output.write(text)
    print(f"Checked {len(report['issues'])} issues and {len(report['pull_requests'])} pull requests")


if __name__ == "__main__":
    main()
