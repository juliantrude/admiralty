"""The Academy tools (M9, 20h): the Coach's calls on a Campaign service, through the MCP server and the CLI.

Synthetic pack and Snapshots on a stand-in for the Campaign service (no save needed); one run through the real
server on the vulkan mid save closes the file.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest
from conftest import MID, SAVES_DIR, VULKAN, reference_save
from test_academy_topics import ENERGY, NAVAL, extract, pack

from admiralty import cli
from admiralty.academy import drill, predictions
from admiralty.academy.tools import AcademyTools, NotCoaching, check_support
from admiralty.mcp.server import build_server
from admiralty.player import store
from admiralty.player.mastery import Refused
from admiralty.workspace.archive import Archive
from admiralty.workspace.config import CampaignConfig
from admiralty.workspace.turnlog import TURN_LOG

TITLE = "Few sources of naval capacity"
DESCRIPTION = "Capacity is a flat base plus additive sources."
FILL = {"path": "naval_capacity.used", "op": ">=", "value": 90}


class Campaign:
    """What `AcademyTools` needs of a `CampaignService`, on a synthetic pack and hand-made Snapshots."""

    def __init__(self, tmp_path, *, mode="coaching", knowledge="fair_play"):
        self.workspace = tmp_path / "workspace"
        self.workspace.mkdir()
        self.config = SimpleNamespace(
            workspace=self.workspace,
            mode=mode,
            knowledge=knowledge,
            god_mode=knowledge == "god_mode",
        )
        self.archive = Archive(self.workspace)
        self.graph_ = pack(tmp_path)
        self.docs: list[dict] = []
        self.academy = AcademyTools(self)
        self.add_snapshot()

    def add_snapshot(self, date="2259.12.25", **options):
        doc = extract(date=date, **options)
        doc["header"] = {
            "date": date,
            "campaign": "vulkan",
            "tracked_empire": {"country_id": 0, "name": "Plexxi"},
            "game_version": "4.5.2",
            "warnings": [],
        }
        self.docs.append(doc)
        self.archive.store(doc, 1.0)
        return doc

    def campaign_status(self):
        return {
            "save_file": f"{self.docs[-1]['header']['date']}.sav",
            "saved_minutes_ago": 1.0,
            "warnings": [],
        }

    def newest(self):
        return self.docs[-1]

    def document(self, ref):
        return ref

    def graph(self, version):
        return self.graph_

    def ingest(self):
        return []


@pytest.fixture
def campaign(tmp_path):
    return Campaign(tmp_path)


def start(campaign, goals=("naval_capacity.more",)):
    return campaign.academy.academy_open(list(goals))


def level_of(concept=NAVAL):
    return store.level_of(store.read_model(), concept)


# --- the Consulting Campaign ---------------------------------------------------------------------


def test_every_tool_is_an_error_in_a_consulting_campaign(tmp_path):
    academy = Campaign(tmp_path, mode="consulting").academy
    calls = [
        lambda: academy.academy_open(["naval_capacity.more"]),
        lambda: academy.academy_attempt("miss"),
        lambda: academy.academy_next(),
        lambda: academy.academy_escape("x"),
        lambda: academy.academy_close("x"),
        lambda: academy.prediction_add("war", "It ends fast."),
        lambda: academy.prediction_check(),
        lambda: academy.rendezvous_set("2262.01.01"),
        lambda: academy.player_model(),
    ]
    for call in calls:
        with pytest.raises(NotCoaching, match="Consulting"):
            call()
    assert not (academy.service.workspace / "academy").exists()


# --- opening -------------------------------------------------------------------------------------


def test_without_goals_the_answer_lists_the_goals_and_opens_nothing(campaign):
    result = campaign.academy.academy_open()
    assert result["needs_goals"] and result["drill"] is None
    assert {
        "id": "naval_capacity.more",
        "domain": "naval_capacity",
        "title": "More naval capacity",
    } in result["goals"]
    assert drill.load(campaign.workspace) is None


def test_the_first_topic_has_neither_the_cause_nor_the_answer(campaign):
    result = start(campaign)
    topic = result["topic"]
    assert topic["ladder"] == 1 and topic["status"] == "current" and topic["asks_for"] == "cause"
    assert "concept" not in topic and "answer" not in topic
    assert result["continued"] is False and result["waiting"] == 0 and result["count"] == 1
    everything = json.dumps(result)
    for secret in (NAVAL, TITLE, DESCRIPTION, "adopt_supremacy", "Supremacy tradition"):
        assert secret not in everything
    assert result["knowledge"] == "fair_play" and result["rendezvous"] == {"position": "none"}


def test_an_unknown_goal_alone_is_an_error(campaign):
    with pytest.raises(ValueError, match="at least one Goal"):
        campaign.academy.academy_open(["nope.more"])


def test_nothing_to_ask_opens_no_drill(campaign):
    store.append("level", concept=NAVAL, level="evaluate", previous="new", reason="test")
    result = start(campaign)
    assert result["nothing_to_ask"] and result["drill"] is None
    assert result["skipped"]["mastered"] == 1 and drill.load(campaign.workspace) is None


def test_a_second_open_continues_the_drill_and_names_a_newer_save(campaign):
    start(campaign)
    again = campaign.academy.academy_open(
        ["energy.more"]
    )  # the goals of a running Drill do not count
    assert again["continued"] is True and again["topic"]["ladder"] == 1
    assert "newer_save" not in again
    campaign.add_snapshot("2260.03.25")
    newer = campaign.academy.academy_open()
    assert newer["continued"] is True
    assert newer["newer_save"] == {"in_game_date": "2260.03.25", "drill_date": "2259.12.25"}
    assert newer["in_game_date"] == "2260.03.25"


# --- attempts: what the model sees --------------------------------------------------------------------


def test_the_cause_appears_only_when_the_ladder_reaches_the_top(campaign):
    start(campaign)
    academy = campaign.academy
    for level in (2, 3):
        topic = academy.academy_attempt("miss")["topic"]
        assert topic["ladder"] == level and "concept" not in topic and "answer" not in topic
    top = academy.academy_attempt("miss")["topic"]
    assert top["ladder"] == 4 and top["may_explain"] is True
    assert top["concept"] == NAVAL
    assert top["answer"]["title"] == TITLE and top["answer"]["description"] == DESCRIPTION
    assert [r["title"] for r in top["answer"]["remedies"]] == ["Adopt the Supremacy tradition tree"]
    done = academy.academy_attempt("full_explanation")["topic"]
    assert done["status"] == "done" and done["concept"] == NAVAL
    assert level_of() == "new"  # told, not found


def test_naming_the_cause_announces_the_level_with_its_title_and_keeps_the_remedy_hidden(campaign):
    start(campaign)
    result = campaign.academy.academy_attempt("cause", text="Not enough capacity sources")
    assert [(a["effect"], a["level"], a["about"]) for a in result["announce"]] == [
        ("level", "understand", TITLE)
    ]
    assert result["topic"]["asks_for"] == "remedy" and "answer" not in result["topic"]
    assert level_of() == "understand"
    done = campaign.academy.academy_attempt("remedy")
    assert done["topic"]["result"] == "named" and done["topic"]["answer"]["title"] == TITLE
    assert done["finished"] is True


def test_a_crisis_topic_climbs_two_levels(campaign):
    campaign.add_snapshot("2259.12.26", energy=(-10, 20))
    result = start(campaign, goals=("energy.more",))
    assert result["crisis"]["crisis"] and result["topic"]["crisis"] is True
    assert result["topic"]["ladder"] == 1
    assert campaign.academy.academy_attempt("miss")["topic"]["ladder"] == 3


def test_the_pointers_carry_figures_and_not_the_answer(campaign):
    topic = start(campaign)["topic"]
    assert {p["metric"] for p in topic["pointers"]} >= {"naval_capacity.fill"}
    assert all("value" in p for p in topic["pointers"])


# --- support ---------------------------------------------------------------------------------------------


def test_a_supported_answer_counts_as_the_cause_and_is_noted(campaign):
    start(campaign)
    result = campaign.academy.academy_attempt("support", text="Fleet is full", support=FILL)
    assert result["support_check"] == {
        "supported": True,
        "path": "naval_capacity.used",
        "found": 95.0,
    }
    assert result["topic"]["asks_for"] == "remedy"
    assert level_of() == "understand"
    notes = [e for e in store.events() if e["kind"] == "note"]
    assert notes and notes[-1]["text"] == "Fleet is full"


def test_an_answer_the_snapshot_does_not_back_asks_where_and_changes_nothing(campaign):
    start(campaign)
    result = campaign.academy.academy_attempt("support", support={**FILL, "value": 99})
    assert result["support_check"]["supported"] is False and result["ask_where"] is True
    assert result["topic"]["ladder"] == 1 and level_of() == "new"


def test_support_without_a_figure_or_with_a_bad_one_is_refused(campaign):
    start(campaign)
    academy = campaign.academy
    with pytest.raises(Refused, match=r"\{path, op, value\}"):
        academy.academy_attempt("support")
    with pytest.raises(Refused, match="operator"):
        academy.academy_attempt("support", support={**FILL, "op": "~"})
    with pytest.raises(Refused, match="number"):
        academy.academy_attempt("support", support={**FILL, "value": "high"})
    assert drill.view(campaign.workspace)["topic"]["attempts"] == 0


def test_a_path_without_a_number_is_not_backed():
    result = check_support({"path": "nope.nothing", "op": ">", "value": 1}, {}, False)
    assert result == {"supported": False, "path": "nope.nothing", "found": None}


def test_fair_play_refuses_a_figure_the_empire_cannot_see():
    hidden = {"path": "known_empires.full.military_power", "op": ">", "value": 1}
    document = {"known_empires": {"full": {"military_power": 9}}}
    with pytest.raises(Refused, match="not visible"):
        check_support(hidden, document, god_mode=False)
    assert check_support(hidden, document, god_mode=True)["supported"] is True


# --- the Escape Hatch, next, close ------------------------------------------------------------------------


def test_the_escape_hatch_reveals_the_answer_and_records_the_situation(campaign):
    start(campaign)
    result = campaign.academy.academy_escape("Fleet cap is blocking a war I want to start")
    assert result["topic"]["status"] == "done" and result["topic"]["answer"]["title"] == TITLE
    hatch = [e for e in store.events() if e["kind"] == "hatch"]
    assert len(hatch) == 1 and "blocking a war" in hatch[0]["situation"]
    assert store.state_of(store.read_model(), NAVAL)["hatch_uses"] == 1


def test_escape_hatch_through_attempt_is_the_same_call(campaign):
    start(campaign)
    with pytest.raises(Refused, match="Situation"):
        campaign.academy.academy_attempt("escape_hatch")
    result = campaign.academy.academy_attempt("escape_hatch", situation="No time to learn it now")
    assert (
        result["topic"]["result"] == "hatch"
        and len([e for e in store.events() if e["kind"] == "hatch"]) == 1
    )


def test_a_full_briefing_covers_further_concepts_and_unknown_ones_are_refused(campaign):
    with pytest.raises(Refused, match="unknown concept"):
        campaign.academy.academy_escape("Asked for a full Briefing", concepts=["nope.nothing"])
    campaign.academy.academy_escape("Asked for a full Briefing", concepts=[NAVAL, ENERGY])
    assert {e["concept"] for e in store.events() if e["kind"] == "hatch"} == {NAVAL, ENERGY}


def test_next_topic_and_the_end_of_the_list(campaign):
    campaign.add_snapshot("2259.12.26", energy=(-10, 20))
    first = start(campaign)
    assert first["waiting"] == 1 and first["topic"]["goals"] == ["energy.more"]
    second = campaign.academy.academy_next()
    assert second["waiting"] == 0 and second["topic"]["status"] == "current"
    last = campaign.academy.academy_next()
    assert last["topic"] is None and last["finished"] is True


def test_close_needs_the_summary_hides_unfinished_topics_and_proposes_the_rendezvous(campaign):
    campaign.add_snapshot("2259.12.26", energy=(-10, 20))
    start(campaign)
    academy = campaign.academy
    with pytest.raises(Refused, match="summary"):
        academy.academy_close(" ")
    academy.academy_escape("Out of energy and need an answer")  # the first topic is over
    closed = academy.academy_close("Build more power plants first, then look at the fleet cap.")
    assert closed["ended"] == "player_stopped"
    done, left = closed["topics"]
    assert done["status"] == "done" and done["title"] and done["concept"]
    assert left["status"] == "left" and "concept" not in left
    assert closed["proposal"] == {
        "date": "2262.01.01",
        "save_name": "Academy 2262-01",
        "checks": [],
    }
    assert closed["agreed"] is None
    assert drill.load(campaign.workspace) is None


# --- evidence at the start of a Drill ---------------------------------------------------------------------


def test_opening_a_drill_runs_the_drop_rule_on_the_archive(campaign):
    store.append(
        "level", concept=NAVAL, level="understand", previous="new", reason="test", date="2250.01.01"
    )
    campaign.add_snapshot("2258.12.20")  # the cause is present, a year before the newest Snapshot
    result = campaign.academy.academy_open()
    drops = [c for c in result["changes"] if c["effect"] == "drop"]
    assert [(d["concept"], d["title"], d["level"], d["announce"]) for d in drops] == [
        (NAVAL, TITLE, "new", True)
    ]
    assert level_of() == "new"
    copied = (campaign.workspace / "academy" / "evidence.jsonl").read_text().splitlines()
    assert json.loads(copied[-1])["kind"] == "drop"
    assert campaign.academy.academy_open()["changes"] == []  # idempotent


def test_a_drill_is_not_opened_over_the_changes_of_another_one(campaign):
    start(campaign)
    assert "changes" not in campaign.academy.academy_open()  # continuing changes nothing


# --- decisions, Predictions, Rendezvous ------------------------------------------------------------------


def test_a_save_announces_a_decision_and_a_prediction_is_stored(campaign):
    campaign.docs[-1]["progression"].update(
        {"tradition_tree_slots": {"free": 1}, "ascension_slots": {"free": 0}}
    )
    campaign.docs[-1]["progression"]["next_tradition"]["affordable"] = True
    result = campaign.academy.academy_open()
    assert [c["kind"] for c in result["announced"]] == ["tradition_tree"]
    stored = campaign.academy.prediction_add(
        "tradition_tree", "Naval capacity grows by a third.", concepts=[NAVAL]
    )
    assert stored["id"] == "p001" and stored["made"] == "2259.12.25"
    assert stored["check_date"] == "2261.12.25" and stored["concepts"] == [NAVAL]
    again = campaign.academy.academy_open()
    assert again["announced"] == [] and [p["id"] for p in again["open_predictions"]] == ["p001"]


def test_a_prediction_outside_the_rules_is_refused(campaign):
    academy = campaign.academy
    with pytest.raises(Refused, match="5 years"):
        academy.prediction_add("war", "It ends fast.", check_date="2270.01.01")
    with pytest.raises(Refused, match="unknown concept"):
        academy.prediction_add("war", "It ends fast.", concepts=["nope.nothing"])
    with pytest.raises(Refused, match="unknown decision"):
        academy.prediction_add("peace", "It ends fast.")
    assert predictions.listing(campaign.workspace) == []


def test_a_measurable_prediction_is_decided_by_the_snapshot_and_lifts_evaluate(campaign):
    campaign.academy.prediction_add(
        "tradition_tree",
        "Capacity is above ninety afterwards.",
        concepts=[NAVAL],
        expect={"path": "naval_capacity.used", "op": ">", "value": 90},
    )
    waiting = campaign.academy.prediction_check()
    assert waiting["waiting"] == ["p001"] and waiting["decided"] == []
    campaign.add_snapshot("2262.01.10", fill=0.97)
    checked = campaign.academy.prediction_check()
    assert [(d["id"], d["state"]) for d in checked["decided"]] == [("p001", "confirmed")]
    assert level_of() == "evaluate" and checked["open"] == []


def test_a_prediction_without_a_measure_waits_for_the_players_verdict(campaign):
    campaign.academy.prediction_add("war", "It is over in a year.", check_date="2260.12.25")
    campaign.add_snapshot("2261.01.10")
    checked = campaign.academy.prediction_check()
    assert [n["id"] for n in checked["needs_verdict"]] == ["p001"]
    verdict = campaign.academy.prediction_check(id="p001", verdict="refuted", note="took 3 years")
    assert verdict["decided_by_player"]["state"] == "refuted"
    assert verdict["decided_by_player"]["decided_by"] == "player"
    with pytest.raises(Refused, match="needs the Prediction"):
        campaign.academy.prediction_check(verdict="confirmed")


def test_the_rendezvous_is_agreed_moved_and_found_by_the_next_open(campaign):
    academy = campaign.academy
    agreed = academy.rendezvous_set("2262.01.01")
    assert agreed["save_name"] == "Academy 2262-01" and agreed["unchecked"] == []
    moved = academy.rendezvous_set("2262.07.01", save_name="Academy mid")
    assert [m["date"] for m in moved["moves"]] == ["2262.01.01"] and moved[
        "save_name"
    ] == "Academy mid"
    assert academy.academy_open()["rendezvous"]["position"] == "before"
    campaign.add_snapshot("2262.07.05")
    opened = academy.academy_open()
    assert opened["rendezvous"]["position"] == "at"
    with pytest.raises(Refused, match="after"):
        academy.rendezvous_set("2250.01.01")


def test_the_proposal_waits_for_open_predictions(campaign):
    campaign.academy.prediction_add("war", "It is over.", check_date="2264.06.25")
    start(campaign)
    closed = campaign.academy.academy_close("Watch the war.")
    assert closed["proposal"]["date"] >= "2264.06.25" and closed["proposal"]["checks"] == ["p001"]


# --- the Player Model ----------------------------------------------------------------------------------------


def test_the_player_model_is_read_only_and_names_the_causes(campaign):
    start(campaign)
    campaign.academy.academy_attempt("cause")
    campaign.academy.academy_escape("Asked for the remedy")
    model = campaign.academy.player_model()
    entry = next(c for c in model["concepts"] if c["concept"] == NAVAL)
    assert entry["title"] == TITLE and entry["level"] == "understand" and entry["hatch_uses"] == 1
    assert model["counts"]["understand"] == 1 and model["events"] == len(store.events())
    assert [e["kind"] for e in model["recent"]] == ["level", "hatch"]
    assert store.events() == model["recent"]  # nothing was written by looking


# --- through the server and the CLI --------------------------------------------------------------------


def call(server, tool, args=None):
    result = asyncio.run(server.call_tool(tool, args or {}))
    return json.loads(result.content[0].text)


TOOLS = {
    "academy_open", "academy_attempt", "academy_next", "academy_escape", "academy_close",
    "prediction_add", "prediction_check", "rendezvous_set", "player_model",
}  # fmt: skip


def consulting_server(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIRALTY_SAVE_DIR", str(tmp_path / "saves"))
    monkeypatch.setenv("ADMIRALTY_EMPIRE", "Plexxi")
    return build_server(tmp_path)


def test_the_server_lists_the_tools_without_the_injected_service(tmp_path, monkeypatch):
    tools = {t.name: t for t in asyncio.run(consulting_server(tmp_path, monkeypatch).list_tools())}
    assert TOOLS <= set(tools)
    assert "svc" not in json.dumps([tools[name].input_schema for name in TOOLS])
    attempt = tools["academy_attempt"].input_schema["properties"]
    assert set(attempt) == {"outcome", "text", "domain_named", "support", "situation"}
    assert tools["academy_attempt"].input_schema["required"] == ["outcome"]


def test_the_server_answers_a_consulting_campaign_with_an_error_and_logs_it(tmp_path, monkeypatch):
    server = consulting_server(tmp_path, monkeypatch)
    answer = call(server, "academy_open", {"goals": ["naval_capacity.more"]})
    assert "Consulting" in answer["error"]
    entry = json.loads((tmp_path / ".admiralty" / TURN_LOG).read_text().splitlines()[0])
    assert entry["tool"] == "academy_open" and entry["result"] == answer


def test_the_cli_runs_the_tools_by_the_same_names_and_logs_them(campaign, monkeypatch, capsys):
    (campaign.workspace / "campaign.yaml").write_text(
        f"save_dir: {campaign.workspace}\nempire: Plexxi\nmode: coaching\n"
    )
    monkeypatch.setattr("admiralty.mcp.service.CampaignService", lambda config: campaign)
    base = ["academy"]
    where = ["--workspace", str(campaign.workspace)]

    assert cli.main([*base, "open", *where, "--goal", "naval_capacity.more"]) == 0
    opened = json.loads(capsys.readouterr().out)
    assert opened["topic"]["asks_for"] == "cause" and "concept" not in opened["topic"]

    assert cli.main([*base, "attempt", "support", *where, "--text", "Fleet is full",
                     "--support-path", "naval_capacity.used", "--support-op", ">=",
                     "--support-value", "90"]) == 0  # fmt: skip
    assert json.loads(capsys.readouterr().out)["support_check"]["supported"] is True

    assert cli.main([*base, "prediction-add", "war", "It is over in a year.", *where]) == 0
    assert json.loads(capsys.readouterr().out)["id"] == "p001"
    assert cli.main([*base, "rendezvous-set", "2262.01.01", *where]) == 0
    assert json.loads(capsys.readouterr().out)["save_name"] == "Academy 2262-01"
    assert cli.main([*base, "player-model", *where]) == 0
    assert json.loads(capsys.readouterr().out)["counts"]["understand"] == 1
    assert cli.main([*base, "escape", "Need the remedy now", *where]) == 0
    assert cli.main([*base, "close", "Add power plants.", *where]) == 0

    logged = [
        json.loads(line)["tool"]
        for line in (campaign.workspace / ".admiralty" / TURN_LOG).read_text().splitlines()
    ]
    assert logged[:3] == ["academy_open", "academy_attempt", "prediction_add"]
    assert "academy_close" in logged and "player_model" in logged


def test_the_cli_reports_a_refused_call_on_stderr(campaign, monkeypatch, capsys):
    (campaign.workspace / "campaign.yaml").write_text(
        f"save_dir: {campaign.workspace}\nempire: Plexxi\nmode: coaching\n"
    )
    monkeypatch.setattr("admiralty.mcp.service.CampaignService", lambda config: campaign)
    assert cli.main(["academy", "close", "Done.", "--workspace", str(campaign.workspace)]) == 1
    captured = capsys.readouterr()
    assert "no Drill is open" in captured.err and captured.out == ""


# --- on the vulkan mid save -----------------------------------------------------------------------------------


@pytest.mark.saves
def test_a_drill_on_the_vulkan_mid_save_through_the_server(tmp_path, monkeypatch):
    reference_save(VULKAN, MID)
    (tmp_path / "campaign.yaml").write_text(
        f"save_dir: {SAVES_DIR / VULKAN}\nempire: Plexxi\nmode: coaching\nknowledge: fair_play\n"
    )
    server = build_server(tmp_path)
    catalogue = call(server, "academy_open")
    assert catalogue["needs_goals"] and any(g["id"] == "unity.more" for g in catalogue["goals"])

    opened = call(server, "academy_open", {"goals": ["unity.more", "naval_capacity.more"]})
    topic = opened["topic"]
    assert "concept" not in topic and "answer" not in topic and opened["count"] >= 2
    assert opened["waiting"] == opened["count"] - 1
    assert CampaignConfig.load(tmp_path).mode == "coaching"

    stuck = call(server, "academy_attempt", {"outcome": "miss"})
    assert stuck["topic"]["ladder"] in (2, 3) and "concept" not in stuck["topic"]
    told = call(server, "academy_escape", {"situation": "Wants the answer to the first question"})
    assert told["topic"]["concept"] and told["topic"]["answer"]["remedies"] is not None
    assert call(server, "academy_next")["topic"]["status"] == "current"
    closed = call(server, "academy_close", {"summary": "Fix the first thing, then look again."})
    assert closed["proposal"]["date"] > opened["in_game_date"]
    model = call(server, "player_model")
    assert model["counts"]["new"] >= 1 and any(c["hatch_uses"] == 1 for c in model["concepts"])

    log = [
        json.loads(line) for line in (tmp_path / ".admiralty" / TURN_LOG).read_text().splitlines()
    ]
    assert [e["tool"] for e in log] == [
        "academy_open", "academy_open", "academy_attempt", "academy_escape",
        "academy_next", "academy_close", "player_model",
    ]  # fmt: skip
    assert "concept" not in json.dumps(log[1]["result"]["topic"])
