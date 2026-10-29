# tools

## `tools/fb_hosted_patch.py`

The installer for the hosted chat window (0.0.194+).

```bat
python tools\fb_hosted_patch.py            # apply / re-apply
python tools\fb_hosted_patch.py --check    # report state, change nothing
python tools\fb_hosted_patch.py --copy-only# unpacked check with the original preload
python tools\fb_hosted_patch.py --restore  # rollback
```

It marks `electron/hosted-preload.cjs` as `unpacked` in `app.asar` and writes an
unpacked copy of that preload with the JS patch appended: Vazirmatn via the
`FontFace` API, the `dir="auto"` marker from `patch/fb-persian-rtl.js`, the 24 px
`.msg` right gutter and Persian-table alignment.

There is no CSS on purpose: the hosted page's CSP rejects `insertCSS` (author and
user origin) and injected `<style>` elements, so a stylesheet never applies. If
you need a visual change, do it through DOM attributes or CSSOM.

Debugging: set `FB_DEBUG_TITLE=1` when running the script to have the hosted
window show `FB-RTL n=<marked elements>` in its title.

## `tools/fb_asar.py`

A minimal asar reader/writer used by the installer: parse the header, read a
file, and repack the header while keeping the data block byte-identical.

## Removed

The old harnesses (`verify_chat_width.py`, `verify_ads_hidden.py`,
`verify_break_autocontinue.py`, `measure_ink.py`, `check_dependencies.py`,
`scan_text_surfaces.py`) and `apply_fb_persian_patch.py` targeted the local
`ui/` renderer, which no longer hosts the chat. They were deleted rather than
left to rot.
