# Findings

Every claim below was verified by pixel measurement (Pillow) against real app
screenshots, not by visual inspection. Screenshot series are referenced by their
file names as captured during development.

**App under test:** Freebuff Desktop 0.0.173 (Electron), UI served from disk at
`resources/orchestrator/ui/`.

---

## What was broken (before the patch)

Measured on the original UI:

| Surface | Measurement | Verdict |
|---|---|---|
| Chat transcript | 15 text lines, left margin 15–25 px, right margin jagged | every line **left-aligned** — RTL broken |
| Mixed Persian + English | word order scrambled within a line | unreadable |
| Question dock | options left-aligned, checkbox column on the left | broken for RTL |
| To-do dock | marks in a column on the left | broken for RTL |
| Reasoning preview | text stranded at the far right edge | wrong side |
| Code inside Persian content | mirrored | broken |

## What is fixed (after the patch)

| Surface | Evidence | Verdict |
|---|---|---|
| User's own message | 10/10 lines end at `x=760` (constant right edge, 160 px margin) | right-aligned |
| Model answers | Persian paragraphs end at a constant right edge | right-aligned |
| English reasoning + numbered list | left edge constant at `x=92` | unchanged, left-aligned |
| Question dock (single + multi-select) | Persian options right-aligned; checkboxes in one unified right column | fixed |
| To-do dock | all marks in one column at `x=715..727`; Latin-first items also right-aligned | fixed |
| Reasoning (thinking) | Persian reasoning RTL; English reasoning LTR; preview sits next to "Thinking" | fixed |
| Numbered list markers | all markers in one column at `x=788..792`, right of the text | fixed |
| Markdown table (English) | header not mirrored; columns share a constant left edge | unchanged |
| Code blocks | header `language` left, `Copy` right; body constant left edge (`x=88`, `x=46`) | LTR, not mirrored |
| Code inside Persian list/blockquote | guarded to `direction: ltr` | LTR |
| File-change summary row | spans `x=47..722`, icon at the left, "1 file changed", "+5", chevron at the right | unchanged (app chrome) |
| Diff view (tool call) | 25,046 green px + 12,886 red px in rows 405–485; line left edge constant at `x=46..47` | colored, LTR, Persian line readable |

## The LTR guarantee

Rendered three Latin-only pages (chat, reasoning, table) with and without the
patch and compared them:

```
PIL.ImageChops.difference(control, patched).getbbox()  ->  None
```

**Zero differing pixels.** An English-speaking user sees the shipped UI exactly.

## Surfaces covered

- chat transcript: paragraphs, headings, lists (bullet + numbered), blockquotes,
  tables, code blocks, inline code
- the user's own message bubble
- composer / input box
- agent question dock (single-select, multi-select, free text)
- to-do dock
- model reasoning (collapsed and expanded), tool-call rows and command output
- file-change summary row and the diff view
- queued prompts

## Known non-goals

- **App chrome stays English.** Headers, labels and buttons are the app's own
  strings and are deliberately left alone. The patch only changes direction and
  geometry, never text.
- **`.question-chip` tag and `.qbody` panel rows** remain left-aligned: their
  text is an unnamed flex child, so no CSS rule can reach it without an
  unkeyed rule that would also hit English rows.
- **Model reasoning sometimes comes back in English regardless of a Persian
  prompt.** That is model behaviour, not a rendering bug.
- **Bundle class names are a moving target.** They are re-derived after every
  update; see `docs/UPDATE_CHECKLIST.md`.

## False positives rejected during verification

A vision model's "looks correct" was wrong on this UI several times. Each was
refuted by measurement, and the measurement is what stands:

- "the checkbox column moved" — it had not; the rows were never marked.
- "the table header is mirrored" — the header's left edges were constant.
- "Persian line spacing is too tight, lines nearly touch" — measured gap is
  ~7 px, identical to the Latin leading at the same pitch.
- "the code block lost its header" — the header was present, oriented LTR.

Record a contradiction like this in the same format rather than repeating the
claim.

## Update log

### 0.0.174
- App updated; bundle renamed (`index-B6bNCncr.js` / `index-9qF84wBi.css`). The
  installer reads the bundle names out of `index.html`, so no script change was
  needed.
- New `ui/fonts/` (Google Sans, DM Mono, Outfit now bundled locally, previously
  a CDN) and `ui/wallpapers/` - no impact on the patch.
- All 71 previous selectors still present; 3 added (`.msg-verdict-note`,
  `.intermission-headline`, `.intermission-subhead`). Health check 74/74.
- Scanned all 92 uncovered classes that carry text directly: the rest are
  English app chrome and deliberately left alone.

### 0.0.176
- App updated; bundle renamed (`index-tvbzIkU3.js` / `index-00nrfH8Q.css`).
- All 74 selectors still present - **no patch change needed**. Patch re-applied,
  `index.html` re-tagged (backup refreshed), health check 74/74.
- Bundle scan found 94 uncovered classes carrying text directly; all are English
  app chrome (crash notice, file-viewer hints, model picker, sponsored-offer
  status). None carry user or model text, so none were added.

### 0.0.179
- App updated; bundle renamed (`index-0IEXXOd1.js` / `index-Dp2LqzE9.css`).
- All 74 selectors still present - **no patch change needed**. Patch re-applied,
  `index.html` re-tagged (backup refreshed), health check 74/74.
- Bundle scan: 101 uncovered classes carrying text directly (up from 94). The 7
  new ones (`.freebucks-intro-price-heading`, `.profile-survey-*`,
  `.workspace-codebase-*`) are English app chrome - a rewards/survey permission
  flow and a project picker. None carry user or model text, so none were added.

### 0.0.180
- App updated; bundle renamed (`index-MhrKAKLz.js` / `index-3Ukgm2iF.css`).
- **Installer fix.** `index.html` now references the bundle with an *absolute*
  prefix (`/assets/...`) instead of the old relative `./assets/...`, and the
  bundle `<script>` now precedes the `<link>`. The old `LINK_RE`/`SCRIPT_RE`
  required `./assets/` and the injection anchor searched for
  `href="./assets/index-`, so the run exited 2 after copying the assets but
  before tagging `index.html` - i.e. a silently inactive patch.
  Now: the regexes accept any prefix, `asset_prefix()` reads the bundle's own
  prefix and `bundle_tags()` copies it onto the patch's tags, and the insertion
  point is whichever of the bundle's `<script>`/`<link>` ends later (falling
  back to `</head>`). The prefix is a correctness issue, not cosmetics: the SPA
  server answers any extensionless path with this document, so a relative href
  on a deep path would 404.
- All 74 selectors still present - no selector change needed.
- Injected tags now land as `/assets/fb-persian-rtl.{css,js}` on lines 217-218,
  after the bundle's `<link>` on line 216, so the patch CSS still wins the
  cascade.
- Bundle scan: 102 uncovered classes carrying text directly. The one new class
  (`.side-chat-note`, "Stopped.") is English app chrome; nothing was added.

### 0.0.182
- App updated; JS bundle renamed to `index-8p4WIDGg.js` (CSS unchanged at
  `index-3Ukgm2iF.css`).
- All 74 selectors still present - **no patch change needed**. Patch re-applied
  with the fixed installer: `/assets/` prefix picked up automatically, tags
  injected on lines 217-218 after the bundle's `<link>` on 216, fresh backup
  written. Health check 74/74, exit 0.
- Bundle scan: 102 uncovered classes carrying text directly - **0 added, 0
  removed** versus 0.0.180. The surface is stable between these two releases.

## Chat width (layout section 5) - added while on 0.0.182

The shipped UI caps the transcript with one custom property,
`--chat-content-max-width: 720px`, defined in the app's own `:root` next to
`--explorer-width: 440px`. Every consumer wraps it in `min()`/`calc()` against
`100%` - the live centre column, i.e. the window minus whichever panels are open
- so the empty band either side was one property's doing, and one override
reclaims it, responsively, with no media query and no JS.

Verified with `tools/verify_chat_width.py` (Selenium + Pillow), 4 window widths x
4 panel states, stock vs patched. DOM geometry at device scale 1:

| panels | viewport | centre | stock | patched | gutter |
|---|---|---|---|---|---|
| both-open | 1264 | 608 | 544 | 544 | 32 |
| both-open | 1584 | 928 | 720 | 864 | 32 |
| both-open | 1904 | 1248 | 720 | 1184 | 32 |
| both-open | 2544 | 1888 | 720 | 1200 | 344 |
| right-closed | 1584 | 1368 | 720 | 1200 | 84 |
| left-closed | 1904 | 1464 | 720 | 1200 | 132 |
| both-closed | 1264 | 1264 | 720 | 1200 | 32 |
| both-closed | 2544 | 2544 | 720 | 1200 | 672 |

In all 16 combinations the patched transcript equals the `.messages` content box
(no inner gap left) and `--chat-content-max-width` resolves to
`min(100%, 1200px)`. Pixel cross-check over the transcript band, both panels
open: ink span **704px (stock) -> 1177px (patched)** at both 1920 and 2560.

Where the centre column is narrower than 720px (both-open @1264 -> 608px) there
is nothing to reclaim, so patched equals stock. That is expected, not a failure -
and it is why the harness asserts widening only where the column exceeds the
shipped cap.

**Trap.** `.prose{max-width:860px;margin:0 auto}` re-caps the text *inside* the
column. Widening the column alone moves the gap inward instead of removing it,
so the transcript's `.prose` is uncapped as well. The file-preview variant
(`.file-markdown-content > .prose`) is a different surface and is not touched.

## Ad surfaces hidden (section 6) - added while on 0.0.182

The banner above the composer is `.sponsored-ad.ad-banner`, rendered by the app's
own React code. The class is built at runtime - `className: \`sponsored-ad
ad-${t}\`` with `t="banner"` - so grepping the bundle for the literal
`"ad-banner"` finds only the app's own telemetry selector, never a `className`.
That initially looked like server-side injection; it is not.

The banner has no dismiss control of its own, which is why it is always present.

### The hazard: .sponsor-intermission is a blocking modal

Before hiding any surface, check whether it can trap the user. This one can:

- `role="dialog" aria-modal="true" aria-label="Sponsored break"`
- its only exits are its own buttons - `intermission-continue` ("Continue
  working") and `spotlight-close` ("Close sponsor break")
- the close button is suppressed while the break is busy (`n ? null : ...`)
- `aqe = 30 * 6e4` - a 30-minute constant near that component

Hiding it would leave the app waiting on a click that can never happen. It is
**not** hidden, and `tools/verify_ads_hidden.py` asserts it stays visible.

### What is hidden, and why each is safe

| Selector | Stock render | Patched | Safety |
|---|---|---|---|
| `.sponsored-ad.ad-banner` | `flex 720x60` | `none 0x0` | no modal role, no dismiss |
| `.ad-showcase` | `block 720x170` | `none 0x0` | no modal role |
| `.sponsored-proposal` | `flex 720x48` | `none 0x0` | `<section aria-label="Sponsored proposal">`, has Minimize/Dismiss |
| `.placement-sidebar-card` | `block 320x240` | `none 0x0` | has its own dismiss |

Scope guard, same run: `.sponsor-intermission` measured `flex 1x849` both before
and after - untouched.

### Telemetry consequence, stated plainly

The app's own telemetry reads `.sponsored-ad.ad-banner, .ad-showcase` and
measures `getBoundingClientRect()` to report ad viewability. A hidden element
measures 0x0, so it is reported as **never in the viewport**. That is the
truthful consequence of hiding it. No non-zero box is faked to manufacture a
"viewed" signal - that would be fabricating ad impressions.

### Sponsored break: auto-continued, not hidden

Hiding `.sponsor-intermission` is not an option - it is a blocking modal and the
user would have no way out. It is instead auto-continued from the runtime half of
the patch: click `.intermission-continue` as soon as it stops being disabled.

Two bundle details decided this:

1. **The impression pixel fires on click, not on render.** The ad's own click
   handler is

   ```js
   const O = useCallback(() => {
     mL(l6, {dwellMs, timerMs: n, timerCompleted: tk(a, n, qa()), clientEventId: ...});
     t.impUrl && Px(t.impUrl, void 0, {provider, surface, placementId});
     nk("click");
   }, [t.impUrl, e, a, n]);
   ```

   so dismissing the break by clicking Continue fires no ad event - and, by the
   same token, hiding the break would not have produced a false impression either.
   The only thing hiding it would produce is a stuck app.

2. **The countdown length is not recoverable from the bundle.** The component
   takes `done` / `progress`, the Continue button is `disabled` while the
   countdown runs and `.spotlight-close` is not rendered at all during it - but
   the timer's duration lives outside what could be traced with confidence. The
   watcher therefore polls (500ms) instead of using a fixed timeout, and only
   while a break is on screen.

Verified by `tools/verify_break_autocontinue.py`:

| Phase | Expected | Measured |
|---|---|---|
| button disabled | 0 clicks | 0 |
| button enabled | exactly 1 click | 1 |
| further polling | still 1 | 1 |
| a fresh break | picked up and clicked | 2 total |

The JS half now carries this second, non-RTL job; the stylesheet deliberately
does not hide the modal, and `tools/verify_ads_hidden.py` asserts that.

### 0.0.183
- App updated; bundle renamed (`index-Dy3ub5tq.js` / `index-0QscbrWU.css`).
- All 83 selectors + 1 overridden property still present - **no patch change
  needed**. Patch re-applied, `index.html` re-tagged on lines 217-218, fresh
  backup written. Health check 83/83, exit 0.
- All three acceptance harnesses re-run against the new bundle and passing:
  - `verify_ads_hidden.py` - 4 ad surfaces hidden, `.sponsor-intermission`
    scope guard still visible (`flex 1x849` both).
  - `verify_break_autocontinue.py` - 0 clicks while disabled, exactly 1 once
    enabled, no repeats, a fresh break picked up.
  - `verify_chat_width.py` - 16/16 geometry rows, pixel cross-check 704 -> 1177px.
- Bundle scan: 107 uncovered classes carrying text directly (up from 102). The 5
  new ones (`.artifacts-error`, `.domain-option-heading`, `.site-chat-menu-note`,
  `.site-menu-check`, `.site-menu-status`) are English app chrome - a
  subdomain-error line, a domain-picker heading and a site-menu status row.
  None carry user or model text, so none were added.

### 0.0.186
- App updated; bundle renamed (`index-qL1TxIwV.js` / `index-DVFThbPT.css`).
- All 83 selectors + 1 overridden property still present - **no patch change
  needed**. Patch re-applied (idempotent), tags confirmed on lines 217-218,
  fresh backup written. Health check 83/83, exit 0.
- All three acceptance harnesses re-run against the new bundle and passing:
  - `verify_ads_hidden.py` - 4 ad surfaces hidden; `.sponsor-intermission`
    scope guard still visible (`flex 1x849` both).
  - `verify_break_autocontinue.py` - 0 clicks while disabled, exactly 1 once
    enabled, no repeats, a fresh break picked up.
  - `verify_chat_width.py` - 16/16 geometry rows, pixel cross-check
    704 -> 1177px.
- **Structural dependency check.** Ten structures the patch relies on were
  verified in the new bundle, not just the class names: the
  `sponsored-ad ad-${t}` className template, the telemetry selector constant,
  `.sponsor-intermission` as a `role="dialog" aria-modal="true"` modal with
  `.intermission-continue`, `impUrl` on click, `--chat-content-max-width:720px`
  and the `--chat-gutter` formula in the app's `:root`, the `.prose` 860px
  inner cap, `.project-sidebar{width:216px}` and `--explorer-width:440px`.
  All ten intact.
- **Trap hit while scanning: grep the right bundle.** Three of those ten checks
  initially reported MISSING because CSS-only strings (`.prose{...860px}`,
  `.project-sidebar{width:216px}`, `--explorer-width:440px`) were searched in
  the JS bundle, and the aria-label pattern carried a stray escape. A
  "MISSING" from a dependency scan is not evidence of a change until it has
  been re-checked against the file the string actually lives in.
- Bundle scan: 110 uncovered classes carrying text directly (up from 107).
  4 new, all English app chrome: `.template-card-description`,
  `.template-card-name`, `.template-strip-heading` (a template picker) and
  `.site-chat-menu-note`. One class went: `.side-chat-menu-note`, renamed to
  `.site-chat-menu-note` ("side" -> "site"). Neither was ever covered by the
  patch, so the rename has no effect on it.

### 0.0.188
- App updated; bundle renamed (`index-C422Roxo.js` / `index-DMHSA4jb.css`).
- All 83 selectors + 1 overridden property still present - **no patch change
  needed**. Patch re-applied, tags confirmed on lines 217-218, fresh backup
  written. Health check 83/83, exit 0.
- Delta analysis against 0.0.186:
  - **Class surface identical** - 0 text-bearing classes added, 0 removed
    (110 uncovered both times).
  - **18/18 structural dependencies intact**, each checked in the bundle it
    actually lives in: the CSS `:root` chat-width property and `--chat-gutter`
    formula, the `.prose` 860px inner cap, `.project-sidebar{width:216px}`,
    `--explorer-width:440px`, the `.ad-banner` / `.ad-showcase` /
    `.intermission-body` / `.messages` rules; and in the JS the
    `sponsored-ad ad-${t}` template, the telemetry ad selector, the
    "Sponsored break" modal with `.sponsor-intermission` +
    `.intermission-continue` + `aria-modal`, `impUrl`, `.sponsored-proposal`
    and `.placement-sidebar-card`.
- All three acceptance harnesses re-run and passing: ads hidden (4 surfaces +
  scope guard intact), break auto-continue (0/1/1/2 clicks across the four
  phases), chat width (16/16 rows, pixel cross-check 704 -> 1177px).

### Environment trap: the session interpreter changed mid-session

The three harnesses first failed with
`ERROR: could not start ChromeDriver: No module named 'selenium'` - then, under
`C:\Python314`, `No module named 'certifi'`. Neither was a patch problem: the
default `python` now resolves to a **per-session Hermes venv** that has no
selenium, no Pillow and no `pip`, and it had been recreated between turns.

- Known-good: `%LOCALAPPDATA%\hermes\hermes-agent\venv\Scripts\python.exe`
  (selenium 4.48.0, pillow 12.3.0, certifi 2026.05.20).
- `C:\Python314\python.exe` has selenium 4.46.0 + pillow but **no certifi**, so
  Selenium Manager still fails there.
- `apply_fb_persian_patch.py` is stdlib-only and is unaffected.

The tools now name this explicitly instead of printing a bare module error, and
`tools/README.md` documents the interpreter table.

### 0.0.190
- App updated; bundle renamed (`index-Cobmrcyj.js` / `index-BZX_IQFm.css`).
- All 83 selectors + 1 overridden property still present - **no patch change
  needed**. The update wiped the whole `ui/` including the previous backup, so a
  fresh `index.html.fb-persian-backup` was written. Tags confirmed on lines
  217-218. Health check 83/83, exit 0.
- **18/18 structural dependencies intact**, each re-checked in the bundle it
  actually lives in. **Two were first reported MISSING and both were false
  alarms** - the third release in a row to produce one, so the pattern is now
  written up in `docs/UPDATE_CHECKLIST.md`.
- All three acceptance harnesses re-run against the new bundle and passing:
  - `verify_ads_hidden.py` - 4 ad surfaces hidden; `.sponsor-intermission`
    scope guard still visible (`flex 1x849` both).
  - `verify_break_autocontinue.py` - 0 clicks while disabled, exactly 1 once
    enabled, no repeats, a fresh break picked up.
  - `verify_chat_width.py` - 16/16 geometry rows, pixel cross-check
    704 -> 1177px, identical to 0.0.188, so the layout did not move.
- **The text-surface scan now has a fixed definition.** New tool:
  `tools/scan_text_surfaces.py` reports classes that carry text directly and are
  not covered by the patch. The per-version counts recorded above (92, 94, 101,
  102, 107, 110) came from an unrecorded ad-hoc method and are **not comparable**
  to anything this tool produces - it reports 517 for 0.0.190. The comparable
  number, and the one worth reading, is the Arabic-script subset: **0 of those
  517 carry Arabic-script text.** A Persian string the patch fails to reach
  would appear there; English app chrome is expected and harmless.

### 0.0.192
- App updated; bundle renamed (`index-CqVmYRQK.js` / `index-A-mFxkKf.css`).
- All 83 selectors + 1 overridden property still present - **no patch change
  needed**. The update wiped `ui/` again, so a fresh
  `index.html.fb-persian-backup` was written and tags landed on lines 217-218.
  Health check 83/83, exit 0.
- **18/18 structural dependencies intact** with the new
  `tools/check_dependencies.py` (this replaces the ad-hoc dependency check that
  had produced false MISSINGes in three consecutive releases). Its first run
  flagged `.project-sidebar` - a needle bug in the tool, not a missing
  dependency: the needle was `--project-sidebar`, a custom property the app does
  not have, and the class is present in 87 CSS and 10 JS places.
- **The project sidebar changed.** It is now `width:256px; flex:0 0 256px` (was
  `216px`) and resizable at runtime (`data-resizing` in the bundle). The 216px
  value survives only as `@media(max-width:900px)`. `--explorer-width` is
  unchanged at 440px.
  **No effect on the patch**, which never reads the sidebar width - confirmed by
  the width harness, still reporting the identical 704 -> 1177px.
- Text-surface scan (`tools/scan_text_surfaces.py`): 521 uncovered classes, and
  again **0 carrying Arabic-script text**. No new Persian surface to cover.
- All three acceptance harnesses re-run against the new bundle and passing:
  - `verify_ads_hidden.py` - 4 ad surfaces hidden; `.sponsor-intermission`
    scope guard still visible (`flex 1x849` both).
  - `verify_break_autocontinue.py` - 0 clicks while disabled, exactly 1 once
    enabled, no repeats, a fresh break picked up.
  - `verify_chat_width.py` - 16/16 geometry rows, pixel cross-check 704 ->
    1177px.

### 0.0.194
- App updated; bundle renamed (`index-dYV4RxYk.js` / `index-CjCPuboV.css`).
- **29 of the 83 selectors disappeared from the bundle** - the app removed /
  restructured a batch of surfaces (artifacts panel, profile survey, search
  modal, thread-detail title, plan-action, run-answer, tool-plan, msg-verdict-note,
  sidebar-thread-title, threads-row-title-text, search-result-text/title,
  fb-skeleton-answer, prompt-rail-preview, domain-explanation, export-thread-body,
  composer-attachment menu/options, preview-context-text, fb-skeleton-conversation,
  and the placement sidebar card). They are gone from BOTH the CSS and the JS,
  so the corresponding RTL rules are no-ops now. Per the documented procedure
  (see `docs/UPDATE_CHECKLIST.md`) they were **dropped from the patch rather
  than left as stale entries** - the JS SELECTOR array went from 83 to 54
  entries and the CSS lost the `fb-skeleton-conversation` width rule and the
  `.placement-sidebar-card` hide rule. Health check is 54/54, exit 0.
- **One structural dependency gone**: `.placement-sidebar-card` (an ad slot)
  no longer exists in the bundle - confirmed by a flattened substring search of
  both the CSS and the JS (0 hits). The other 17 of 18 dependencies are intact.
  The ad-hiding harness (`tools/verify_ads_hidden.py`) was updated to target the
  3 surviving ad surfaces; its scope guard (`.sponsor-intermission` must stay
  visible) still passes.
- **Two candidate renames, left unverified**: `plan-action` -> `plan-actions`
  and the `composer-attachment-*` family -> `composer-preview-contexts`. Both new
  names appear only in the CSS (0 hits in the JS), so it is not yet clear they
  are the same surfaces carrying Persian text - they are recorded here for a
  future screenshot-driven re-derivation rather than guessed at. No coverage is
  lost in the meantime because the old surfaces are gone.
- Text-surface scan (`tools/scan_text_surfaces.py`): the 0.0.194 bundle renders far fewer
  literal `className`/`children` pairs (13 `className` occurrences in the whole
  bundle), so the scan now reports 1 uncovered text-bearing class, **0 carrying
  Arabic-script text** - same signal as 0.0.190/0.0.192 (no new Persian
  surface to cover), just a much smaller denominator. No new Persian surface to
  cover.
- All three acceptance harnesses re-run against the new bundle and passing:
  - `verify_ads_hidden.py` - 3 ad surfaces hidden; `.sponsor-intermission`
    scope guard still visible (`flex 1x849` both).
  - `verify_break_autocontinue.py` - 0 clicks while disabled, exactly 1 once
    enabled, no repeats, a fresh break picked up.
  - `verify_chat_width.py` - 16/16 geometry rows, pixel cross-check
    704 -> 1177px (unchanged from 0.0.192).
- A fresh `index.html.fb-persian-backup` was written (the update wiped `ui/`);
  tags landed on lines 217-218 with the `/assets/` prefix.

### 0.0.194 follow-up — the chat moved to a hosted web app (patch delivery changed)

This release is the one where the local-file patch stopped working, and the
reason was not a renamed selector.

- `resources/orchestrator/ui/` is now only the splash / sign-in shell. Its
  bundle contains none of the chat classes (`prose`, `composer`, `reasoning`,
  `user-message`, `markdown` all count 0 in the JS), while the stylesheet still
  carries them.
- The chat is the hosted web app, opened in its own BrowserWindow:
  `electron/hosted-workspace.cjs` has
  `HOSTED_ORIGINS = ['https://staging-2-auth.freebuffweb.site',
  'https://staging-auth.freebuff.com', 'https://freebuff.com']` and
  `win.loadURL(bootstrap.url)`; the partition
  `%APPDATA%/Freebuff/Partitions/freebuff-hosted-v1-*` is created on first use.
- So a green `54/54 selectors` check was meaningless: it matched classes in the
  local stylesheet that the chat window never loads.

**New delivery.** `tools/fb_hosted_patch.py` marks `electron/hosted-preload.cjs`
as `unpacked` in the asar header (data block untouched) and writes an unpacked
preload that injects the patch into the hosted page:

- `webFrame.insertCSS(css)` for the stylesheet.
- `document.fonts.add(new FontFace('Vazirmatn FB', <binary>, { unicodeRange }))`
  for the font, so the page's CSP cannot block a font fetch and Latin text keeps
  its original face.
- The existing `dir="auto"` marker runs unchanged.

Attendance evidence: with a temporary title marker the hosted window reported
`FB-RTL n=110`, i.e. the preload ran and 110 elements were marked. Measured on a
screenshot afterwards: right-edge spread 52 px against left-edge spread 319 px
(right-aligned), where the unpatched control was 111 px / 256 px.

**Chat width.** The hosted app names the cap `--dk-chat-content-max-width: 720px`
(the local shell uses the unprefixed name). The patch now overrides both, with
`!important`, plus `.messages .prose { max-width: none !important }`. Measured:
text spans ~999 px of a 1050 px pane, versus ~720 px before.

**Ads are NOT hidden any more.** The hosted app detects a hidden ad slot and
shows a blocking "Please allow ads on Freebuff" banner. `display:none` was
caught, and so was a 1 px-high, transparent box; section 6 was therefore removed
and the ad slots left alone. That is the honest trade: about 50 px of banner in
exchange for not fighting a detector that risks the account.

**To-dos are unreachable in hosted mode.** `orchestrator.js` builds its tool
list as `...(options.workspace ? [] : ["write_todos"])`, so the workspace agent
never gets the todo tool, and the Claude path has
`CLAUDE_DISALLOWED_TOOLS = ["TodoWrite"]`. The `.todo-dock` styles still exist in
the stylesheet, but no tool call can produce one; the model can only write a
Markdown checklist. Do not chase dock selectors for this mode.
