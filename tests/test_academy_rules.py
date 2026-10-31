"""The Academy's rules without a language model (M9, 20k): a scripted Player runs Drills through the real tools.

Nothing here guesses at what the Coach would say: each scene feeds the tools the outcomes a Coach would report and
checks what the Player Model, the Drill and the Rendezvous do with them. The first half runs on a synthetic pack and
hand-made Snapshots (any machine); the second half runs the tools on the vulkan saves 2259.12.25, 2273.09.03 and
2284.09.27 through the real server and prints the numbers the Log records (`pytest -s`).
"""

from __future__ import annotations

import copy
import dataclasses
import io
import json
import time

import pytest
from conftest import MID, SAVES_DIR, VULKAN, reference_save
from test_academy_tools import FILL, Campaign, call
from test_academy_topics import ENERGY, NAVAL

from admiralty.academy import drill, rendezvous
from admiralty.mcp.server import build_server
from admiralty.player import evidence, guard, mastery, store
from admiralty.player.mastery import Refused

REMEDY = "naval_capacity.adopt_supremacy"
TREE = "traditions.supremacy_tree"
CRISIS = {"energy": (-10, 20)}


def scripted(tmp_path, *, implementable=True) -> Campaign:
    """The synthetic Campaign; the Remedy "Adopt the Supremacy tradition tree" can be seen in a Snapshot."""
    campaign = Campaign(tmp_path)
    if implementable:
        campaign.graph_.metrics[TREE] = {
            "contains": {"path": "progression.tradition_trees", "label": "Supremacy"},
            "unit": "1 when adopted",
        }
        campaign.graph_.nodes[REMEDY]["applied_when"] = {
            "metric": TREE,
            "op": "==",
            "compare_to": 1,
        }
    return campaign


def snapshot(campaign, date, *, trees=(), **options):
    progression = {"next_tradition": {"cost": 50}, "tradition_trees": list(trees)}
    return campaign.add_snapshot(date, progression=progression, **options)


def level(concept=NAVAL):
    return store.level_of(store.read_model(), concept)


def kinds():
    return [(e["kind"], e["concept"], e.get("level")) for e in store.events()]


def understood(campaign, text="Not enough capacity sources"):
    """Open a Drill on the naval topic, name its Cause at once and finish the topic with the Remedy."""
    opened = campaign.academy.academy_open(["naval_capacity.more"])
    assert opened["topic"]["ladder"] == 1
    campaign.academy.academy_attempt("cause", text=text)
    campaign.academy.academy_attempt("remedy")
    return campaign.academy.academy_close("Adopt the tree when Unity allows it.")


# --- a whole Drill ---------------------------------------------------------------------------------------


def test_two_misses_a_hinted_cause_and_the_remedy_make_a_whole_topic(tmp_path):
    campaign = scripted(tmp_path)
    academy = campaign.academy
    opened = academy.academy_open(["naval_capacity.more"])
    assert opened["topic"]["ladder"] == 1 and opened["count"] == 1 and level() == "new"

    first = academy.academy_attempt("miss")
    assert first["topic"]["ladder"] == 2 and "concept" not in first["topic"]
    second = academy.academy_attempt("miss")
    assert second["topic"]["ladder"] == 3 and "answer" not in second["topic"]
    assert store.events() == []  # nothing is written for a miss

    named = academy.academy_attempt("cause", text="Too few ways to raise it")
    assert named["topic"]["asks_for"] == "remedy" and "answer" not in named["topic"]
    assert level() == "new"  # named with a hint on the third rung: no level for that

    done = academy.academy_attempt("remedy")
    assert done["finished"] is True and done["topic"]["status"] == "done"
    assert done["topic"]["concept"] == NAVAL and done["topic"]["answer"]["remedies"]
    assert level() == "new"
    closed = academy.academy_close("The tree is the way to more capacity.")
    assert closed["ended"] == "all_done" and drill.load(campaign.workspace) is None
    assert closed["proposal"]["date"] == "2262.01.01"


def test_naming_the_cause_before_any_hint_is_the_understand_level(tmp_path):
    campaign = scripted(tmp_path)
    understood(campaign)
    assert level() == "understand"
    assert kinds() == [("level", NAVAL, "understand")]
    event = store.events()[0]
    assert event["previous"] == "new" and event["reason"] and event["campaign"] == "vulkan"


def test_a_crisis_climbs_two_rungs_and_the_player_may_pull_the_escape_hatch(tmp_path):
    campaign = scripted(tmp_path)
    snapshot(campaign, "2259.12.26", **CRISIS)
    opened = campaign.academy.academy_open(["energy.more"])
    first = opened["topic"]
    assert opened["crisis"]["crisis"] and first["crisis"] and first["ladder"] == 1
    assert campaign.academy.academy_attempt("miss")["topic"]["ladder"] == 3

    with pytest.raises(Refused, match="Situation"):
        campaign.academy.academy_attempt("escape_hatch")
    pulled = campaign.academy.academy_attempt(
        "escape_hatch", situation="Energy is gone and I need the answer now"
    )
    assert pulled["topic"]["status"] == "done" and pulled["topic"]["concept"] == ENERGY
    assert pulled["topic"]["answer"]["remedies"]
    assert kinds() == [("hatch", ENERGY, None)]
    assert store.events()[0]["situation"] == "Energy is gone and I need the answer now"
    assert level(ENERGY) == "new"  # told, not found
    assert store.state_of(store.read_model(), ENERGY)["hatch_uses"] == 1


def test_a_full_explanation_is_refused_below_the_top_rung(tmp_path):
    campaign = scripted(tmp_path)
    campaign.academy.academy_open(["naval_capacity.more"])
    with pytest.raises(Exception, match="rung|level|ladder|top"):
        campaign.academy.academy_attempt("full_explanation")
    assert store.events() == []


# --- support -------------------------------------------------------------------------------------------


def test_a_supported_answer_is_the_cause_and_one_the_save_denies_is_not(tmp_path):
    campaign = scripted(tmp_path)
    campaign.academy.academy_open(["naval_capacity.more"])
    denied = campaign.academy.academy_attempt("support", support={**FILL, "value": 99})
    assert denied["support_check"]["supported"] is False and denied["ask_where"] is True
    assert denied["topic"]["ladder"] == 1 and store.events() == []
    held = campaign.academy.academy_attempt("support", text="The fleet is full", support=FILL)
    assert held["support_check"] == {
        "supported": True,
        "path": "naval_capacity.used",
        "found": 95.0,
    }
    assert level() == "understand"
    assert [e["kind"] for e in store.events()] == ["note", "level"] or [
        e["kind"] for e in store.events()
    ] == ["level", "note"]


# --- the five-year window -----------------------------------------------------------------------------


def test_apply_comes_when_a_save_within_five_years_shows_the_remedy(tmp_path):
    campaign = scripted(tmp_path)
    understood(campaign)
    snapshot(campaign, "2262.06.25", trees=["Supremacy"])
    opened = campaign.academy.academy_open()
    applied = [c for c in opened["changes"] if c["effect"] == "level"]
    assert [(c["concept"], c["level"]) for c in applied] == [(NAVAL, "apply")]
    assert level() == "apply"
    assert campaign.academy.academy_open()["changes"] == []  # twice changes nothing more
    assert [e["kind"] for e in store.events()].count("level") == 2


def test_without_the_remedy_in_five_years_the_level_stays_and_the_coach_asks_once(tmp_path):
    campaign = scripted(tmp_path)
    understood(campaign)
    snapshot(campaign, "2263.06.25", fill=0.5)  # the Cause is gone, so no drop gets in the way
    assert campaign.academy.academy_open()["changes"] == []  # inside the window: still waiting
    snapshot(campaign, "2265.01.30", fill=0.5)  # past the window, the Remedy never shown
    changes = campaign.academy.academy_open()["changes"]
    assert [c["effect"] for c in changes] == ["ask_once"] and level() == "understand"
    assert campaign.academy.academy_open()["changes"][0]["effect"] == "ask_once"  # still pending...
    asked = [e for e in store.events() if e.get("ask_once")]
    assert len(asked) == 1  # ...but written only once


def test_a_remedy_shown_on_the_day_it_was_raised_does_not_count(tmp_path):
    campaign = scripted(tmp_path)
    snapshot(campaign, "2260.01.10", trees=["Supremacy"])  # the Drill runs on this one
    understood(campaign)
    snapshot(campaign, "2262.06.25", trees=["Supremacy"])
    assert campaign.academy.academy_open()["changes"] == []
    assert level() == "understand"


# --- the drop ---------------------------------------------------------------------------------------------


def test_two_snapshots_a_year_apart_with_the_cause_present_drop_one_level(tmp_path):
    campaign = scripted(tmp_path, implementable=False)
    understood(campaign)
    snapshot(campaign, "2260.03.25")
    assert campaign.academy.academy_open()["changes"] == []  # one Snapshot is not enough
    snapshot(campaign, "2261.06.25")
    drops = [c for c in campaign.academy.academy_open()["changes"] if c["effect"] == "drop"]
    assert [(d["concept"], d["level"], d["announce"]) for d in drops] == [(NAVAL, "new", True)]
    assert level() == "new" and store.events()[-1]["kind"] == "drop"
    assert "year or more apart" in store.events()[-1]["reason"]
    assert campaign.academy.academy_open()["changes"] == []


def test_less_than_a_year_apart_does_not_drop(tmp_path):
    campaign = scripted(tmp_path, implementable=False)
    understood(campaign)
    snapshot(campaign, "2260.03.25")
    snapshot(campaign, "2261.02.25")  # 337 days
    assert campaign.academy.academy_open()["changes"] == [] and level() == "understand"


def test_a_crisis_snapshot_never_counts_for_the_drop(tmp_path):
    campaign = scripted(tmp_path, implementable=False)
    understood(campaign)
    snapshot(campaign, "2260.03.25", **CRISIS)
    snapshot(campaign, "2261.06.25", **CRISIS)
    assert campaign.academy.academy_open()["changes"] == [] and level() == "understand"
    snapshot(campaign, "2262.09.25")  # one calm Snapshot: still not two a year apart
    assert campaign.academy.academy_open()["changes"] == []
    assert level() == "understand"


# --- the patch rule ---------------------------------------------------------------------------------------


def test_a_patch_that_changes_the_formula_sends_apply_back_to_understand(tmp_path):
    campaign = scripted(tmp_path)
    understood(campaign)
    snapshot(campaign, "2262.06.25", trees=["Supremacy"])
    campaign.academy.academy_open()
    assert level() == "apply"

    old = campaign.graph_
    nodes = copy.deepcopy(old.nodes)
    twin = {**copy.deepcopy(nodes[REMEDY]), "id": "naval_capacity.other"}
    nodes[twin["id"]] = twin
    nodes[NAVAL]["remedies"].append(twin["id"])
    patched = dataclasses.replace(old, version="4.6.0", nodes=nodes)

    moved = mastery.record_patch(old, patched, date="2263.01.01")
    assert list(moved) == [NAVAL] and level() == "understand"
    state = store.state_of(store.read_model(), NAVAL)
    assert state["peak"] == "apply" and "changed between" in store.events()[-1]["reason"]
    assert mastery.record_patch(old, old) == {}  # no change in the pack, no event


# --- the Rendezvous --------------------------------------------------------------------------------------


def test_the_rendezvous_is_before_at_and_after_the_agreed_date(tmp_path):
    campaign = scripted(tmp_path)
    academy = campaign.academy
    understood(campaign)
    agreed = academy.rendezvous_set("2262.01.01")
    assert agreed["save_name"] == "Academy 2262-01"
    assert academy.academy_open()["rendezvous"]["position"] == "before"
    snapshot(campaign, "2262.01.20")
    assert academy.academy_open()["rendezvous"]["position"] == "at"
    snapshot(campaign, "2262.04.01")  # more than 30 days past it
    after = academy.academy_open()["rendezvous"]
    assert after["position"] == "after"
    moved = academy.rendezvous_set("2263.01.01")
    assert [m["date"] for m in moved["moves"]] == ["2262.01.01"]
    assert academy.academy_open()["rendezvous"]["position"] == "before"
    assert rendezvous.load(campaign.workspace)["date"] == "2263.01.01"


def test_an_open_prediction_pushes_the_proposal_past_its_check_date(tmp_path):
    campaign = scripted(tmp_path)
    campaign.academy.prediction_add("war", "It is over by 2265.", check_date="2264.06.25")
    closed = understood(campaign)
    assert closed["proposal"]["date"] >= "2264.06.25" and closed["proposal"]["checks"] == ["p001"]
    with pytest.raises(Refused, match="5 years"):
        campaign.academy.prediction_add("war", "Much later.", check_date="2270.01.01")


# --- the single write path ----------------------------------------------------------------------------


def test_every_event_comes_from_a_tool_and_the_cache_equals_the_replay(tmp_path):
    campaign = scripted(tmp_path)
    understood(campaign)
    snapshot(campaign, "2262.06.25", trees=["Supremacy"])
    campaign.academy.academy_open()
    campaign.academy.academy_escape("Needs the answer for the energy topic", concepts=[ENERGY])

    folder = store.model_dir()
    assert sorted(p.name for p in folder.iterdir()) == [".lock", "events.jsonl", "model.json"]
    events = store.events()
    assert [e["seq"] for e in events] == list(range(1, len(events) + 1))
    assert all(e["reason"] and e["kind"] in store.KINDS for e in events)
    assert json.loads((folder / "model.json").read_text()) == store.replay(events)


def test_a_hand_edited_cache_is_not_believed(tmp_path):
    campaign = scripted(tmp_path)
    understood(campaign)
    cache = store.model_dir() / "model.json"
    document = json.loads(cache.read_text())
    document["concepts"][NAVAL]["level"] = "create"
    cache.write_text(json.dumps(document))
    assert level() == "understand"  # the replay wins and the cache is rebuilt
    assert json.loads(cache.read_text())["concepts"][NAVAL]["level"] == "understand"


def test_the_hook_refuses_every_hand_on_the_player_model(tmp_path):
    campaign = scripted(tmp_path)
    understood(campaign)
    folder = store.model_dir()

    def verdict(tool, **arguments):
        stdout = io.StringIO()
        payload = {"tool_name": tool, "tool_input": arguments, "cwd": str(tmp_path)}
        assert guard.pretooluse(io.StringIO(json.dumps(payload)), stdout) == 0
        text = stdout.getvalue()
        return json.loads(text)["hookSpecificOutput"]["permissionDecision"] if text else "allow"

    assert verdict("Write", file_path=str(folder / "model.json")) == "deny"
    assert verdict("Edit", file_path=str(folder / "events.jsonl")) == "deny"
    assert verdict("Bash", command=f"echo '{{}}' > {folder}/events.jsonl") == "deny"
    assert verdict("Bash", command=f"sed -i s/understand/create/ {folder}/model.json") == "deny"
    assert verdict("Write", file_path=str(campaign.workspace / "notes.md")) == "allow"
    assert verdict("Bash", command="ls ~/Work") == "allow"
    before = store.events()
    assert verdict("Write", file_path=str(folder / "events.jsonl")) == "deny"
    assert store.events() == before  # a denied call changed nothing


def test_the_tools_are_the_only_door_a_refused_attempt_writes_nothing(tmp_path):
    campaign = scripted(tmp_path)
    campaign.academy.academy_open(["naval_capacity.more"])
    for bad in ({"outcome": "bogus"}, {"outcome": "support"}, {"outcome": "evaluate"}):
        with pytest.raises(Exception):  # noqa: B017 - any refusal will do, the point is the store
            campaign.academy.academy_attempt(**bad)
    assert store.events() == [] and drill.view(campaign.workspace)["topic"]["attempts"] == 0
    assert evidence.crisis(campaign.docs[-1])["crisis"] is False


# --- on the vulkan saves -------------------------------------------------------------------------------------

STAGES = ("2259.12.25.sav", "2273.09.03.sav", "2284.09.27.sav")


def stage(folder, name):
    """Only this save lies in the folder; the earlier ones are in the workspace archive by then."""
    for old in folder.glob("*.sav"):
        old.unlink()
    link = folder / name
    link.symlink_to(SAVES_DIR / VULKAN / name)
    return link


@pytest.mark.saves
def test_a_scripted_player_over_three_vulkan_saves(tmp_path, capsys):
    for name in STAGES:
        reference_save(VULKAN, name)
    assert STAGES[0] == MID
    saves = tmp_path / "saves"
    saves.mkdir()
    (tmp_path / "campaign.yaml").write_text(
        f"save_dir: {saves}\nempire: Plexxi\nmode: coaching\nknowledge: fair_play\n"
    )
    stage(saves, STAGES[0])
    started = time.perf_counter()
    server = build_server(tmp_path)

    opened = call(server, "academy_open", {"goals": ["unity.more", "naval_capacity.more"]})
    count = opened["count"]
    start_date = opened[
        "in_game_date"
    ]  # the file name is the game's autosave day, not the Snapshot's
    assert start_date.startswith("2259.12") and count >= 2
    assert "concept" not in opened["topic"] and "answer" not in opened["topic"]
    call(server, "academy_attempt", {"outcome": "miss"})
    hinted = call(server, "academy_attempt", {"outcome": "miss"})
    assert hinted["topic"]["ladder"] in (2, 3)
    call(server, "academy_attempt", {"outcome": "cause", "text": "scripted"})
    first = call(server, "academy_attempt", {"outcome": "remedy"})
    assert first["topic"]["status"] == "done" and first["topic"]["concept"]
    second = call(server, "academy_next")
    assert second["topic"]["status"] == "current" and second["topic"]["ladder"] == 1
    named = call(server, "academy_attempt", {"outcome": "cause", "text": "scripted, at once"})
    assert [a["level"] for a in named["announce"]] == ["understand"]
    call(server, "academy_attempt", {"outcome": "remedy"})
    third = call(server, "academy_next")
    assert third["topic"]["status"] == "current"
    call(server, "academy_escape", {"situation": "Scripted: wants the answer now"})
    closed = call(server, "academy_close", {"summary": "Scripted summary."})
    agreed = call(server, "rendezvous_set", {"date": closed["proposal"]["date"]})
    assert call(server, "academy_open")["rendezvous"]["position"] == "before"
    written = len(store.events())
    assert call(server, "player_model")["events"] == written

    stage(saves, STAGES[1])
    later = call(server, "academy_open", {"goals": ["unity.more"]})
    assert (
        later["in_game_date"].startswith("2273.09") and later["rendezvous"]["position"] == "after"
    )
    assert start_date < agreed["date"] < later["in_game_date"]
    stage(saves, STAGES[2])
    last = call(server, "academy_open", {"goals": ["unity.more"]})
    assert last["in_game_date"].startswith("2284.09") and last["continued"] is True
    changes = [*later.get("changes", []), *last.get("changes", [])]
    call(server, "academy_close", {"summary": "Scripted, second Drill."})

    events = store.events()
    assert all(e["reason"] for e in events) and [e["seq"] for e in events] == list(
        range(1, len(events) + 1)
    )
    folder = store.model_dir()
    assert json.loads((folder / "model.json").read_text()) == store.replay(events)
    for change in changes:
        if change["effect"] == "drop":
            assert change["announce"] is True
        assert change["concept"] and change["title"]
    elapsed = time.perf_counter() - started
    by_kind = {k: sum(1 for e in events if e["kind"] == k) for k in store.KINDS}
    with capsys.disabled():
        print(
            f"\nACADEMY RULES vulkan: topics {count}, events written {len(events)} {by_kind}, "
            f"changes by the later saves {[c['effect'] for c in changes]}, "
            f"run time {elapsed:.1f} s (3 saves)"
        )
