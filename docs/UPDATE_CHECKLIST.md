# Re-applying after a Freebuff update

An update replaces `resources/app.asar`, so the patch is gone. Run this by hand -
there is no scheduled task.

```bat
cd C:\Users\Siroos\Hermes\freebuff-persian-rtl
python tools\fb_hosted_patch.py
```

Then restart Freebuff Desktop.

## What the script does

1. Copies `app.asar` to `app.asar.fb-orig` if that backup does not exist yet.
2. Reads `electron/hosted-preload.cjs` out of the asar and sets `"unpacked": true`
   on that one header entry. Offsets are relative to the data block, and the data
   block is copied unchanged, so nothing shifts.
3. Writes `app.asar.unpacked/electron/hosted-preload.cjs` = the original preload
   plus the JS addon: Vazirmatn via `FontFace`, the `dir="auto"` marker from
   `patch/fb-persian-rtl.js`, the 24 px `.msg` right gutter and the Persian-table
   alignment.

Rollback: `python tools\fb_hosted_patch.py --restore`.

## Check after applying

1. Launch the app; the hosted window must open (title "Freebuff: The free coding
   agent", not the local "Freebuff Desktop" splash).
2. Persian paragraphs: right-aligned.
3. A Persian table: first column on the right, cells right-aligned.
4. Transcript blocks stop before the window's right edge.
5. No red "Please allow ads on Freebuff" banner (the patch never touches ads).

## Traps

- `--remote-debugging-port` is refused (`app.exit(1)`), and the fuses keep
  `--inspect` / `NODE_OPTIONS --require` from being useful. Do not plan on
  DevTools injection; use a temporary `document.title` marker from the preload if
  you need to observe the live DOM.
- The hosted window intermittently fails to open with
  `unknown certificate verification error` (status 400/409). That is the app's
  local broker; restart Freebuff.
- Do not add CSS. The hosted page's CSP rejects `insertCSS` and injected
  `<style>` elements, so a stylesheet is a silent no-op there. Use DOM / CSSOM.
