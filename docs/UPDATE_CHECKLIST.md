# Re-applying after an update

An update replaces `resources/app.asar`, so the patch is gone. It is applied by
hand - there is no scheduled task.

```bat
cd path\to\freebuff-persian-rtl
python tools\fb_hosted_patch.py
```

Then restart Freebuff.

## What the script does

1. Copies `app.asar` to `app.asar.fb-orig` if that backup does not exist yet.
2. Reads `electron/hosted-preload.cjs` out of the asar and sets `"unpacked": true`
   on that one header entry. Offsets are relative to the data block and the block
   is copied unchanged, so nothing shifts.
3. Writes `app.asar.unpacked/electron/hosted-preload.cjs` = the original preload
   plus the JS addon: the Vazirmatn faces, the `dir="auto"` marker, the chat
   column fill, and the table and block direction rules.

Rollback: `python tools\fb_hosted_patch.py --restore`.

## Check after applying

1. Launch the app; the workspace window opens (title "Freebuff: The free coding
   agent").
2. Persian paragraphs sit on the right with a ragged left edge; Latin and code
   stay left-to-right.
3. A Persian table: first column on the right, cells right-aligned.
4. The chat column fills the pane and shrinks/expands with the side panels.
5. No red "Please allow ads on Freebuff" banner (the patch never touches ads).

## Traps

- **A failing hosted window is usually the app, not the patch.**
  `Couldn't send. Try again.`, `hosted-workspace:open` timeouts and
  `unknown certificate verification error` come from the app's own broker and
  network. A/B with `python tools\fb_hosted_patch.py --copy-only` (original
  preload) tells you whether the patch is involved.
- **DevTools is refused** (`app.exit(1)` on `--remote-debugging-port`); use the
  `FB_DEBUG_DOM` title probe described in `AGENTS.md`.
- **Do not add CSS.** `insertCSS` and injected `<style>` elements are silent
  no-ops on this page.
