# AGENTS.md

Guidance for AI coding agents working on this repository.

## 1. What this repo is

A runtime patch that makes Persian / Arabic render correctly in the **hosted
build of Freebuff Desktop**. The chat is a web app opened in its own
`BrowserWindow`; it is not rendered from `resources/orchestrator/ui/`, which is
only the splash. The patch lives in that window's preload, so nothing here is
built or forked.

## 2. Hard constraints

1. **No CSS.** The hosted page's CSP rejects `webFrame.insertCSS` (author and
   `cssOrigin:'user'`) and injected `<style>` elements - measured, silent no-ops.
   Every visual change goes through DOM attributes or CSSOM
   (`element.style.x = ...`). Do not add a stylesheet.
2. **Never touch `display` / visibility of ad slots.** The app detects hidden or
   collapsed ads and blocks with a "Please allow ads" banner; `display:none` and
   a 1 px transparent box were both caught. Ads stay as shipped.
3. **An LTR user must see the shipped layout.** `dir="auto"` on Latin text
   resolves to `ltr`, and the font is scoped with `unicode-range`.
4. **Code stays left-to-right.** Never mirror code, terminals, diffs or paths.
5. **No scheduled task.** The installer is run by hand after each update.
6. **Verify by measurement, not by eye.** Pixel measurement (Pillow) or a live
   DOM probe (below) is the only accepted evidence.

## 3. Where things are

| What | Where |
|---|---|
| Install root | `%LOCALAPPDATA%\Programs\@codebufffreebuff-desktop\` |
| Chat UI | hosted web app in its own window (`electron/hosted-workspace.cjs`) |
| Patch point | `resources/app.asar` -> `electron/hosted-preload.cjs` |
| Patch sources | `patch/fb-persian-rtl.js`, `patch/*.woff2` |

## 4. How the patch is delivered

`tools/fb_hosted_patch.py`:

1. Keeps `resources/app.asar.fb-orig` as the rollback copy.
2. Sets `"unpacked": true` on the single header entry
   `electron/hosted-preload.cjs`. Offsets are relative to the data block and that
   block is copied byte-for-byte, so no offset moves.
3. Writes `app.asar.unpacked/electron/hosted-preload.cjs` = the original preload
   plus an addon that, in JS only:
   - waits for `document.fonts.ready`, then registers the bundled Vazirmatn faces
     through `FontFace` **only if the page has none** (`document.fonts.check`),
     with the Arabic `unicode-range`. The page already defines a family named
     `Vazirmatn FB`; registering a second one under the same name makes the
     browser swap between faces mid-load and Persian looks broken;
   - sets `font-family` through CSSOM on the transcript, composer, `.msg` and
     Persian-dominant blocks (`'Vazirmatn FB'` first, the app's stack behind it,
     so Latin and code keep their own fonts);
   - runs `patch/fb-persian-rtl.js` (`dir="auto"` marker, sponsored-break
     auto-continue);
   - fills the chat column **only when a transcript exists** (a new chat tab has
     no transcript and its composer is laid out differently - forcing
     `width:auto` there collapses the input to a few pixels, so the overrides are
     removed in that state): `width:auto` + `max-width:none` + a symmetric 24 px
     margin on `.workspace-transcript-content`, and `width:auto` on
     `.composer-box` / `.composer.workspace-composer`. The transcript is pinned
     to a fixed width and pushed right by a computed gutter margin, which is why
     it needs both overrides. **`auto`, never a fixed width or a forced
     percentage**: the pane is a flex layout, and a forced width stops it
     shrinking when a side panel opens, so the panel then paints over the chat;
   - sets `style.marginRight = '24px'` on `.msg` blocks;
   - sets `direction: rtl` and right-aligned cells on Persian-dominant tables;
   - sets `dir`/`text-align` on Persian-dominant blocks (`li`, `p`, `blockquote`,
     `th`, `td`) so a leading checkbox or icon moves to the right edge, and pins
     `pre`/`code` to LTR.

Rollback: `python tools\fb_hosted_patch.py --restore`.

## 5. Re-applying after an update

An update replaces `app.asar`, so the patch is gone:

```bat
python tools\fb_hosted_patch.py
```

Then restart the app. See `docs/UPDATE_CHECKLIST.md`.

## 6. Live DOM probes

DevTools is not available: the app exits on `--remote-debugging-port`, and the
fuses block `--inspect` / `NODE_OPTIONS --require`. The preload is the only
injection point, so add a temporary block under `FB_DEBUG_DOM` in
`tools/fb_hosted_patch.py` that writes what you need into `document.title`, then
read the window title:

```powershell
Get-Process Freebuff | Where-Object MainWindowTitle | Select-Object -ExpandProperty MainWindowTitle
```

This is how the fixed transcript width (and its computed gutter margin) and the
composer's column were measured. Remove the probe before the final build; it
changes the window title.

## 7. Verification

Pixel measurement with Pillow against a screenshot: Persian paragraphs with a
constant right edge and a ragged left, Persian tables right-aligned, the chat
column filling the pane and following the side panels, and no red "allow ads"
banner.

## 8. Known dead ends

- **CSS** - blocked by CSP; see constraint 1.
- **Width through CSS variables** - `--dk-chat-content-max-width` has no effect:
  the transcript carries a fixed width and a computed gutter margin.
- **Forcing widths** - a fixed width or a forced percentage on the transcript or
  on any ancestor of `.composer-box` breaks the flex shrink, so opening a side
  panel overlays the chat. Only `width:auto` is safe.
- **Re-registering a font family the page already defines** - check
  `document.fonts.check` first, or the browser swaps faces mid-load.
- **To-do dock** - unreachable in this build: `orchestrator.js` only adds
  `write_todos` when `!options.workspace`, and the Claude path disallows
  `TodoWrite`. The model can only write a Markdown checklist.
- **`.prose` / `hr` selectors** - the chat has neither; it uses `.msg` blocks and
  Tailwind classes.
- **Ad hiding** - detected; see constraint 2.
- **React and inline styles** - React re-renders the composer subtree and drops
  inline styles, so the writes are repeated on a 1.2 s tick. Do not "optimise"
  that away without re-testing.
