#!/usr/bin/env python3
"""Verify the sponsored-break auto-continue in the runtime half of the patch.

The sponsored break (`.sponsor-intermission`) is a blocking modal whose exits are
both unavailable while its countdown runs, so the patch dismisses it by clicking
"Continue working" as soon as that button becomes enabled. Three claims:

  1. while the button is still disabled, nothing is clicked - clicking a disabled
     button does nothing anyway, but a poll that ignores `disabled` would fire on
     every tick and is the bug worth catching;
  2. once the button is enabled, it is clicked exactly once;
  3. it is not clicked again on later ticks (no repeat clicking while React has
     yet to unmount the dialog).

Method: render the real break markup with the real patch script loaded, attach a
click counter, and drive the button's disabled state from the test while reading
the counter back out of the page.

Usage:
  python tools/verify_break_autocontinue.py [--headful]

Exit status: 0 all checks passed, 1 a check failed, 2 the harness could not run.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import time

DISABLED_WAIT_S = 1.4      # > 2 poll ticks at 500ms
ENABLED_WAIT_S = 1.4
REPEAT_WAIT_S = 1.4

HARNESS = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>break auto-continue harness</title>
<!--
  NOTE: this template is substituted with str.replace, not str.format - the
  inline script below is full of braces and .format would treat them as fields.
-->
<script>
  window.__clicks = 0;
  window.__lastClickAt = null;
  document.addEventListener('DOMContentLoaded', function () {
    var b = document.querySelector('.intermission-continue');
    if (b) b.addEventListener('click', function () {
      window.__clicks++;
      window.__lastClickAt = Date.now();
    });
  });
</script>
<script defer src="__PATCH_JS__"></script>
</head><body>
<!-- The real break markup, from the bundle's own JSX. The Continue button starts
     disabled, which is how it renders while the countdown runs. -->
<div class="sponsor-intermission sb-card" role="dialog" aria-modal="true"
     aria-label="Sponsored break" tabindex="-1">
  <div class="intermission-body">
    <div class="intermission-text">
      <div class="sb-label intermission-disclosure"><span>sponsor.example</span></div>
      <h2 class="sb-headline intermission-headline">A sponsored break</h2>
      <p class="sb-subhead intermission-subhead">Some copy.</p>
    </div>
    <div class="intermission-actions">
      <button type="button" class="sb-button intermission-continue"
              disabled aria-disabled="true">Continue working</button>
    </div>
  </div>
</div>
</body></html>
"""


def ui_dir() -> str:
    return os.path.join(os.environ["LOCALAPPDATA"], "Programs",
                        "@codebufffreebuff-desktop", "resources", "orchestrator", "ui")


def file_url(path: str) -> str:
    return "file:///" + os.path.abspath(path).replace("\\", "/")


def make_driver(headful: bool, profile: str):
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    opts = Options()
    if not headful:
        opts.add_argument("--headless=new")
    for arg in ("--disable-gpu", "--no-sandbox", "--no-first-run",
                "--disable-extensions", "--hide-scrollbars",
                "--user-data-dir=" + profile):
        opts.add_argument(arg)
    return webdriver.Chrome(options=opts)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--headful", action="store_true", help="show the browser window")
    args = ap.parse_args()

    ui = ui_dir()
    patch_js = os.path.join(ui, "assets", "fb-persian-rtl.js")
    if not os.path.isfile(patch_js):
        print("ERROR: the patch is not installed; run apply_fb_persian_patch.py first",
              file=sys.stderr)
        return 2

    tmp = tempfile.mkdtemp(prefix="fb-break-")
    page = os.path.join(tmp, "break.html")
    with open(page, "w", encoding="utf-8") as fh:
        fh.write(HARNESS.replace("__PATCH_JS__", file_url(patch_js)))

    try:
        driver = make_driver(args.headful, os.path.join(tmp, "ud"))
    except Exception as exc:  # surfaced verbatim
        print("ERROR: could not start ChromeDriver: %s" % exc, file=sys.stderr)
        return 2
    print("chrome : %s" % driver.capabilities.get("browserVersion"))
    print("scratch: %s\n" % tmp)

    failures: list[str] = []
    try:
        driver.get(file_url(page))
        time.sleep(0.6)   # let DOMContentLoaded fire and the poll start

        state = driver.execute_script(
            "var b=document.querySelector('.intermission-continue');"
            "return {disabled: b.disabled, aria: b.getAttribute('aria-disabled'),"
            " clicks: window.__clicks};")
        print("=== phase 1: button still disabled (countdown running) ===")
        print("  start state: disabled=%s aria-disabled=%s clicks=%s"
              % (state["disabled"], state["aria"], state["clicks"]))

        time.sleep(DISABLED_WAIT_S)
        clicks_disabled = driver.execute_script("return window.__clicks;")
        ok = clicks_disabled == 0
        if not ok:
            failures.append("clicked %d time(s) while the button was disabled"
                            % clicks_disabled)
        print("  after %.1fs: clicks=%d  -> %s"
              % (DISABLED_WAIT_S, clicks_disabled, "no click OK" if ok else "FAIL"))

        print("\n=== phase 2: enable the button (countdown finished) ===")
        driver.execute_script(
            "var b=document.querySelector('.intermission-continue');"
            "b.disabled=false; b.removeAttribute('aria-disabled');")
        time.sleep(ENABLED_WAIT_S)
        clicks_enabled = driver.execute_script("return window.__clicks;")
        ok = clicks_enabled == 1
        if not ok:
            failures.append("expected exactly 1 click once enabled, got %d"
                            % clicks_enabled)
        print("  after %.1fs: clicks=%d  -> %s"
              % (ENABLED_WAIT_S, clicks_enabled,
                 "clicked once OK" if ok else "FAIL"))

        print("\n=== phase 3: keep polling (must not click again) ===")
        time.sleep(REPEAT_WAIT_S)
        clicks_repeat = driver.execute_script("return window.__clicks;")
        ok = clicks_repeat == 1
        if not ok:
            failures.append("clicked %d times in total - repeat clicking" % clicks_repeat)
        print("  after %.1fs more: clicks=%d  -> %s"
              % (REPEAT_WAIT_S, clicks_repeat,
                 "still exactly 1 OK" if ok else "FAIL"))

        print("\n=== phase 4: dialog gone (poll must stop) ===")
        driver.execute_script(
            "var d=document.querySelector('.sponsor-intermission'); d.remove();")
        time.sleep(1.0)
        # Re-insert a fresh break: it must be picked up and clicked, which proves
        # the watcher restarted rather than the interval having died.
        driver.execute_script(
            "var h=document.createElement('div');"
            "h.className='sponsor-intermission sb-card';"
            "h.setAttribute('role','dialog');"
            "h.innerHTML='<button class=\"intermission-continue\">Continue working</button>';"
            "h.querySelector('button').addEventListener('click',function(){window.__clicks++;});"
            "document.body.appendChild(h);")
        time.sleep(1.4)
        clicks_new = driver.execute_script("return window.__clicks;")
        ok = clicks_new == 2
        if not ok:
            failures.append("a fresh break was not auto-continued (clicks=%d, expected 2)"
                            % clicks_new)
        print("  a new break appeared: clicks=%d  -> %s"
              % (clicks_new, "picked up OK" if ok else "FAIL"))
    finally:
        driver.quit()

    print()
    if failures:
        print("FAILED %d check(s):" % len(failures))
        for f in failures:
            print("  - " + f)
        return 1
    print("PASS: the sponsored break is continued exactly once, only after its "
          "countdown finishes, and a later break is picked up too.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
