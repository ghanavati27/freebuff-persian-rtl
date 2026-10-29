"""Inject the Persian/RTL patch into the HOSTED workspace window.

Freebuff 0.0.194 stopped rendering the chat from resources/orchestrator/ui.
The local UI is only the splash; the chat is the hosted web app opened in its
own BrowserWindow with electron/hosted-preload.cjs.

This script repoints that one preload at app.asar.unpacked/ (leaving the asar
data block byte-identical) and writes a preload that inserts the patch CSS and
runs the dir="auto" marker in the hosted document.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import shutil
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fb_asar  # noqa: E402

REL = "electron/hosted-preload.cjs"
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def paths() -> tuple[str, str, str]:
    root = os.path.join(os.environ["LOCALAPPDATA"], "Programs", "@codebufffreebuff-desktop")
    asar = os.path.join(root, "resources", "app.asar")
    unpacked = asar + ".unpacked"
    return asar, unpacked, os.path.join(unpacked, "electron", "hosted-preload.cjs")


def shift_offsets(header: dict, original: dict, delta: int) -> None:
    for rel, e in fb_asar.walk(header):
        if "offset" in e:
            e["offset"] = str(int(original[rel]) + delta)


def repack(asar: str, header: dict, data: bytes) -> None:
    # Asar offsets are relative to the start of the data block, and the data
    # block is copied through untouched - so no offset needs to move when the
    # header changes length.
    raw = json.dumps(header, separators=(",", ":")).encode()
    raw += b" " * ((-len(raw)) % 4)
    # four nested little-endian lengths, as Electron's asar reader expects:
    # 4 | json+8 | json+4 | json
    prefix = struct.pack("<4I", 4, len(raw) + 8, len(raw) + 4, len(raw))
    tmp = asar + ".new"
    with open(tmp, "wb") as fh:
        fh.write(prefix)
        fh.write(raw)
        fh.write(data)
    os.replace(tmp, asar)


def font_data_uri(path: str) -> str:
    with open(path, "rb") as fh:
        return "data:font/woff2;base64," + base64.b64encode(fh.read()).decode()


def build_preload(original: str) -> str:
    css_path = os.path.join(REPO, "patch", "fb-persian-rtl.css")
    js_path = os.path.join(REPO, "patch", "fb-persian-rtl.js")
    css = open(css_path, encoding="utf-8").read()
    # fonts are added through the FontFace API (binary source, no CSP fetch)
    css = re.sub(r"@font-face\s*\{[^}]*\}\s*", "", css)
    for weight in (400, 500, 700):
        css = css.replace(
            'url("./fb-vazirmatn-%d.woff2")' % weight,
            "url(%s)" % font_data_uri(os.path.join(REPO, "patch", "fb-vazirmatn-%d.woff2" % weight)),
        )
    js = open(js_path, encoding="utf-8").read()
    fonts = []
    for weight in (400, 500, 700):
        p = os.path.join(REPO, "patch", "fb-vazirmatn-%d.woff2" % weight)
        fonts.append(json.dumps({"w": weight, "b": font_data_uri(p)}))
    addon = """
// ---- fb-persian-rtl: injected into the hosted workspace ----
;(function () {
  try {
    var webFrame = require('electron').webFrame
    var CSS = %s
    var FONTS = [%s]
    var marked = false
    function b64(uri) {
      var s = uri.slice(uri.indexOf(',') + 1)
      var bin = atob(s), out = new Uint8Array(bin.length)
      for (var i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i)
      return out.buffer
    }
    function addFonts() {
      if (marked || !document.fonts) return
      marked = true
      for (var i = 0; i < FONTS.length; i++) {
        try {
          document.fonts.add(new FontFace('Vazirmatn FB', b64(FONTS[i].b), {
            weight: String(FONTS[i].w),
            unicodeRange: 'U+0600-06FF, U+0750-077F, U+08A0-08FF, U+FB50-FDFF, U+FE70-FEFF, U+200C-200D'
          }))
        } catch (e) {}
      }
    }
    function run() {
      try { webFrame.insertCSS(CSS, { cssOrigin: 'user' }) } catch (e) { try { webFrame.insertCSS(CSS) } catch (e2) {} }
      addFonts()
      try { %s } catch (e) {}
      %s
      try { (function(){function pad(root){try{if(!root||root.nodeType!==1)return;var hit=[];if(root.matches&&root.matches(".msg"))hit.push(root);var l=root.querySelectorAll?root.querySelectorAll(".msg"):[];for(var i=0;i<l.length;i++)hit.push(l[i]);for(var j=0;j<hit.length;j++){var el=hit[j];if(el.dataset&&el.dataset.fbPad)continue;el.style.marginRight="24px";if(el.dataset)el.dataset.fbPad="1";}}catch(e){}}pad(document.documentElement);new MutationObserver(function(rs){for(var r=0;r<rs.length;r++){var a=rs[r].addedNodes;for(var n=0;n<a.length;n++)pad(a[n]);}}).observe(document.documentElement,{childList:true,subtree:true});})() } catch (e) {}
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', run, { once: true })
    else run()
  } catch (e) {}
})()
""" % (json.dumps(css), ",".join(fonts), js,
       ("try { var msg=null;setInterval(function(){ if(msg)return;"
        "var out=[];document.querySelectorAll('div,section,article,ul,ol').forEach(function(d){"
        "var r=d.getBoundingClientRect();"
        "if(r.width>700&&r.height<=5&&r.top>60&&out.length<3){out.push((d.className||d.tagName)+'');}});"
        "if(!out.length)return;"
        "msg='FBDBG thin='+out.length+' '+out.join(' | ').slice(0,170);"
        "setInterval(function(){document.title=msg},700);},1500); } catch (e) {}"
        if os.environ.get("FB_DEBUG_DOM") else ""))
    return original + addon


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--restore", action="store_true")
    ap.add_argument("--copy-only", action="store_true", help="verify the unpacked mechanism with an identical copy")
    args = ap.parse_args()

    asar, unpacked, target = paths()
    backup = asar + ".fb-orig"
    if not os.path.exists(asar):
        print("ERROR: app.asar not found at", asar, file=sys.stderr)
        return 2

    if args.restore:
        if os.path.exists(backup):
            shutil.copy2(backup, asar)
            print("restored app.asar from", backup)
        else:
            print("ERROR: no backup at", backup, file=sys.stderr)
            return 2
        if os.path.isdir(unpacked):
            shutil.rmtree(unpacked, ignore_errors=True)
            print("removed", unpacked)
        return 0

    header, data = fb_asar.load(asar)
    e = fb_asar.entry(header, REL)
    original = data[int(e["offset"]):int(e["offset"]) + int(e["size"])].decode("utf-8", "replace")
    print("app.asar     :", asar)
    print("preload size :", e["size"], "bytes, unpacked:", e.get("unpacked", False))
    print("backup       :", "present" if os.path.exists(backup) else "MISSING")

    if args.check:
        return 0

    if not os.path.exists(backup):
        shutil.copy2(asar, backup)
        print("wrote backup ->", backup)

    if not e.get("unpacked"):
        e["unpacked"] = True
        repack(asar, header, data)
        print("patched asar header: %s -> unpacked" % REL)

    os.makedirs(os.path.dirname(target), exist_ok=True)
    payload = original if args.copy_only else build_preload(original)
    with open(target, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(payload)
    print("wrote        ->", target, "(%d bytes)" % len(payload.encode()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
