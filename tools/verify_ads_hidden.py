#!/usr/bin/env python3
"""Verify the ad-hiding section of the patch, by measurement.

Two claims to verify, and the second matters as much as the first:

  1. each ad surface the section targets is gone after the patch - computed
     `display: none` and a 0x0 box, where the stock render had a real box;
  2. .sponsor-intermission is NOT hidden. It is a blocking modal whose only exits
     are its own buttons, so a hide rule that over-reached into it would leave
     the app waiting on a click that can never happen. Over-reach is the failure
     mode a hide rule is most likely to have, so it is asserted, not assumed.

Method: render the real ad markup (traced out of the bundle's own JSX) against
the real bundle CSS in headless Chromium via Selenium, once unpatched and once
patched, and read `getComputedStyle(...).display` plus getBoundingClientRect()
back out of the DOM.

Usage:
  python tools/verify_ads_hidden.py [--headful]

Exit status: 0 all checks passed, 1 a check failed, 2 the harness could not run.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile

# (selector, human label) - the surfaces the patch is supposed to hide.
TARGETS = [
    (".sponsored-ad.ad-banner", "composer banner"),
    (".ad-showcase", "large sponsor card"),
    (".sponsored-proposal", "sponsored proposal panel"),
]

# Surfaces the patch must NOT touch. The intermission is a blocking modal: hiding
# it removes the user's only way out of it.
MUST_STAY = [
    (".sponsor-intermission", "sponsored break modal (blocking - must stay)"),
]

# Markup copied from the bundle's own JSX (className: `sponsored-ad ad-${t}`, the
# ad-showcase tree, the sponsored-proposal <section>, and the intermission
# dialog). Deliberately the real class lists, not lookalikes.
HARNESS = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>ad-hide harness</title>
<link rel="stylesheet" href="{bundle_css}">
{patch_link}
<style>html, body {{ margin: 0; padding: 0; background: #101010; color: #ddd; }}</style>
</head><body>
<a class="sponsored-ad ad-banner" href="#" target="_blank" rel="noreferrer noopener sponsored">
  <span class="ad-content">
    <span class="ad-head">
      <span class="ad-heading"><span class="ad-title">Partner product</span></span>
      <span class="ad-disclosure">Ad</span>
    </span>
    <span class="ad-detail"><span class="ad-copy">Try it now</span></span>
  </span>
</a>

<div class="ad-showcase">
  <a class="ad-showcase-link" href="#" rel="noreferrer noopener sponsored">
    <span class="ad-showcase-copy">
      <span class="ad-showcase-brand"><span class="ad-title">Partner</span></span>
    </span>
  </a>
</div>

<section class="sponsored-proposal" data-state="offered" aria-label="Sponsored proposal">
  <div class="proposal-head">
    <span class="proposal-heading">
      <span class="proposal-advertiser">Advertiser</span>
      <span class="proposal-offer-line">A sponsored task</span>
    </span>
    <span class="proposal-controls">
      <span class="proposal-disclosure">Sponsored</span>
      <button type="button" class="proposal-dismiss">Dismiss</button>
    </span>
  </div>
</section>

<div class="placement-sidebar-card">
  <a class="placement-creative-link" href="#" rel="noreferrer noopener sponsored">
    <span class="placement-ad-chip">Ad</span>
  </a>
  <button type="button" class="placement-dismiss" aria-label="Dismiss">x</button>
</div>

<div class="sponsor-intermission sb-card" role="dialog" aria-modal="true"
     aria-label="Sponsored break" tabindex="-1">
  <div class="intermission-body">
    <div class="intermission-text">
      <div class="sb-label intermission-disclosure"><span>sponsor.example</span></div>
      <h2 class="sb-headline intermission-headline">A sponsored break</h2>
      <p class="sb-subhead intermission-subhead">Some copy.</p>
    </div>
    <div class="intermission-actions">
      <button type="button" class="sb-button intermission-continue">Continue working</button>
    </div>
  </div>
</div>

<pre id="fb-probe" style="position:fixed;left:-9999px"></pre>
<script>
(function () {{
  function probe(sel) {{
    var el = document.querySelector(sel);
    if (!el) return {{missing: true}};
    var r = el.getBoundingClientRect();
    return {{
      display: getComputedStyle(el).display,
      width: Math.round(r.width), height: Math.round(r.height),
      inFlow: r.width > 0 && r.height > 0
    }};
  }}
  var out = {{}};
  {selectors}.forEach(function (s) {{ out[s] = probe(s); }});
  document.getElementById('fb-probe').textContent = JSON.stringify(out);
}})();
</script>
</body></html>
"""

PROBE_JS = "return document.getElementById('fb-probe').textContent;"


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


def build_page(ui: str, patched: bool, tmp: str) -> str:
    patch_link = ""
    if patched:
        patch_link = ('<link rel="stylesheet" href="%s">'
                      % file_url(os.path.join(ui, "assets", "fb-persian-rtl.css")))
    sels = [s for s, _ in TARGETS + MUST_STAY]
    html = HARNESS.format(
        bundle_css=file_url(os.path.join(ui, "assets", bundle_css(ui))),
        patch_link=patch_link,
        selectors=json.dumps(sels))
    name = "ads_%s.html" % ("patched" if patched else "stock")
    path = os.path.join(tmp, name)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html)
    return path


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
    ap.add_argument("--headful", action="store_true", help="show the browser window")
    args = ap.parse_args()

    ui = ui_dir()
    if not os.path.isfile(os.path.join(ui, "assets", "fb-persian-rtl.css")):
        print("ERROR: the patch is not installed; run apply_fb_persian_patch.py first",
              file=sys.stderr)
        return 2

    tmp = tempfile.mkdtemp(prefix="fb-adhide-")
    try:
        driver = make_driver(args.headful, os.path.join(tmp, "ud"))
    except Exception as exc:  # surfaced verbatim
        print("ERROR: could not start ChromeDriver: %s" % exc, file=sys.stderr)
        if "No module named" in str(exc):
            print(
                "This is an INTERPRETER problem, not a patch problem. Selenium "
                "needs selenium + certifi; the pixel checks need Pillow. The "
                "default `python` in a Hermes session venv may have none of "
                "them. See the Interpreter note in tools/README.md.",
                file=sys.stderr)
        return 2
    print("chrome : %s" % driver.capabilities.get("browserVersion"))
    print("scratch: %s\n" % tmp)

    failures: list[str] = []
    try:
        driver.set_window_size(1400, 1000)
        stock, patched = {}, {}
        for flag, sink in ((False, stock), (True, patched)):
            driver.get(file_url(build_page(ui, flag, tmp)))
            sink.update(json.loads(driver.execute_script(PROBE_JS)))
    finally:
        driver.quit()

    print("=== targeted surfaces (must be gone after the patch) ===")
    print("%-26s %-30s %-18s %s" % ("selector", "stock", "patched", "verdict"))
    for sel, label in TARGETS:
        s, p = stock.get(sel, {}), patched.get(sel, {})
        if s.get("missing") or p.get("missing"):
            failures.append("%s: element missing from the harness" % sel)
            print("%-26s %-30s %-18s %s" % (sel, "MISSING", "MISSING", "FAIL"))
            continue
        ok = p["display"] == "none" and not p["inFlow"] and s["inFlow"]
        if not ok:
            failures.append(
                "%s (%s): stock display=%s box=%sx%s, patched display=%s box=%sx%s"
                % (sel, label, s["display"], s["width"], s["height"],
                   p["display"], p["width"], p["height"]))
        print("%-26s %-30s %-18s %s"
              % (sel,
                 "%s %sx%s" % (s["display"], s["width"], s["height"]),
                 "%s %sx%s" % (p["display"], p["width"], p["height"]),
                 "hidden OK" if ok else "FAIL"))
        print("%-26s   (%s)" % ("", label))

    print("\n=== scope guard (must still be visible) ===")
    for sel, label in MUST_STAY:
        s, p = stock.get(sel, {}), patched.get(sel, {})
        if s.get("missing") or p.get("missing"):
            failures.append("%s: element missing from the harness" % sel)
            print("%-26s MISSING  FAIL" % sel)
            continue
        ok = p["display"] != "none" and p["inFlow"]
        if not ok:
            failures.append(
                "%s: the patch hid a blocking modal (patched display=%s box=%sx%s)"
                % (sel, p["display"], p["width"], p["height"]))
        print("%-26s %-30s %-18s %s"
              % (sel,
                 "%s %sx%s" % (s["display"], s["width"], s["height"]),
                 "%s %sx%s" % (p["display"], p["width"], p["height"]),
                 "still visible OK" if ok else "FAIL"))
        print("%-26s   (%s)" % ("", label))

    print()
    if failures:
        print("FAILED %d check(s):" % len(failures))
        for f in failures:
            print("  - " + f)
        return 1
    print("PASS: all %d targeted ad surfaces are hidden, and the blocking "
          "sponsored-break modal is untouched." % len(TARGETS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
