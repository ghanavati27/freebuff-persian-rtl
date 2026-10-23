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

## Paragraph direction from the dominant script (replaces dir="auto")

**The bug.** `dir="auto"` resolves direction from an element's FIRST STRONG
CHARACTER (HTML spec). A Persian paragraph that happens to begin with a URL, a
file path or a variable name therefore resolved to LTR: the whole block
left-aligned and every line's bidi order computed against the wrong base
direction. The user reported it with a screenshot; measured on the real markup,
a paragraph of `http://127.0.0.1:3000 با توضیح در همان فایل ...` laid out with
its ink at the box's LEFT edge, while a Persian-first paragraph of the same
length laid out at the RIGHT edge.

**The fix.** Count Arabic-block letters against Latin letters and take the
majority, ties to Persian. Only LETTERS vote: digits, punctuation, spaces and
the zero-width joiner are script-neutral, or a long URL inside Persian prose
could outvote the prose. No letters at all keeps `dir="auto"`, exactly as before.

**The constraint that shaped it.** Forcing `dir="rtl"` on everything would have
fixed the reported case and broken genuinely English paragraphs. Measured, with
the ink edge of each paragraph as the verdict:

| strategy | A latin-first Persian | B genuinely English | C persian-first |
|---|---|---|---|
| `auto` (old) | left (wrong) | left (correct) | right (correct) |
| `rtl` on all | right | right (WRONG) | right |
| dominant (new) | right | left | right |

**Streaming.** Replies arrive token by token, so a paragraph can start
Latin-dominant and become Persian-dominant. Direction is recomputed on text
changes too, debounced 120ms. React replaces the text node rather than mutating
it, so childList records whose node is a Text node must be handled as well as
`characterData` records - `apply()` skips a Text node and would leave the
direction stale.

**The CSS had to move with it.** The alignment reset was keyed on
`[dir="auto"]:dir(rtl)`, which stops matching once the script writes `rtl`/`ltr`.
It is now `[dir="rtl"], [dir="auto"]:dir(rtl)`. Safe because the app never sets a
dir attribute itself - checked against the bundle, whose only `dir:` hit is the
unrelated language-definition string `dir:"qmldir"`.

**One trap is now historical.** Under `dir="auto"`, a marked container whose text
sat entirely inside marked descendants was skipped and fell back to LTR. Direction
now comes from `dominantDir(el.textContent)`, which includes marked descendants,
so marking a container works. Lists and blockquotes are still left to the
stylesheet's `:has()` rules - their geometry is a marker/bar position, not a
direction.

### Verified by `tools/verify_paragraph_direction.py`

Loads the REAL patch file (not a reimplementation) and measures with Pillow:

| case | dir | measured |
|---|---|---|
| A latin-first, mostly Persian | `rtl` | ink L119..R822 -> right |
| B genuinely English | `ltr` | ink L62..R786 -> left |
| C persian-first | `rtl` | ink L120..R822 -> right |
| E digits/punctuation only | `auto` | ink L62..R222 -> left (unchanged) |
| D streamed: Latin-dominant -> Persian | `ltr` -> `rtl` | left -> right |
| LTR regression, Latin-only page | - | **IDENTICAL: 0 differing pixels** |

The other three harnesses were re-run against the new script and all pass:
`verify_ads_hidden.py`, `verify_break_autocontinue.py`, `verify_chat_width.py`.

## Direction by WORD, not by character (fixes the second reported paragraph)

The dominant-script rule shipped as a CHARACTER count, and the user reported it
still failing: a Persian paragraph came out left-aligned because its English
identifiers out-numbered the Persian letters. That is the rule's fault, not the
paragraph's - identifiers are long. `SITE_BASE_URL` is one word and thirteen
characters, so a handful of them can out-vote a whole sentence of Persian.

**Measured on the user's own conversations.** The app caches its API payloads, so
the real message bodies could be read back and analysed rather than guessed at:
8,633 mixed-script paragraphs.

| rule | says rtl |
|---|---|
| character count (previous) | 4,376  (51%) |
| word count (now) | 4,867  (56%) |

They disagreed on **495** paragraphs. Reading all of them:

- **494** were the reported class - Persian prose carrying English file paths and
  identifiers, where the character rule said ltr and the word rule says rtl. The
  word rule is correct in every one.
- **1** went the other way, a genuinely bilingual list. Either verdict is
  defensible there.

So the word rule is a strict improvement on this data. Every token votes by the
letters it contains, tokens with no letters (`§7.34`) do not vote at all, and
ties still go to Persian.

**These counts are a snapshot, not a constant.** The cache grows as the app is
used, so re-running `tools/analyze_direction_rules.py` reports different totals -
a later run gave 9,432 paragraphs and 530 disagreements. The split is what
matters and it stayed the same: **529 to 1** in favour of the word rule.

**The explicit signal was checked first and is absent.** A bidi control character
in the source (RLM/RLE/LRM) would have been the cleanest answer - explicit
authorial intent beating any heuristic. Scanning the cached payloads found **no**
bidi controls, only ZWNJ, so there is nothing to honour. The model writes Persian
prose; it does not mark it.

**Message-level inheritance was measured and rejected.** 552 paragraphs were
judged ltr inside a Persian-dominant message, and reading them showed the
majority are code blocks and English prose that are correctly LTR - inheriting
the message's direction would have broken far more than it fixed. A narrow
near-tie tie-breaker (follow the message only when the paragraph's own counts are
within 15% and it has at least 6 script words) was also measured: it changes 136
verdicts of 97,434 and never touches a paragraph with zero Persian words. It was
offered and deliberately NOT taken - the user chose the simple rule.

### Verified

`tools/verify_paragraph_direction.py`, loading the real patch file:

| case | chars | words | dir | measured |
|---|---|---|---|---|
| A latin-first Persian | 82/4 | 23/1 | rtl | right |
| B genuinely English | 0/109 | 0/25 | ltr | left |
| C persian-first | 82/4 | 23/1 | rtl | right |
| **F Persian prose + English identifiers** | **35/40** | **12/5** | **rtl** | **right** |
| E digits/punctuation only | 0/0 | 0/0 | auto | left |
| D streamed, Latin -> Persian | - | - | ltr -> rtl | left -> right |
| LTR regression, Latin-only page | - | - | - | IDENTICAL, 0 px |

Case F is the one that pins the rule: the character count says ltr there and the
word count says rtl, and rtl is what the paragraph needs.
