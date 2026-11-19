"""Prepare the complete Windows build tools without reading any game input."""
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
def main():
    from dekuforge.open_engine import manifest
    from dekuforge.open_game_build import CONFIG
    from dekuforge.update_status import read_record
    previous = read_record(CONFIG)
    revision = manifest("hookshot")["revision"]
    recorded_work = previous.get("work")
    work = None
    if isinstance(recorded_work, str):
        marker = read_record(Path(recorded_work)/".dekuforge-open-work.json")
        if marker.get("provider_revision") == revision or previous.get("provider_revision") == revision:
            work = recorded_work
    command = [sys.executable, "-B", str(ROOT/"tools/provision_open_tools.py"), "--configure-launcher"]
    command += ["--work", work or str(ROOT/"build"/f"open-engine-work-{revision[:12]}")]
    if work and isinstance(previous.get("source"), str) and Path(previous["source"]).is_dir():
        command += ["--source", previous["source"]]
    subprocess.run(command, cwd=ROOT, check=True)
    print("DekuForge build tools are ready. No game files were downloaded or generated.",flush=True)


if __name__=="__main__":main()
