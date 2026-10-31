"""Run engine pages in headless Chromium and read back what they wrote.

The page under test is copied to a temp directory next to engine/vendor/, and Chromium runs with name
resolution switched off: the page has to work offline (ADR 0004). The page reports its result in
`<pre id="engine-state">` as JSON; `render()` returns that JSON parsed.
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
VENDOR = ROOT / "engine" / "vendor"

CHROMIUM = next(
    (
        found
        for name in ("chromium", "chromium-browser", "google-chrome")
        if (found := shutil.which(name))
    ),
    None,
)
STATE_RE = re.compile(r'<pre id="engine-state"[^>]*>(.*?)</pre>', re.S)
# What would make a page load something: a script or stylesheet by URL, a CSS import, a url() that is not inline data.
LOAD_RE = re.compile(
    r"<script\b[^>]*\bsrc\s*=|<link\b[^>]*\bhref\s*=|@import\b|\burl\(\s*(?![\"']?data:)", re.I
)
ENGINE = ROOT / "engine"
ENGINE_FILES = ("engine.js", "engine.css")
GRAPH_SLOT = "<!-- solution-graph -->"


class EngineDriverError(RuntimeError):
    pass


def skip_reason() -> str | None:
    """Why headless tests cannot run here, or None."""
    return "no Chromium on PATH" if CHROMIUM is None else None


def external_loads(html: str) -> list[str]:
    """What a page would load from outside itself (files, URLs); a bundled page has none."""
    return [match.group(0) for match in LOAD_RE.finditer(html)]


def dump_dom(
    html: str, *, files: dict[str, str] | None = None, budget_ms: int = 20000, timeout: float = 90
) -> str:
    """Load `html` in headless Chromium without network and return the final DOM.

    `files` are written next to the page (name -> text), for the page's own script and style;
    engine/vendor/ is copied to `vendor/` for the unbundled page."""
    reason = skip_reason()
    if reason:
        raise EngineDriverError(reason)
    with tempfile.TemporaryDirectory(prefix="engine-") as tmp:
        page = Path(tmp) / "page.html"
        page.write_text(html, encoding="utf-8")
        shutil.copytree(VENDOR, Path(tmp) / "vendor")
        for name, text in (files or {}).items():
            (Path(tmp) / name).write_text(text, encoding="utf-8")
        result = subprocess.run(
            [
                CHROMIUM,
                "--headless=new",
                "--no-sandbox",
                "--disable-gpu",
                "--allow-file-access-from-files",
                "--host-resolver-rules=MAP * ~NOTFOUND",
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


def embed_graph(html: str, graph: dict | str | None) -> str:
    """Put the graph into the page's data source 1 (`<script id="solution-graph">`).

    A dict is dumped as JSON, a str goes in as it is (to test malformed data), None leaves the page
    without embedded data. `</` is escaped so that no text in the data can close the script element.
    """
    if graph is None:
        return html.replace(GRAPH_SLOT, "")
    text = graph if isinstance(graph, str) else json.dumps(graph, ensure_ascii=False)
    tag = (
        f'<script id="solution-graph" type="application/json">{text.replace("</", "<\\/")}</script>'
    )
    return html.replace(GRAPH_SLOT, tag)


def engine_dom(
    graph: dict | str | None, *, after_ready: str | None = None, index: Path | None = None, **kwargs
) -> str:
    """Render engine/index.html (or `index`) with `graph` embedded and return the final DOM.

    `after_ready` is JavaScript run once, right after the page's first layout (the page's `engine-ready`
    event), for clicking: it uses the page's own seams, e.g. `AdmiraltyEngine.click("id")`."""
    base = (index or ENGINE / "index.html").parent
    html = embed_graph((index or ENGINE / "index.html").read_text(encoding="utf-8"), graph)
    if after_ready:
        hook = (
            # no animation: headless Chromium runs animation frames unreliably, and the end state is what counts
            '<script id="driver-hook">window.admiraltyAnimationMs = 0;'
            'document.addEventListener("engine-ready", () => {'
            f"{after_ready}}}, {{once: true}});</script>"
        )
        # The unbundled page loads engine.js; the bundle has the same code inline as <script id="engine-script">.
        for engine_script in ('<script src="engine.js"></script>', '<script id="engine-script">'):
            if engine_script in html:
                html = html.replace(engine_script, hook + engine_script)
                break
        else:
            raise EngineDriverError("page has no engine script to hook in before")
    files = {
        name: (base / name).read_text(encoding="utf-8")
        for name in ENGINE_FILES
        if (base / name).exists()
    }
    return dump_dom(html, files=files, **kwargs)


def render_engine(graph: dict | str | None, **kwargs) -> dict:
    """Render engine/index.html (or `index`) with `graph` embedded and return its `engine-state`."""
    return read_state(engine_dom(graph, **kwargs))
