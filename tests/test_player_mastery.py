"""The fixed Mastery rules (M9, 20b): one test per row of the table in `docs/plans/M9.md`, plus the refusals."""

from __future__ import annotations

import copy

import pytest
import yaml
from test_mechanics_graph import FACT, GRAPH, node, write_pack

from admiralty.graph.mechanics import MechanicsGraph
from admiralty.player import mastery, store
from admiralty.player.mastery import Refused, apply

CONCEPT = "naval_capacity.few_sources"


def state(level="new", peak=None, **extra):
    return {
        "level": level,
        "peak": peak or level,
        "last_change": None,
        "drops": 0,
        "hatch_uses": 0,
        **extra,
    }


def attempt(outcome, ladder=1, domain_named=True, **extra):
    return {
        "type": "attempt",
        "outcome": outcome,
        "ladder": ladder,
        "domain_named": domain_named,
        **extra,
    }


def levels(effects):
    return [e["level"] for e in effects if e["effect"] == "level"]


# --- cause: New -> Understand -----------------------------------------------------------------


@pytest.mark.parametrize("ladder", [1, 2])
def test_a_cause_on_question_or_hint_lifts_new_to_understand(ladder):
    new, effects = apply(state(), attempt("cause", ladder))
    assert new["level"] == "understand" and new["peak"] == "understand"
    assert levels(effects) == ["understand"]
    assert effects[0]["previous"] == "new" and f"Ladder level {ladder}" in effects[0]["reason"]


@pytest.mark.parametrize("ladder", [3, 4])
def test_a_cause_on_partial_or_full_answer_stays_new(ladder):
    new, effects = apply(state(), attempt("cause", ladder))
    assert new == state() and effects == []


@pytest.mark.parametrize("outcome", ["partial", "full_explanation", "miss", "remedy"])
@pytest.mark.parametrize("ladder", [1, 2, 3, 4])
def test_the_other_outcomes_change_no_level(outcome, ladder):
    for level in ("new", "understand", "apply"):
        assert apply(state(level), attempt(outcome, ladder)) == (state(level), [])


def test_a_cause_on_a_concept_that_is_already_understood_changes_nothing():
    assert apply(state("understand"), attempt("cause", 2)) == (state("understand"), [])
    assert apply(state("apply"), attempt("cause", 1)) == (state("apply"), [])


# --- Escape Hatch -----------------------------------------------------------------------------


def test_the_escape_hatch_is_recorded_with_its_situation_and_the_level_stays():
    new, effects = apply(state(), attempt("escape_hatch", 4, situation="energy runs out"))
    assert new["level"] == "new" and new["hatch_uses"] == 1
    assert effects == [
        {
            "effect": "hatch",
            "situation": "energy runs out",
            "reason": "Escape Hatch at Ladder level 4: energy runs out",
        }
    ]


def test_the_escape_hatch_does_not_take_away_a_level():
    new, effects = apply(state("apply"), attempt("escape_hatch", 4, situation="no idea"))
    assert new["level"] == "apply" and levels(effects) == []


@pytest.mark.parametrize("level", ["evaluate", "create"])
def test_the_escape_hatch_is_honoured_on_a_skipped_concept_too(level):
    new, effects = apply(state(level), attempt("escape_hatch", 4, situation="asked outright"))
    assert new["hatch_uses"] == 1 and effects[0]["effect"] == "hatch"


@pytest.mark.parametrize("situation", [None, "", "  "])
def test_an_escape_hatch_without_situation_is_refused(situation):
    with pytest.raises(Refused, match="Situation"):
        apply(state(), attempt("escape_hatch", 4, situation=situation))


# --- support ----------------------------------------------------------------------------------


def test_a_supported_answer_counts_as_a_cause_and_becomes_a_candidate():
    new, effects = apply(
        state(), attempt("support", 1, supported=True, text="too few farms for the pops")
    )
    assert new["level"] == "understand"
    assert [e["effect"] for e in effects] == ["candidate", "level"]
    assert effects[0]["text"] == "too few farms for the pops"


def test_a_supported_answer_on_a_late_ladder_level_is_a_candidate_only():
    new, effects = apply(state(), attempt("support", 3, supported=True, text="x"))
    assert new["level"] == "new" and [e["effect"] for e in effects] == ["candidate"]


def test_an_unsupported_answer_asks_where_the_player_sees_it_and_changes_nothing():
    new, effects = apply(state(), attempt("support", 1, supported=False, text="x"))
    assert new == state()
    assert [e["effect"] for e in effects] == ["ask_where"]


@pytest.mark.parametrize("supported", [None, "yes", 1])
def test_a_support_answer_needs_the_tools_check(supported):
    with pytest.raises(Refused, match="supported"):
        apply(state(), attempt("support", 1, supported=supported, text="x"))


# --- Analyse ----------------------------------------------------------------------------------


def test_a_cause_before_the_domain_was_named_lifts_a_concept_that_reached_apply_to_analyse():
    new, effects = apply(state("apply"), attempt("cause", 1, domain_named=False))
    assert new["level"] == "analyse" and levels(effects) == ["analyse"]


def test_analyse_after_a_drop_uses_the_peak_not_the_current_level():
    new, _ = apply(state("understand", peak="apply"), attempt("cause", 1, domain_named=False))
    assert new["level"] == "analyse"


def test_without_apply_once_the_open_answer_gives_understand_only():
    new, effects = apply(state(), attempt("cause", 1, domain_named=False))
    assert new["level"] == "understand" and levels(effects) == ["understand"]
    new, effects = apply(state("understand"), attempt("cause", 1, domain_named=False))
    assert new["level"] == "understand" and effects == []


def test_a_cause_on_a_hint_does_not_count_as_before_the_domain_was_named():
    new, _ = apply(state("apply"), attempt("cause", 2, domain_named=False))
    assert new["level"] == "apply"


def test_an_open_answer_at_analyse_changes_nothing_a_domain_question_is_refused():
    assert apply(state("analyse"), attempt("cause", 1, domain_named=False)) == (
        state("analyse"),
        [],
    )
    with pytest.raises(Refused, match="does not name the domain"):
        apply(state("analyse"), attempt("cause", 1, domain_named=True))


# --- Evaluate ---------------------------------------------------------------------------------


@pytest.mark.parametrize("basis", ["choice", "prediction"])
@pytest.mark.parametrize("level", ["new", "understand", "apply", "analyse"])
def test_a_choice_with_reasons_or_a_true_prediction_gives_evaluate(basis, level):
    new, effects = apply(
        state(level), {"type": "evaluate", "basis": basis, "detail": "foundry zones are cheaper"}
    )
    assert new["level"] == "evaluate" and new["peak"] == "evaluate"
    assert levels(effects) == ["evaluate"] and "foundry zones are cheaper" in effects[0]["reason"]


@pytest.mark.parametrize(
    "event, message",
    [
        ({"basis": "choice", "detail": ""}, "reasons"),
        ({"basis": "choice"}, "reasons"),
        ({"basis": "guess", "detail": "x"}, "unknown basis"),
    ],
)
def test_evaluate_needs_a_known_basis_and_the_reasons(event, message):
    with pytest.raises(Refused, match=message):
        apply(state("apply"), {"type": "evaluate", **event})


@pytest.mark.parametrize("level", ["evaluate", "create"])
def test_evaluate_is_refused_where_the_concept_is_already_there(level):
    with pytest.raises(Refused, match="already"):
        apply(state(level), {"type": "evaluate", "basis": "choice", "detail": "r"})


# --- refusals ---------------------------------------------------------------------------------


@pytest.mark.parametrize("level", ["evaluate", "create"])
@pytest.mark.parametrize("outcome", ["cause", "remedy", "miss", "partial", "full_explanation"])
def test_an_attempt_on_a_skipped_concept_is_refused(level, outcome):
    with pytest.raises(Refused, match="skips it"):
        apply(state(level), attempt(outcome))


def test_support_on_a_skipped_concept_is_refused_before_the_check_matters():
    with pytest.raises(Refused, match="skips it"):
        apply(state("evaluate"), attempt("support", supported=True, text="x"))


@pytest.mark.parametrize(
    "event, message",
    [
        (attempt("guess"), "unknown outcome"),
        (attempt("cause", 0), "Ladder level"),
        (attempt("cause", 5), "Ladder level"),
        (attempt("cause", None), "Ladder level"),
        ({"type": "bogus"}, "unknown event type"),
        ({}, "unknown event type"),
    ],
)
def test_unknown_outcomes_ladder_levels_and_events_are_refused(event, message):
    with pytest.raises(Refused, match=message):
        apply(state(), event)


def test_apply_does_not_change_the_state_it_was_given():
    before = state("apply")
    snapshot = copy.deepcopy(before)
    apply(before, attempt("cause", 1, domain_named=False))
    assert before == snapshot


# --- the patch rule ---------------------------------------------------------------------------


def patch_event(changed=True):
    return {"type": "patch", "changed": changed, "from": "v4.5.2", "to": "v4.6.0"}


@pytest.mark.parametrize("level", ["apply", "analyse", "evaluate", "create"])
def test_a_changed_cause_falls_back_to_understand_and_is_announced(level):
    new, effects = apply(state(level), patch_event())
    assert new["level"] == "understand" and new["peak"] == level
    assert levels(effects) == ["understand"] and effects[0]["announce"] is True


@pytest.mark.parametrize("level", ["new", "understand"])
def test_a_changed_cause_leaves_new_and_understand_alone(level):
    assert apply(state(level), patch_event()) == (state(level), [])


def test_an_unchanged_cause_keeps_its_level():
    assert apply(state("evaluate"), patch_event(changed=False)) == (state("evaluate"), [])


def packs(tmp_path, change=None, amount=None):
    old = write_pack(tmp_path / "old")
    graph = copy.deepcopy(GRAPH)
    if change:
        change(graph)
    new = write_pack(tmp_path / "new", graph=graph)
    if amount is not None:
        generated = new / "4.5.2" / "generated" / "naval_capacity.yaml"
        document = yaml.safe_load(generated.read_text())
        document["facts"][0]["amount"] = amount
        generated.write_text(yaml.safe_dump(document))
    return MechanicsGraph.load(root=old), MechanicsGraph.load(root=new)


def test_changed_concepts_name_a_changed_formula_and_a_changed_link(tmp_path):
    def formula(graph):
        node(graph, "few_sources")["facts"] = [FACT]

    def link(graph):
        other = {**copy.deepcopy(node(graph, "adopt_supremacy")), "id": "naval_capacity.other"}
        graph["nodes"].append(other)
        node(graph, "few_sources")["remedies"].append(other["id"])

    assert mastery.changed_concepts(*packs(tmp_path / "a", formula)) == [CONCEPT]
    assert mastery.changed_concepts(*packs(tmp_path / "b", link)) == [CONCEPT]


def test_changed_concepts_ignore_numbers_titles_and_descriptions(tmp_path):
    def words(graph):
        cause = node(graph, "few_sources")
        cause["title"] = "Naval capacity has few sources"
        cause["description"] = "Another sentence."

    assert mastery.changed_concepts(*packs(tmp_path / "a", words)) == []
    assert mastery.changed_concepts(*packs(tmp_path / "b", amount=99)) == []


def test_record_patch_resets_only_concepts_the_player_has_and_that_changed(tmp_path):
    mastery.record(CONCEPT, attempt("cause", 1), date="2259.12.25")
    store.append("level", concept=CONCEPT, level="apply", reason="Snapshot shows it")
    store.append("level", concept="food.other", level="apply", reason="Snapshot shows it")

    def formula(graph):
        node(graph, "few_sources")["facts"] = [FACT]

    moved = mastery.record_patch(*packs(tmp_path, formula), date="2260.01.01")
    assert list(moved) == [CONCEPT]
    model = store.read_model()
    assert model["concepts"][CONCEPT]["level"] == "understand"
    assert model["concepts"][CONCEPT]["peak"] == "apply"
    assert model["concepts"]["food.other"]["level"] == "apply"
    assert "changed between" in store.events()[-1]["reason"]


def test_record_patch_with_no_change_writes_nothing(tmp_path):
    store.append("level", concept=CONCEPT, level="apply", reason="Snapshot shows it")
    assert mastery.record_patch(*packs(tmp_path)) == {}
    assert len(store.events()) == 1


# --- record: the one write path ---------------------------------------------------------------


def test_record_writes_the_level_through_the_store_with_campaign_and_date():
    result = mastery.record(CONCEPT, attempt("cause", 2), campaign="vulkan", date="2259.12.25")
    assert result["state"]["level"] == "understand"
    (event,) = store.events()
    assert event == result["events"][0]
    assert (event["kind"], event["concept"], event["level"], event["previous"]) == (
        "level",
        CONCEPT,
        "understand",
        "new",
    )
    assert (event["campaign"], event["date"]) == ("vulkan", "2259.12.25")
    assert store.read_model()["concepts"][CONCEPT]["level"] == "understand"


def test_record_reads_the_stored_state_so_the_second_answer_changes_nothing():
    mastery.record(CONCEPT, attempt("cause", 1))
    again = mastery.record(CONCEPT, attempt("cause", 1))
    assert again["effects"] == [] and len(store.events()) == 1


def test_record_writes_the_hatch_and_the_candidate_as_events():
    mastery.record(CONCEPT, attempt("escape_hatch", 4, situation="stuck"))
    mastery.record("food.x", attempt("support", 3, supported=True, text="more farms"))
    kinds = [(e["kind"], e["concept"]) for e in store.events()]
    assert kinds == [("hatch", CONCEPT), ("note", "food.x")]
    assert store.events()[0]["situation"] == "stuck"
    assert store.events()[1]["text"] == "more farms" and store.events()[1]["candidate"] is True
    assert store.read_model()["concepts"][CONCEPT]["hatch_uses"] == 1


def test_a_refused_event_writes_nothing():
    store.append("level", concept=CONCEPT, level="evaluate", reason="a true Prediction")
    with pytest.raises(Refused):
        mastery.record(CONCEPT, attempt("cause", 1))
    assert len(store.events()) == 1


def test_the_unsupported_answer_writes_no_event_but_reports_the_follow_up():
    result = mastery.record(CONCEPT, attempt("support", 1, supported=False, text="x"))
    assert [e["effect"] for e in result["effects"]] == ["ask_where"]
    assert store.events() == []


def test_a_whole_climb_through_record_keeps_peak_in_the_model():
    mastery.record(CONCEPT, attempt("cause", 1))
    store.append("level", concept=CONCEPT, level="apply", reason="Snapshot shows it")
    mastery.record(CONCEPT, attempt("cause", 1, domain_named=False))
    mastery.record(CONCEPT, {"type": "evaluate", "basis": "choice", "detail": "cheaper"})
    entry = store.read_model()["concepts"][CONCEPT]
    assert (entry["level"], entry["peak"]) == ("evaluate", "evaluate")
    assert [e.get("level") for e in store.events()] == [
        "understand",
        "apply",
        "analyse",
        "evaluate",
    ]
