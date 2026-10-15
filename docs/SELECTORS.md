# Selectors

The class list in `patch/fb-persian-rtl.js` is the runtime source of truth. This
document records **why** the list is shaped the way it is, so a future edit
does not undo a hard-won fix.

## How the list was derived

The desktop source is private, so the classes were read out of the shipped
bundle: the minified JS contains them as `className:"..."`, and the CSS
contains the rules that hard-code `text-align:left`. Each candidate was then
confirmed against the live app by rendering its real markup in headless
Chromium and pixel-measuring the result.

## Rules of thumb

- **Mark the row, never the text node inside it.** A row is a flex container;
  marking only its inner text leaves the row unmirrored and the icon on the left.
- **Mark a list or table as a unit.** A cell holding only a number, or an item
  starting with a Latin word, has no strong character and would flip back to
  LTR, misaligning one column next to its neighbours.
- **Never mark `ul`/`ol`.** See trap 1 below.
- **Never mark code, terminal or diff surfaces.** They are guarded to LTR in
  the stylesheet instead.
- **Element selectors (`pre`, `code`, `kbd`, `samp`) are not classes** and are
  excluded from the installer's health check.

## The traps, in the order they bit

1. **Chromium skips marked descendants when resolving an ancestor's
   direction.** `<div dir="auto"><p dir="auto">text</p></div>` resolves the
   *parent* to LTR. Fix: `ul`/`ol` are handled by
   `.prose ul:has(> li:dir(rtl))` in the stylesheet, not by the script.
2. **A `text-align:left` rule beats inherited direction**, so `.question-option`,
   `.qbody` and `.prose th/td` need an explicit reset - RTL only.
3. **The collapsed reasoning preview is `flex:1`**, so `text-align` decides
   where its text sits; it needs `text-align: left` to stay next to the
   "Thinking" label in both directions.
4. **`::marker` needs padding, not direction.** The bundle reserves the marker's
   room with `padding-left` and draws the quote bar with `border-left`; both
   must move right.
5. **Code inside Persian content inherits RTL and mirrors.** Guarded with
   `direction: ltr; unicode-bidi: isolate`.
6. **A font without `unicode-range` changes Latin text too.** The Persian
   family is scoped to Arabic-script code points only.

## Health check

`apply_fb_persian_patch.py --check` extracts every class the patch relies on
from the patch files themselves and confirms it still appears in the shipped
bundle:

```
selectors  : 71/71 still present in the bundle
```

A count below `N/N` means a release renamed or removed a class. Re-derive it per
`docs/UPDATE_CHECKLIST.md` - do not delete a selector silently.

## Known dead ends

| Selector | Status |
|---|---|
| `.text-attachment-card` | **Removed** in 0.0.173. The real attachment classes are `.composer-attachment-menu` / `.composer-attachment-options`; the dead selector was replaced, and the health check is green again. |
| `.question-chip`, `.qbody` panel rows | Not fixable with CSS: their text is an unnamed flex child, so reaching it needs an unkeyed rule that would also hit English rows. |
