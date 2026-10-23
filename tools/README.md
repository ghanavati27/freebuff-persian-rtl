# Measurement tools

Pixel measurement for the patch. A vision model's "looks correct" produced
false positives on this UI repeatedly, so every claim is backed by a number.

## measure_ink.py

Requires Pillow.

```bat
python tools\measure_ink.py screenshot.png [more.png ...]
python tools\measure_ink.py --diff before.png after.png
python tools\measure_ink.py --diff before.png after.png --threshold 0
```

**Per-line geometry.** Each text band is printed as an ink bounding box plus a
`LEFT` / `RIGHT` label. Read the numbers, not the label:

- Persian lines in RTL surfaces end at a **constant right edge**.
- English lines start at a **constant left edge**.
- Code and diff lines start at a **constant left edge**.

**Diff tints.** Green and red tinted rows are reported so a diff block can be
located without guessing, then its left edge checked.

**LTR regression (mandatory).** `--diff before.png after.png` must report
`IDENTICAL: 0 differing pixels` for a Latin-only page. Anything else means a
patch rule reached an LTR element.

## The control/patched harness

Render the app's real markup with the app's real CSS in headless Chromium, once
unpatched and once patched, and compare with `PIL.ImageChops.difference`.

```bat
chromium --headless --disable-gpu --screenshot=out.png --window-size=1280,900 file:///<harness>.html
```

Build the harness page from the real markup: copy the app's own CSS
(`assets/index-*.css`), the real HTML structure, and the patch files. Do not
hand-write markup that only resembles the app - the point is to exercise the
real rules.

## verify_chat_width.py

The acceptance test for the chat-width section. Requires Selenium + Pillow and a
Chromium.

```bat
python tools\verify_chat_width.py
python tools\verify_chat_width.py --keep      REM keep the rendered PNGs
```

It renders the app's real bundle CSS with a faithful shell (the app's own
`.threadview` / `.messages` / `.msg.assistant` / `.prose` markup, and its own
216px `.project-sidebar` and 440px explorer either side) at 4 window widths x 4
panel states, once unpatched and once patched, and checks:

| Check | Pass condition |
|---|---|
| Stock baseline | transcript is the shipped cap (720px) wherever the centre column can reach it |
| Inner re-cap | patched `.prose` computed `max-width` is `none` |
| No remaining gap | patched prose width == `.messages` content width |
| Cap respected | patched prose width <= min(centre - 64, 1200) |
| Responsive | widening occurs in every case the centre column exceeds 720px |
| Gutter floor | `.messages` left padding never drops below `--space-8` (32px) |
| Pixel cross-check | Pillow ink span of the transcript band grows between stock and patched |

**Use Selenium, not `chrome.exe --headless --screenshot`.** On Windows a raw
chrome.exe invocation delegates to an already-running browser and silently
produces nothing - the screenshot flag returns exit 0 and writes no file. This
cost real time; do not re-derive it.

## Acceptance criteria

| Check | Pass condition |
|---|---|
| LTR regression | `getbbox() is None` (0 pixels) |
| Persian paragraph | constant right edge across lines |
| English paragraph | constant left edge across lines |
| Code / diff | constant left edge; language label left, `Copy` right |
| Diff colours | green rows for `+`, red rows for `-` |

If a check contradicts a prior belief, record the contradiction and keep the
measurement.

## verify_ads_hidden.py

The acceptance test for the ad-hiding section. Requires Selenium + a Chromium.

```bat
python tools\verify_ads_hidden.py
```

Renders the real ad markup (traced out of the bundle's own JSX) against the real
bundle CSS, once unpatched and once patched, and reads
`getComputedStyle(...).display` plus `getBoundingClientRect()` back out of the
DOM. It checks two things, and the second matters as much as the first:

| Check | Pass condition |
|---|---|
| Targeted surfaces | each computes `display: none` with a 0x0 box, where stock had a real box |
| Scope guard | `.sponsor-intermission` is **still visible** - it is a blocking modal, and hiding it would trap the user |

Over-reach is the failure mode a hide rule is most likely to have, so it is
asserted rather than assumed. When adding a surface to the hide list, first check
whether it has a `role="dialog"` / `aria-modal` and whether it owns a dismiss
control; if it has no exit of its own, do not hide it.

## verify_break_autocontinue.py

The acceptance test for the sponsored-break auto-continue in the runtime half.
Requires Selenium + a Chromium.

```bat
python tools\verify_break_autocontinue.py
```

Renders the real break markup with the real patch script loaded, attaches a click
counter, and drives the button's disabled state from the test while reading the
counter back out of the page:

| Phase | Pass condition |
|---|---|
| button still disabled | 0 clicks (a poll that ignores `disabled` is the bug worth catching) |
| button enabled | exactly 1 click |
| further polling | still exactly 1 - no repeat clicking while React unmounts |
| a fresh break appears | picked up and clicked, proving the watcher restarted |

Note the harness template is substituted with `str.replace`, not `str.format`:
the inline script is full of braces and `.format` treats them as fields.

## Interpreter

Every tool here needs Selenium + Pillow, and Selenium Manager additionally needs
certifi. Run them with an interpreter that has all three:

| Interpreter | selenium | pillow | certifi |
|---|---|---|---|
| `%LOCALAPPDATA%\hermes\hermes-agent\venv\Scripts\python.exe` | 4.48.0 | 12.3.0 | 2026.05.20 |
| `C:\Python314\python.exe` | 4.46.0 | 12.3.0 | **missing** - Selenium Manager fails |

**Do not assume the default `python` works.** In a Hermes session it can resolve
to a per-session venv (`...\hermes\installs\<id>\environments\<id>\venv\`)
that has neither package and no `pip` at all. A run that succeeded earlier in the
same session can start failing once that environment is recreated, and the error
is only `could not start ChromeDriver: No module named '<x>'` - an interpreter
problem, not a patch problem. The tools now say so explicitly; this table is the
fix.

Known-good invocation:

```bat
"%LOCALAPPDATA%\hermes\hermes-agent\venv\Scripts\python.exe" tools\verify_ads_hidden.py
```

Note `apply_fb_persian_patch.py` has no such requirement - it is stdlib only, so
the default `python` is fine for applying and health-checking the patch.
