"""Run engine pages in headless Chromium and read back what they wrote.

The page under test is copied to a temp directory with its CDN script tags rewritten to the git-ignored
cache from tools/fetch_engine_libs.py, so the tests never touch the network. The page reports its
result in `<pre id="engine-state">` as JSON; `render()` returns that JSON parsed.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PINS = ROOT / "engine" / "pins.json"
LIBS = ROOT / "tests" / "fixtures" / "engine-libs"

CHROMIUM = next(
    (
        found
        for name in ("chromium", "chromium-browser", "google-chrome")
        if (found := shutil.which(name))
    ),
    None,
)
STATE_RE = re.compile(r'<pre id="engine-state"[^>]*>(.*?)</pre>', re.S)
SCRIPT_TAG_RE = re.compile(r"<script\b[^>]*\bsrc\s*=[^>]*>\s*</script>", re.I)


class EngineDriverError(RuntimeError):
    pass


def libs_missing() -> list[str]:
    pins = json.loads(PINS.read_text(encoding="utf-8"))["libraries"]
    return [pin["file"] for pin in pins if not (LIBS / pin["file"]).exists()]


def skip_reason() -> str | None:
    """Why headless tests cannot run here, or None."""
    if CHROMIUM is None:
        return "no Chromium on PATH"
    if missing := libs_missing():
        return f"engine libraries not cached ({', '.join(missing)}): run tools/fetch_engine_libs.py"
    return None


def script_pin_problems(html: str) -> list[str]:
    """Every `<script src>` must be an exact-version CDN URL with integrity and crossorigin."""
    problems = []
    tags = SCRIPT_TAG_RE.findall(html)
    if not tags:
        problems.append("no <script src> found")
    for tag in tags:
        src = re.search(r'\bsrc\s*=\s*"([^"]*)"', tag)
        url = src.group(1) if src else tag
        if not re.search(r"@\d+\.\d+\.\d+(?=[/\"])", url) or re.search(r"@(latest|[\^~<>*])", url):
            problems.append(f"{url}: no exact version")
        if not re.search(r'\bintegrity\s*=\s*"sha(256|384|512)-[A-Za-z0-9+/=]+"', tag):
            problems.append(f"{url}: no integrity hash")
        if not re.search(r"\bcrossorigin\b", tag):
            problems.append(f"{url}: no crossorigin")
    return problems


def offline_copy(html: str) -> str:
    """Point pinned CDN script tags at the cache and drop integrity/crossorigin (file:// has no CORS)."""
    pins = json.loads(PINS.read_text(encoding="utf-8"))["libraries"]

    def rewrite(match: re.Match) -> str:
        tag = match.group(0)
        for pin in pins:
            if pin["url"] in tag:
                return f'<script src="{(LIBS / pin["file"]).as_uri()}"></script>'
        raise EngineDriverError(f"script tag without a pinned URL: {tag}")

    return SCRIPT_TAG_RE.sub(rewrite, html)


def dump_dom(html: str, *, budget_ms: int = 20000, timeout: float = 90) -> str:
    """Load `html` (CDN tags rewritten to the cache) in headless Chromium and return the final DOM."""
    reason = skip_reason()
    if reason:
        raise EngineDriverError(reason)
    with tempfile.TemporaryDirectory(prefix="engine-") as tmp:
        page = Path(tmp) / "page.html"
        page.write_text(offline_copy(html), encoding="utf-8")
        result = subprocess.run(
            [
                CHROMIUM,
                "--headless=new",
                "--no-sandbox",
                "--disable-gpu",
                "--allow-file-access-from-files",
                f"--user-data-dir={Path(tmp) / 'profile'}",
                f"--virtual-time-budget={budget_ms}",
                "--dump-dom",
                page.as_uri(),
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    if result.returncode != 0:
        raise EngineDriverError(f"chromium exited {result.returncode}: {result.stderr[-500:]}")
    return result.stdout


def read_state(dom: str) -> dict:
    import html as htmllib

    match = STATE_RE.search(dom)
    if not match:
        raise EngineDriverError('page wrote no <pre id="engine-state">')
    return json.loads(htmllib.unescape(match.group(1)))


def render(html: str, **kwargs) -> dict:
    return read_state(dump_dom(html, **kwargs))
