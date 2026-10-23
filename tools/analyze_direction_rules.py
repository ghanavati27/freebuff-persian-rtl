#!/usr/bin/env python3
"""Measure the direction rule against the user's REAL conversations.

The app caches its API payloads on disk, so the message bodies the patch has to
lay out can be read back and counted, instead of reasoned about from samples.
This is how the word rule was chosen over the character rule: 8,633 mixed-script
paragraphs, 495 disagreements, and every one of the 494 that the word rule calls
rtl turned out to be Persian prose carrying English paths and identifiers.

Read-only. Nothing is written outside stdout.

Usage:
  python tools/analyze_direction_rules.py [--sample N]

Exit status: 0 always (it is a measurement; read the numbers).
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import sys

ARABIC_RANGES = ((0x0600, 0x06FF), (0x0750, 0x077F), (0x08A0, 0x08FF),
                 (0xFB50, 0xFDFF), (0xFE70, 0xFEFF))
ESCAPES = {"n": "\n", "t": "\t", "r": "\r"}


def is_arabic(ch: str) -> bool:
    c = ord(ch)
    return any(lo <= c <= hi for lo, hi in ARABIC_RANGES)


def is_latin(ch: str) -> bool:
    c = ord(ch)
    return (0x41 <= c <= 0x5A) or (0x61 <= c <= 0x7A) or (0x00C0 <= c <= 0x024F)


def counts(text: str) -> tuple[int, int, int, int]:
    """(persian chars, latin chars, persian words, latin words)."""
    ca = sum(1 for c in text if is_arabic(c))
    cl = sum(1 for c in text if is_latin(c))
    wa = wl = 0
    for token in text.split():
        a = sum(1 for c in token if is_arabic(c))
        l = sum(1 for c in token if is_latin(c))
        if not a and not l:
            continue                      # no letters -> no vote
        if a >= l:
            wa += 1
        else:
            wl += 1
    return ca, cl, wa, wl


def cache_dir() -> str:
    return os.path.join(os.environ.get("APPDATA", ""), "Freebuff", "Cache", "Cache_Data")


def message_bodies(root: str, min_len: int = 200) -> list[str]:
    """Every `"text":"..."` value in the cached payloads, unescaped."""
    out: list[str] = []
    for path in sorted(glob.glob(os.path.join(root, "*"))):
        try:
            blob = open(path, "rb").read().decode("utf-8", "replace")
        except OSError:
            continue
        marker = '"text":"'
        i = 0
        while True:
            i = blob.find(marker, i)
            if i < 0:
                break
            j = i + len(marker)
            buf: list[str] = []
            while j < len(blob) and len(buf) < 20000:
                ch = blob[j]
                if ch == '"':
                    break
                if ch == chr(92) and j + 1 < len(blob):
                    buf.append(ESCAPES.get(blob[j + 1], blob[j + 1]))
                    j += 2
                    continue
                buf.append(ch)
                j += 1
            i = j
            body = "".join(buf)
            if len(body) >= min_len:
                out.append(body)
    return out


def paragraphs(bodies: list[str]) -> list[tuple[str, int, int, int, int]]:
    found: list[tuple[str, int, int, int, int]] = []
    for body in bodies:
        for para in re.split(r"\n\s*\n", body):
            para = para.strip()
            if len(para) < 30:
                continue
            ca, cl, wa, wl = counts(para)
            if ca == 0 or cl == 0:
                continue                      # not mixed-script
            found.append((para, ca, cl, wa, wl))
    return found


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sample", type=int, default=8,
                    help="how many disagreements to print (default 8)")
    args = ap.parse_args()

    root = cache_dir()
    if not os.path.isdir(root):
        print("ERROR: Freebuff cache not found at %s" % root, file=sys.stderr)
        return 2

    bodies = message_bodies(root)
    paras = paragraphs(bodies)
    if not paras:
        print("ERROR: no mixed-script paragraphs found in the cache", file=sys.stderr)
        return 2

    char_rtl = sum(1 for p in paras if p[1] >= p[2])
    word_rtl = sum(1 for p in paras if p[3] >= p[4])
    print("messages      : %d" % len(bodies))
    print("paragraphs    : %d  (mixed-script only)" % len(paras))
    print("char rule rtl : %d  (%.0f%%)" % (char_rtl, 100 * char_rtl / len(paras)))
    print("word rule rtl : %d  (%.0f%%)" % (word_rtl, 100 * word_rtl / len(paras)))

    dis = [p for p in paras if (p[1] >= p[2]) != (p[3] >= p[4])]
    to_rtl = [p for p in dis if p[1] < p[2] and p[3] >= p[4]]
    to_ltr = [p for p in dis if p[1] >= p[2] and p[3] < p[4]]
    print("\ndisagreements : %d   (chars-ltr/words-rtl: %d, chars-rtl/words-ltr: %d)"
          % (len(dis), len(to_rtl), len(to_ltr)))
    print("Reading them is the point: the first group should be Persian prose\n"
          "carrying English identifiers, the second group should be rare and\n"
          "genuinely bilingual.\n")

    print("=== the word rule says rtl where the character rule said ltr (sample) ===")
    for para, ca, cl, wa, wl in to_rtl[:args.sample]:
        print("\n  chars %4d/%-4d   words %3d/%-3d" % (ca, cl, wa, wl))
        print("  %s" % para[:170].replace("\n", " "))

    if to_ltr:
        print("\n=== the other direction (rare - read these too) ===")
        for para, ca, cl, wa, wl in to_ltr[:args.sample]:
            print("\n  chars %4d/%-4d   words %3d/%-3d" % (ca, cl, wa, wl))
            print("  %s" % para[:170].replace("\n", " "))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
