#!/usr/bin/env python3
"""List classes in the shipped bundle that carry text directly and are NOT
covered by the patch - the "did the app grow a new text surface" probe the
update checklist asks for.

The definition is fixed here so the number MEANS THE SAME THING between
releases. Without that, the per-version counts in docs/FINDINGS.md (92, 94,
101, 102, 107, 110) are not comparable to anything a later run produces.

  text-bearing  a `className:"..."` occurrence whose element also carries a
                literal `children:"..."` string of at least MIN_LETTERS letters
                within LOOKAHEAD characters. That is "text written directly in
                the JSX" - text passed as a variable is not counted, which is
                the right call: a variable could be anything.
  uncovered     no class of the occurrence is referenced by the patch files.

Read-only.

Usage:
  python tools/scan_text_surfaces.py            [--app <ui dir>]
  python tools/scan_text_surfaces.py --list 40  (show more of the classes)

Exit: 0 always - it is a measurement. Read the numbers.
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import sys

LOOKAHEAD = 220
MIN_LETTERS = 3
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATCH_FILES = ("patch/fb-persian-rtl.css", "patch/fb-persian-rtl.js",
               "apply_fb_persian_patch.py")

DEFAULT_UI = os.path.join(
    os.environ.get("LOCALAPPDATA", ""),
    "Programs", "@codebufffreebuff-desktop", "resources", "orchestrator", "ui")

CLASS_ATTR = re.compile(r'className\s*:\s*[`"]([^`"]+)[`"]')
LITERAL = re.compile(r'children\s*:\s*"([^"]{2,200})"')
CLASS_TOKEN = re.compile(r"[A-Za-z_][\w-]*")


def patch_classes() -> set[str]:
    """Every class name the patch references - so 'covered' means the same
    thing here as in the installer's health check."""
    out: set[str] = set()
    blob = ""
    for rel in PATCH_FILES:
        path = os.path.join(REPO, rel)
        if os.path.exists(path):
            blob += open(path, encoding="utf-8", errors="replace").read()
    blob = re.sub(r"/\*.*?\*/", "", blob, flags=re.S)          # CSS comments
    for quoted in re.findall(r"'\.([\w-]+)'", blob):           # JS '.foo'
        out.add(quoted)
    for css in re.findall(r"\.([a-zA-Z_][\w-]*)", blob):       # CSS .foo
        out.add(css)
    return out


def bundle_paths(ui: str) -> tuple[str, str]:
    html = open(os.path.join(ui, "index.html"), encoding="utf-8",
                errors="replace").read()
    js = re.search(r'src="[^"]*?(index-[^"]+\.js)"', html)
    css = re.search(r'href="[^"]*?(index-[^"]+\.css)"', html)
    if not js or not css:
        raise SystemExit("ERROR: could not read the bundle names out of index.html")
    return os.path.join(ui, "assets", js.group(1)), os.path.join(ui, "assets", css.group(1))


def text_bearing_classes(js_text: str) -> dict[str, str]:
    """class -> a sample of the direct text found with it."""
    found: dict[str, str] = {}
    for m in CLASS_ATTR.finditer(js_text):
        window = js_text[m.end():m.end() + LOOKAHEAD]
        lit = LITERAL.search(window)
        if not lit:
            continue
        text = lit.group(1)
        if sum(1 for c in text if c.isalpha()) < MIN_LETTERS:
            continue
        for cls in m.group(1).split():
            cls = cls.strip()
            # skip template-literal fragments such as `ad-${t}`
            if cls and "${" not in cls and cls not in found:
                found[cls] = text
    return found


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--app", default=DEFAULT_UI, help="the ui/ directory")
    ap.add_argument("--list", type=int, default=0, help="print N uncovered classes")
    args = ap.parse_args()

    if not os.path.isdir(args.app):
        print("ERROR: ui directory not found: %s" % args.app, file=sys.stderr)
        return 2
    js_path, css_path = bundle_paths(args.app)
    js_text = open(js_path, encoding="utf-8", errors="replace").read()

    covered = patch_classes()
    bearing = text_bearing_classes(js_text)
    uncovered = {c: t for c, t in bearing.items() if c not in covered}

    # The signal that actually matters: an UNCOVERED class whose own text is
    # Arabic-script. English chrome is expected and harmless; a Persian string
    # the patch does not reach is a real miss.
    arabic = {c: t for c, t in uncovered.items()
              if any(0x0600 <= ord(ch) <= 0x06FF or 0xFB50 <= ord(ch) <= 0xFDFF
                     for ch in t)}

    print("bundle     : %s" % os.path.basename(js_path))
    print("covered    : %d classes referenced by the patch" % len(covered))
    print("text-bearing: %d classes carry text directly" % len(bearing))
    print("UNCOVERED  : %d" % len(uncovered))
    print("  of which Arabic-script text: %d  <-- must be 0" % len(arabic))
    for cls, text in sorted(arabic.items()):
        print("    %-32s %s" % (cls, text[:70]))
    print("\nNOTE: the absolute count depends on this file's definition and is NOT\n"
          "comparable to the per-version counts recorded in docs/FINDINGS.md\n"
          "before this tool existed (those used an unrecorded method). The Arabic\n"
          "count IS the meaningful number, and it is definition-independent.")
    print("\nMost uncovered classes are English app chrome. Read the text beside\n"
          "each one before deciding.\n")
    for cls in sorted(uncovered)[:args.list or 25]:
        print("  %-34s %s" % (cls, uncovered[cls][:64]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
