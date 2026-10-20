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
