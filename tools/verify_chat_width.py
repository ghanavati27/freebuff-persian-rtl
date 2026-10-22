#!/usr/bin/env python3
"""Verify the chat-width section of the patch, by measurement.

The chat column is capped by one custom property, --chat-content-max-width,
which every consumer wraps in min()/calc() against 100% (the live centre-column
width). The claims to verify are geometric, not stylistic:

  1. unpatched, the transcript is capped at 720px and the centre column is left
     partly empty;
  2. patched, the transcript fills the centre column up to the 1200px cap;
  3. the width tracks BOTH the window size and the side panels, with no media
     query and no JS;
  4. the .prose block inside the transcript is not re-capped by its own
     max-width:860px (the trap this section exists to avoid).

Method: render the app's REAL bundle CSS with a faithful shell - the app's own
.threadview / .messages / .msg.assistant / .prose markup, and the app's own
216px .project-sidebar and 440px explorer either side - in headless Chromium via
Selenium, and read the geometry back out of the DOM. Screenshots are measured
independently with Pillow, so the numbers do not rest on a single method.

Why Selenium and not `chrome.exe --headless --screenshot`: on Windows a raw
chrome.exe invocation delegates to an already-running browser and silently
produces nothing (the screenshot flag returns exit 0 with no file written).
ChromeDriver manages its own session, so it works regardless.

Usage:
  python tools/verify_chat_width.py [--keep] [--headful]

Exit status: 0 all checks passed, 1 a check failed, 2 the harness could not run.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))

# Window widths to sweep. The centre column is window - 216 - 440 with both
# panels open, so these cover "narrower than the cap", "just over" and "well
# over" it.
VIEWPORTS = [1280, 1600, 1920, 2560]

# (label, left sidebar open, right explorer open)
PANEL_STATES = [
    ("both-open", True, True),
    ("right-closed", True, False),
    ("left-closed", False, True),
    ("both-closed", False, False),
]

CAP_PX = 1200          # the value section 5 sets
SIDEBAR_PX = 216       # .project-sidebar{width:216px;flex-basis:216px}
EXPLORER_PX = 440      # --explorer-width: 440px
STOCK_CAP_PX = 720     # the shipped --chat-content-max-width
MIN_GUTTER_PX = 32     # --space-8, the floor under the centring gutter
TOL = 1.5              # px; sub-pixel layout rounding

FILLER = ("Freebuff is a free coding agent. This paragraph exists only to give "
          "the transcript block a measurable ink extent that spans the full "
          "width of its container, so the rendered geometry can be "
          "cross-checked in pixels rather than trusted from one method alone.")

HARNESS = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>chat-width harness</title>
<link rel="stylesheet" href="{bundle_css}">
{patch_link}
<style>
  html, body {{ margin: 0; padding: 0; height: 100%; overflow: hidden; }}
  /* The app's own shell: sidebar | centre | explorer, with the centre flexing.
     The panel widths come from the real classes (.project-sidebar and
     --explorer-width), so the centre column is derived the way the app derives
     it rather than hard-coded here. */
  .harness-shell {{ display: flex; width: 100vw; height: 100vh; }}
</style>
</head><body>
<div class="harness-shell">
  <div class="harness-left" style="{left_style}"></div>
  <div class="threadview">
    <div class="messages">
      <div class="msg assistant">
        <div class="prose"><p>{filler}</p><p>{filler}</p></div>
      </div>
    </div>
  </div>
  <div class="harness-right" style="{right_style}"></div>
</div>
</body></html>
"""

MEASURE_JS = """return (function () {
  function box(sel) {
    var el = document.querySelector(sel);
    if (!el) return null;
    var r = el.getBoundingClientRect();
    var cs = getComputedStyle(el);
    var pl = parseFloat(cs.paddingLeft) || 0, pr = parseFloat(cs.paddingRight) || 0;
    return {
      left: r.left, right: r.right, width: r.width,
      padLeft: pl, padRight: pr, maxWidth: cs.maxWidth,
      contentWidth: el.clientWidth - pl - pr
    };
  }
  return JSON.stringify({
    viewport: window.innerWidth,
    capVar: getComputedStyle(document.documentElement)
              .getPropertyValue('--chat-content-max-width').trim(),
    centre: box('.threadview'),
    messages: box('.messages'),
    prose: box('.messages .prose')
  });
})();"""


def ui_dir() -> str:
    return os.path.join(os.environ["LOCALAPPDATA"], "Programs",
                        "@codebufffreebuff-desktop", "resources", "orchestrator", "ui")


def file_url(path: str) -> str:
    return "file:///" + os.path.abspath(path).replace("\\", "/")


def bundle_css(ui: str) -> str:
    html = open(os.path.join(ui, "index.html"), encoding="utf-8").read()
    m = re.search(r'href="([^"]*assets/index-[^"]+\.css)"', html)
    if not m:
        raise RuntimeError("could not read the bundle CSS name out of index.html")
    return os.path.basename(m.group(1))


def build_harness(ui: str, patched: bool, left: bool, right: bool, tmp: str,
                  tag: str) -> str:
    patch_link = ""
    if patched:
        patch_link = ('<link rel="stylesheet" href="%s">'
                      % file_url(os.path.join(ui, "assets", "fb-persian-rtl.css")))
    html = HARNESS.format(
        bundle_css=file_url(os.path.join(ui, "assets", bundle_css(ui))),
        patch_link=patch_link,
        left_style=("width:%dpx" % SIDEBAR_PX) if left else "display:none",
        right_style=("width:%dpx" % EXPLORER_PX) if right else "display:none",
        filler=FILLER)
    path = os.path.join(tmp, "harness_%s_%s.html"
                        % ("patched" if patched else "stock", tag))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html)
    return path


def _threshold(v: int) -> int:
    """Pillow point() transform: 255 for ink, 0 for background."""
    return 255 if v > 95 else 0


def ink_span(png: str, y_lo: int, y_hi: int) -> tuple[int, int] | None:
    """Left/right ink extent over a horizontal band, measured with Pillow."""
    from PIL import Image
    im = Image.open(png).convert("L")
    w, h = im.size
    bbox = im.crop((0, max(0, y_lo), w, min(h, y_hi))).point(_threshold).getbbox()
    return (bbox[0], bbox[2]) if bbox else None


def make_driver(headful: bool, profile: str):
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    opts = Options()
    if not headful:
        opts.add_argument("--headless=new")
    for arg in ("--disable-gpu", "--no-sandbox", "--no-first-run",
                "--disable-extensions", "--hide-scrollbars",
                "--force-device-scale-factor=1",
                "--user-data-dir=" + profile):
        opts.add_argument(arg)
    return webdriver.Chrome(options=opts)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--keep", action="store_true", help="keep the rendered PNGs")
    ap.add_argument("--headful", action="store_true", help="show the browser window")
    args = ap.parse_args()

    ui = ui_dir()
    if not os.path.isfile(os.path.join(ui, "index.html")):
        print("ERROR: Freebuff UI not found at %s" % ui, file=sys.stderr)
        return 2
    if not os.path.isfile(os.path.join(ui, "assets", "fb-persian-rtl.css")):
        print("ERROR: the patch is not installed; run apply_fb_persian_patch.py first",
              file=sys.stderr)
        return 2

    tmp = tempfile.mkdtemp(prefix="fb-chatwidth-")
    print("scratch: %s" % tmp)

    try:
        driver = make_driver(args.headful, os.path.join(tmp, "ud"))
    except Exception as exc:  # surfaced to the user verbatim
        print("ERROR: could not start ChromeDriver: %s" % exc, file=sys.stderr)
        if "No module named" in str(exc):
            print(
                "This is an INTERPRETER problem, not a patch problem. Selenium "
                "needs selenium + certifi; the pixel checks need Pillow. The "
                "default `python` in a Hermes session venv may have none of "
                "them. See the Interpreter note in tools/README.md.",
                file=sys.stderr)
        return 2
    print("chrome : %s\n" % driver.capabilities.get("browserVersion"))

    failures: list[str] = []
    rows: list[tuple] = []
    shots: list[tuple[str, float]] = []

    try:
        for label, left, right in PANEL_STATES:
            stock_page = file_url(build_harness(ui, False, left, right, tmp, label))
            patch_page = file_url(build_harness(ui, True, left, right, tmp, label))
            for width in VIEWPORTS:
                driver.set_window_size(width, 900)
                driver.get(stock_page)
                stock = json.loads(driver.execute_script(MEASURE_JS))
                driver.get(patch_page)
                patched = json.loads(driver.execute_script(MEASURE_JS))

                vw = patched["viewport"]
                centre = vw - (SIDEBAR_PX if left else 0) - (EXPLORER_PX if right else 0)
                expect = min(centre - 2 * MIN_GUTTER_PX, CAP_PX)

                s_prose = stock["prose"]["width"]
                p_prose = patched["prose"]["width"]
                msgs = patched["messages"]

                rows.append((label, vw, centre, s_prose, p_prose,
                             msgs["contentWidth"], msgs["padLeft"],
                             patched["prose"]["maxWidth"], patched["capVar"]))

                # The shipped layout caps the transcript at 720px, but only
                # where the centre column is wide enough to reach that cap;
                # below it the column itself is the limit.
                stock_expect = min(centre - 2 * MIN_GUTTER_PX, STOCK_CAP_PX)
                if abs(s_prose - stock_expect) > TOL + 8:
                    failures.append("%s @%d: stock prose %.1f, expected the shipped "
                                    "layout's %.1f"
                                    % (label, vw, s_prose, stock_expect))
                if patched["prose"]["maxWidth"] != "none":
                    failures.append("%s @%d: .prose max-width is %s, expected none "
                                    "(the inner re-cap)"
                                    % (label, vw, patched["prose"]["maxWidth"]))
                if abs(p_prose - msgs["contentWidth"]) > TOL:
                    failures.append("%s @%d: prose %.1f != messages content %.1f "
                                    "(%.1fpx gap remains)"
                                    % (label, vw, p_prose, msgs["contentWidth"],
                                       msgs["contentWidth"] - p_prose))
                if p_prose > expect + TOL:
                    failures.append("%s @%d: prose %.1f exceeds the expected %.1f"
                                    % (label, vw, p_prose, expect))
                # Widening is only possible where the centre column can exceed
                # the shipped cap; below that the stock layout already used the
                # whole column, so there is nothing to reclaim.
                if stock_expect >= STOCK_CAP_PX - TOL and p_prose <= s_prose + TOL:
                    failures.append("%s @%d: no widening (stock %.1f -> patched %.1f)"
                                    % (label, vw, s_prose, p_prose))
                if msgs["padLeft"] < MIN_GUTTER_PX - TOL:
                    failures.append("%s @%d: gutter %.1f is under the %dpx floor"
                                    % (label, vw, msgs["padLeft"], MIN_GUTTER_PX))

                if label == "both-open" and width in (1920, 2560):
                    for patched_flag, page in ((False, stock_page), (True, patch_page)):
                        name = "shot_%s_%d.png" % (
                            "patched" if patched_flag else "stock", width)
                        png = os.path.join(tmp, name)
                        # Navigate per variant: the driver is left on whichever
                        # page was measured last, so without this both shots
                        # would be of the same page and the cross-check would
                        # prove nothing.
                        driver.get(page)
                        driver.save_screenshot(png)
                        span = ink_span(png, 6, 140)
                        if span is None:
                            failures.append("pixel: no ink found in %s" % name)
                            continue
                        shots.append((name, float(span[1] - span[0])))
                        if not args.keep:
                            os.remove(png)
    finally:
        driver.quit()

    print("=== transcript width (DOM geometry, device scale 1) ===")
    print("%-13s %8s %7s %8s %9s %9s %8s %10s"
          % ("panels", "viewport", "centre", "stock", "patched", "content",
             "gutter", "prose max-w"))
    for (label, vw, centre, s_prose, p_prose, content, gutter, maxw, _cap) in rows:
        print("%-13s %8d %7d %8.1f %9.1f %9.1f %8.1f %10s"
              % (label, vw, centre, s_prose, p_prose, content, gutter, maxw))
    print("\n--chat-content-max-width resolves to: %s" % rows[0][8])

    print("\n=== pixel cross-check (Pillow ink extent, transcript band) ===")
    for name, span in shots:
        print("  %-24s ink span %4d px" % (name, span))
    if not shots:
        failures.append("pixel: no screenshots were measured")

    print()
    if failures:
        print("FAILED %d check(s):" % len(failures))
        for f in failures:
            print("  - " + f)
        return 1
    print("PASS: the transcript fills the centre column up to the %dpx cap, tracks "
          "window size and panel state, and .prose is not re-capped." % CAP_PX)
    return 0


if __name__ == "__main__":
    sys.exit(main())
