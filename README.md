# freebuff-persian-rtl

Persian / RTL patch for Freebuff Desktop. Two delivery paths, picked by the app
version - check which one you have before running anything.

| Freebuff Desktop | UI lives in | Use |
|---|---|---|
| 0.0.192 and older | local files, `resources/orchestrator/ui/` | `apply_fb_persian_patch.py` |
| 0.0.194 and newer | hosted web app in its own window | `tools/fb_hosted_patch.py` |

How to tell: `python apply_fb_persian_patch.py --check` prints the installed
version. 0.0.194+ has `resources/app.asar.unpacked/electron/hosted-preload.cjs`
(the hosted shell), and its window title is "Freebuff: The free coding agent".

## Old UI (0.0.192 and older) - CSS + JS

```bat
cd C:\Users\Siroos\Hermes\freebuff-persian-rtl
python apply_fb_persian_patch.py
```

Copies `patch/fb-persian-rtl.css`, `patch/fb-persian-rtl.js` and the Vazirmatn
fonts into `resources/orchestrator/ui/assets/`, then adds the two tags to
`index.html` (original kept as `index.html.fb-persian-backup`). `--check` reports
state, `--dry-run` shows the plan, `--force` re-applies.

Here CSS works: the local renderer has no CSP, so direction rules, the 1200 px
chat column, list and table alignment are all stylesheet rules.

## Hosted UI (0.0.194 and newer) - JavaScript only

```bat
python tools\fb_hosted_patch.py
```

Marks `electron/hosted-preload.cjs` as unpacked in `app.asar` and writes a
patched copy of that preload. The hosted page's CSP rejects `insertCSS` (author
and `user` origin) and injected `<style>` elements, so there is no stylesheet at
all there: direction, font, layout and table alignment are done through the DOM
and CSSOM.

Rollback: `python tools\fb_hosted_patch.py --restore`.

## What the patch does

- `dir="auto"` on text-bearing elements, so Persian reads right-to-left and Latin
  stays left-to-right.
- `dir` / `text-align` on Persian-dominant blocks (`li`, `p`, `blockquote`,
  `th`, `td`) so a leading checkbox or icon sits on the right; `pre` / `code`
  stay LTR.
- Persian-dominant tables right-aligned; Latin tables untouched.
- Vazirmatn, scoped to the Arabic Unicode ranges so Latin keeps the app font.
- 1200 px chat column with the composer matched to it, 30 px gap on each side
  (hosted path).
- The sponsored break is auto-continued once its button enables.

Ads are never touched: the app detects hidden or collapsed ad slots and blocks
with a "Please allow ads" banner.

## Files

```
apply_fb_persian_patch.py   installer for the local UI (0.0.192 and older)
patch/fb-persian-rtl.css    stylesheet for the local UI
patch/fb-persian-rtl.js     dir="auto" marker + sponsored-break auto-continue (both paths)
patch/*.woff2               Vazirmatn (SIL Open Font License 1.1)
tools/fb_hosted_patch.py    installer / rollback for the hosted preload
tools/fb_asar.py            minimal asar reader/writer it uses
docs/FINDINGS.md            measurements and the CSP finding
docs/UPDATE_CHECKLIST.md    re-apply procedure after an app update
```
