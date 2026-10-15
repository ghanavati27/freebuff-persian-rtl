# Freebuff Desktop — Persian / RTL patch

Fixes Persian and Arabic text rendering in Freebuff Desktop by patching the UI
files the app serves from disk. No rebuild, no fork.

## The problem

Freebuff Desktop (Electron) renders Persian/Arabic incorrectly:

- Persian paragraphs come out **left-aligned**.
- Mixed Persian + English lines get **scrambled word order**.
- List markers, checkboxes and quote bars sit on the **wrong side**.
- Code inside Persian content gets **mirrored**.

An English-speaking user is unaffected by design; see *Guarantees* below.

## Why a runtime patch

The desktop source is private — `github.com/CodebuffAI/freebuff` is a public
mirror that explicitly excludes it. But the renderer is a local Bun server
that serves the UI straight from `resources/orchestrator/ui/` with no CSP and
no integrity check, so the served files can be patched in place. That is the
mechanism used here.

## Install / re-apply

Run this **by hand** after every Freebuff Desktop update (an update replaces
the whole `ui/` directory and wipes the patch):

```bat
cd <this repo>
python apply_fb_persian_patch.py
```

Then restart the app.

Useful flags:

| Flag | Effect |
|---|---|
| *(none)* | apply (idempotent) |
| `--check` | report app version, installed assets and selector health; change nothing |
| `--dry-run` | show what would happen |
| `--force` | re-apply even if the tags are already present |

The script copies the five `patch/` files into `ui\assets\`, injects two tags
into `index.html` after the bundle's own stylesheet, and keeps a one-time
`index.html.fb-persian-backup`.

## Rollback

```bat
copy /Y resources\orchestrator\ui\index.html.fb-persian-backup resources\orchestrator\ui\index.html
del resources\orchestrator\ui\assets\fb-*.css,fb-*.js,fb-*.woff2
```

## Repo layout

```
AGENTS.md                  read this before touching anything
apply_fb_persian_patch.py  installer / health checker
patch/                     the two patch halves + fonts
tools/                     pixel-measurement and harness scripts
docs/FINDINGS.md           what was broken, what was fixed, and the evidence
docs/SELECTORS.md          the selector list and the traps behind it
docs/UPDATE_CHECKLIST.md    re-derivation procedure after an app update
```

## Updating after a new Freebuff release

An update may rename or remove bundle classes. The installer's health check
catches this:

```bat
python apply_fb_persian_patch.py --check
```

Follow `docs/UPDATE_CHECKLIST.md` to re-derive any selector that went missing,
then re-run the installer until the check reports `N/N`.

## Guarantees

1. **English users are untouched.** Every rule is keyed on `:dir(rtl)` or
   `dir="auto"`, so a Latin element never matches. Verified by a **0-pixel
   regression diff** of a Latin-only page.
2. **Code stays left-to-right.** Code blocks, terminals, diffs, JSON and
   identifiers are forced `direction: ltr` even inside Persian content.
3. **Verified by measurement, not by eye.** All claims in `docs/FINDINGS.md`
   are backed by Pillow pixel measurement.

## License

The patch code is provided as-is for personal use. The bundled Vazirmatn fonts
are SIL Open Font License 1.1.
