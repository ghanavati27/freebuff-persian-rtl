# Findings

Everything here was measured on the installed app, not inferred.

## The chat is a hosted web app

- `resources/orchestrator/ui/` is the splash / sign-in shell only: its bundle has
  none of the chat classes (`workspace-transcript`, `composer-input-scroll`,
  `msg`, `prose` all count 0 in its JS).
- The chat is opened by `electron/hosted-workspace.cjs`
  (`win.loadURL(bootstrap.url)`), with its own session partition.
- Consequence: patching `ui/` cannot reach the chat, and any "N/N selectors
  present" check against the local bundle is meaningless.

## CSS does not work in that window (CSP)

Measured with probes injected into the live window:

- `webFrame.insertCSS(css)` returns without throwing, for the default author
  origin and for `{ cssOrigin: 'user' }`, and changes nothing.
- A `<style>` element appended by the preload is accepted by the DOM but its
  rules never apply.

The direction work only ever worked because it is JavaScript.

## The asar header is padded

The header block is padded so the data section starts 4-byte aligned, and file
offsets are relative to that padded start - not to `16 + json_length`. Reading
from `16 + len` makes the preload begin mid-line and the patched file fails to
parse. `tools/fb_asar.py` computes `pad = (-(16 + header_len)) % 4` on read and,
on write, shifts every offset by the real data-block delta until the digit count
settles.

## The app ships its own Vazirmatn

A live probe returned the computed stack `"Vazirmatn FB", "Vazirmatn FB"` - the
page already defines that family. Registering a second `FontFace` under the same
name does not replace it: the browser keeps both and swaps between them while
they load, so Persian text looks broken until loading settles.

The patch therefore waits for `document.fonts.ready`, registers its bundled faces
**only** when `document.fonts.check('16px "Vazirmatn FB"')` is false, and sets
`font-family` through CSSOM with `'Vazirmatn FB'` first and the app's stack
behind it. The bundled faces carry an `unicode-range` limited to Arabic, so Latin
and code still render in the app's own fonts.

## Filling the chat column

Two things pin the chat to a fixed width, not one: the transcript block carries a
fixed width **and** a computed left margin (measured 293 px in a 1306 px pane)
that keeps the column centred. Setting `width:auto` alone left it at 1003 px and
stuck to the right. The patch writes `width:auto; max-width:none; margin:0 24px`
on `.workspace-transcript-content` and `width:auto` on `.composer-box` and
`.composer.workspace-composer`.

Measured after the change: pane 1306, transcript 1248, composer 1258 - the two
match and follow the pane. `auto` rather than a fixed width is what keeps the
flex layout free to shrink the pane when a side panel opens; a forced width or
percentage stops the shrink and the panel then paints over the chat.

## What the JS patch does

- `dir="auto"` on text-bearing elements, with a `MutationObserver` for React
  re-renders.
- `dir` / `text-align` on Persian-dominant blocks, plus `pre` / `code` pinned to
  LTR so code inside an RTL block is not mirrored.
- Persian-dominant tables: `direction: rtl` and right-aligned `th` / `td`. Latin
  tables are left alone.
- Vazirmatn as described above.
- The sponsored break is auto-continued once its button enables.

## What is deliberately not done

- **Ads are not touched.** The app detects hidden or collapsed ad slots and
  blocks with "Please allow ads on Freebuff"; `display:none` was caught, and so
  was a 1 px transparent box. Hiding them is a cat-and-mouse game that risks the
  account.
- **No to-do dock.** `orchestrator.js` only exposes `write_todos` when
  `!options.workspace`, and the Claude path disallows `TodoWrite`, so the model
  can only write a Markdown checklist.
- **No DevTools injection.** The app exits on `--remote-debugging-port`, and the
  fuses keep `--inspect` and `NODE_OPTIONS --require` from being useful.

## Traps seen while working on this

- The hosted window intermittently fails to open with
  `unknown certificate verification error` (status 400/409). It is the app's
  local broker, not the patch; one restart fixes it.
- `.prose` and `<hr>` do not exist in the chat; it uses `.msg` blocks and
  Tailwind classes.
- React re-renders the composer subtree and drops inline styles, so the style
  writes are repeated on a 1.2 s tick.

## The empty state must be left alone

A new chat tab has no transcript, and its composer sits in a different layout:
the wrapper is sized by the app's own rules rather than by the conversation
column. Applying `width:auto` there collapses it - measured `.composer-box` at
10 px and `.composer-input-scroll` at 0 px, i.e. an invisible input.

`fit()` is therefore gated on `.workspace-transcript-content` existing: inside a
conversation it applies the width overrides, and outside one it removes them
again so the app's empty-state layout is untouched.

## The model's question UI ships left-to-right

`ask_questions` renders in a bottom dock (`section.question-dock`) or a centred
modal, and both are laid out LTR: the dock computes `direction: ltr` and
`.question-text` computes `text-align: start`. The question line only looked
right because it is a single RTL run; the option rows did not. Measured on the
shipped build, option text had a constant left edge (x = 34, 35, 48, 50) and a
ragged right - Persian pinned to the left margin, marker on the left.

`fixQ()` in the addon fixes it. Every text block of that UI
(`.question-text`, `.question-option`, `-label`, `-desc`, `.question-head`,
`.question-chip`, `.question-hint`, `.question-title`) gets `dir` and
`text-align` from its own content, with the same `fa > 0 && fa*2 >= la` ratio
used for tables and list items, and the `.question-dock` / `.question-modal` /
`.question-panel` container is flipped to RTL when its question text resolved
to RTL. After: every option line ends at x = 1152 (question 1165) with a ragged
left edge, `dock dir=rtl`, `.question-text` `text-align: right`.

Two traps:

- The dock is not in the DOM at startup. `fixQ()` was called once at boot and
  the 1.2 s tick did not include it, so it ran `runs=1` and applied nothing.
  It has to be in the interval.
- The option rows contain no `input[type=checkbox]` (`inputs=0`), so the marker
  is drawn by CSS - measure it in pixels, not in the DOM.
