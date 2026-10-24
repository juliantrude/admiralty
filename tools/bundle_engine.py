"""Build engine/dist/index.html: engine/index.html with engine.css and engine.js inlined.

The Artifact is one file; the repo keeps three for readability (docs/plans/M6.md). The CDN script tags
stay as they are (pinned, with integrity hashes). The output depends only on the three source files:
no timestamp, no local path. `bundle()` is also used by tests/test_engine_bundle.py to check that the
committed file is not stale.

    uv run python tools/bundle_engine.py          # write engine/dist/index.html
    uv run python tools/bundle_engine.py --check  # exit 1 if the committed bundle is stale
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ENGINE = Path(__file__).resolve().parent.parent / "engine"
DIST = ENGINE / "dist" / "index.html"
STYLE_TAG = '<link rel="stylesheet" href="engine.css">'
SCRIPT_TAG = '<script src="engine.js"></script>'
# The inlined script keeps this id so that the test driver can find the place to hook in.
INLINE_SCRIPT_OPEN = '<script id="engine-script">'


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
