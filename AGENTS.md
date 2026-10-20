# AGENTS.md

Guidance for AI coding agents working in this repository.

This file is the source of truth for "what an agent must know before touching this
repo". Read it end to end before changing anything.

---

## 1. What this repo is

Freebuff Desktop is an Electron app. Its chat is built with React and Markdown,
and **Persian / Arabic text renders badly**: paragraphs come out left-aligned,
mixed Persian+English lines get scrambled word order, list markers sit on the
wrong side, and checkboxes do not move to the right for RTL options.

The desktop source is private (`github.com/CodebuffAI/freebuff` is a public
mirror that explicitly excludes it), so the only viable fix is a **runtime
patch on the UI files the app serves from disk**. This repo contains that patch
and the tooling to (re)install it.

There is nothing to build and nothing to fork.

---

## 2. Hard constraints

These are not style preferences. Violating them breaks the app or its users.

1. **Never rebuild the app.** The renderer is served from
   `resources/orchestrator/ui/` by a local Bun server with no CSP and no
   integrity check. Editing those files in place *is* the mechanism. A "proper
   build" is impossible (private source) and unnecessary.

2. **Never let a patch rule reach an LTR element.** An English-speaking user
   must see exactly the shipped UI. Every patch rule must be keyed on
   `:dir(rtl)` / `dir="auto"` so Latin content is provably untouched. The
   acceptance test is a **0-pixel regression diff** of a Latin-only page, not
   a visual impression. The chat-width section is the one deliberate exception -
   see section 11.

3. **Code stays left-to-right.** Code blocks, terminals, diffs, JSON, file
   paths and identifiers are code, not prose. They must never be mirrored,
   even when they appear inside Persian content. A `diff` block in a Persian
   answer is still LTR.

4. **`text-align: left` in the bundle is deliberate.** The bundle hard-codes
   `text-align:left` in several places. `dir="auto"` sets direction but cannot
   override an explicit rule, so the patch resets those - but *only* on elements
   that actually resolved to RTL.

5. **Do not delete `index.html.fb-persian-backup`.** It is the one-click
   rollback for the whole patch.

6. **Never run or schedule anything outside this repo without asking the
   user.** In particular, do not create a scheduled task to re-apply the
   patch; the user runs `apply_fb_persian_patch.py` by hand after each update.

7. **Verify by measurement, not by eye.** Pixel measurement with Pillow (see
   `tools/`) is the only accepted evidence. "Looks right" is not evidence.

---

## 3. The app, and where to look

| What | Where |
|---|---|
| Install root | `%LOCALAPPDATA%\Programs\@codebufffreebuff-desktop\` |
| UI served from disk | `resources\orchestrator\ui\` |
| Entry HTML | `resources\orchestrator\ui\index.html` |
| Bundle CSS | `resources\orchestrator\ui\assets\index-*.css` |
| Bundle JS | `resources\orchestrator\ui\assets\index-*.js` |
| Electron package.json | `resources\app.asar` (byte-offset archive) |
| Updater state | `%APPDATA%\Roaming\Freebuff\update-state.json` |

The bundle file names change on every release, so **never hard-code them**. Read
them out of `index.html`. Both the names *and the path style* vary: 0.0.173 and
earlier used relative hrefs (`<link href="./assets/index-XXX.css">`), 0.0.180
uses absolute ones (`<link href="/assets/index-XXX.css">`), and the
`<script>`/`<link>` order is not fixed either. `apply_fb_persian_patch.py` reads
both out of the document and copies the bundle's own prefix onto the patch's
tags; keep it that way. The prefix is not cosmetic - the SPA server answers any
extensionless path with this document, so a relative href on a deep path would
resolve to `/<deep>/assets/...` and 404.

`apply_fb_persian_patch.py --check` prints the detected app version and which
bundle files it read.

---

## 4. How the patch works

Two halves, both in `patch/`:

| File | Job |
|---|---|
| `fb-persian-rtl.js` | Sets `dir="auto"` on every text-bearing element, via a `MutationObserver` that also catches React re-renders. |
| `fb-persian-rtl.css` | Adds the Persian webfont (scoped to Arabic-script code points) and a handful of `:dir(rtl)`-keyed geometry rules. |
| `fb-vazirmatn-{400,500,700}.woff2` | The font (SIL Open Font License 1.1). |

Why `dir="auto"` and not CSS: CSS cannot ask "is this element's content
RTL?", so it cannot move a checkbox to the right for a Persian option while
leaving an English row alone. `dir="auto"` can - the element derives its own
direction from its first strong character, which fixes text order, alignment
*and* flex-row direction (so `[icon][text]` rows mirror correctly).

Why an LTR guarantee holds: `dir="auto"` on Latin content resolves to `ltr`,
which is exactly the shipped layout - no attribute value, no alignment change,
no row-order change. That is why the font is also scoped by `unicode-range`.

---

## 5. Files in this repo

```
apply_fb_persian_patch.py   idempotent installer / health checker
patch/fb-persian-rtl.js     runtime half (dir="auto" marking)
patch/fb-persian-rtl.css    style half (font + :dir(rtl) geometry)
patch/*.woff2               Vazirmatn fonts
tools/                      pixel-measurement and harness scripts
docs/FINDINGS.md            what was broken, what was fixed, and the evidence
docs/SELECTORS.md           the selector list and every trap behind it
docs/UPDATE_CHECKLIST.md     the re-derivation procedure after an app update
```

---

## 6. Re-applying after a Freebuff update

An update replaces the whole `ui/` directory, so the patch is gone. The user
runs this by hand - **no scheduled task**:

```bat
cd <this repo>
python apply_fb_persian_patch.py
```

Then restart Freebuff Desktop.

What the script does:

1. Locates the UI directory (several candidate paths are tried).
2. Reads the app version out of `app.asar`.
3. Copies the five `patch/` files into `ui\assets\`.
4. Injects two tags into `index.html` right after the bundle's own stylesheet
   link. Idempotent: tags already present are not duplicated.
5. Keeps a one-time `index.html.fb-persian-backup` so the patch is reversible
   by hand.
6. **Health check**: extracts every class the patch relies on and confirms it
   still exists in the shipped bundle. Reports any that vanished.

Exit status `1` means "applied, but some selectors look stale" - read the
output and update the selector list (see section 7). Exit status `2` is a hard
failure (app not found, or `index.html` no longer has the expected shape).

To roll back by hand: copy `index.html.fb-persian-backup` over `index.html`
and delete the five `fb-*` files from `ui\assets\`.

---

## 7. If the app updates and something breaks

Follow `docs/UPDATE_CHECKLIST.md`. The short version:

1. Run `python apply_fb_persian_patch.py --check` and read the selector report.
2. For each selector reported missing, re-derive it from the new bundle:
   - Grep the bundle JS for `className:"..."` to find the real class names.
   - Cross-check against the visible UI (screenshot + inspect) to decide
     whether the element carries user/model text.
3. Update `patch/fb-persian-rtl.js` and/or `patch/fb-persian-rtl.css`.
4. Re-run the installer; the health check must go back to `N/N`.
5. Re-run the verification in section 8.

**Do not** "fix" a missing selector by deleting it silently. If a surface
genuinely no longer exists, note it in `docs/FINDINGS.md`; if it was renamed,
replace it and record the rename.

---

## 8. Verification method

The only accepted evidence is pixel measurement. `tools/` contains the
harnesses used during development.

**The control/patched pair.** Render the app's real markup with the app's real
CSS in headless Chromium, once unpatched and once patched, then compare with
`PIL.ImageChops.difference`.

**The LTR regression test (mandatory).** A Latin-only page must be *identical*
before and after the patch. Assert `ImageChops.difference(...).getbbox() is None`.

**The alignment test.** For each text line, compute the ink bounding box
(Pillow, threshold on luminance) and assert:

- Persian lines end at a constant right edge (`ink.max_x` is stable across
  lines) - i.e. they are right-aligned.
- English lines start at a constant left edge - i.e. they are left-aligned.
- Code/diff lines start at a constant left edge - i.e. they are left-aligned.

**The diff-tint test.** Scan for green/red tinted rows to locate a diff block
without guessing, then check its left edge is constant.

**Never** report a fix as verified from a screenshot alone. A vision model's
"looks correct" has repeatedly produced false positives on this exact UI.

---

## 9. Known traps

These cost real debugging time. Read them before writing any selector.

1. **Chromium skips marked descendants when resolving an ancestor's direction.**
   `<div dir="auto"><p dir="auto">text</p></div>` resolves the *parent* to LTR
   because the child is already marked. So `ul`/`ol` must **not** be marked by
   the script; their RTL geometry comes from
   `.prose ul:has(> li:dir(rtl))` in the stylesheet instead. Marking them would
   leave the list LTR and strand the marker.

2. **Mark rows, not the text node inside them.** A row is a flex container; if
   only the inner text node is marked, the row does not mirror and the icon
   stays on the left. This applies to question options, to-do items, and
   tool-call rows.

3. **Mark tables and lists as a whole unit.** A cell holding only a number or a
   Latin identifier has no strong character of its own and would flip back to
   LTR, leaving one column misaligned next to its neighbours. Same for a list
   item whose text starts with a Latin word.

4. **`::marker` needs padding, not just direction.** The bundle reserves the
   marker's room with `padding-left` and draws the quote bar with
   `border-left`. In RTL both must move to the right.

5. **The collapsed reasoning preview is a `flex:1` box.** `text-align` decides
   where its text sits inside it, so it needs `text-align: left` to stay next
   to the "Thinking" label in both directions.

6. **An explicit `text-align:left` beats inherited direction.** `.question-option`,
   `.qbody` and `.prose th/td` need an explicit reset, and only on RTL.

7. **Code must be forced LTR, not just "not RTL".** A fenced block inside a
   Persian blockquote or list item inherits RTL and would mirror. Guard with
   `direction: ltr; unicode-bidi: isolate` on `pre`, `code`, `kbd`, `samp`,
   `.cm-editor`, `.xterm`, `.md-code`, `.md-pre`.

8. **Fonts must be scoped by `unicode-range`.** Without it, Latin text falls
   back to the Persian font and the whole UI changes for English users.

9. **Bundle class names change between releases.** Always re-derive; never
   assume a selector from an older bundle still exists. The health check in
   `apply_fb_persian_patch.py` exists for exactly this.

10. **`index.html` uses CRLF.** Preserve it when injecting tags, or the diff
    becomes noisy and editors complain.

---

## 11. Layout exceptions

Constraint 2 says an LTR user must see the shipped UI. Section 5 of
`patch/fb-persian-rtl.css` (chat width) is an **explicit, deliberate exception**
to that: it changes the layout for every language, by request.

Two rules apply to anything in this category:

1. **It must be its own, clearly-marked section** of the CSS, stating in a
   comment that it is not RTL-gated and why. Never bury a layout change inside
   the direction work.
2. **It must be documented here.** An undocumented layout change looks like a
   bug to the next reader, and the 0-pixel test will "fail" for a reason nobody
   can find.

For the chat width specifically:

- The shipped UI caps the transcript with one custom property,
  `--chat-content-max-width: 720px`, defined in the app's own `:root` next to
  `--explorer-width`. Every consumer wraps it in `min()`/`calc()` against `100%`
  (the live centre column), so overriding the single property is enough - and it
  is enough *responsively*, with no media query and no JS.
- `.prose` carries its own `max-width: 860px; margin: 0 auto`, which would
  re-centre the text inside a widened column and put the gap back, so the
  transcript's copy is uncapped. The file-preview variant
  (`.file-markdown-content > .prose`) is a different surface and is not touched.
- Because the property name is a dependency the class check cannot see, it is
  listed in `CHECKED_PROPS` in the installer and reported by `--check`.
- `tools/verify_chat_width.py` is the acceptance test for this section. The
  0-pixel LTR regression test still applies to sections 1-4; it cannot apply to
  a layout change that is meant to be visible.

---

## 12. Tone and reporting

- Be concise. Lead with the result, then the evidence.
- Distinguish a measurement from an inference. If you cannot measure
  something, say so rather than asserting a number.
- When a check contradicts a prior belief, report the contradiction plainly.
- If you are about to repeat a command that already failed, stop and diagnose
  the root cause instead.
