# AGENTS.md

Guidance for AI coding agents working on this repository.

## 1. What this repo is

A runtime patch that makes Persian / Arabic render correctly in **Freebuff
Desktop**. There are two delivery paths; the app version decides which one is
live:

| Freebuff Desktop | Chat UI | Installer | Styling |
|---|---|---|---|
| 0.0.192 and older | local `resources/orchestrator/ui/` | `apply_fb_persian_patch.py` | CSS works |
| 0.0.194 and newer | hosted web app window | `tools/fb_hosted_patch.py` | JS/CSSOM only |

Always check the version first (`python apply_fb_persian_patch.py --check`
prints it). Running the wrong installer does nothing useful: 0.0.194+ never
loads `ui/` for the chat, and 0.0.192 has no `hosted-preload`.

## 2. Hard constraints

1. **CSS only works in the local UI.** The hosted page's CSP rejects
   `webFrame.insertCSS` (author and `cssOrigin:'user'`) and injected `<style>`
   elements - measured, silent no-ops. On 0.0.194+ every visual change must go
   through DOM attributes or CSSOM (`element.style.x = ...`). Do not add a
   stylesheet to the hosted path.
2. **Never touch `display` / visibility of ad slots.** The app detects hidden or
   collapsed ads and blocks with a "Please allow ads" banner; `display:none`
   and a 1 px transparent box were both caught. Ads stay as shipped.
3. **An LTR user must see the shipped layout.** `dir="auto"` on Latin content
   resolves to `ltr`; the font is scoped with `unicode-range`. The layout
   overrides (1200 px column, 30 px side gaps) are deliberate and approved.
4. **Code stays left-to-right.** Never mirror code, terminals, diffs or paths.
5. **No scheduled task.** The user runs the installer by hand after each update.
6. **Verify by measurement, not by eye.** Pixel measurement (Pillow) or a live
   DOM probe (below) is the only accepted evidence.

## 3. Where things are

| What | Where |
|---|---|
| Install root | `%LOCALAPPDATA%\Programs\@codebufffreebuff-desktop\` |
| Local UI | `resources/orchestrator/ui/` (index.html + assets) |
| Hosted UI | hosted web app in its own window (`electron/hosted-workspace.cjs`) |
| Shared sources | `patch/fb-persian-rtl.js`, `patch/*.woff2`, `patch/fb-persian-rtl.css` |

## 4. How the patch is delivered

### Local UI (0.0.192 and older)

`apply_fb_persian_patch.py` copies the CSS, the JS and the fonts into
`resources/orchestrator/ui/assets/`, then adds `<link>` and `<script>` tags to
`index.html` (original kept as `index.html.fb-persian-backup`). `--check`
reports state, `--dry-run` shows the plan, `--force` re-applies. The selectors in
`patch/fb-persian-rtl.css` must exist in the bundle; the installer verifies this
and exits 1 when some are stale. It also **blocks the auto-updater**, which otherwise
downloads the newest hosted build and installs it on quit: `app-update.yml` is
pointed at a dead feed, cached installers are deleted, and the updater's
`pending/` folder gets a deny-write ACE (`(OI)(CI)(WD,AD)`). `--allow-updates`
reverses that.

### Hosted UI (0.0.194 and newer)

`tools/fb_hosted_patch.py`:

1. Keeps `resources/app.asar.fb-orig` as the rollback copy.
2. Sets `"unpacked": true` on the single header entry
   `electron/hosted-preload.cjs`. Asar offsets are relative to the data block and
   that block is copied byte-for-byte, so no offset moves.
3. Writes `app.asar.unpacked/electron/hosted-preload.cjs` = the original preload
   plus an addon that, in JS only:
   - waits for `document.fonts.ready`, then registers its bundled Vazirmatn faces
     through `FontFace` **only if the page has none** (`document.fonts.check`),
     with the Arabic `unicode-range`. The hosted app already defines a family
     named `Vazirmatn FB`; registering a second one under the same name makes the
     browser swap between faces mid-load and Persian text looks broken;
   - sets `font-family` through CSSOM on the transcript, composer, `.msg` and
     Persian-dominant blocks (`'Vazirmatn FB'` first, the app's stack behind it,
     so Latin and code keep their own fonts);
   - runs `patch/fb-persian-rtl.js` (`dir="auto"` marker, sponsored-break
     auto-continue);
   - widens the transcript with `width:auto` + `max-width:1200px` + auto margins,
     and leaves the composer chain alone (the app keeps the two equal itself).
     **Never force `width:100%`, and never walk up the composer's ancestors
     setting widths**: the chat pane is a flex layout, and a forced width stops it
     shrinking when the right panel opens, so the panel then paints over the chat
     instead of narrowing it (measured on 0.0.196);
   - adds 6 px left/right padding on the lowest common ancestor of transcript and
     composer; the pane already insets 24 px, so the measured gap is 30 px on each
     side;
   - sets `style.marginRight = '24px'` on `.msg` blocks;
   - sets `direction: rtl` and right-aligned cells on Persian-dominant tables;
   - sets `dir`/`text-align` on Persian-dominant blocks (`li`, `p`, `blockquote`,
     `th`, `td`) so a leading checkbox or icon moves to the right edge, and
     pins `pre`/`code` to LTR.

Rollback: `python tools\fb_hosted_patch.py --restore`.

## 5. Re-applying after an update

An update replaces the UI, so the patch is gone. Check the version, then run the
matching installer and restart the app:

```bat
python apply_fb_persian_patch.py --check
python apply_fb_persian_patch.py          :: 0.0.192 and older
python tools\fb_hosted_patch.py           :: 0.0.194 and newer
```

See `docs/UPDATE_CHECKLIST.md`.

## 6. Live DOM probes (hosted path)

DevTools is not available: the app calls `app.exit(1)` on
`--remote-debugging-port`, and the fuses block `--inspect` / `NODE_OPTIONS
--require`. The preload is the only injection point, so add a temporary block
under `FB_DEBUG_DOM` in `tools/fb_hosted_patch.py` that writes what you need into
`document.title`, then read the window title:

```powershell
Get-Process Freebuff | Where-Object MainWindowTitle | Select-Object -ExpandProperty MainWindowTitle
```

This is how the 720 px transcript cap and the 610 px composer column were found.
Remove the probe before the final build; it changes the window title. On the
local UI this is unnecessary - the page has no CSP, so the CSS itself applies.

## 7. Verification

- Local UI: the installer's own check (every selector present in the bundle),
  plus a screenshot for direction and the 1200 px column.
- Hosted UI: pixel measurement with Pillow against a screenshot - Persian
  paragraphs with a constant right edge and ragged left, Persian tables
  right-aligned, chat column ~1200 px with the composer matching it, 30 px gaps,
  and no red "allow ads" banner.

## 8. Known dead ends

- **CSS on the hosted page** - blocked by CSP, as above. Do not add a stylesheet
  to that path.
- **Width via CSS variables on the hosted page** - `--dk-chat-content-max-width`
  has no effect there: the transcript is hard-coded to `width: 720px` with
  `max-width: none`.
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
- **Re-registering a font family the page already defines** - the hosted app
  ships `Vazirmatn FB` itself; adding a second face with that name makes the
  browser swap between them while they load. Check `document.fonts.check` first.
- **Forcing widths on the hosted layout** - `width:100%` on
  `.workspace-transcript-content`, or on any ancestor of `.composer-box`, breaks
  the flex shrink: opening the right panel overlays the chat. Only `width:auto`
  plus `max-width` is safe. `FB_NO_LAYOUT=1 python toolsb_hosted_patch.py`
  builds the direction-only variant used to prove which half was at fault.
