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
