#!/usr/bin/env python3
"""Acceptance test: paragraph direction is decided by the DOMINANT script.

The bug this covers: `dir="auto"` resolves direction from an element's FIRST
STRONG CHARACTER, so a Persian paragraph beginning with a URL, a path or a
variable name resolved to LTR - the block left-aligned and every line's bidi
order computed against the wrong base direction.

The patch now counts Arabic-block letters against Latin letters and takes the
majority. This test loads the REAL patch file (not a reimplementation of it) and
checks, by pixel measurement:

  1. A  Persian paragraph starting with a Latin token  -> RIGHT-aligned
  2. B  genuinely English paragraph                    -> LEFT-aligned
  3. C  Persian paragraph starting with Persian        -> RIGHT-aligned
  4. D  a paragraph that STARTS Latin-dominant and gains Persian text
        (the streaming case)                            -> flips to RIGHT-aligned
  5. E  a digits/punctuation-only paragraph             -> left as dir="auto"
  6. LTR regression: a Latin-only page must be pixel-IDENTICAL with and without
     the patch, since Latin-dominant content resolves to ltr either way.

Usage:
  python tools/verify_paragraph_direction.py [--keep]

Exit status: 0 all checks passed, 1 a check failed, 2 the harness could not run.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

# The streaming case needs the debounce in the patch (120ms) to have elapsed.
STREAM_WAIT_S = 1.2
TOL = 3          # px; how close to an edge counts as "hugging" it

# What each expected DIRECTION looks like once measured as an alignment.
# `auto` with no letters at all resolves to ltr in the browser, so it lays out
# left - which is exactly the pre-existing behaviour for such a string.
EXPECT_ALIGN = {"rtl": "right", "ltr": "left", "auto": "left"}

PERSIAN = ("\u0628\u0627 \u062a\u0648\u0636\u06cc\u062d \u062f\u0631 \u0647\u0645\u0627\u0646 "
           "\u0641\u0627\u06cc\u0644 \u0648 \u0644\u06cc\u0646\u06a9 \u0627\u06cc\u0645\u06cc\u0644 "
           "\u0648 \u0644\u06cc\u0646\u06a9 \u0631\u0641\u0631\u0627\u0644 \u062f\u0634\u0628\u0648\u0631\u062f "
           "\u0647\u0631 \u062f\u0648 \u0631\u0648\u06cc \u0647\u0645\u0627\u0646 \u0622\u062f\u0631\u0633 "
           "\u0647\u0633\u062a\u0646\u062f \u06a9\u0647 \u0645\u0631\u0648\u0631\u06af\u0631 "
           "\u0634\u0645\u0627 \u0628\u0627\u0632 \u0645\u06cc\u200c\u06a9\u0646\u062f")

CASES = [
    ("A_latin_first_persian", "http://127.0.0.1:3000 " + PERSIAN, "rtl"),
    ("B_genuinely_english",
     "The server restarts with the new env, so the emailed link and the referral "
     "link both point at the same address that your browser opens.", "ltr"),
    ("C_persian_first", PERSIAN + " http://127.0.0.1:3000", "rtl"),
    ("E_no_letters", "404 / 127.0.0.1:3000 -- 42 %", "auto"),
]

# Case D: inserted Latin-dominant, then grown into Persian-dominant.
STREAM_LATIN = "http://127.0.0.1:3000 src/server.mjs"
STREAM_GROWN = STREAM_LATIN + " " + PERSIAN

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>paragraph direction</title>
<link rel="stylesheet" href="__BUNDLE_CSS__">
__PATCH_LINK__
<style>
  html,body{margin:0;padding:0;background:#101010;color:#e6e6e6}
  .wrap{width:760px;margin:0 auto;padding:20px 0}
  .prose p{margin:0 0 18px}
</style>
</head><body>
<div class="wrap"><div class="prose" id="prose"></div></div>
<script>
  var CASES = __CASES__;
  var host = document.getElementById('prose');
  CASES.forEach(function (c) {
    var p = document.createElement('p');
    p.textContent = c[1];
    p.id = c[0];
    host.appendChild(p);
  });
  var d = document.createElement('p');
  d.id = 'D_stream';
  d.textContent = __STREAM_LATIN__;
  host.appendChild(d);
</script>
__PATCH_JS__
</body></html>
"""


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
    return os.path.join(ui, m.group(1).lstrip("/"))


def build_page(ui: str, patched: bool, tmp: str, cases=None, stream: bool = True,
               tag: str = "") -> str:
    patch_css = os.path.join(ui, "assets", "fb-persian-rtl.css")
    patch_js = os.path.join(ui, "assets", "fb-persian-rtl.js")
    link = '<link rel="stylesheet" href="%s">' % file_url(patch_css) if patched else ""
    script = '<script src="%s"></script>' % file_url(patch_js) if patched else ""
    import json
    chosen = CASES if cases is None else cases
    html = (PAGE
            .replace("__BUNDLE_CSS__", file_url(bundle_css(ui)))
            .replace("__PATCH_LINK__", link)
            .replace("__CASES__", json.dumps([[c[0], c[1]] for c in chosen]))
            .replace("__STREAM_LATIN__", json.dumps(STREAM_LATIN))
            .replace("__PATCH_JS__", script))
    if not stream:
        # The streaming case exists only on the page that tests streaming; a
        # Latin-only regression page must carry nothing the stock page cannot.
        html = html.replace("""  var d = document.createElement('p');
  d.id = 'D_stream';
  d.textContent = %s;
  host.appendChild(d);""" % json.dumps(STREAM_LATIN), "")
    name = "pdir_%s_%s.html" % ("patched" if patched else "stock", tag or "all")
    path = os.path.join(tmp, name)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html)
    return path


def make_driver(profile: str):
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    opts = Options()
    opts.add_argument("--headless=new")
    for a in ("--disable-gpu", "--no-sandbox", "--no-first-run",
              "--hide-scrollbars", "--force-device-scale-factor=1",
              "--user-data-dir=" + profile):
        opts.add_argument(a)
    return webdriver.Chrome(options=opts)


def _threshold(v: int) -> int:
    """Pillow point() transform: 255 for ink, 0 for background."""
    return 255 if v > 95 else 0


def band_ink(im, y0: int, y1: int):
    band = im.crop((0, max(0, y0), im.size[0], min(im.size[1], y1)))
    bbox = band.point(_threshold).getbbox()
    return (bbox[0], bbox[2]) if bbox else (None, None)


def verdict(box_l, box_r, ink_l, ink_r) -> str:
    if ink_l is None:
        return "no ink"
    hugs_right = abs(ink_r - box_r) <= TOL and abs(ink_l - box_l) > TOL
    hugs_left = abs(ink_l - box_l) <= TOL and abs(ink_r - box_r) > TOL
    if hugs_right:
        return "right"
    if hugs_left:
        return "left"
    return "full-width"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--keep", action="store_true", help="keep the rendered PNGs")
    args = ap.parse_args()

    ui = ui_dir()
    if not os.path.isfile(os.path.join(ui, "assets", "fb-persian-rtl.js")):
        print("ERROR: the patch is not installed; run apply_fb_persian_patch.py first",
              file=sys.stderr)
        return 2

    tmp = tempfile.mkdtemp(prefix="fb-pdir-")
    try:
        driver = make_driver(os.path.join(tmp, "ud"))
    except Exception as exc:
        print("ERROR: could not start ChromeDriver: %s" % exc, file=sys.stderr)
        if "No module named" in str(exc):
            print("This is an INTERPRETER problem, not a patch problem. See the "
                  "Interpreter note in tools/README.md.", file=sys.stderr)
        return 2
    print("chrome : %s" % driver.capabilities.get("browserVersion"))
    print("scratch: %s\n" % tmp)

    from PIL import Image, ImageChops

    failures: list[str] = []
    rows: list[tuple] = []
    try:
        driver.set_window_size(900, 900)

        # --- stock render, for the LTR regression diff -------------------------
        driver.get(file_url(build_page(ui, False, tmp)))
        stock_png = os.path.join(tmp, "stock.png")
        driver.save_screenshot(stock_png)

        # --- patched render ---------------------------------------------------
        driver.get(file_url(build_page(ui, True, tmp)))
        time.sleep(0.4)
        patched_png = os.path.join(tmp, "patched.png")
        driver.save_screenshot(patched_png)
        boxes = driver.execute_script("""
          return Array.prototype.map.call(document.querySelectorAll('p'),
            function (p) {
              var r = p.getBoundingClientRect();
              return {id: p.id, dir: p.getAttribute('dir'),
                      resolved: getComputedStyle(p).direction,
                      boxL: Math.round(r.left), boxR: Math.round(r.right),
                      boxT: Math.round(r.top), boxB: Math.round(r.bottom)};
            });""")

        im = Image.open(patched_png).convert("L")
        print("=== direction per paragraph (real patch, pixel-measured) ===")
        print("  %-24s %-6s %-8s %-9s %s" % ("case", "attr", "resolved", "ink", "verdict"))
        for row in boxes:
            il, ir = band_ink(im, row["boxT"], row["boxB"])
            v = verdict(row["boxL"], row["boxR"], il, ir)
            rows.append((row, il, ir, v))
            print("  %-24s %-6s %-8s L%s..R%s  %s"
                  % (row["id"][:24], row["dir"], row["resolved"], il, ir, v))

        by_id = {r[0]["id"]: (r[0], r[3]) for r in rows}
        for cid, _text, want in CASES:
            got = by_id.get(cid, (None, "missing"))[1]
            expect = EXPECT_ALIGN[want]
            if got != expect:
                failures.append("%s: dir=%s should lay out %s, measured %s"
                                % (cid, want, expect, got))

        # --- streaming: grow case D from Latin-dominant to Persian-dominant ----
        driver.execute_script(
            "var d=document.getElementById('D_stream'); d.textContent=arguments[0];",
            STREAM_GROWN)
        time.sleep(STREAM_WAIT_S)
        d_info = driver.execute_script("""
          var p=document.getElementById('D_stream');
          var r=p.getBoundingClientRect();
          return {dir:p.getAttribute('dir'), resolved:getComputedStyle(p).direction,
                  boxL:Math.round(r.left), boxR:Math.round(r.right),
                  boxT:Math.round(r.top), boxB:Math.round(r.bottom)};""")
        grow_png = os.path.join(tmp, "grown.png")
        driver.save_screenshot(grow_png)
        im2 = Image.open(grow_png).convert("L")
        il, ir = band_ink(im2, d_info["boxT"], d_info["boxB"])
        v = verdict(d_info["boxL"], d_info["boxR"], il, ir)
        print("\n=== streaming: paragraph grew from Latin-dominant to Persian ===")
        print("  D_stream  attr=%s resolved=%s  ink L%s..R%s  -> %s"
              % (d_info["dir"], d_info["resolved"], il, ir, v))
        if v != "right":
            failures.append("D_stream: expected right after the text grew Persian, "
                            "measured %s (attr=%s)" % (v, d_info["dir"]))

        # --- LTR regression ---------------------------------------------------
        # A Latin-ONLY page: the patch must not move a single pixel on it. (The
        # mixed page above legitimately differs - that IS the fix - so it cannot
        # serve as the regression baseline.)
        print("\n=== LTR regression (Latin-only page, stock vs patched) ===")
        latin_only = [c for c in CASES if c[2] == "ltr"]
        reg = {}
        for patched in (False, True):
            driver.get(file_url(build_page(ui, patched, tmp, cases=latin_only,
                                           stream=False, tag="latinonly")))
            png = os.path.join(tmp, "reg_%s.png" % ("patched" if patched else "stock"))
            driver.save_screenshot(png)
            reg[patched] = png
        a = Image.open(reg[False]).convert("RGB")
        b = Image.open(reg[True]).convert("RGB")
        if a.size != b.size:
            failures.append("LTR regression: render size differs %s vs %s" % (a.size, b.size))
            print("  size mismatch")
        else:
            bbox = ImageChops.difference(a, b).getbbox()
            if bbox is None:
                print("  IDENTICAL: 0 differing pixels  -> LTR guarantee holds")
            else:
                failures.append("LTR regression: a Latin-only page differs at %s" % (bbox,))
                print("  DIFFER at %s  -> the patch reached an LTR element" % (bbox,))

        if not args.keep:
            for f in (stock_png, patched_png, grow_png,
                      reg.get(False), reg.get(True)):
                if f and os.path.exists(f):
                    os.remove(f)
    finally:
        driver.quit()

    print()
    if failures:
        print("FAILED %d check(s):" % len(failures))
        for f in failures:
            print("  - " + f)
        return 1
    print("PASS: latin-first Persian -> right, English -> left, persian-first -> "
          "right, no-letter -> auto, and a streamed paragraph flips to right once "
          "Persian dominates.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
