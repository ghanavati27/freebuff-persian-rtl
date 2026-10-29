# freebuff-persian-rtl

Persian / RTL patch for **Freebuff Desktop 0.0.194+**.

Freebuff no longer renders its chat from files on disk: `resources/orchestrator/ui/`
is only the splash / sign-in shell, and the chat is the hosted web app opened in
its own `BrowserWindow`. This repo patches that window from its preload.

## Apply

```bat
cd C:\Users\Siroos\Hermes\freebuff-persian-rtl
python tools\fb_hosted_patch.py
```

Then restart Freebuff. Run this again after every app update (an update replaces
`resources/app.asar`, so the patch is gone).

## Roll back

```bat
python tools\fb_hosted_patch.py --restore
```

Restores `app.asar` from `app.asar.fb-orig` and deletes `app.asar.unpacked/`.

## What it does (JavaScript only)

The hosted page's CSP rejects stylesheets - `insertCSS` (author and `user`
origin) and injected `<style>` elements are all silent no-ops there - so the
patch never ships CSS. Everything is done through the DOM / CSSOM:

- `dir="auto"` on text-bearing elements (via `patch/fb-persian-rtl.js`).
- Vazirmatn registered through the `FontFace` API, scoped by `unicode-range`.
- 24 px right gutter on transcript blocks (`.msg`), matching the left gap.
- Persian-dominant tables: `direction: rtl` plus right-aligned `th` / `td`.
- The sponsored break is auto-continued once its button enables.

Ads are left untouched: the app detects hidden or collapsed ad slots.

## Files

```
patch/fb-persian-rtl.js   dir="auto" marker + sponsored-break auto-continue
patch/*.woff2             Vazirmatn (SIL Open Font License 1.1)
tools/fb_hosted_patch.py  installer / rollback for the hosted preload
tools/fb_asar.py          minimal asar reader/writer it uses
docs/FINDINGS.md          what was measured and why the CSS route is dead
docs/UPDATE_CHECKLIST.md  re-apply procedure after an app update
```
