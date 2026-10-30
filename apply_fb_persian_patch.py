#!/usr/bin/env python3
"""Apply / re-apply the Freebuff Desktop Persian/RTL patch.

Freebuff Desktop is Electron. Its renderer is a local Bun server that serves
the UI straight from disk (resources/orchestrator/ui/) with no CSP and no
integrity check, so the fix is: drop two files next to the bundle and reference
them from index.html. An app update replaces the whole ui/ directory, which is
why this script exists. Run it once after every Freebuff Desktop update and
the patch is restored in one step.

    python apply_fb_persian_patch.py            apply
    python apply_fb_persian_patch.py --check    report state, change nothing
    python apply_fb_persian_patch.py --dry-run  show what would happen
    python apply_fb_persian_patch.py --force    re-apply even if already present
    python apply_fb_persian_patch.py --allow-updates
                                                undo the update block

Applying the patch also disables the auto-updater: the app otherwise downloads
the newest hosted build and installs it the moment you quit, which would replace
this 0.0.192 install. That means pointing app-update.yml at a dead feed, deleting
any installer already downloaded, and denying write access to its pending/ folder.

Exit status: 0 ok, 1 applied but some selectors look stale, 2 hard failure.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ASSET_DIR = os.path.join(HERE, "patch")

ASSETS = [
    "fb-persian-rtl.css",
    "fb-persian-rtl.js",
    "fb-vazirmatn-400.woff2",
    "fb-vazirmatn-500.woff2",
    "fb-vazirmatn-700.woff2",
]

# index.html references the built bundle as
#   <link rel="stylesheet" crossorigin href="/assets/index-XXX.css">
#   <script type="module" crossorigin src="/assets/index-YYY.js"></script>
# Older builds used a relative "./assets/..." href. Both the file names *and*
# the path style change between releases, so neither is hard-coded here: the
# names are read out of index.html and the prefix is copied from whatever the
# bundle itself uses.
#
# The prefix is not cosmetic. The SPA server answers any extensionless path
# with this document, so on a deep path a relative "./assets/..." resolves to
# "/<deep>/assets/..." and 404s. The patch's own tags must therefore resolve
# exactly the way the bundle's do.
LINK_RE = re.compile(rb'<link[^>]+href="([^"]*assets/index-[^"]+\.css)"')
SCRIPT_RE = re.compile(rb'<script[^>]+src="([^"]*assets/index-[^"]+\.js)"')

CANDIDATES = [
    os.path.join(
        os.environ.get("LOCALAPPDATA", ""),
        "Programs", "@codebufffreebuff-desktop", "resources", "orchestrator", "ui",
    ),
    # Portable / per-machine installs and renamed package names.
    os.path.join(
        os.environ.get("ProgramFiles", ""),
        "@codebufffreebuff-desktop", "resources", "orchestrator", "ui",
    ),
    os.path.join(
        os.environ.get("ProgramFiles(x86)", ""),
        "@codebufffreebuff-desktop", "resources", "orchestrator", "ui",
    ),
]


def find_ui_dir() -> str | None:
    for path in CANDIDATES:
        if path and os.path.isfile(os.path.join(path, "index.html")):
            return path
    return None


VERSION_RE = re.compile(
    rb'"name"\s*:\s*"@codebuff/freebuff-desktop"\s*,\s*"version"\s*:\s*"([^"]+)"'
)


def app_version(ui_dir: str) -> str:
    """Best-effort version string; used only for reporting."""
    # The electron main package.json lives inside app.asar, which is a byte
    # offset archive - no extraction needed for a single string. It sits past
    # the first megabyte, so scan the archive in chunks.
    asar = os.path.join(ui_dir, "..", "..", "app.asar")
    if os.path.isfile(asar):
        try:
            with open(asar, "rb") as fh:
                overlap, buf = b"", b""
                while True:
                    chunk = fh.read(4 << 20)
                    if not chunk:
                        break
                    m = VERSION_RE.search(overlap + chunk)
                    if m:
                        return m.group(1).decode()
                    overlap = chunk[-64:]
                    buf = chunk
        except OSError:
            pass
    for rel in (os.path.join("..", "..", "app-update-info.json"),
                os.path.join("..", "..", "package.json")):
        p = os.path.join(ui_dir, rel)
        if os.path.isfile(p):
            try:
                with open(p, encoding="utf-8") as fh:
                    data = json.load(fh)
            except (OSError, ValueError):
                continue
            for key in ("currentVersion", "version", "targetVersion"):
                if data.get(key):
                    return str(data[key])
    return "unknown"


def asset_prefix(html: bytes) -> bytes:
    """The path prefix the bundle itself uses (b'/assets/' or b'./assets/').

    Copied onto the patch's own tags so they resolve the same way whatever path
    the app is loaded from.
    """
    for rx in (LINK_RE, SCRIPT_RE):
        m = rx.search(html)
        if m:
            href = m.group(1)
            return href[: href.rindex(b"assets/")]
    return b"/"


def bundle_tags(html: bytes) -> list[bytes]:
    """The two tags the patch adds, in the bundle's own path style."""
    prefix = asset_prefix(html)
    return [
        b'<link rel="stylesheet" href="' + prefix + b'assets/fb-persian-rtl.css">',
        b'<script defer src="' + prefix + b'assets/fb-persian-rtl.js"></script>',
    ]


def bundle_text(ui_dir: str) -> tuple[str, str, str]:
    """Return (combined bundle text, css name, js name) read from index.html."""
    with open(os.path.join(ui_dir, "index.html"), "rb") as fh:
        html = fh.read()

    css_name = js_name = ""
    m = LINK_RE.search(html)
    if m:
        css_name = os.path.basename(m.group(1).decode("ascii", "replace"))
    m = SCRIPT_RE.search(html)
    if m:
        js_name = os.path.basename(m.group(1).decode("ascii", "replace"))

    parts: list[str] = []
    for name in (css_name, js_name):
        if name:
            p = os.path.join(ui_dir, "assets", name)
            if os.path.isfile(p):
                parts.append(open(p, encoding="utf-8", errors="replace").read())
    return "\n".join(parts), css_name, js_name


# The stylesheet's element selectors (pre, code, kbd, samp) target tags, not
# classes, so they must not take part in the class check.
SKIP = {"pre", "code", "kbd", "samp"}

# Custom properties this patch overrides, checked by name. See missing_props().
CHECKED_PROPS = ["--chat-content-max-width"]


def extract_selectors() -> list[str]:
    """Every class the patch relies on, read out of the patch itself.

    Keeping the source of truth in the patch files means a future edit to the
    selector list is picked up here automatically.
    """
    found: list[str] = []
    for name in ("fb-persian-rtl.js", "fb-persian-rtl.css"):
        p = os.path.join(ASSET_DIR, name)
        if not os.path.isfile(p):
            continue
        text = open(p, encoding="utf-8").read()
        # Strip comments first: a class named only in prose (e.g. a comment
        # explaining why .file-markdown-content is left alone) is not a
        # dependency, and counting it would fail the check on a class the patch
        # never actually targets.
        if name.endswith(".css"):
            text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
        # Quoted class lists, e.g. '.prose p' in the JS. Every class in a
        # compound selector is taken, not just the first.
        for quote in ("'", '"'):
            for chain in re.findall(
                    re.escape(quote) + r"\.([A-Za-z][\w-]*(?:\.[A-Za-z][\w-]*)*)",
                    text):
                found += chain.split(".")
        # Bare CSS selectors, likewise including every class of a compound
        # selector. Taking only the first would mean `.sponsored-ad.ad-banner`
        # checked `sponsored-ad` alone, so a release that renamed the variant
        # (the part that decides WHICH ad surface the rule hides) would leave
        # the rule silently dead while the check stayed green.
        #
        # The leading delimiter is required so a dot inside url("./x.woff2")
        # cannot be read as a class - there the dot follows a slash.
        for chain in re.findall(
                r"(?:\{|,|\}|\s|>|\+|~)\.([A-Za-z][\w-]*(?:\.[A-Za-z][\w-]*)*)"
                r"(?![\"'])", text):
            found += chain.split(".")
    return [s for s in dict.fromkeys(found) if s not in SKIP]


def health_check(ui_dir: str) -> tuple[int, int, list[str]]:
    """How many patch selectors still exist in the shipped bundle."""
    text, css_name, js_name = bundle_text(ui_dir)
    if not text:
        return 0, 0, ["no bundle readable"]

    # Match the class name as a whole token: a bundle class often appears as
    # part of a multi-class string ("terminal-context-output preview-context-text"),
    # so requiring a literal ".name" would report a false miss.
    selectors = extract_selectors()
    missing = [
        s for s in selectors
        if re.search(r"(?<![\w-])" + re.escape(s) + r"(?![\w-])", text) is None
    ]
    return len(selectors) - len(missing), len(selectors), missing


def missing_props(ui_dir: str) -> list[str]:
    """Custom properties the patch overrides that have vanished from the bundle.

    A class check cannot see these: if a release renames one, the patch still
    installs and every selector still matches, but the override silently stops
    applying - the failure mode the selector check exists to prevent, one level
    down. The chat-width section depends on --chat-content-max-width existing in
    the app's own :root, so it is checked by name.
    """
    text, _, _ = bundle_text(ui_dir)
    return [p for p in CHECKED_PROPS if p not in text]


# --- auto-updater block -----------------------------------------------------
# The app auto-updates to the newest hosted build and installs it the moment the
# window closes, which turns this 0.0.192 install into 0.0.195. Applying the
# patch therefore pins the feed, deletes anything already downloaded, and denies
# write access to the updater's pending/ folder.

UPDATE_FEED_URL = "https://freebuff.com/api/desktop/updates/win-x64/"
UPDATE_BLOCK_URL = "http://127.0.0.1:9/disabled-by-user/"


def resources_dir(ui_dir: str) -> str:
    return os.path.dirname(os.path.dirname(ui_dir))


def updater_cache(yml_text: str) -> str | None:
    m = re.search(r"^updaterCacheDirName:\s*'?([^'\r\n]+?)'?\s*$", yml_text, re.M)
    if not m:
        return None
    base = os.environ.get("LOCALAPPDATA", "")
    return os.path.join(base, m.group(1)) if base else None


def pending_files(cache: str | None) -> list[str]:
    if not cache:
        return []
    pend = os.path.join(cache, "pending")
    if not os.path.isdir(pend):
        return []
    try:
        names = os.listdir(pend)
    except OSError:
        # A deny ACE that also covers listing hides the names; the folder is
        # locked either way, so report nothing rather than crash.
        return []
    return [os.path.join(pend, n) for n in names]


def write_denied(path: str) -> bool:
    probe = os.path.join(path, ".fb-write-probe")
    try:
        with open(probe, "wb") as fh:
            fh.write(b"x")
        os.remove(probe)
        return False
    except OSError:
        return True


def update_state(ui_dir: str) -> dict:
    yml = os.path.join(resources_dir(ui_dir), "app-update.yml")
    text = open(yml, encoding="utf-8").read() if os.path.isfile(yml) else ""
    cache = updater_cache(text)
    files = pending_files(cache)
    size = sum(os.path.getsize(p) for p in files if os.path.isfile(p))
    pend = os.path.join(cache, "pending") if cache else ""
    return {"yml": yml, "exists": bool(text), "blocked": UPDATE_BLOCK_URL in text,
            "cache": cache, "files": files, "bytes": size,
            "locked": bool(pend and os.path.isdir(pend) and write_denied(pend))}


def describe_updates(ui_dir: str) -> None:
    st = update_state(ui_dir)
    if not st["exists"]:
        print("updates    : app-update.yml missing (cannot tell)")
        return
    feed = "disabled" if st["blocked"] else "LIVE - the app will update on quit"
    lock = "locked" if st["locked"] else "writable"
    print(f"updates    : feed {feed}; pending {len(st['files'])} file(s) "
          f"({st['bytes'] / 1048576:.1f} MB); pending/ {lock}")


def block_updates(ui_dir: str, dry_run: bool = False) -> int:
    st = update_state(ui_dir)
    yml = st["yml"]
    if not st["exists"]:
        print("update block: app-update.yml not found, skipped")
        return 0
    if not st["blocked"]:
        if dry_run:
            print("update block: would point app-update.yml at a dead feed")
        else:
            bak = yml + ".fb-orig"
            if not os.path.isfile(bak):
                shutil.copy2(yml, bak)
            text = open(yml, encoding="utf-8").read()
            new = re.sub(r"^url:\s*\S+.*$", "url: " + UPDATE_BLOCK_URL, text,
                         count=1, flags=re.M)
            if new == text:
                new = text.rstrip("\r\n") + "\nurl: " + UPDATE_BLOCK_URL + "\n"
            with open(yml, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(new)
            print("update block: feed disabled (backup app-update.yml.fb-orig)")
    else:
        print("update block: feed already disabled")

    cache = st["cache"]
    if not cache:
        print("update block: no updaterCacheDirName, cache cleanup skipped")
        return 0
    pend = os.path.join(cache, "pending")
    if not dry_run:
        os.makedirs(pend, exist_ok=True)
    removed, freed = 0, 0
    for path in [os.path.join(cache, "installer.exe"),
                 os.path.join(cache, "current.blockmap")] + st["files"]:
        if not os.path.isfile(path):
            continue
        if dry_run:
            print(f"update block: would delete {path}")
            continue
        try:
            size = os.path.getsize(path)
            os.remove(path)
            removed += 1
            freed += size
        except OSError as exc:
            print(f"update block: could not delete {path}: {exc}")
    if removed:
        print(f"update block: removed {removed} cached file(s), {freed / 1048576:.1f} MB")
    if os.name == "nt" and not dry_run:
        user = os.environ.get("USERNAME", "")
        try:
            res = subprocess.run(["icacls", pend, "/deny", f"{user}:(OI)(CI)(WD,AD)"],
                                 capture_output=True, text=True, timeout=30)
            if res.returncode == 0:
                print("update block: pending/ locked (write denied)")
            else:
                print(f"update block: icacls failed: {res.stderr.strip() or res.stdout.strip()}")
        except (OSError, subprocess.SubprocessError) as exc:
            print(f"update block: icacls unavailable ({exc})")
    return 0


def allow_updates(ui_dir: str) -> int:
    st = update_state(ui_dir)
    pend = os.path.join(st["cache"], "pending") if st["cache"] else ""
    if os.name == "nt" and pend and os.path.isdir(pend):
        user = os.environ.get("USERNAME", "")
        subprocess.run(["icacls", pend, "/remove:d", user],
                       capture_output=True, text=True, timeout=30)
        print("updates: pending/ unlocked")
    bak = st["yml"] + ".fb-orig"
    if os.path.isfile(bak):
        shutil.copy2(bak, st["yml"])
        print("updates: app-update.yml restored")
    else:
        print("updates: no app-update.yml.fb-orig backup to restore")
    return 0


def check_state(ui_dir: str) -> int:
    print(f"ui dir     : {ui_dir}")
    print(f"app version: {app_version(ui_dir)}")
    describe_updates(ui_dir)
    ok, total, missing = health_check(ui_dir)
    print(f"selectors  : {ok}/{total} still present in the bundle")
    gone_props = missing_props(ui_dir)
    print(f"props      : {len(CHECKED_PROPS) - len(gone_props)}/{len(CHECKED_PROPS)}"
          f" overridden custom properties still defined in the bundle")

    with open(os.path.join(ui_dir, "index.html"), "rb") as fh:
        html = fh.read()
    _, css_name, js_name = bundle_text(ui_dir)
    print(f"bundle ref : css={css_name or '?'}  js={js_name or '?'}  "
          f"prefix={asset_prefix(html).decode('ascii', 'replace')}")
    linked = [n for n in ASSETS if n.encode() in html]
    print(f"patched    : {len(linked)}/{len(ASSETS)} referenced from index.html")

    for name in ASSETS:
        p = os.path.join(ui_dir, "assets", name)
        print(f"  asset {name:<24} {'present' if os.path.isfile(p) else 'MISSING'}")

    if missing or gone_props:
        if missing:
            print("\nWARNING: these patch selectors no longer appear in the bundle:")
            for s in missing:
                print(f"    {s}")
        if gone_props:
            print("\nWARNING: these overridden custom properties are gone from the bundle:")
            for p in gone_props:
                print(f"    {p}")
        print("The patch will still install, but something above needs updating.")
    return 1 if (missing or gone_props) else 0


def apply_patch(ui_dir: str, dry_run: bool = False, force: bool = False) -> int:
    assets_dir = os.path.join(ui_dir, "assets")
    index = os.path.join(ui_dir, "index.html")
    backup = os.path.join(ui_dir, "index.html.fb-persian-backup")

    print(f"ui dir     : {ui_dir}")
    print(f"app version: {app_version(ui_dir)}")

    with open(index, "rb") as fh:
        html = fh.read()
    newline = b"\r\n" if b"\r\n" in html else b"\n"

    tags = bundle_tags(html)
    already = [t for t in tags if t in html]

    if dry_run:
        print("dry run    : no changes made")
        if not os.path.exists(backup):
            print("  would back up index.html")
        for name in ASSETS:
            print(f"  would copy patch/{name} -> assets/")
        if len(already) == len(tags):
            print("  index.html already patched")
        else:
            print("  would add the missing tag(s) after the bundle's stylesheet link")
        block_updates(ui_dir, dry_run=True)
        return 0

    # 1) one-time backup, so the patch stays reversible by hand
    if not os.path.exists(backup):
        shutil.copy2(index, backup)
        print(f"backed up  -> index.html.fb-persian-backup")
    else:
        print("backup     -> already exists (kept)")

    # 2) install the assets
    os.makedirs(assets_dir, exist_ok=True)
    for name in ASSETS:
        src = os.path.join(ASSET_DIR, name)
        if not os.path.isfile(src):
            print(f"ERROR: patch asset missing: {src}", file=sys.stderr)
            return 2
        dst = os.path.join(assets_dir, name)
        shutil.copy2(src, dst)
        print(f"installed  -> assets/{name}  ({os.path.getsize(dst)} bytes)")

    # 3) reference them from index.html, after the bundle's own asset tags.
    #
    # The bundle's stylesheet <link> is the cascade anchor (the patch's CSS must
    # come after it), but some releases emit the <script> last. Inserting after
    # whichever of the two ends later keeps the patch's tags last in <head> in
    # both layouts.
    ends = [m.end() for m in (LINK_RE.search(html), SCRIPT_RE.search(html)) if m]
    if ends:
        end = html.find(b">", max(ends)) + 1
    else:
        end = html.find(b"</head>")
    if end <= 0:
        print(
            "ERROR: could not find the bundle's asset tags or </head> in "
            "index.html - the UI layout changed, see docs/UPDATE_CHECKLIST.md",
            file=sys.stderr,
        )
        return 2

    missing = [t for t in tags if t not in html]
    if missing and (force or len(already) < len(tags)):
        block = b"".join(newline + b"    " + t for t in missing)
        open(index, "wb").write(html[:end] + block + html[end:])
        names = [t.split(b'href="')[1].split(b'"')[0].decode() if b'href' in t
                 else t.split(b'src="')[1].split(b'"')[0].decode() for t in missing]
        print(f"index.html -> added {', '.join(names)}")
    elif not missing and not force:
        print("index.html -> already patched, nothing to do")

    block_updates(ui_dir)

    ok, total, gone = health_check(ui_dir)
    print(f"\nselectors  : {ok}/{total} present in the bundle")
    gone_props = missing_props(ui_dir)
    print(f"props      : {len(CHECKED_PROPS) - len(gone_props)}/{len(CHECKED_PROPS)}"
          f" overridden custom properties still defined in the bundle")
    if gone:
        print("WARNING: these patch selectors no longer appear in the bundle:")
        for s in gone:
            print(f"    {s}")
        print("Update docs/SELECTORS.md with replacements before relying on it.")
        return 1
    if gone_props:
        print("WARNING: these overridden custom properties are gone from the bundle:")
        for p in gone_props:
            print(f"    {p}")
        print("The chat-width section will silently stop applying until fixed.")
        return 1
    print("OK: patch applied and every selector verified.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true",
                    help="report state only, change nothing")
    ap.add_argument("--dry-run", action="store_true", help="show what would happen")
    ap.add_argument("--force", action="store_true", help="re-apply even if already present")
    ap.add_argument("--allow-updates", action="store_true",
                    help="undo the auto-update block (restore app-update.yml, unlock pending/)")
    args = ap.parse_args()

    ui_dir = find_ui_dir()
    if not ui_dir:
        print("ERROR: Freebuff Desktop is not installed at any known location.",
              file=sys.stderr)
        return 2

    if args.allow_updates:
        return allow_updates(ui_dir)
    if args.check:
        return check_state(ui_dir)
    return apply_patch(ui_dir, dry_run=args.dry_run, force=args.force)


if __name__ == "__main__":
    sys.exit(main())
