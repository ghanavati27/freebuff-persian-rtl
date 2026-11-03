# freebuff-persian-rtl

Persian / RTL patch for the **hosted build of Freebuff Desktop**, where the chat
runs as a web app in its own window and the local `ui/` folder is only the splash.

## Apply

```bat
python tools\fb_hosted_patch.py
```

Then restart Freebuff. Run it again after every app update - an update replaces
`resources/app.asar` and the patch goes with it.

## Roll back

```bat
python tools\fb_hosted_patch.py --restore
```

## What it does

Everything is JavaScript, injected into the workspace preload. The hosted page's
CSP rejects stylesheets (`insertCSS` and injected `<style>` elements are silent
no-ops there), so this repo ships no CSS at all:

- `dir="auto"` on text, and `dir` / `text-align` on Persian-dominant blocks
  (`li`, `p`, `blockquote`, `th`, `td`) so a leading checkbox or icon lands on
  the right; `pre` / `code` are pinned back to left-to-right.
- Persian-dominant tables get `direction: rtl` with right-aligned cells; Latin
  tables are left untouched.
- Vazirmatn through the `FontFace` API, scoped with `unicode-range` so Latin and
  code keep the app's own fonts. The bundled faces are registered only when the
  page has none of its own, and only after `document.fonts.ready`.
- The chat column fills the pane and follows the side panels: `width:auto` with a
  symmetric 24 px margin, never a forced width.
- The sponsored break is auto-continued once its button enables.

Ads are never touched: the app detects hidden or collapsed ad slots and blocks
with a "Please allow ads" banner.

## Diagnostics

```bat
set FB_DEBUG_DOM=1
python tools\fb_hosted_patch.py
```

builds a variant that reports live DOM measurements in the window title; rebuild
without the variable when you are done.

## Files

```
patch/fb-persian-rtl.js   dir="auto" marker + sponsored-break auto-continue
patch/*.woff2             Vazirmatn (SIL Open Font License 1.1)
tools/fb_hosted_patch.py  installer / rollback for the hosted preload
tools/fb_asar.py          minimal asar reader/writer it uses
docs/FINDINGS.md          measurements behind the patch
docs/UPDATE_CHECKLIST.md  re-apply procedure after an app update
```
