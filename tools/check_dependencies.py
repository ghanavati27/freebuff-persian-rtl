#!/usr/bin/env python3
"""Check the structural dependencies the patch relies on, each in the bundle it
actually lives in.

Classes are one thing; the patch also depends on CSS rules, a custom property
formula, a className template, telemetry selectors and a modal's aria roles.
None of those is visible to the selector health check, and a release can move any
of them while every class still matches - the patch keeps "applying" and one
surface quietly stops working.

Whitespace-tolerant by design, and that is load-bearing: 0.0.190 writes
`--explorer-width: 440px` WITH a space after the colon while `.prose{max-width:860px`
has none, so a needle written from one release's CSS missed in another and
produced two false MISSINGes. **Do not widen a needle to a bare property name to
make a miss go away** - that trades a false negative for a false positive.

Read-only.

Usage:
  python tools/check_dependencies.py [--app <ui dir>]

Exit: 0 = all intact, 1 = something missing (re-check it by hand first).
"""

from __future__ import annotations

import argparse
import os
import re
import sys

DEFAULT_UI = os.path.join(
    os.environ.get("LOCALAPPDATA", ""),
    "Programs", "@codebufffreebuff-desktop", "resources", "orchestrator", "ui")

# (label, needle). Each needle is matched against BOTH bundles, because a
# dependency can legitimately live in either and guessing wrong is how the
# false MISSINGes happen. CSS-specific rules stay CSS-only: the label says so.
CHECKS = [
    ("chat-width custom property",     "--chat-content-max-width"),
    ("chat gutter formula",            "--chat-gutter"),
    ("transcript inner cap",           ".prose{max-width:860px"),
    ("project sidebar class",          ".project-sidebar"),
    ("explorer width",                 "--explorer-width"),
    ("ad-banner rule",                 "ad-banner"),
    ("ad-showcase rule",               ".ad-showcase"),
    ("intermission body rule",         ".intermission-body"),
    ("messages rule",                  ".messages"),
    ("sponsored-ad template",          "sponsored-ad ad-"),
    ("telemetry ad selector",          ".sponsored-ad.ad-banner"),
    ("sponsored break label",          "Sponsored break"),
    ("intermission modal class",       "sponsor-intermission"),
    ("continue button class",          "intermission-continue"),
    ("modal aria",                     "aria-modal"),
    ("impression pixel",               "impUrl"),
    ("sponsored proposal",             "sponsored-proposal"),
    ("placement sidebar card",         "placement-sidebar-card"),
]


def bundle_paths(ui: str) -> tuple[str, str, str]:
    html_path = os.path.join(ui, "index.html")
    html = open(html_path, encoding="utf-8", errors="replace").read()
    js = re.search(r'src="[^"]*?(index-[^"]+\.js)"', html)
    css = re.search(r'href="[^"]*?(index-[^"]+\.css)"', html)
    if not js or not css:
        raise SystemExit("ERROR: could not read the bundle names out of index.html")
    return (html_path,
            os.path.join(ui, "assets", js.group(1)),
            os.path.join(ui, "assets", css.group(1)))


def flat(path: str) -> str:
    return re.sub(r"\s+", "", open(path, encoding="utf-8", errors="replace").read())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--app", default=DEFAULT_UI, help="the ui/ directory")
    args = ap.parse_args()

    if not os.path.isdir(args.app):
        print("ERROR: ui directory not found: %s" % args.app, file=sys.stderr)
        return 2

    html_path, js_path, css_path = bundle_paths(args.app)
    blobs = {"html": flat(html_path), "css": flat(css_path), "js": flat(js_path)}
    print("css bundle : %s" % os.path.basename(css_path))
    print("js bundle  : %s" % os.path.basename(js_path))
    print()

    ok = 0
    missing = []
    for label, needle in CHECKS:
        target = re.sub(r"\s+", "", needle)
        # where it was found, so a MISSING can be re-checked in the right file
        hits = [name for name, blob in blobs.items() if target in blob]
        ok += bool(hits)
        print("  %-28s %s" % (label, ",".join(hits) if hits else "MISSING"))
        if not hits:
            missing.append(label)

    total = len(CHECKS)
    print("\n%d/%d structural dependencies intact" % (ok, total))
    if missing:
        print("\nA MISSING is a HYPOTHESIS, not a finding. Re-check each one by hand in")
        print("the file it should live in before concluding anything:")
        for label in missing:
            print("  - %s" % label)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
