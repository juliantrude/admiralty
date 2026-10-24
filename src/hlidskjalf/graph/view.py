"""`hlidskjalf briefing view`: look at a Solution Graph locally, publishing nothing.

The bundled page (engine/dist/index.html) and a copy of the JSON go into a temp directory that a stdlib
HTTP server serves from 127.0.0.1 only (docs/plans/M6.md). The page finds the JSON as its sibling
`solution-graph.json`.
"""

from __future__ import annotations

import functools
import json
import shutil
import tempfile
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BUNDLE = Path(__file__).resolve().parents[3] / "engine" / "dist" / "index.html"
LOOPBACK = "127.0.0.1"


class ViewUnavailable(Exception):
    pass


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass


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


def make_server(directory: Path, port: int = 0) -> ThreadingHTTPServer:
    """A server for `directory` on 127.0.0.1 (`port` 0 = a random free port)."""
    handler = functools.partial(_QuietHandler, directory=str(directory))
    return ThreadingHTTPServer((LOOPBACK, port), handler)


def serve(solution_graph: Path, port: int = 0, bundle: Path = BUNDLE) -> None:
    """Prepare, print the URL and serve until interrupted."""
    with tempfile.TemporaryDirectory(prefix="hlidskjalf-view-") as tmp:
        prepare(solution_graph, Path(tmp), bundle)
        with make_server(Path(tmp), port) as server:
            print(f"http://{LOOPBACK}:{server.server_address[1]}/index.html", flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
