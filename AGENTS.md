# AGENTS.md

Guidance for AI coding agents working on this repository.

## 1. What this repo is

A runtime patch that makes Persian / Arabic render correctly in **Freebuff
Desktop 0.0.194 and later**.

Since 0.0.194 the chat is **not** local: `resources/orchestrator/ui/` is the
splash / sign-in shell only, and the real UI is the hosted web app
(`freebuff.com` or a staging origin) opened in its own `BrowserWindow` with
`electron/hosted-preload.cjs`. The patch lives in that preload.

There is nothing to build and nothing to fork.

## 2. Hard constraints

1. **No CSS. The hosted page's CSP rejects it.** Measured: `webFrame.insertCSS`
   (author and `cssOrigin:'user'`) returns without throwing and changes nothing,
   and an injected `<style>` element is parsed but its rules never apply. Any
   visual change must be made through DOM attributes or CSSOM
   (`element.style.x = ...`), which CSP does not block.
2. **Never touch `display` / visibility of ad slots.** The app detects hidden or
   collapsed ads and blocks with a "Please allow ads" banner; `display:none`
   and a 1 px transparent box were both caught. Ads stay as shipped.
3. **An LTR user must see the shipped layout.** `dir="auto"` on Latin content
   resolves to `ltr`; the font is scoped with `unicode-range`. The layout
   overrides (1200 px column, 24 px side gaps) are deliberate and approved.
4. **Code stays left-to-right.** Never mirror code, terminals, diffs or paths.
5. **No scheduled task.** The user runs `tools/fb_hosted_patch.py` by hand after
   each update.
6. **Verify by measurement, not by eye.** Pixel measurement (Pillow) or a live
   DOM probe (below) is the only accepted evidence.

## 3. Where things are

| What | Where |
|---|---|
| Install root | `%LOCALAPPDATA%\Programs\@codebufffreebuff-desktop\` |
| Chat UI | hosted web app in its own window (`hosted-workspace.cjs`) |
| Preload patched | `resources/app.asar` -> `electron/hosted-preload.cjs` |
| Patch sources | `patch/fb-persian-rtl.js`, `patch/*.woff2` |
| Installer | `tools/fb_hosted_patch.py` (+ `tools/fb_asar.py`) |

## 4. How the patch is delivered

`tools/fb_hosted_patch.py`:

1. Keeps `resources/app.asar.fb-orig` as the rollback copy.
2. Sets `"unpacked": true` on the single header entry
   `electron/hosted-preload.cjs`. Asar offsets are relative to the data block and
   that block is copied byte-for-byte, so no offset moves.
3. Writes `app.asar.unpacked/electron/hosted-preload.cjs` = the original preload
   plus an addon that, in JS only:
   - registers Vazirmatn through `FontFace` (binary source, so CSP cannot block a
     font fetch) with the Arabic `unicode-range`;
   - runs `patch/fb-persian-rtl.js` (`dir="auto"` marker, sponsored-break
     auto-continue);
   - widens the transcript (`width:100%`, `max-width:1200px`, auto margins) and
     matches the composer to it by climbing from `.composer-box` to the first
     ancestor at least 900 px wide;
   - puts 24 px left/right padding on the lowest common ancestor of transcript
     and composer (sidebar gap and right gap);
   - sets `style.marginRight = '24px'` on `.msg` blocks;
   - sets `direction: rtl` and right-aligned cells on Persian-dominant tables.

Rollback: `python tools\fb_hosted_patch.py --restore`.

## 5. Re-applying after an update

An update replaces `app.asar`, so the patch is gone.

```bat
python tools\fb_hosted_patch.py
```

Then restart Freebuff. See `docs/UPDATE_CHECKLIST.md`.

## 6. Live DOM probes

DevTools is not available: the app calls `app.exit(1)` on
`--remote-debugging-port`, and the fuses block `--inspect` / `NODE_OPTIONS
--require`. The preload is the only injection point, so add a temporary block
under `FB_DEBUG_DOM` in `tools/fb_hosted_patch.py` that writes what you need into
`document.title`, then read the window title:

```powershell
Get-Process Freebuff | Where-Object MainWindowTitle | Select-Object -ExpandProperty MainWindowTitle
```

This is how the 720 px transcript cap and the 610 px composer column were found.
Remove the probe before the final build; it changes the window title.

## 7. Verification

Pixel measurement with Pillow against a screenshot of the hosted window:

- Persian paragraphs: constant right edge, ragged left.
- Tables: Persian-dominant tables right-aligned; Latin tables unchanged.
- Chat column ~1200 px wide, composer the same width, ~24 px gaps on both sides.
- No red "allow ads" banner (ads untouched).

## 8. Known dead ends

- **CSS** - blocked by CSP, as above. Do not reintroduce a stylesheet.
- **Width via CSS variables** - `--dk-chat-content-max-width` has no effect: the
  transcript is hard-coded to `width: 720px` with `max-width: none`.
- **To-do dock** - unreachable in hosted mode: `orchestrator.js` only adds
  `write_todos` when `!options.workspace`, and the Claude path has
  `CLAUDE_DISALLOWED_TOOLS = ["TodoWrite"]`. The model can only write a
  Markdown checklist.
- **`.prose` / `hr` selectors** - the hosted chat has neither; it uses `.msg`
  blocks and Tailwind classes.
- **Ad hiding** - detected; see constraint 2.
- **React and inline styles** - React re-renders the composer subtree and drops
  inline styles, so the layout writes are repeated on a 1.2 s tick. Do not
  "optimise" that away without re-testing.
