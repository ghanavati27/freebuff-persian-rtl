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
    """Original preload + the JS-only injection for the hosted page.

    No CSS: the hosted page's CSP rejects `insertCSS` (author and user origin)
    and injected <style> elements, so every stylesheet rule is a silent no-op
    there. Direction, font, gutter and table alignment are all done through
    the DOM / CSSOM instead.
    """
    js_path = os.path.join(REPO, "patch", "fb-persian-rtl.js")
    js = open(js_path, encoding="utf-8").read()
    fonts = []
    for weight in (400, 500, 700):
        fp = os.path.join(REPO, "patch", "fb-vazirmatn-%d.woff2" % weight)
        fonts.append(json.dumps({"w": weight, "b": font_data_uri(fp)}))
    debug = ""
    if os.environ.get("FB_DEBUG_DOM"):
        debug = '''try { setInterval(function(){var m=document.querySelector(".msg");var ff=m?getComputedStyle(m).fontFamily:"";var pe=null,els=document.querySelectorAll("p,li");for(var i=0;i<els.length;i++){var t=els[i].textContent||"";if(t.length&&t.charCodeAt(0)>1536){pe=els[i];break;}}var pf=pe?getComputedStyle(pe).fontFamily:"";document.title="FBDBG fonts="+document.fonts.size+" msg="+(ff||"-").slice(0,30)+" fa="+(pf||"-").slice(0,30);},3000); } catch (e) {}'''
    addon = """
// ---- fb-persian-rtl: injected into the hosted workspace ----
;(function () {
  try {
    var FONTS = [%s]
    var marked = false
    function b64(uri) {
      var s = uri.slice(uri.indexOf(',') + 1)
      var bin = atob(s), out = new Uint8Array(bin.length)
      for (var i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i)
      return out.buffer
    }
    function addFonts() {
      if (!document.fonts || document.fonts.fbRegistered) return
      document.fonts.fbRegistered = true
      try {
        // The hosted app ships its own copy of this family. Registering a second
        // face under the same name makes the browser swap between them while they
        // load, and text looks broken until they settle - so only fill the gap
        // when the page has nothing of its own.
        if (document.fonts.check('16px "Vazirmatn FB"')) return
      } catch (e) {}
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
      addFonts()
      try { %s } catch (e) {}
      %s
      try { (function(){
        function pad(root){try{if(!root||root.nodeType!==1)return;var hit=[];
          if(root.matches&&root.matches('.msg'))hit.push(root);
          var l=root.querySelectorAll?root.querySelectorAll('.msg'):[];
          for(var i=0;i<l.length;i++)hit.push(l[i]);
          for(var j=0;j<hit.length;j++){var el=hit[j];
            if(el.dataset&&el.dataset.fbPad)continue;
            el.style.marginRight='24px';
            if(el.dataset)el.dataset.fbPad='1';}}catch(e){}}
        function fixT(root){try{if(!root||root.nodeType!==1)return;var ts=[];
          if(root.matches&&root.matches('table'))ts.push(root);
          var l=root.querySelectorAll?root.querySelectorAll('table'):[];
          for(var i=0;i<l.length;i++)ts.push(l[i]);
          for(var j=0;j<ts.length;j++){var t=ts[j];
            if(t.dataset&&t.dataset.fbTbl)continue;
            var s=t.innerText||'',fa=0,la=0;
            for(var k=0;k<s.length;k++){var c=s.charCodeAt(k);
              if(c>=1536&&c<=1791)fa++;else if((c>=65&&c<=90)||(c>=97&&c<=122))la++;}
            if(fa>0&&fa*2>=la){t.style.direction='rtl';t.setAttribute('dir','rtl');
              var cs=t.querySelectorAll('th,td');
              for(var m=0;m<cs.length;m++)cs[m].style.textAlign='right';}
            if(t.dataset)t.dataset.fbTbl='1';}}catch(e){}}
        function setW(){try{var r=document.documentElement;r.style.setProperty('--dk-chat-content-max-width','1200px');r.style.setProperty('--chat-content-max-width','1200px');}catch(e){}}
        function widen(){try{
          var t=document.querySelector('.workspace-transcript-content');
          if(t){t.style.width='auto';t.style.maxWidth='1200px';
                t.style.marginLeft='auto';t.style.marginRight='auto';}
        }catch(e){}}
        function lca(a,b){var s=new Set();for(var e=a;e;e=e.parentElement)s.add(e);for(var e=b;e;e=e.parentElement)if(s.has(e))return e;return null;}
        function layout(){try{
          var t=document.querySelector('.workspace-transcript-content');
          var ci=document.querySelector('.composer-input-scroll');
          if(t){t.style.width='auto';t.style.maxWidth='1200px';
                t.style.marginLeft='auto';t.style.marginRight='auto';}
          if(t&&ci){
            var p=lca(t,ci);
            if(p&&p!==document.body){
              p.style.paddingLeft='6px';p.style.paddingRight='6px';
            }
          }
        }catch(e){}}
        var FB_FAMILY = "'Vazirmatn FB'";
        function setFont(el){try{
          if(!el||el.nodeType!==1)return;
          var cur=getComputedStyle(el).fontFamily||'';
          if(cur.indexOf('Vazirmatn FB')===0)return;
          el.style.fontFamily=FB_FAMILY+(cur?', '+cur:'');
        }catch(e){}}
        function applyFonts(){try{
          setFont(document.body);
          var ls=document.querySelectorAll('.workspace-transcript-content,.composer-box,.composer-input-scroll,.msg');
          for(var i=0;i<ls.length;i++)setFont(ls[i]);
        }catch(e){}}
        function dirCount(s){var fa=0,la=0;for(var i=0;i<s.length;i++){var c=s.charCodeAt(i);if((c>=1536&&c<=1791)||(c>=1872&&c<=1919)||(c>=64336&&c<=65023))fa++;else if((c>=65&&c<=90)||(c>=97&&c<=122))la++;}return [fa,la];}
        function fixB(root){try{
          var els=root.querySelectorAll?root.querySelectorAll('li,p,blockquote,td,th'):[];
          for(var i=0;i<els.length;i++){var el=els[i];
            if(el.querySelector('li,p,table,pre'))continue;
            var t=el.textContent||'';if(t.length>4000)continue;
            var n=dirCount(t);var fa=n[0],la=n[1];
            if(fa>0&&fa*2>=la){el.setAttribute('dir','rtl');el.style.textAlign='right';setFont(el);}
            else if(la>0&&fa===0){el.setAttribute('dir','ltr');el.style.textAlign='left';}}
          var cs=root.querySelectorAll?root.querySelectorAll('pre,code,kbd,samp'):[];
          for(var j=0;j<cs.length;j++){var cf=cs[j];cf.style.direction='ltr';cf.style.unicodeBidi='isolate';cf.style.textAlign='left';}
        }catch(e){}}
                function apply(root){pad(root);fixT(root);fixB(root);setW();}
        apply(document.documentElement);
        applyFonts();
        widen();
        var n=0,iv=setInterval(function(){applyFonts();widen();layout();fixB(document);},1200);
        new MutationObserver(function(rs){for(var r=0;r<rs.length;r++){
          var a=rs[r].addedNodes;for(var n=0;n<a.length;n++)apply(a[n]);}
        }).observe(document.documentElement,{childList:true,subtree:true});
      })() } catch (e) {}
    }
    function start() {
      try {
        if (document.fonts && document.fonts.ready && document.fonts.ready.then) {
          document.fonts.ready.then(function () { addFonts(); run() })
          return
        }
      } catch (e) {}
      run()
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, { once: true })
    else start()
  } catch (e) {}
})()
""" % (",".join(fonts), js, debug)
    if os.environ.get("FB_NO_LAYOUT"):
        # A/B switch: keep direction work, drop the width/gap overrides.
        addon = addon.replace("var n=0,iv=setInterval(function(){widen();layout();fixB(document);},1200);",
                              "var n=0,iv=setInterval(function(){fixB(document);},1200);")
        addon = addon.replace("        widen();", "        ")
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
