"""Compare a captured movie resample against an independent scalar CPU reference.

Inputs are local render-dump PNGs from the same frame, never repository fixtures.
This checks the reconstruction arithmetic, not whether the source movie is correct.
"""
import argparse
import json
import math
import random
from PIL import Image


def weights(x):
    return (-x / 2 + x*x - x*x*x / 2, 1 - 2.5*x*x + 1.5*x*x*x,
            x / 2 + 2*x*x - 1.5*x*x*x, -x*x / 2 + x*x*x / 2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    with Image.open(args.source) as image:
        source = image.convert("RGB")
    with Image.open(args.output) as image:
        target = image.convert("RGB")
    sw, sh = source.size
    tw, th = target.size
    if min(sw, sh, tw, th) < 2 or sw * th != sh * tw:
        raise ValueError("Expected matching nonempty aspect ratios")
    rng = random.Random(2026)
    points = [(0, 0), (tw-1, 0), (0, th-1), (tw-1, th-1)]
    points += [(rng.randrange(tw), rng.randrange(th)) for _ in range(1024)]
    squared = maximum = 0.0
    for x, y in points:
        sx, sy = (x + 0.5) * sw / tw - 0.5, (y + 0.5) * sh / th - 0.5
        bx, by = math.floor(sx), math.floor(sy)
        wx, wy = weights(sx - bx), weights(sy - by)
        value, low, high = [0.0] * 3, [255] * 3, [0] * 3
        for j in range(4):
            for i in range(4):
                pixel = source.getpixel((min(sw-1, max(0, bx+i-1)), min(sh-1, max(0, by+j-1))))
                for c in range(3):
                    value[c] += pixel[c] * wx[i] * wy[j]
                    if i in (1, 2) and j in (1, 2):
                        low[c], high[c] = min(low[c], pixel[c]), max(high[c], pixel[c])
        actual = target.getpixel((x, y))
        for c in range(3):
            error = abs(actual[c] - min(high[c], max(low[c], value[c])))
            maximum = max(maximum, error)
            squared += error * error
    result = {"samples": len(points), "maximum_channel_error": round(maximum, 4),
              "rms_channel_error": round(math.sqrt(squared / (3 * len(points))), 4),
              "source_visually_verified": False}
    print(json.dumps(result, indent=2))
    if maximum > 3:
        raise AssertionError("GPU movie resample differs from the scalar reference")


if __name__ == "__main__":
    main()
