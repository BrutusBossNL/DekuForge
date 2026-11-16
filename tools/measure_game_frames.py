"""Measure a specified frame interval from an isolated runtime trace.

This measures presentation cadence, not GPU time. A scene must be visually
verified separately; loading frames are never silently discarded.
"""
import argparse
import json
from pathlib import Path
import re
import statistics


def measure(text, first, last):
    rows = [(int(frame), float(ms)) for frame, ms in re.findall(
        r"present: frame (\d+) interval ([\d.]+) ms", text)]
    rows = [(frame, ms) for frame, ms in rows if first <= frame <= last and ms > 0]
    if len(rows) < 120:
        raise ValueError("At least 120 measured presentation intervals are required")
    times = [ms for _, ms in rows]
    slowest = sorted(times, reverse=True)[:max(1, (len(times) + 99) // 100)]
    return {"first_frame": rows[0][0], "last_frame": rows[-1][0],
            "samples": len(times), "seconds": round(sum(times) / 1000, 3),
            "average_fps": round(1000 / statistics.mean(times), 2),
            "one_percent_low_fps": round(1000 / statistics.mean(slowest), 2),
            "median_frame_ms": round(statistics.median(times), 3),
            "maximum_frame_ms": max(times), "scene_visually_verified": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    parser.add_argument("--first", type=int, required=True)
    parser.add_argument("--last", type=int, required=True)
    args = parser.parse_args()
    print(json.dumps(measure(args.log.read_text(encoding="utf-8", errors="replace"),
                             args.first, args.last), indent=2))


if __name__ == "__main__":
    main()
