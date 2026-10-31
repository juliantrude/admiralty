"""`admiralty briefing view`: look at a Solution Graph locally, publishing nothing.

The bundled page (engine/dist/index.html) goes into a temp directory that a stdlib HTTP server
serves from 127.0.0.1 only (docs/plans/M6.md). The page finds the JSON as its sibling
`solution-graph.json`, which the server reads from the Solution Graph file on every request: a
reload shows the Briefing as it is now.

`show_current` is what `admiralty briefing compose` calls after it published a Briefing: it
starts one such server per workspace, detached and ended by an idle timeout, and opens the
page in the browser (docs/proposals/ops.md entry 7). The Python core does this itself, not
Claude Code (ADR 0004).
"""

from __future__ import annotations

import functools
import http.client
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

BUNDLE = Path(__file__).resolve().parents[3] / "engine" / "dist" / "index.html"
LOOPBACK = "127.0.0.1"


class ViewUnavailable(Exception):
    pass


GRAPH_URL_PATH = "/solution-graph.json"
IDLE_SECONDS = 4 * 3600  # a detached server ends after this long without a request
VIEW_STATE = "view.json"  # in the state directory of the workspace: pid, url, graph
NO_BROWSER_ENV = "ADMIRALTY_NO_BROWSER"  # set: compose starts no server and opens nothing


class _QuietHandler(SimpleHTTPRequestHandler):
    graph: Path | None = None  # the file behind /solution-graph.json, read on every request

    def log_message(self, format, *args):
        pass

    def handle(self):
        self.server.last_request = time.monotonic()
        super().handle()

    def translate_path(self, path):
        if self.graph is not None and urlsplit(path).path == GRAPH_URL_PATH:
            return str(self.graph)
        return super().translate_path(path)


def prepare(solution_graph: Path, directory: Path, bundle: Path = BUNDLE) -> None:
    """Copy the bundled page and the Solution Graph into `directory` (the JSON must parse)."""
    if not bundle.is_file():
        raise ViewUnavailable(f"bundled page missing: {bundle} (run tools/bundle_engine.py)")
    try:
        json.loads(solution_graph.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ViewUnavailable(f"cannot read solution graph {solution_graph}: {error}") from error
    shutil.copyfile(bundle, directory / "index.html")
    shutil.copyfile(solution_graph, directory / "solution-graph.json")


def make_server(directory: Path, port: int = 0, graph: Path | None = None) -> ThreadingHTTPServer:
    """A server for `directory` on 127.0.0.1 (`port` 0 = a random free port). With `graph`, the
    page's `solution-graph.json` is read from that file at every request."""
    handler = type("_Handler", (_QuietHandler,), {"graph": graph})
    server = ThreadingHTTPServer(
        (LOOPBACK, port), functools.partial(handler, directory=str(directory))
    )
    server.last_request = time.monotonic()
    return server


def serve(
    solution_graph: Path,
    port: int = 0,
    bundle: Path = BUNDLE,
    open_browser: bool = False,
    idle_seconds: float | None = None,
) -> None:
    """Prepare, print the URL and serve until interrupted (or, with `idle_seconds`, until that
    long has passed without a request)."""
    with tempfile.TemporaryDirectory(prefix="admiralty-view-") as tmp:
        prepare(solution_graph, Path(tmp), bundle)
        with make_server(Path(tmp), port, graph=solution_graph.resolve()) as server:
            url = f"http://{LOOPBACK}:{server.server_address[1]}/index.html"
            print(url, flush=True)
            if open_browser:
                _open(url)
            try:
                if idle_seconds is None:
                    server.serve_forever()
                else:
                    server.timeout = min(30.0, idle_seconds)
                    while time.monotonic() - server.last_request < idle_seconds:
                        server.handle_request()
            except KeyboardInterrupt:
                pass


def _open(url: str) -> bool:
    try:
        return webbrowser.open(url)
    except webbrowser.Error:
        return False


def show_current(workspace: Path, graph: Path, idle_seconds: float = IDLE_SECONDS) -> dict:
    """Make the page for `graph` (the current Briefing) available and open it in the browser.
    A server that still runs for this workspace is used again, since it reads the file afresh;
    otherwise a detached one is started. Never raises: a machine without a browser or without
    the bundled page gets `opened: False` and, if there is one, the URL to open by hand."""
    if os.environ.get(NO_BROWSER_ENV):
        return {"url": None, "opened": False}
    state_file = workspace / ".admiralty" / VIEW_STATE
    url = _running_url(state_file, graph)
    if url is None:
        url = _start_detached(graph, idle_seconds)
        if url is not None:
            state_file.parent.mkdir(parents=True, exist_ok=True)
            state_file.write_text(json.dumps({"url": url, "graph": str(graph.resolve())}))
    return {"url": url, "opened": url is not None and _open(url)}


def _running_url(state_file: Path, graph: Path) -> str | None:
    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
        if state["graph"] != str(graph.resolve()):
            return None
        parts = urlsplit(state["url"])
        connection = http.client.HTTPConnection(parts.hostname, parts.port, timeout=2)
        try:
            connection.request("GET", GRAPH_URL_PATH)
            alive = connection.getresponse().status == 200
        finally:
            connection.close()
        return state["url"] if alive else None
    except OSError, ValueError, KeyError, http.client.HTTPException:
        return None


def _start_detached(graph: Path, idle_seconds: float) -> str | None:
    """`admiralty briefing view` in a process of its own; its first output line is the URL."""
    command = [
        sys.executable, "-m", "admiralty.cli", "briefing", "view", str(graph),
        "--idle-timeout", str(idle_seconds),
    ]  # fmt: skip
    try:
        child = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            text=True,
        )
    except OSError:
        return None
    line = child.stdout.readline().strip()  # EOF at once when the child refused to start
    child.stdout.close()
    return line if line.startswith("http://") else None
