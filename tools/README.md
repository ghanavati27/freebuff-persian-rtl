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
