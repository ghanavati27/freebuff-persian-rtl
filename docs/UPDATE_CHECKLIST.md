# Re-deriving the patch after a Freebuff update

An app update replaces `resources/orchestrator/ui/` wholesale: the patch files
are deleted, `index.html` is rewritten, and the bundle is rebuilt with new
hash-suffixed names and possibly new class names.

`apply_fb_persian_patch.py` will usually still work, because it reads the new
bundle names out of `index.html`. The risk is **class renaming**: a selector in
`patch/fb-persian-rtl.js` that no longer exists makes its rule a silent no-op.

## Procedure

1. **Apply and inspect.**

   ```bat
   python apply_fb_persian_patch.py --check
   python apply_fb_persian_patch.py
   ```

   Read the `selectors: N/M` line. If `M < N`, some selectors are stale.

2. **Locate the new bundle.** Read the CSS and JS file names from
   `index.html` (`<link href="./assets/index-*.css">`,
   `<script src="./assets/index-*.js">`). Never hard-code them.

3. **Find the replacement classes.** In the bundle JS, class names appear as
   `className:"..."` or `"class":"..."` in the minified output. Search for the
   *old* name; if it is gone, search for a near match and for the UI string
   that element renders.

   ```bat
   findstr /C:"className:" assets\index-*.js | findstr /C:"prose"
   ```

   Use the app itself to confirm: open the surface, screenshot it, and read the
   text the element carries. That decides whether it is user/model text
   (needs `dir="auto"`) or app chrome (does not).

4. **Update the patch.** Edit `patch/fb-persian-rtl.js` (runtime selectors) or
   `patch/fb-persian-rtl.css` (`:dir(rtl)` geometry rules). Keep the rules
   `:dir(rtl)`-keyed - an unkeyed rule would reach English users.

5. **Re-run the installer** until the health check reports `N/N`:

   ```bat
   python apply_fb_persian_patch.py
   ```

6. **Re-verify.** Follow section 8 of `AGENTS.md` - control/patched pixel diff,
   LTR regression must be exactly 0 pixels, plus the alignment and diff-tint
   tests on the surfaces that changed.

7. **Record it.** Note the rename or removal in `docs/FINDINGS.md` so the next
   agent does not relearn it.

## If a surface disappears

If a selector no longer exists because the UI element was removed, do not
silently delete the rule. Record it in `docs/FINDINGS.md` as removed in the
version where it vanished, and drop the selector only once the health check is
green.

## If `index.html` changes shape

The installer looks for `href="./assets/index-` to place its tags. If the new
`index.html` no longer has that anchor, the script exits with status `2` and a
pointer to this file. Inspect the new `index.html`, move the anchor constant in
the script, and re-run. Keep the injected tags immediately after the bundle's
own stylesheet link so the patch stylesheet loads after the bundle's.

## 0.0.180 - the asset path style is not fixed

`index.html` used to reference the bundle relatively:

```html
<link rel="stylesheet" href="./assets/index-XXX.css">
<script src="./assets/index-YYY.js"></script>
```

0.0.180 switched to absolute paths and put the `<script>` first:

```html
<script type="module" crossorigin src="/assets/index-MhrKAKLz.js"></script>
<link rel="stylesheet" crossorigin href="/assets/index-3Ukgm2iF.css">
```

Do not assume either. When re-deriving, grep for `assets/index-` and copy
whatever prefix the document actually uses onto the patch's own tags. The
prefix is a correctness issue: the SPA server answers any extensionless path
with this document, so a relative href on a deep path resolves to
`/<deep>/assets/...` and 404s - which silently disables the whole patch.

A hard failure (exit 2) after "installed -> assets/..." but with no
"index.html -> added ..." line means the anchor was not found. That is this
class of change; the assets are on disk but the patch is **not active**.
