#!/usr/bin/env python3
"""Pixel measurements for the Freebuff Desktop Persian/RTL patch.

Two jobs, both based on Pillow rather than on visual inspection:

  * per-line ink geometry  -> is a text line left- or right-aligned?
  * pixel diff of two renders -> the LTR regression test

Usage:
  python tools/measure_ink.py shot.png [more.png ...]
  python tools/measure_ink.py --diff before.png after.png [--threshold 0]

A "line" is a horizontal band of rows containing ink (luminance above a
threshold). For each band the ink bounding box is printed as
`ink  <min_x>..<max_x>` and classified:

  LEFT    min_x is close to the other lines' min_x  (left-aligned)
  RIGHT   max_x is close to the other lines' max_x  (right-aligned)

The classification is a sanity aid only. The numbers are the evidence; read
them, do not trust the label.

Exit status: 0 always. Use --diff's output for pass/fail decisions.
"""

from __future__ import annotations

import argparse
import sys

try:
    from PIL import Image, ImageChops
except ImportError:  # pragma: no cover
    sys.stderr.write("Pillow is required:  pip install Pillow\n")
    raise

INK_THRESHOLD = 95       # luminance (0-255) above which a pixel counts as ink
MIN_BAND_PIXELS = 4      # ignore specks (watermark anti-aliasing, etc.)
TOLERANCE = 6            # px; edges within this are "the same edge"


def ink_bands(path: str) -> list[tuple[int, int, int, int]]:
    """Return (y0, y1, min_x, max_x) for every text band in the image."""
    im = Image.open(path).convert("L")
    width, height = im.size
    px = im.load()

    bands: list[tuple[int, int, int, int]] = []
    y = 0
    while y < height:
        xs = [x for x in range(width) if px[x, y] > INK_THRESHOLD]
        if xs:
            y0, acc = y, []
            while y < height:
                xs = [x for x in range(width) if px[x, y] > INK_THRESHOLD]
                if not xs:
                    break
                acc.extend(xs)
                y += 1
            if len(acc) >= MIN_BAND_PIXELS:
                bands.append((y0, y - 1, min(acc), max(acc)))
        y += 1
    return bands


def classify(bands: list[tuple[int, int, int, int]]) -> None:
    """Print each band with a LEFT / RIGHT / - label for quick reading."""
    if not bands:
        print("  (no text bands found)")
        return
    lefts = [b[2] for b in bands]
    rights = [b[3] for b in bands]
    # The container's own margin is whichever edge repeats most often.
    from collections import Counter
    left_mode = Counter(lefts).most_common(1)[0][0]
    right_mode = Counter(rights).most_common(1)[0][0]

    for y0, y1, x0, x1 in bands:
        if abs(x0 - left_mode) <= TOLERANCE:
            label = "LEFT"
        elif abs(x1 - right_mode) <= TOLERANCE:
            label = "RIGHT"
        else:
            label = "-"
        print(f"  y{y0:>4}-{y1:<4} ink {x0:>4}..{x1:<4}  {label}")


def diff_tints(path: str) -> None:
    """Report green/red tinted areas, which locate a diff block objectively."""
    im = Image.open(path).convert("RGB")
    width, height = im.size
    px = im.load()
    green_rows: set[int] = set()
    red_rows: set[int] = set()
    for y in range(height):
        for x in range(width):
            r, g, b = px[x, y]
            if g > r + 8 and g > b + 8 and g > 30:
                green_rows.add(y)
            elif r > g + 12 and r > b + 8 and r > 30:
                red_rows.add(y)

    def rng(rows: set[int]) -> str:
        return f"{min(rows)}..{max(rows)}" if rows else "-"

    print(f"  green (added lines)   : rows {rng(green_rows)}")
    print(f"  red   (removed lines) : rows {rng(red_rows)}")


def report_diff(before: str, after: str, threshold: int) -> int:
    """The LTR regression test: two renders of a Latin-only page."""
    a = Image.open(before).convert("RGB")
    b = Image.open(after).convert("RGB")
    if a.size != b.size:
        print(f"ERROR: size mismatch {a.size} vs {b.size}", file=sys.stderr)
        return 2

    bbox = ImageChops.difference(a, b).getbbox()
    if bbox is None:
        print(f"IDENTICAL: 0 differing pixels between {before} and {after}")
        return 0

    changed = sum(
        1
        for y in range(a.size[1])
        for x in range(a.size[0])
        if any(abs(v - w) > threshold for v, w in zip(a.getpixel((x, y)),
                                                     b.getpixel((x, y))))
    )
    print(f"DIFFER: bbox={bbox}  pixels changed={changed}")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("images", nargs="*", help="screenshots to measure")
    ap.add_argument("--diff", nargs=2, metavar=("BEFORE", "AFTER"),
                    help="compare two renders pixel by pixel")
    ap.add_argument("--threshold", type=int, default=0,
                    help="per-channel tolerance for --diff (default 0)")
    args = ap.parse_args()

    if args.diff:
        return report_diff(args.diff[0], args.diff[1], args.threshold)

    if not args.images:
        ap.print_help()
        return 0

    for path in args.images:
        print(f"=== {path} ===")
        try:
            classify(ink_bands(path))
            diff_tints(path)
        except FileNotFoundError:
            print(f"  ERROR: {path} not found", file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
