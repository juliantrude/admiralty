"""Build engine/dist/index.html: engine/index.html with engine.css and engine.js inlined.

The page is one file so that it opens offline from anywhere (ADR 0004); the repo keeps the sources apart
for readability: engine.css, engine.js and the pinned files of engine/vendor/ (three libraries, the font
Exo 2). The libraries become inline scripts, the font files data URIs. Each vendored file is checked
against its hash in pins.json first. The output depends only on the sources: no timestamp, no local path. `bundle()` is also used by tests/test_engine_bundle.py to check that the
committed file is not stale.

    uv run python tools/bundle_engine.py          # write engine/dist/index.html
    uv run python tools/bundle_engine.py --check  # exit 1 if the committed bundle is stale
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import sys
from pathlib import Path

ENGINE = Path(__file__).resolve().parent.parent / "engine"
DIST = ENGINE / "dist" / "index.html"
STYLE_TAG = '<link rel="stylesheet" href="engine.css">'
SCRIPT_TAG = '<script src="engine.js"></script>'
VENDOR_SCRIPT_RE = re.compile(r'<script src="vendor/([^"]+)"></script>')
FONT_URL_RE = re.compile(r'url\("vendor/([^"]+\.woff2)"\)')
# The inlined script keeps this id so that the test driver can find the place to hook in.
INLINE_SCRIPT_OPEN = '<script id="engine-script">'


def _vendored(engine: Path, name: str) -> bytes:
    """The bytes of engine/vendor/<name>, refused unless they match the SRI hash pinned for it."""
    pins = json.loads((engine / "pins.json").read_text(encoding="utf-8"))["libraries"]
    pin = next((pin for pin in pins if pin["file"] == name), None)
    if pin is None:
        raise SystemExit(f"bundle_engine: vendor/{name} is not pinned in pins.json")
    data = (engine / "vendor" / name).read_bytes()
    got = "sha384-" + base64.b64encode(hashlib.sha384(data).digest()).decode("ascii")
    if got != pin["integrity"]:
        raise SystemExit(f"bundle_engine: vendor/{name} does not match its pinned hash")
    return data


def bundle(engine: Path = ENGINE) -> str:
    html = (engine / "index.html").read_text(encoding="utf-8")
    css = (engine / "engine.css").read_text(encoding="utf-8")
    js = (engine / "engine.js").read_text(encoding="utf-8")
    for tag in (STYLE_TAG, SCRIPT_TAG):
        if html.count(tag) != 1:
            raise SystemExit(f"bundle_engine: expected exactly one {tag} in index.html")
    # A closing tag inside the inlined text would end the element early.
    if "</style" in css.lower() or "</script" in js.lower() or "<!--" in js:
        raise SystemExit(
            "bundle_engine: engine.css/engine.js contain a sequence that breaks inlining"
        )
    css = FONT_URL_RE.sub(
        lambda m: (
            "url(data:font/woff2;base64,"
            + base64.b64encode(_vendored(engine, m.group(1))).decode("ascii")
            + ")"
        ),
        css,
    )

    def library(match: re.Match) -> str:
        text = _vendored(engine, match.group(1)).decode("utf-8")
        if "</script" in text.lower() or "<!--" in text:
            raise SystemExit(f"bundle_engine: vendor/{match.group(1)} breaks inlining")
        return f"<script>\n{text.rstrip()}\n</script>"

    html = VENDOR_SCRIPT_RE.sub(library, html)
    html = html.replace(STYLE_TAG, f"<style>\n{css.rstrip()}\n</style>")
    return html.replace(SCRIPT_TAG, f"{INLINE_SCRIPT_OPEN}\n{js.rstrip()}\n</script>")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--check", action="store_true", help="do not write; exit 1 if stale")
    args = parser.parse_args(argv)
    text = bundle()
    if args.check:
        current = DIST.read_text(encoding="utf-8") if DIST.exists() else None
        if current != text:
            print("engine/dist/index.html is stale: run tools/bundle_engine.py", file=sys.stderr)
            return 1
        return 0
    DIST.parent.mkdir(parents=True, exist_ok=True)
    DIST.write_text(text, encoding="utf-8")
    print(f"wrote {DIST.relative_to(ENGINE.parent)} ({len(text)} characters)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
