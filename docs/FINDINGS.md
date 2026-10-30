# Findings

Everything here was measured on the installed app, not inferred.

## The chat is a hosted web app (0.0.194+)

- `resources/orchestrator/ui/` contains the splash / sign-in shell only. Its
  bundle has none of the chat classes (`prose`, `composer`, `reasoning`,
  `user-message`, `markdown` all count 0 in the JS), while its stylesheet still
  carries them.
- The chat is opened by `electron/hosted-workspace.cjs`
  (`HOSTED_ORIGINS = ['https://staging-2-auth.freebuffweb.site',
  'https://staging-auth.freebuff.com', 'https://freebuff.com']`,
  `win.loadURL(bootstrap.url)`), with its own session partition
  `%APPDATA%/Freebuff/Partitions/freebuff-hosted-v1-*`.
- Consequence: patching `ui/` cannot reach the chat. Any "N/N selectors present"
  check that searches the local bundle is meaningless for the chat.

## CSS does not work in that window (CSP)

Measured with probes injected into the live window:

- `webFrame.insertCSS(css)` returns without throwing, for both the default
  author origin and `{ cssOrigin: 'user' }`, and changes nothing.
- A `<style>` element appended by the preload is accepted by the DOM
  (`style ok`) but its rules never apply.
- Therefore every stylesheet is a silent no-op in the hosted window. The repo
  keeps `patch/fb-persian-rtl.css` only for the local UI path (Freebuff 0.0.192
  and older), where the renderer has no CSP.

The direction work only ever worked because it is JavaScript.

## What the JS patch does

- `dir="auto"` on text-bearing elements, with a `MutationObserver` for React
  re-renders (verified: the hosted window reported 110 marked elements).
- Vazirmatn through the `FontFace` API, scoped by `unicode-range` so Latin text
  keeps its original face.
- 24 px right gutter on `.msg` blocks: the pane is flush with the window edge,
  so the transcript ran into the frame while the sidebar gave the left a gap.
- Persian-dominant tables: `style.direction = 'rtl'` and `textAlign = 'right'`
  on every `th` / `td`. The old CSS rule for this never ran; tables were coming
  out left-aligned.
- The sponsored break is auto-continued once its button enables.

## What is deliberately not done

- **Ads are not touched.** The hosted app detects hidden or collapsed ad slots
  and blocks with "Please allow ads on Freebuff". `display:none` was caught, and
  so was a 1 px transparent box. Hiding them is a cat-and-mouse game that risks
  the account.
- **No to-do dock.** `orchestrator.js` only exposes `write_todos` when
  `!options.workspace`, and the Claude path has
  `CLAUDE_DISALLOWED_TOOLS = ["TodoWrite"]`. In the hosted workspace the model
  can only write a Markdown checklist.
- **No DevTools injection.** The app exits on `--remote-debugging-port`
  (`app.exit(1)`); the fuses keep `--inspect` and `NODE_OPTIONS --require` from
  being useful.

## Traps seen while working on this

- Opening the hosted window intermittently fails with
  `unknown certificate verification error` (status 400/409). It is the app's
  local broker, not the patch; one restart fixes it.
- `.prose` and `<hr>` do not exist in the hosted chat; it uses `.msg` blocks and
  Tailwind classes. Selectors written for the old local UI silently match
  nothing.

## Width, composer and side gaps (JS)

- The transcript container is `.workspace-transcript-content`. It carries a hard
  `width: 720px` with `max-width: none`, so overriding
  `--dk-chat-content-max-width` changed nothing at all.
- The composer is a separate column: `.composer-input-scroll` < `.composer-box` <
  `.composer.workspace-composer` < `.thread-bottom` < `.thread-body`, all 610 px
  wide before the fix. Widening the transcript does not touch it.
- The patch now sets `width: 100%` + `max-width: 1200px` + auto margins on the
  transcript, and climbs from `.composer-box` to the first ancestor at least
  900 px wide, widening each step on the way. Padding on the
  lowest common ancestor of transcript and composer adds to the pane's own 24 px
  inset; 6 px on top of that gives a measured 30 px gap on both sides.
- Measured on 1364x718: composer input 552 -> 992 px, `.thread-body`
  610 -> 1050 px; composer border at x=358..1327 with the sidebar ending at 328
  and the pane ending at 1356, i.e. 30 px left and 29 px right.
- The styles are re-applied every 1.2 s: React re-renders the composer subtree
  and drops inline styles, so a one-shot write does not survive.

## Checkboxes and icons at the start of a Persian line

Markdown checklists render as `<li><input type="checkbox"> text</li>`. The input
is a separate inline element, so `dir="auto"` *on the text* resolves to RTL while
the paragraph itself stays LTR: the box is painted at the left edge (the LTR
inline start) and only the text flips. The same happens with an icon or emoji
before a Persian sentence.

Fix: `fixB()` sets `dir` and `text-align` on the **block** (`li`, `p`,
`blockquote`, `th`, `td`, skipping containers that hold nested blocks) using the
same Persian/Latin ratio as the tables (`fa*2 >= la`). A block with no Persian
characters is pinned to `ltr`. `pre`/`code`/`kbd`/`samp` are forced back to
`direction: ltr; unicode-bidi: isolate` so code inside an RTL block is not
mirrored. It runs with the 1.2 s tick for the same React reason.
