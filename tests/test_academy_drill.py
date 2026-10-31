"""Hint Ladder, Escape Hatch and Drill state (M9, 20d): one test per rule of `academy/ladder.py` and `academy/drill.py`."""

from __future__ import annotations

import json

import pytest
from test_player_evidence import extract

from admiralty.academy import drill, ladder
from admiralty.academy.drill import DrillError
from admiralty.player import evidence, store
from admiralty.player.mastery import Refused

A, B, C = "energy.low_output", "food.vats_eat", "naval_capacity.few_sources"
DATE = "2259.12.25"


def topics(*concepts, crisis=()):
    return [{"concept": c, "crisis": c in crisis} for c in concepts]


@pytest.fixture
def ws(tmp_path):
    return tmp_path / "workspace"


def opened(ws, *concepts, crisis=(), **options):
    return drill.open_drill(
        ws,
        date=DATE,
        topics=topics(*(concepts or (A, B, C)), crisis=crisis),
        campaign="vulkan",
        **options,
    )


def events():
    return store.events()


# --- the Ladder, pure -------------------------------------------------------------------------------


def test_a_miss_climbs_one_level_and_stops_at_the_top():
    levels = [1]
    for _ in range(5):
        levels.append(ladder.move(levels[-1], "miss")["level"])
    assert levels == [1, 2, 3, 4, 4, 4]


def test_a_crisis_climbs_two_levels_per_miss():
    assert [ladder.climb(level, crisis=True) for level in (1, 2, 3, 4)] == [3, 4, 4, 4]
    assert ladder.move(1, "partial", crisis=True)["level"] == 3


@pytest.mark.parametrize("outcome", ["cause", "remedy"])
@pytest.mark.parametrize("level", [1, 2, 3, 4])
def test_naming_the_cause_or_the_remedy_sends_the_ladder_back_to_the_question(outcome, level):
    result = ladder.move(level, outcome, crisis=True)
    assert result["level"] == 1 and result["named"] == outcome


def test_a_supported_answer_counts_as_the_cause_an_unsupported_one_asks_where():
    assert ladder.move(3, "support", supported=True) == {
        "level": 1,
        "named": "cause",
        "explained": False,
        "ask_where": False,
    }
    result = ladder.move(3, "support", supported=False)
    assert result["level"] == 3 and result["ask_where"] and result["named"] is None


def test_a_support_answer_without_the_check_is_refused():
    with pytest.raises(Refused, match="check against the Snapshot"):
        ladder.move(1, "support")


def test_the_full_explanation_comes_only_on_the_top_level():
    for level in (1, 2, 3):
        with pytest.raises(Refused, match="full explanation comes on Ladder level 4"):
            ladder.move(level, "full_explanation")
    assert ladder.move(4, "full_explanation")["explained"] is True


def test_the_escape_hatch_jumps_to_the_top():
    assert ladder.move(1, "escape_hatch")["level"] == 4


def test_unknown_outcomes_and_levels_are_refused():
    with pytest.raises(Refused, match="unknown outcome"):
        ladder.move(1, "guess")
    for level in (0, 5):
        with pytest.raises(Refused, match="level must be 1 to 4"):
            ladder.move(level, "miss")


# --- opening ------------------------------------------------------------------------------------------


def test_opening_raises_the_first_topic_and_counts_the_others_without_naming_them(ws):
    result = opened(ws)
    assert result["topic"]["concept"] == A and result["topic"]["status"] == "current"
    assert result["topic"]["ladder"] == 1 and result["topic"]["ladder_name"] == "question"
    assert result["topic"]["asks_for"] == "cause" and result["topic"]["may_explain"] is False
    assert result["waiting"] == 2 and result["finished"] is False
    assert B not in json.dumps(result) and C not in json.dumps(result)
    assert (ws / "academy" / "drill.json").exists()


def test_the_drill_keeps_the_crisis_of_its_snapshot(ws):
    result = opened(ws, extract=extract(energy=(-100, 400)))
    assert result["crisis"]["crisis"] is True
    assert result["crisis"]["resources"][0]["resource"] == "energy"
    assert drill.load(ws)["crisis"]["resources"][0]["reserve_months"] == 4.0


def test_a_drill_without_a_snapshot_extract_has_no_crisis(ws):
    assert opened(ws)["crisis"] == {"crisis": False, "resources": []}


def test_a_second_drill_cannot_be_opened_while_one_is_open(ws):
    opened(ws)
    with pytest.raises(DrillError, match="already open"):
        opened(ws)


def test_a_topic_needs_a_concept_and_a_concept_comes_once(ws):
    with pytest.raises(DrillError, match="needs a concept"):
        drill.open_drill(ws, date=DATE, topics=[{"crisis": True}])
    with pytest.raises(DrillError, match="twice"):
        drill.open_drill(ws, date=DATE, topics=topics(A, A))
    assert drill.load(ws) is None


def test_the_date_must_be_an_in_game_date(ws):
    with pytest.raises(ValueError, match="in-game date"):
        drill.open_drill(ws, date="2259-12-25", topics=topics(A))


def test_extra_topic_fields_survive(ws):
    drill.open_drill(ws, date=DATE, topics=[{"concept": A, "pointers": ["energy net"]}])
    assert drill.load(ws)["topics"][0]["pointers"] == ["energy net"]


def test_an_empty_drill_is_finished_at_once_and_closes(ws):
    result = drill.open_drill(ws, date=DATE, topics=[])
    assert result["topic"] is None and result["finished"] is True
    assert drill.close(ws, "Nothing to ask.")["ended"] == "all_done"


def test_calls_without_an_open_drill_say_so(ws):
    for call in (
        lambda: drill.view(ws),
        lambda: drill.attempt(ws, "miss"),
        lambda: drill.next_topic(ws),
        lambda: drill.close(ws, "x"),
        lambda: drill.escape(ws, "energy runs out"),
    ):
        with pytest.raises(DrillError, match="no Drill is open"):
            call()


# --- attempts: ladder movement ------------------------------------------------------------------------


def test_misses_move_the_ladder_and_the_full_explanation_ends_the_topic(ws):
    opened(ws)
    seen = [drill.attempt(ws, "miss")["topic"]["ladder"] for _ in range(3)]
    assert seen == [2, 3, 4]
    reached = drill.view(ws)["topic"]
    assert reached["may_explain"] is True and reached["ladder_name"] == "full explanation"
    result = drill.attempt(ws, "full_explanation")
    assert result["topic"]["status"] == "done" and result["topic"]["result"] == "explained"
    assert result["topic"]["may_explain"] is False


def test_the_full_explanation_before_the_ladder_reached_it_is_refused_and_changes_nothing(ws):
    opened(ws)
    drill.attempt(ws, "miss")
    before = (ws / "academy" / "drill.json").read_text()
    with pytest.raises(Refused, match="level 4"):
        drill.attempt(ws, "full_explanation")
    assert (ws / "academy" / "drill.json").read_text() == before


def test_a_crisis_topic_climbs_two_levels_per_miss(ws):
    opened(ws, crisis=(A,))
    assert drill.attempt(ws, "miss")["topic"]["ladder"] == 3
    assert drill.attempt(ws, "miss")["topic"]["ladder"] == 4


def test_a_success_sends_the_ladder_back_to_one_and_asks_for_the_remedy_next(ws):
    opened(ws)
    drill.attempt(ws, "miss")
    result = drill.attempt(ws, "cause")
    assert result["topic"]["ladder"] == 1 and result["topic"]["asks_for"] == "remedy"
    assert result["topic"]["status"] == "current"
    # a miss on the remedy question climbs again, from one
    assert drill.attempt(ws, "partial")["topic"]["ladder"] == 2


def test_cause_then_remedy_ends_the_topic_as_named(ws):
    opened(ws)
    drill.attempt(ws, "cause")
    result = drill.attempt(ws, "remedy")
    assert result["topic"]["status"] == "done" and result["topic"]["result"] == "named"
    assert result["topic"]["named"] == ["cause", "remedy"]


def test_naming_the_remedy_first_leaves_the_cause_to_ask(ws):
    opened(ws)
    result = drill.attempt(ws, "remedy")
    assert result["topic"]["status"] == "current" and result["topic"]["asks_for"] == "cause"
    assert drill.attempt(ws, "cause")["topic"]["result"] == "named"


def test_naming_the_same_thing_twice_does_not_end_the_topic(ws):
    opened(ws)
    drill.attempt(ws, "cause")
    result = drill.attempt(ws, "cause")
    assert result["topic"]["status"] == "current" and result["topic"]["named"] == ["cause"]


def test_a_support_answer_the_snapshot_backs_is_the_cause_and_a_candidate(ws):
    opened(ws)
    result = drill.attempt(ws, "support", supported=True, text="Clone vats eat the food")
    assert result["topic"]["asks_for"] == "remedy" and result["ask_where"] is False
    by_kind = {e["kind"]: e for e in events()}
    assert sorted(by_kind) == ["level", "note"]
    assert (
        by_kind["note"]["candidate"] is True
        and by_kind["note"]["text"] == "Clone vats eat the food"
    )


def test_an_unsupported_support_answer_asks_where_and_writes_nothing(ws):
    opened(ws)
    drill.attempt(ws, "miss")
    result = drill.attempt(ws, "support", supported=False)
    assert result["ask_where"] is True and result["topic"]["ladder"] == 2
    assert result["topic"]["named"] == [] and events() == []


def test_an_attempt_on_a_finished_topic_is_refused(ws):
    opened(ws)
    drill.attempt(ws, "cause")
    drill.attempt(ws, "remedy")
    with pytest.raises(DrillError, match="next topic"):
        drill.attempt(ws, "miss")


# --- attempts: the Mastery rules run ---------------------------------------------------------------------------


def test_a_cause_on_the_question_lifts_the_concept_and_the_tool_reports_it(ws):
    opened(ws)
    result = drill.attempt(ws, "cause")
    assert [e["level"] for e in result["announce"]] == ["understand"]
    assert store.level_of(store.read_model(), A) == "understand"
    event = events()[0]
    assert (
        event["campaign"] == "vulkan"
        and event["date"] == DATE
        and "Ladder level 1" in event["reason"]
    )


def test_a_cause_only_after_the_full_explanation_level_keeps_the_concept_new(ws):
    opened(ws)
    for _ in range(3):
        drill.attempt(ws, "miss")
    result = drill.attempt(ws, "cause")
    assert result["announce"] == [] and store.level_of(store.read_model(), A) == "new"
    assert events() == []


def test_the_mastery_rules_refuse_what_the_state_does_not_allow_and_the_drill_stays_as_it_was(ws):
    store.append("level", concept=A, level="evaluate", previous="new", reason="choice")
    opened(ws)
    before = (ws / "academy" / "drill.json").read_text()
    with pytest.raises(Refused, match="skips it"):
        drill.attempt(ws, "miss")
    assert (ws / "academy" / "drill.json").read_text() == before


def test_a_question_that_did_not_name_the_domain_can_reach_analyse(ws):
    store.append("level", concept=A, level="apply", previous="understand", reason="done")
    opened(ws)
    result = drill.attempt(ws, "cause", domain_named=False)
    assert [e["level"] for e in result["announce"]] == ["analyse"]


def test_events_written_by_the_drill_are_copied_to_the_campaign_log(ws):
    opened(ws)
    drill.attempt(ws, "cause")
    copied = [
        json.loads(line) for line in (ws / "academy" / "evidence.jsonl").read_text().splitlines()
    ]
    assert copied == events()


# --- Escape Hatch ----------------------------------------------------------------------------------------------------------


def test_the_escape_hatch_records_its_situation_ends_the_topic_and_allows_the_answer(ws):
    opened(ws)
    result = drill.escape(ws, "energy runs out in four months")
    assert result["topic"]["result"] == "hatch" and result["topic"]["ladder"] == 4
    assert result["concepts"] == [A] and result["events"] == 1
    hatch = events()[0]
    assert hatch["kind"] == "hatch" and hatch["concept"] == A
    assert "energy runs out in four months" in hatch["situation"]
    assert store.read_model()["concepts"][A]["hatch_uses"] == 1
    assert store.level_of(store.read_model(), A) == "new"


def test_the_escape_hatch_needs_a_situation(ws):
    opened(ws)
    for situation in ("", "   ", None):
        with pytest.raises(Refused, match="Situation"):
            drill.escape(ws, situation)
    assert events() == []


def test_the_escape_hatch_through_attempt_is_the_same_event(ws):
    opened(ws)
    result = drill.attempt(ws, "escape_hatch", situation="no idea")
    assert result["topic"]["result"] == "hatch" and events()[0]["kind"] == "hatch"
    drill.next_topic(ws)
    with pytest.raises(Refused, match="Situation"):
        drill.attempt(ws, "escape_hatch")
    assert len(events()) == 1


def test_a_full_briefing_counts_as_a_hatch_for_every_concept_in_it(ws):
    opened(ws)
    result = drill.escape(ws, "asked for the whole Briefing", concepts=[B, C, A])
    assert result["concepts"] == [A, B, C] and result["events"] == 3
    assert sorted(e["concept"] for e in events()) == [A, B, C]


def test_a_briefing_hatch_with_an_unknown_concept_is_refused(ws):
    opened(ws)
    with pytest.raises(Refused, match="unknown concept"):
        drill.escape(ws, "whole Briefing", concepts=["nonsense.node"], known={A, B, C})
    assert events() == []


def test_a_briefing_hatch_works_without_an_open_drill_but_needs_a_concept(ws):
    result = drill.escape(ws, "asked for the whole Briefing", concepts=[A])
    assert result["events"] == 1 and "topic" not in result
    with pytest.raises(DrillError, match="no concept"):
        drill.escape(ws, "asked for the whole Briefing")


# --- next topic, the end -------------------------------------------------------------------------------------------------------


def test_next_topic_raises_the_next_one_at_the_first_ladder_level(ws):
    opened(ws)
    drill.attempt(ws, "miss")
    result = drill.next_topic(ws)
    assert result["topic"]["concept"] == B and result["topic"]["ladder"] == 1
    assert result["waiting"] == 1 and result["finished"] is False
    stored = drill.load(ws)["topics"]
    assert [t["status"] for t in stored] == ["skipped", "current", "waiting"]


def test_next_topic_after_a_finished_topic_keeps_its_result(ws):
    opened(ws)
    drill.attempt(ws, "cause")
    drill.attempt(ws, "remedy")
    drill.next_topic(ws)
    assert [t["status"] for t in drill.load(ws)["topics"]][:2] == ["done", "current"]


def test_the_last_topic_finishes_the_drill_when_it_is_over(ws):
    opened(ws, A)
    assert drill.view(ws)["finished"] is False
    result = drill.escape(ws, "no idea")
    assert result["finished"] is True and result["waiting"] == 0
    after = drill.next_topic(ws)
    assert after["topic"] is None and after["finished"] is True
    with pytest.raises(DrillError, match="no topic is current"):
        drill.attempt(ws, "miss")


def test_close_needs_the_summary(ws):
    opened(ws, A)
    for summary in ("", "  ", None):
        with pytest.raises(Refused, match="summary"):
            drill.close(ws, summary)
    assert drill.load(ws) is not None


def test_close_archives_the_drill_and_marks_what_was_not_reached_as_left(ws):
    opened(ws)
    drill.attempt(ws, "cause")
    drill.attempt(ws, "remedy")
    drill.next_topic(ws)
    result = drill.close(ws, "Build a second generator district, then look at the food.")
    assert result["ended"] == "player_stopped"
    assert [(t["concept"], t["status"]) for t in result["topics"]] == [
        (A, "done"),
        (B, "left"),
        (C, "left"),
    ]
    assert drill.load(ws) is None and not (ws / "academy" / "drill.json").exists()
    archived = [json.loads(x) for x in (ws / "academy" / "drills.jsonl").read_text().splitlines()]
    assert len(archived) == 1 and archived[0]["summary"].startswith("Build a second")
    assert archived[0]["status"] == "closed"


def test_a_drill_whose_topics_were_all_taken_ends_as_all_done(ws):
    opened(ws, A, B)
    drill.next_topic(ws)
    drill.attempt(ws, "escape_hatch", situation="skip it")
    assert drill.close(ws, "Play on.")["ended"] == "all_done"


def test_a_new_drill_can_follow_a_closed_one(ws):
    opened(ws, A)
    drill.close(ws, "Done.")
    assert opened(ws, B)["topic"]["concept"] == B


# --- what the Evidence rules need ------------------------------------------------------------------------------------------------


def test_raised_dates_cover_the_open_and_the_closed_drills(ws):
    drill.open_drill(ws, date="2250.01.01", topics=topics(A, B))
    drill.next_topic(ws)
    drill.close(ws, "First.")
    drill.open_drill(ws, date="2255.06.01", topics=topics(A, C))
    assert drill.raised_dates(ws, A) == ["2250.01.01", "2255.06.01"]
    assert drill.raised_dates(ws, B) == ["2250.01.01"]
    assert drill.raised_dates(ws, C) == []  # waiting, never put to the Player
    assert drill.evidence_inputs(ws, A) == {
        "raised": "2255.06.01",
        "prompts": ["2250.01.01", "2255.06.01"],
    }
    assert drill.evidence_inputs(ws, C) == {"raised": None, "prompts": []}


def test_a_topic_that_was_never_current_has_no_raised_date(ws):
    opened(ws)
    assert [t["raised"] for t in drill.load(ws)["topics"]] == [DATE, None, None]


def test_the_stored_dates_feed_the_evidence_rules(ws):
    """`raised` and `prompts` from the Drill are the inputs `record_evidence` takes."""
    from test_player_evidence import REMEDY, pack  # the synthetic pack of the evidence tests

    graph = pack(ws.parent)
    drill.open_drill(ws, date="2250.01.01", topics=topics(C))
    drill.attempt(ws, "cause")
    inputs = drill.evidence_inputs(ws, C)
    snapshots = [
        ("2250.01.01", extract(trees=[])),
        ("2252.01.01", extract(trees=["Supremacy"])),
    ]
    result = evidence.record_evidence(graph, C, snapshots, **inputs, campaign="vulkan")
    assert [e["level"] for e in result["effects"]] == ["apply"]
    assert REMEDY in result["events"][0]["reason"]
