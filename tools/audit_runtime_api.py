"""Inventory requested graphics entry points against local runtime registrations."""
import argparse
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    args = parser.parse_args()
    requested = set(re.findall(r"df proc (nvn\w+) caller", (ROOT / "build/windows-game/test-play.log").read_text()))
    if not requested:
        raise ValueError("First record an API inventory with DEKUFORGE_TRACE_NVNP=1")
    def registrations(folder):
        return set(re.findall(r"NVN_PROC\((nvn\w+)\)", (folder / "runtime/nvn_procs.inc").read_text()))
    staged = registrations(ROOT / "build/engine-work")
    reference = registrations(args.reference)
    report = {"requested_count": len(requested), "registered_count": len(staged),
              "missing_in_current": sorted(requested - staged),
              "missing_in_reference_registration_table": sorted(requested - reference),
              "note": "Registration alone does not prove implementation, compatible ABI, or rendering correctness."}
    output = ROOT / "build/runtime-api-audit.json"
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(f"Requested {len(requested)}; missing registrations {len(requested - staged)}; report {output}")


if __name__ == "__main__":
    main()
