# tools

## `tools/fb_hosted_patch.py`

The installer for the hosted chat window.

```bat
python tools\fb_hosted_patch.py            # apply / re-apply
python tools\fb_hosted_patch.py --check    # report state, change nothing
python tools\fb_hosted_patch.py --copy-only# unpacked check with the original preload
python tools\fb_hosted_patch.py --restore  # rollback
```

It marks `electron/hosted-preload.cjs` as `unpacked` in `app.asar` and writes an
unpacked copy of that preload with the JS patch appended: the Vazirmatn faces
(registered only when the page has none, after `document.fonts.ready`), the
`dir="auto"` marker from `patch/fb-persian-rtl.js`, the chat-column fill, and the
table and block direction rules.

There is no CSS on purpose: the page's CSP rejects `insertCSS` and injected
`<style>` elements, so a stylesheet never applies. Visual changes go through DOM
attributes or CSSOM.

Debugging: `FB_DEBUG_DOM=1` makes the built preload report live DOM measurements
in the window title. Rebuild without it when you are done - it changes the title.

## `tools/fb_asar.py`

A minimal asar reader/writer used by the installer: parse the header (including
the padding that precedes the data block), read a file, and repack the header
while keeping the data block byte-identical.
