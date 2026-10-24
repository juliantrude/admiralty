"""MCP server tests: the Campaign service and the tool wiring, on the reference saves."""

from __future__ import annotations

import asyncio
import json
import os
import time

import pytest
from conftest import SAVES_DIR, VULKAN, reference_save

from hlidskjalf.mcp.server import build_server
from hlidskjalf.mcp.service import CampaignService
from hlidskjalf.workspace.config import CampaignConfig, SetupMissing
from hlidskjalf.workspace.turnlog import TURN_LOG

pytestmark = pytest.mark.saves


@pytest.fixture(scope="module")
def save_dir():
    reference_save(VULKAN, "2259.12.25.sav")  # skips when the saves are missing
    return SAVES_DIR / VULKAN


def make_service(tmp_path, save_dir, knowledge="fair_play") -> CampaignService:
    (tmp_path / "campaign.yaml").write_text(
        f"save_dir: {save_dir}\nempire: Plexxi\nmode: consulting\nknowledge: {knowledge}\n"
    )
    return CampaignService(CampaignConfig.load(tmp_path))


@pytest.fixture(scope="module")
def service(tmp_path_factory, save_dir) -> CampaignService:
    return make_service(tmp_path_factory.mktemp("workspace"), save_dir)


def test_setup_missing_is_explained(tmp_path, monkeypatch):
    monkeypatch.delenv("HLIDSKJALF_SAVE_DIR", raising=False)
    monkeypatch.delenv("HLIDSKJALF_EMPIRE", raising=False)
    with pytest.raises(SetupMissing, match="hlidskjalf:setup"):
        CampaignConfig.load(tmp_path)


def test_campaign_status_names_newest_save(service):
    status = service.campaign_status()
    newest = service.saves()[-1]
    assert status["save_file"] == newest.path.name
    assert status["tracked_empire"]["player"] == "Plexxi"
    assert status["game_version"] == "4.5.2"
    assert status["knowledge"] == "fair_play"


def test_old_save_asks_for_a_new_one(service, monkeypatch):
    monkeypatch.setattr(time, "time", lambda: service.newest().mtime + 11 * 60)
    status = service.campaign_status()
    assert status["save_is_stale"] is True
    assert any("save again" in w for w in status["warnings"])


def test_fresh_save_is_not_stale(service, monkeypatch):
    monkeypatch.setattr(time, "time", lambda: service.newest().mtime + 60)
    assert "save_is_stale" not in service.campaign_status()


def test_older_save_by_date(service):
    overview = service.empire_overview("2259.12.25")
    assert overview["date"] == "2259.12.29"
    assert overview["naval_capacity"]["used"] == 195


def test_planet_by_name_and_unknown_planet(service):
    result = service.planet("2", save="2259.12.25")
    assert [p["system"] for p in result["planets"]] == ["Astarte"]
    assert result["planets"][0]["jobs"]
    with pytest.raises(LookupError, match="Planets:"):
        service.planet("Nowhere", save="2259.12.25")


def test_fair_play_hides_full_facts(service, tmp_path, save_dir):
    fair = service.military("2259.12.25")
    assert all("full" not in e for e in fair["known_empires"])
    god = make_service(tmp_path, save_dir, knowledge="god_mode").military("2259.12.25")
    assert all("full" in e for e in god["known_empires"])


def test_compare_two_saves(service):
    diff = service.compare("2220.04.22", "2259.12.25")
    assert (diff["from"], diff["to"]) == ("2220.04.26", "2259.12.29")


def test_timeline_range(service):
    events = service.timeline(since="2230.01.01", until="2240.01.01", save="2259.12.25")["events"]
    assert events and all("2230.01.01" <= e["date"] <= "2240.01.01" for e in events)


def call(server, tool, args=None):
    result = asyncio.run(server.call_tool(tool, args or {}))
    return json.loads(result.content[0].text)


def test_tools_log_every_result(tmp_path, save_dir, monkeypatch):
    monkeypatch.setenv("HLIDSKJALF_SAVE_DIR", str(save_dir))
    monkeypatch.setenv("HLIDSKJALF_EMPIRE", "Plexxi")
    server = build_server(tmp_path)
    tools = {t.name: t for t in asyncio.run(server.list_tools())}
    assert set(tools) == {
        "campaign_status", "empire_overview", "planets", "planet", "economy",
        "military", "progression", "timeline", "compare", "expand_graph",
    }  # fmt: skip
    assert "svc" not in json.dumps(tools["planet"].input_schema)

    economy = call(server, "economy", {"save": "2259.12.25"})
    assert economy["resources"]["energy"]["label"] == "Energy Credits"
    missing = call(server, "planet", {"name": "Nowhere", "save": "2259.12.25"})
    assert "error" in missing

    log = (tmp_path / ".hlidskjalf" / TURN_LOG).read_text().splitlines()
    entries = [json.loads(line) for line in log]
    assert [e["tool"] for e in entries] == ["economy", "planet"]
    assert entries[0]["args"] == {"save": "2259.12.25"}
    assert entries[0]["result"] == economy


def graph_server(tmp_path, save_dir, monkeypatch):
    monkeypatch.setenv("HLIDSKJALF_SAVE_DIR", str(save_dir))
    monkeypatch.setenv("HLIDSKJALF_EMPIRE", "Plexxi")
    return build_server(tmp_path)


def log_entries(workspace):
    lines = (workspace / ".hlidskjalf" / TURN_LOG).read_text().splitlines()
    return [json.loads(line) for line in lines]


def test_expand_graph_tool_is_listed_with_its_schema(tmp_path, save_dir, monkeypatch):
    tools = {
        t.name: t for t in asyncio.run(graph_server(tmp_path, save_dir, monkeypatch).list_tools())
    }
    schema = tools["expand_graph"].input_schema
    assert set(schema["properties"]) == {"goals", "crisis_goals", "save"}
    assert not schema.get("required")
    assert "svc" not in json.dumps(schema)


def test_expand_graph_catalogue_then_expansion_with_turn_log_id(tmp_path, save_dir, monkeypatch):
    server = graph_server(tmp_path, save_dir, monkeypatch)
    catalogue = call(server, "expand_graph", {"save": "2259.12.25"})
    assert "expansion_id" not in catalogue and "nodes" not in catalogue
    goals = {g["id"]: g for g in catalogue["goals"]}
    assert len(goals) >= 13
    unity = goals["unity.more"]
    assert unity["domain"] == "unity" and unity["title"]
    assert {s["metric"] for s in unity["symptoms"]} == {"unity.net", "traditions.next_cost"}
    assert all(s["value"] is not None for s in unity["symptoms"])

    expansion = call(
        server,
        "expand_graph",
        {"goals": ["unity.more"], "crisis_goals": ["unity.more"], "save": "2259.12.25"},
    )
    assert expansion["goals"][0]["crisis"] is True
    assert expansion["nodes"] and expansion["key_action_candidates"]
    assert expansion["date"] == catalogue["date"]

    entries = log_entries(tmp_path)
    assert [e["tool"] for e in entries] == ["expand_graph", "expand_graph"]
    assert expansion["expansion_id"] == 2  # the line number of its own turn-log entry
    assert entries[1]["result"] == expansion
    assert entries[1]["args"] == {
        "goals": ["unity.more"],
        "crisis_goals": ["unity.more"],
        "save": "2259.12.25",
    }


def test_expand_graph_result_stays_in_budget_for_several_goals(tmp_path, save_dir, monkeypatch):
    server = graph_server(tmp_path, save_dir, monkeypatch)
    goals = ["unity.more", "naval_capacity.more", "energy.more"]
    catalogue = call(server, "expand_graph", {"save": "2259.12.25"})
    assert set(goals) <= {g["id"] for g in catalogue["goals"]}
    result = call(server, "expand_graph", {"goals": goals, "save": "2259.12.25"})
    assert len(json.dumps(result)) <= 41_000, "over the budget: see Expansion.to_dict"


def test_expand_graph_errors_are_answers_not_crashes(tmp_path, save_dir, monkeypatch):
    server = graph_server(tmp_path, save_dir, monkeypatch)
    unknown = call(server, "expand_graph", {"goals": ["nope.more"], "save": "2259.12.25"})
    assert "nope.more" in unknown["error"] and "unity.more" in unknown["error"]
    assert "expansion_id" not in unknown
    assert [e["result"] for e in log_entries(tmp_path)] == [unknown]


def test_expand_graph_without_a_pack_for_the_version_is_an_error(service, monkeypatch):
    from hlidskjalf.graph.mechanics import GraphMissing

    doc = service.document(service.find("2259.12.25"))
    monkeypatch.setitem(doc["header"], "game_version", "9.9.9")
    with pytest.raises(GraphMissing, match="no knowledge pack for v9.9.9"):
        service.expand_graph(["unity.more"], save="2259.12.25")


def test_tools_explain_missing_setup(tmp_path, monkeypatch):
    monkeypatch.delenv("HLIDSKJALF_SAVE_DIR", raising=False)
    monkeypatch.delenv("HLIDSKJALF_EMPIRE", raising=False)
    assert "hlidskjalf:setup" in call(build_server(tmp_path), "campaign_status")["error"]


def test_env_overrides_do_not_leak():
    assert "HLIDSKJALF_EMPIRE" not in os.environ
