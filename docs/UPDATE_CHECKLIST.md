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

2. **Run the two structural scans.** Both are cheap, and both catch failures the
   class check cannot see:

   ```bat
   python tools\check_dependencies.py
   python tools\scan_text_surfaces.py
   ```

   `check_dependencies.py` reports `N/N` and names the bundle each dependency
   was found in. `scan_text_surfaces.py` reports uncovered text-bearing classes;
   **read its Arabic-script count**, which should be 0. Treat a MISSING from
   either one as a hypothesis - re-check the needle in the file it should live
   in before concluding that anything moved.

3. **Locate the new bundle.** Read the CSS and JS file names from
   `index.html` (`<link href="./assets/index-*.css">`,
   `<script src="./assets/index-*.js">`). Never hard-code them.

4. **Find the replacement classes.** In the bundle JS, class names appear as
   `className:"..."` or `"class":"..."` in the minified output. Search for the
   *old* name; if it is gone, search for a near match and for the UI string
   that element renders.

   ```bat
   findstr /C:"className:" assets\index-*.js | findstr /C:"prose"
   ```

   Use the app itself to confirm: open the surface, screenshot it, and read the
   text the element carries. That decides whether it is user/model text
   (needs `dir="auto"`) or app chrome (does not).

5. **Update the patch.** Edit `patch/fb-persian-rtl.js` (runtime selectors) or
   `patch/fb-persian-rtl.css` (`:dir(rtl)` geometry rules). Keep the rules
   `:dir(rtl)`-keyed - an unkeyed rule would reach English users.

6. **Re-run the installer** until the health check reports `N/N`:

   ```bat
   python apply_fb_persian_patch.py
   ```

7. **Re-verify.** Follow section 8 of `AGENTS.md` - control/patched pixel diff,
   LTR regression must be exactly 0 pixels, plus the alignment and diff-tint
   tests on the surfaces that changed.

8. **Record it.** Note the rename or removal in `docs/FINDINGS.md` so the next
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

## 0.0.186 - grep the bundle the string actually lives in

A structural dependency scan reported three "MISSING" entries that turned out
to be fine. The causes:

1. CSS-only strings (`.prose{...860px}`, `.project-sidebar{width:216px}`,
   `--explorer-width:440px`) were searched in the **JS** bundle. The UI ships as
   two files; a rule lives in exactly one of them. Before reporting a structure
   as gone, re-check it against the file it lives in - the CSS for rules and
   custom properties, the JS for className templates, JSX attributes and event
   wiring.
2. A pattern written for printed output (with `\"` escapes) was run against the
   raw file, where no backslash exists. Write patterns against the file's real
   bytes, not against how a print of it looked.

A "MISSING" from a scan is a hypothesis until re-checked. The class health check
in the installer already reads both files; a hand-written structural scan must
do the same.

## 0.0.190 - a MISSING needs whitespace-tolerant matching

The structural dependency check compares needles against the bundle text.
Bundles are minified but **not** whitespace-free: 0.0.190 writes
`--explorer-width: 440px` with a space after the colon while
`.prose{max-width:860px` has none. A needle written from one release's CSS
therefore misses in another, and both `--explorer-width` and
`--chat-content-max-width` were reported MISSING while being plainly present.

Two rules, in order:

1. **Re-check before believing it.** A MISSING from a dependency scan is a
   hypothesis until the string has been searched for in the file it actually
   lives in. Three releases in a row have produced at least one false MISSING.
2. **Fix the match, not the needle.** Strip whitespace from both the needle and
   the bundle text before comparing. Never widen a needle to a bare property
   name to make a miss go away - that trades a false negative for a false
   positive, and the scan exists precisely to notice when a dependency moves.

Known false-MISSING causes so far: a CSS-only string searched in the JS bundle
(0.0.186), a stray escape in an aria-label pattern (0.0.186), and a missing
space in the needle (0.0.190).

## 0.0.190 - the text-surface scan has a fixed definition now

`tools/scan_text_surfaces.py` is the scan the update log keeps citing. Run it
after every update:

```
python tools/scan_text_surfaces.py --list 40
```

It reports classes that carry text DIRECTLY in the bundle (`className:"x"` with
a literal `children:"..."` nearby) and are not referenced by the patch. Read the
**Arabic-script count**, not the total: a Persian string the patch does not
reach is a real miss, while uncovered English chrome is expected. The totals
recorded before this tool existed are not comparable to its output.

## 0.0.192 - use tools/check_dependencies.py for the dependency scan

The structural dependency scan is now a tool, not an ad-hoc command:

```
python tools/check_dependencies.py
```

It checks each dependency in the bundle it actually lives in, matches
whitespace-insensitively, and reports **where** each one was found so a MISSING
can be re-checked in the right file.

Its needle set is a maintained list, so a needle that is wrong shows up
immediately rather than being rewritten each release: `--project-sidebar` was
such a needle (the app has the class `.project-sidebar`, not that property) and
the first 0.0.192 run reported it MISSING before the needle was corrected.
### 0.0.194 - 29 selectors dropped, one ad slot gone, two candidate renames

0.0.194 removed or restructured 29 of the 83 surfaces the patch covered
(artifacts panel, profile survey, search modal, thread-detail title, plan-action,
run-answer, tool-plan, msg-verdict-note, sidebar-thread-title,
threads-row-title-text, search-result-text/title, fb-skeleton-answer,
prompt-rail-preview, domain-explanation, export-thread-body, composer-attachment
menu/options, preview-context-text, fb-skeleton-conversation, and the placement
sidebar card). All 29 are gone from BOTH the CSS and the JS, so the rules were
no-ops. Per the "If a surface disappears" rule they were dropped from the patch
(JS SELECTOR array 83 -> 54, plus the `fb-skeleton-conversation` width rule and
the `.placement-sidebar-card` hide rule) only after recording them in
FINDINGS.md - the health check is 54/54.

One structural dependency is gone: `.placement-sidebar-card` (an ad slot)
returns 0 hits in a flattened search of both bundles. The other 17 of 18 are
intact. `tools/verify_ads_hidden.py` was updated to target the 3 surviving ad
surfaces; its `.sponsor-intermission` scope guard still passes.

Two possible renames were left UNVERIFIED and are recorded in FINDINGS.md for a
future screenshot-driven re-derivation rather than guessed at:
- `plan-action` -> `plan-actions`
- `composer-attachment-*` -> `composer-preview-contexts`

Both new names appear only in the CSS (0 hits in the JS), so it is not yet
clear they are the same surfaces carrying Persian text. No coverage is lost
because the old surfaces are gone.

The text-surface scan reports 517 uncovered classes, 0 carrying Arabic-script
text - identical to 0.0.190/0.0.192. No new Persian surface to cover.
