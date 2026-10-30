# Re-applying after a Freebuff update

An update replaces the UI files, so the patch is gone. Run the installer by hand -
there is no scheduled task.

## 1. Check the version

```bat
cd C:\Users\Siroos\Hermes\freebuff-persian-rtl
python apply_fb_persian_patch.py --check
```

The first lines print the `ui dir` and the installed version. That decides which
installer to run.

## 2. Run the matching installer

**0.0.192 and older** - local UI served from `resources/orchestrator/ui/`:

```bat
python apply_fb_persian_patch.py
```

Copies `fb-persian-rtl.css`, `fb-persian-rtl.js` and the three fonts into
`ui/assets/`, adds the tags to `index.html`, and verifies that every selector in
the stylesheet still exists in the bundle. A selector mismatch means the UI
changed: update `patch/fb-persian-rtl.css` before shipping.

It also disables the auto-updater: the feed in `resources/app-update.yml` is
pinned to a dead URL, anything already downloaded is deleted, and
`%LOCALAPPDATA%\@codebufffreebuff-desktop-updater\pending` is write-locked so the
app cannot fetch 0.0.195 again. `python apply_fb_persian_patch.py --check` reports
all three; `--allow-updates` undoes them when you want to move to a hosted
build on purpose.

**0.0.194 and newer** - hosted web app window:

```bat
python tools\fb_hosted_patch.py
```

Marks `electron/hosted-preload.cjs` as unpacked in `app.asar` and writes a
patched preload (JS only - the hosted page's CSP blocks stylesheets).
Rollback: `python tools\fb_hosted_patch.py --restore`.

## 3. Restart and check

1. Launch Freebuff.
2. Persian paragraphs sit on the right, Latin and code stay on the left.
3. A Persian table: first column on the right, cells right-aligned.
4. The chat column is wide (~1200 px) with a visible gap on both sides.
5. No red "Please allow ads on Freebuff" banner (the patch never touches ads).

## Traps

- **Right installer matters.** On 0.0.194+ the local `ui/` files are the splash
  only, so `apply_fb_persian_patch.py` reports success and changes nothing you
  can see. On 0.0.192 there is no hosted preload.
- **Hosted window failures are usually not the patch.** `Couldn't send. Try
  again.`, `hosted-workspace:open` timeouts and `unknown certificate
  verification error` come from the app's own broker/network. A/B with
  `python tools\fb_hosted_patch.py --copy-only` (original preload) tells you
  whether the patch is involved.
- **DevTools** is refused on the hosted build (`app.exit(1)` on
  `--remote-debugging-port`); use the `FB_DEBUG_DOM` title probe described in
  `AGENTS.md`.
- **Do not add CSS to the hosted path.** `insertCSS` and injected `<style>`
  elements are silent no-ops there.
