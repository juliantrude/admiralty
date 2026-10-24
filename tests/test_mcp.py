"""MCP server tests: the Campaign service and the tool wiring, on the reference saves."""

from __future__ import annotations

import asyncio
import json
import os
import time

import pytest
from conftest import SAVES_DIR, VULKAN, reference_save

from hlidskjalf.mcp.server import build_server
from hlidskjalf.mcp.service import TURN_LOG, CampaignService
from hlidskjalf.workspace.config import CampaignConfig, SetupMissing

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
        "military", "progression", "timeline", "compare",
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


def test_tools_explain_missing_setup(tmp_path, monkeypatch):
    monkeypatch.delenv("HLIDSKJALF_SAVE_DIR", raising=False)
    monkeypatch.delenv("HLIDSKJALF_EMPIRE", raising=False)
    assert "hlidskjalf:setup" in call(build_server(tmp_path), "campaign_status")["error"]


def test_env_overrides_do_not_leak():
    assert "HLIDSKJALF_EMPIRE" not in os.environ
