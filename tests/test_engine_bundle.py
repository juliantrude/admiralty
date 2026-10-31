"""Bundle (tools/bundle_engine.py), `briefing view` and "the model never writes HTML" (M6 step 5)."""

from __future__ import annotations

import http.client
import json
import re
import subprocess
import sys
import threading
from pathlib import Path

import engine_driver as driver
import pytest
from test_engine_encodings import rich_graph
from test_engine_page import needs_browser

from admiralty.cli import main
from admiralty.graph import view

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import bundle_engine  # noqa: E402


def test_the_bundle_is_the_same_on_every_run():
    assert bundle_engine.bundle() == bundle_engine.bundle()


def test_the_committed_bundle_is_not_stale():
    committed = (ROOT / "engine" / "dist" / "index.html").read_text(encoding="utf-8")
    assert committed == bundle_engine.bundle(), "run: uv run python tools/bundle_engine.py"
    assert bundle_engine.main(["--check"]) == 0


def test_the_bundle_is_one_file_with_the_cdn_tags_and_no_local_path():
    html = bundle_engine.bundle()
    assert 'href="engine.css"' not in html and 'src="engine.js"' not in html
    assert '<script id="engine-script">' in html and "<style>" in html
    assert driver.script_pin_problems(html) == []
    assert html.count("<script src=") == 3  # only the pinned libraries remain external
    for local in (str(ROOT), str(Path.home()), "/home/", "/tmp/", "C:\\"):
        assert local not in html


def test_the_bundler_refuses_a_closing_tag_inside_the_script(tmp_path):
    for name in ("index.html", "engine.css", "engine.js"):
        (tmp_path / name).write_text((ROOT / "engine" / name).read_text(encoding="utf-8"))
    (tmp_path / "engine.js").write_text('const s = "</script>";', encoding="utf-8")
    with pytest.raises(SystemExit, match="breaks inlining"):
        bundle_engine.bundle(tmp_path)


@needs_browser
def test_the_bundled_page_gives_the_same_engine_state_as_the_unbundled_page(tmp_path):
    graph = rich_graph()
    bundled = tmp_path / "index.html"
    bundled.write_text(bundle_engine.bundle(), encoding="utf-8")
    assert driver.render_engine(graph, index=bundled) == driver.render_engine(graph)


@needs_browser
def test_the_driver_hooks_into_the_bundle_too(tmp_path):
    bundled = tmp_path / "index.html"
    bundled.write_text(bundle_engine.bundle(), encoding="utf-8")
    dom = driver.engine_dom(
        rich_graph(), index=bundled, after_ready='AdmiraltyEngine.click("energy.more")'
    )
    assert driver.read_state(dom)["selected"] == ["energy.more"]


@pytest.fixture
def running_view(tmp_path):
    graph = tmp_path / "solution-graph.json"
    graph.write_text(json.dumps(rich_graph()), encoding="utf-8")
    served = tmp_path / "served"
    served.mkdir()
    view.prepare(graph, served)
    (tmp_path / "secret.txt").write_text("outside", encoding="utf-8")
    server = view.make_server(served)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server, graph
    server.shutdown()
    server.server_close()


def _get(server, path: str) -> tuple[int, bytes]:
    connection = http.client.HTTPConnection(*server.server_address, timeout=10)
    connection.request("GET", path)
    response = connection.getresponse()
    body = response.read()
    connection.close()
    return response.status, body


def test_view_serves_the_page_and_the_json_on_loopback_only(running_view):
    server, graph = running_view
    assert server.server_address[0] == "127.0.0.1"
    assert server.server_address[1] != 0
    status, body = _get(server, "/index.html")
    assert status == 200 and b'id="engine-script"' in body
    status, body = _get(server, "/solution-graph.json")
    assert status == 200 and body == graph.read_bytes()


def test_view_reads_the_graph_file_afresh_on_every_request(tmp_path):
    graph = tmp_path / "solution-graph.json"
    graph.write_text('{"v": 1}', encoding="utf-8")
    served = tmp_path / "served"
    served.mkdir()
    view.prepare(graph, served)
    server = view.make_server(served, graph=graph)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        assert _get(server, "/solution-graph.json") == (200, b'{"v": 1}')
        graph.write_text('{"v": 2}', encoding="utf-8")
        assert _get(server, "/solution-graph.json") == (200, b'{"v": 2}')
        assert _get(server, "/solution-graph.json?x=1")[1] == b'{"v": 2}'
    finally:
        server.shutdown()
        server.server_close()


def test_view_refuses_a_path_outside_the_directory(running_view):
    server, _ = running_view
    for path in ("/../secret.txt", "/%2e%2e/secret.txt", "/..%2fsecret.txt", "//etc/passwd"):
        status, body = _get(server, path)
        assert status in (301, 400, 403, 404), path
        assert b"outside" not in body and b"root:" not in body, path


def test_view_refuses_what_is_not_a_solution_graph_or_has_no_bundle(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("not json", encoding="utf-8")
    with pytest.raises(view.ViewUnavailable, match="cannot read"):
        view.prepare(bad, tmp_path)
    good = tmp_path / "good.json"
    good.write_text("{}", encoding="utf-8")
    with pytest.raises(view.ViewUnavailable, match="bundled page missing"):
        view.prepare(good, tmp_path, bundle=tmp_path / "nope.html")


def test_the_cli_command_exists_and_reports_a_missing_file(tmp_path, capsys):
    assert main(["briefing", "view", str(tmp_path / "missing.json")]) == 1
    assert "cannot read" in capsys.readouterr().err


@needs_browser
def test_the_bundled_page_served_by_view_reads_the_sibling_json(running_view, tmp_path):
    server, _ = running_view
    host, port = server.server_address
    result = subprocess.run(
        [
            driver.CHROMIUM,
            "--headless=new",
            "--no-sandbox",
            "--disable-gpu",
            "--user-data-dir=" + str(tmp_path / "profile"),
            "--virtual-time-budget=20000",
            "--dump-dom",
            f"http://{host}:{port}/index.html",
        ],
        capture_output=True,
        text=True,
        timeout=90,
    )
    # The CDN is reachable from the page only when the machine is online; the sibling fetch is what we test.
    assert 'id="engine-state"' in result.stdout


# --- the model never writes HTML ------------------------------------------------------------------

SKILLS = sorted((ROOT / "skills").glob("*/SKILL.md"))


def test_there_are_skills_to_check():
    assert {path.parent.name for path in SKILLS} >= {"ops", "setup"}


@pytest.mark.parametrize("skill", SKILLS, ids=lambda p: p.parent.name)
def test_no_skill_tells_the_model_to_write_html_js_or_css(skill):
    text = skill.read_text(encoding="utf-8")
    for line in text.splitlines():
        lowered = line.lower()
        denies = re.search(r"\b(never|no|not|don't|nothing)\b", lowered)
        names_page = re.search(r"\.(html|js|css)\b|<html|<script|<style", lowered)
        asks_to_write = re.search(r"\b(write|create|save|generate|produce|output)\b", lowered)
        assert not (names_page and asks_to_write and not denies), f"{skill}: {line}"


def test_the_consult_skill_writes_only_the_overlay_and_runs_only_the_two_commands():
    text = (ROOT / "skills" / "ops" / "SKILL.md").read_text(encoding="utf-8")
    assert "It is the only file you write by hand." in text
    assert "You never write HTML" in text
    commands = set(re.findall(r"admiralty (\w+(?: [\w-]+)?)", text))
    assert {"briefing compose", "graph check-solution"} <= commands
    assert "briefing view" not in text, "the consult skill does not open the page (plan M6)"
    assert len(re.findall(r"`overlay\.json`|overlay\.json", text)) >= 1
    for forbidden in ("index.html", "engine.js", "engine.css", "dist/"):
        assert forbidden not in text


def test_nothing_in_compose_or_the_schema_accepts_html():
    schema = (ROOT / "src" / "admiralty" / "graph" / "solution.schema.json").read_text()
    assert not re.search(r'"(html|markup|script|style|svg)"\s*:', schema, re.I)
    from admiralty.graph.solution import _OVERLAY_KEYS

    assert not {"html", "markup", "script", "style", "svg"} & set(_OVERLAY_KEYS)
