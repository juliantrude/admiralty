"""`briefing compose` opens the current Briefing in the browser (docs/proposals/ops.md entry 7)."""

from __future__ import annotations

import http.client
import json
import time
import webbrowser
from urllib.parse import urlsplit

import pytest
from test_engine_encodings import rich_graph

from admiralty.graph import view


@pytest.fixture
def opened(monkeypatch):
    urls = []
    monkeypatch.setattr(webbrowser, "open", lambda url: urls.append(url) or True)
    monkeypatch.delenv(view.NO_BROWSER_ENV)
    return urls


def _status(url: str, path: str) -> int | None:
    parts = urlsplit(url)
    connection = http.client.HTTPConnection(parts.hostname, parts.port, timeout=3)
    try:
        connection.request("GET", path)
        return connection.getresponse().status
    except OSError:
        return None
    finally:
        connection.close()


def _graph(workspace):
    graph = workspace / "briefings" / "current" / "solution-graph.json"
    graph.parent.mkdir(parents=True)
    graph.write_text(json.dumps(rich_graph()), encoding="utf-8")
    return graph


def test_nothing_starts_when_the_environment_says_no_browser(tmp_path, monkeypatch):
    graph = _graph(tmp_path)
    monkeypatch.setattr(webbrowser, "open", lambda url: pytest.fail("opened a browser"))
    assert view.show_current(tmp_path, graph) == {"url": None, "opened": False}
    assert not (tmp_path / ".admiralty").exists()


def test_a_detached_server_shows_the_page_and_is_used_again(tmp_path, opened):
    graph = _graph(tmp_path)
    first = view.show_current(tmp_path, graph, idle_seconds=4)  # ends by itself soon after
    assert first["opened"] and opened == [first["url"]]
    assert first["url"].startswith("http://127.0.0.1:")
    assert _status(first["url"], "/index.html") == 200
    assert _status(first["url"], "/solution-graph.json") == 200
    second = view.show_current(tmp_path, graph, idle_seconds=4)
    assert second["url"] == first["url"] and opened == [first["url"]] * 2


def test_the_detached_server_ends_after_the_idle_time(tmp_path, opened):
    graph = _graph(tmp_path)
    url = view.show_current(tmp_path, graph, idle_seconds=2)["url"]
    assert _status(url, "/index.html") == 200
    time.sleep(6)  # no request meanwhile: every request, even a probe, would restart the idle time
    assert _status(url, "/index.html") is None


def test_a_dead_server_in_the_state_file_is_replaced(tmp_path, opened):
    graph = _graph(tmp_path)
    state = tmp_path / ".admiralty" / view.VIEW_STATE
    state.parent.mkdir()
    state.write_text(json.dumps({"url": "http://127.0.0.1:1/index.html", "graph": str(graph)}))
    result = view.show_current(tmp_path, graph, idle_seconds=2)
    assert result["url"] != "http://127.0.0.1:1/index.html"
    assert json.loads(state.read_text())["url"] == result["url"]


def test_a_machine_without_a_browser_still_gets_the_url(tmp_path, monkeypatch):
    graph = _graph(tmp_path)
    monkeypatch.delenv(view.NO_BROWSER_ENV)
    monkeypatch.setattr(webbrowser, "open", lambda url: False)
    result = view.show_current(tmp_path, graph, idle_seconds=2)
    assert result["opened"] is False and result["url"].startswith("http://")


def test_an_unreadable_graph_does_not_fail_the_briefing(tmp_path, opened):
    graph = _graph(tmp_path)
    graph.write_text("not json", encoding="utf-8")  # the child refuses to serve it
    assert view.show_current(tmp_path, graph, idle_seconds=2) == {"url": None, "opened": False}
    assert opened == []
