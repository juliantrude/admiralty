"""The `retrospective` tool: assembly, budget, Fair Play, Consulting versus Coaching, the turn log,
and the Unverified Claim check over a figure taken from the result. Synthetic archives only."""

from __future__ import annotations

import asyncio
import json

import pytest
from test_muninn_series import doc

from hlidskjalf.claims.check import check_answer
from hlidskjalf.claims.evidence import build_evidence, read_turn_log
from hlidskjalf.mcp.server import build_server
from hlidskjalf.mcp.service import CampaignService, SaveRef
from hlidskjalf.muninn.frame import load_campaign, resolve_frame
from hlidskjalf.muninn.result import build_result
from hlidskjalf.workspace.archive import Archive
from hlidskjalf.workspace.config import CampaignConfig
from hlidskjalf.workspace.turnlog import TURN_LOG

TIMELINE = [{"date": "2230.07.17", "event": "War Declared", "involves": ["Vulkan"]}]


def documents(version="4.5.2"):
    return [
        doc("2200.01.01", planets=2, pops=100, military=1000, game_version=version),
        doc("2220.04.26", planets=4, pops=150, military=1200, game_version=version),
        doc("2245.01.23", planets=5, pops=200, military=800, wars=["War A"], timeline=TIMELINE,
            game_version=version),
        doc("2259.12.29", planets=5, pops=260, military=900, timeline=TIMELINE,
            game_version=version),
    ]  # fmt: skip


def workspace(tmp_path, docs=None, mode="consulting", knowledge="fair_play", saves=True):
    saves_dir = tmp_path / "saves"
    saves_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / "campaign.yaml").write_text(
        f"save_dir: {saves_dir}\nempire: Anna\nmode: {mode}\nknowledge: {knowledge}\n"
    )
    archive = Archive(tmp_path)
    for index, d in enumerate(documents() if docs is None else docs):
        archive.store(d, 100.0 + index)
    return CampaignService(CampaignConfig.load(tmp_path))


def call(server, tool, args=None):
    return json.loads(asyncio.run(server.call_tool(tool, args or {})).content[0].text)


def server_in(tmp_path, monkeypatch, **kwargs):
    workspace(tmp_path, **kwargs)
    monkeypatch.delenv("HLIDSKJALF_SAVE_DIR", raising=False)
    monkeypatch.delenv("HLIDSKJALF_EMPIRE", raising=False)
    return build_server(tmp_path)


# --- the result ------------------------------------------------------------------------------


def test_the_result_holds_every_part_the_plan_names(tmp_path):
    result = workspace(tmp_path).retrospective("all")
    assert set(result) == {
        "frame", "series", "intervals", "timeline", "epoch_candidates", "findings", "goals",
        "warnings",
    }  # fmt: skip
    frame = result["frame"]
    assert (frame["from"], frame["to"], frame["request"]) == ("2200.01.01", "2259.12.29", "all")
    assert frame["dates"] == ["2200.01.01", "2220.04.26", "2245.01.23", "2259.12.29"]
    assert frame["span_years"] == 59.99
    assert frame["campaign"] == "vulkan" and frame["tracked_empire"]["name"] == "Die Borg"
    assert (frame["mode"], frame["knowledge"]) == ("consulting", "fair_play")
    assert frame["problems"] == [] and frame["timeline_complete"] is True
    assert [p["date"] for p in result["series"]] == frame["dates"]
    assert result["series"][-1]["values"]["pops"] == 260
    first = result["intervals"][0]
    assert (first["from"], first["to"], first["years"]) == ("2200.01.01", "2220.04.26", 20.32)
    assert first["values"]["pops"] == {"from": 100, "to": 150, "change": 50, "change_pct": 50.0}
    assert result["timeline"] == {"events": TIMELINE, "before_frame": 0}
    assert {c["date"] for c in result["epoch_candidates"]} >= {"2230.07.17", "2200.01.01"}
    assert result["findings"]


def test_the_default_frame_is_the_last_two_dates_and_says_so(tmp_path):
    frame = workspace(tmp_path).retrospective()["frame"]
    assert (frame["from"], frame["to"], frame["request"]) == ("2245.01.23", "2259.12.29", "last")
    assert frame["dates"] == ["2245.01.23", "2259.12.29"]


def test_timeline_events_before_the_frame_are_counted(tmp_path):
    timeline = workspace(tmp_path).retrospective()["timeline"]
    assert timeline == {"events": [], "before_frame": 1}  # 2230.07.17 lies before 2245.01.23


def test_fewer_than_two_archived_dates_is_an_error_that_says_how_many(tmp_path):
    service = workspace(tmp_path, docs=documents()[:1])
    with pytest.raises(ValueError, match=r"only 2200\.01\.01.*read another save"):
        service.retrospective()


def test_corrupt_archive_files_are_listed_and_not_fatal(tmp_path):
    service = workspace(tmp_path)
    (service.archive.extracts / "2240.01.01.json.zst").write_bytes(b"not zstd")
    result = service.retrospective("all")
    assert any("2240.01.01" in problem for problem in result["frame"]["problems"])
    assert len(result["frame"]["dates"]) == 4


# --- Fair Play, Consulting and Coaching -------------------------------------------------------


def test_fair_play_hides_full_facts_and_god_mode_shows_them(tmp_path):
    fair = workspace(tmp_path / "fair").retrospective("all")
    god = workspace(tmp_path / "god", knowledge="god_mode").retrospective("all")
    assert all("full" not in e for p in fair["series"] for e in p["known_empires"])
    assert all("full" in e for p in god["series"] for e in p["known_empires"])
    assert "full" not in json.dumps(fair["intervals"])
    assert god["frame"]["knowledge"] == "god_mode"


def test_consulting_has_the_symptoms_of_every_goal_at_both_ends(tmp_path):
    goals = workspace(tmp_path).retrospective("all")["goals"]
    assert (goals["from"], goals["to"], goals["version"]) == ("2200.01.01", "2259.12.29", "v4.5.2")
    ids = {g["id"] for g in goals["goals"]}
    assert {"unity.more", "naval_capacity.more"} <= ids
    unity = next(g for g in goals["goals"] if g["id"] == "unity.more")
    assert unity["title"] and unity["domain"] == "unity"
    assert {s["metric"] for s in unity["symptoms"]} == {"unity.net", "traditions.next_cost"}
    assert all({"from", "to"} <= set(s) for g in goals["goals"] for s in g["symptoms"])


def test_coaching_has_no_goals_at_all(tmp_path):
    result = workspace(tmp_path, mode="coaching").retrospective("all")
    assert "goals" not in result
    assert result["frame"]["mode"] == "coaching"


def test_a_missing_knowledge_pack_is_an_error_inside_goals_only(tmp_path):
    result = workspace(tmp_path, docs=documents("9.9.9")).retrospective("all")
    assert "no knowledge pack for v9.9.9" in result["goals"]["error"]
    assert result["series"] and result["intervals"] and result["epoch_candidates"]


# --- the newest save first, and no save at all ----------------------------------------------


def test_without_any_save_the_archive_alone_answers_and_says_so(tmp_path):
    result = workspace(tmp_path).retrospective()
    assert any("archive alone" in w and "2259.12.29" in w for w in result["warnings"])


def test_an_unknown_save_argument_is_an_error(tmp_path):
    with pytest.raises(FileNotFoundError, match="no save matching"):
        workspace(tmp_path).retrospective(save="1999.01.01")


def test_the_newest_save_is_read_and_archived_before_the_frame_is_resolved(tmp_path, monkeypatch):
    service = workspace(tmp_path, docs=documents()[:3])
    save = service.config.save_dir / "2259.12.25.sav"
    save.write_bytes(b"")
    ref = SaveRef(save, 500.0)
    monkeypatch.setattr(service, "find", lambda name: ref)

    def read(ref, planet_detail=False):
        newest = documents()[3]
        service._archive(ref, newest)  # what `document` does for every save it reads
        return newest

    monkeypatch.setattr(service, "document", read)
    result = service.retrospective()
    assert result["frame"]["to"] == "2259.12.29"
    assert not any("older than" in w for w in result["warnings"])


def test_a_save_older_than_the_newest_archived_date_is_read_and_warned_about(tmp_path, monkeypatch):
    service = workspace(tmp_path)
    save = service.config.save_dir / "2220.04.20.sav"
    save.write_bytes(b"")
    monkeypatch.setattr(service, "find", lambda name: SaveRef(save, 500.0))
    monkeypatch.setattr(service, "document", lambda ref, planet_detail=False: documents()[1])
    result = service.retrospective()
    assert result["frame"]["to"] == "2259.12.29"
    assert any("2220.04.26" in w and "older than the newest archived date 2259.12.29" in w
               for w in result["warnings"])  # fmt: skip


# --- the size budget --------------------------------------------------------------------------


def many(count):
    return [doc(f"{2200 + i // 12}.{i % 12 + 1:02d}.01", planets=2) for i in range(count)]


def built(docs, budget):
    archive_dir = {d["header"]["date"]: d for d in docs}
    from hlidskjalf.muninn.frame import Loaded

    loaded = Loaded(archive_dir, [])
    frame = resolve_frame(loaded.dates, "all")
    return build_result(loaded, frame, mode="coaching", god_mode=False, budget=budget)


def test_a_result_over_budget_loses_series_detail_of_interior_dates_and_says_so():
    docs = many(24)
    whole = built(docs, 10**9)
    size = len(json.dumps(whole, ensure_ascii=False))
    trimmed = built(docs, size - 1)
    assert len(trimmed["series"]) <= len(whole["series"])
    assert any("over" in w for w in trimmed["warnings"])
    squeezed = built(docs, size // 3)
    kept = [p["date"] for p in squeezed["series"]]
    assert kept[0] == "2200.01.01" and kept[-1] == whole["series"][-1]["date"]
    assert len(kept) < len(whole["series"])
    assert any("interior dates left out" in w for w in squeezed["warnings"])
    assert squeezed["intervals"] == whole["intervals"]  # every figure stays in the intervals


def test_a_result_within_budget_is_untouched():
    docs = many(8)
    assert built(docs, 10**9)["warnings"] == []


def test_a_hopeless_budget_warns_instead_of_failing():
    result = built(many(8), 100)
    assert any("shorter frame" in w for w in result["warnings"])


def test_the_reference_sized_result_fits_the_default_budget(tmp_path):
    result = workspace(tmp_path).retrospective("all")
    assert len(json.dumps(result, ensure_ascii=False)) < 40_000
    assert result["warnings"] == [w for w in result["warnings"] if "over" not in w]


# --- the tool ---------------------------------------------------------------------------------


def test_the_tool_is_listed_with_its_arguments(tmp_path, monkeypatch):
    server = server_in(tmp_path, monkeypatch)
    tools = {t.name: t for t in asyncio.run(server.list_tools())}
    assert "retrospective" in tools
    schema = tools["retrospective"].input_schema
    assert set(schema["properties"]) == {"since", "until", "save"}
    assert not schema.get("required")
    assert "svc" not in json.dumps(schema)


def test_the_tool_answers_and_logs_to_the_turn_log(tmp_path, monkeypatch):
    server = server_in(tmp_path, monkeypatch)
    result = call(server, "retrospective", {"since": "all", "until": "2250.01.01"})
    assert result["frame"]["to"] == "2245.01.23"
    lines = (tmp_path / ".hlidskjalf" / TURN_LOG).read_text().splitlines()
    entry = json.loads(lines[-1])
    assert entry["tool"] == "retrospective"
    assert entry["args"] == {"since": "all", "until": "2250.01.01"}
    assert entry["result"] == result


def test_a_frame_that_cannot_be_resolved_is_an_answer_not_a_crash(tmp_path, monkeypatch):
    server = server_in(tmp_path, monkeypatch, docs=documents()[:1])
    result = call(server, "retrospective")
    assert "needs two archived dates" in result["error"]
    entries = [
        json.loads(x) for x in (tmp_path / ".hlidskjalf" / TURN_LOG).read_text().splitlines()
    ]
    assert [e["result"] for e in entries] == [result]


def test_a_bad_date_is_an_answer_not_a_crash(tmp_path, monkeypatch):
    server = server_in(tmp_path, monkeypatch)
    assert "not an in-game date" in call(server, "retrospective", {"since": "gestern"})["error"]


# --- the Unverified Claim check over the result --------------------------------------------


def evidence_of(tmp_path, monkeypatch):
    server = server_in(tmp_path, monkeypatch)
    call(server, "retrospective", {"since": "all"})
    return build_evidence(read_turn_log(tmp_path))


def test_a_figure_from_the_result_passes_the_claim_check(tmp_path, monkeypatch):
    evidence = evidence_of(tmp_path, monkeypatch)
    answer = (
        "Zwischen 2200.01.01 und 2220.04.26 stieg die Zahl der Pops von 100 auf 150, "
        "das sind 50 % in 20.32 Jahren."
    )
    assert check_answer(answer, evidence).ok


def test_an_invented_figure_is_blocked(tmp_path, monkeypatch):
    evidence = evidence_of(tmp_path, monkeypatch)
    verdict = check_answer("Zwischen 2200 und 2220 wuchs die Bevölkerung um 4711 Pops.", evidence)
    assert not verdict.ok
    assert any(u.claim.text == "4711" for u in verdict.unverified)


def test_the_loader_and_the_tool_agree_on_the_dates(tmp_path):
    service = workspace(tmp_path)
    assert service.retrospective("all")["frame"]["dates"] == load_campaign(service.archive).dates
