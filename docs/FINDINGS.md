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
- Therefore every stylesheet in this repo was a silent no-op in the hosted
  window, and the repo no longer ships any CSS.

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
