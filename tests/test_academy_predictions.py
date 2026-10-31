"""Predictions (M9, 20g): the decision list, detection before and after, the date rules, the check and the Evaluate feed.

Synthetic extracts; one smoke run on two vulkan saves (structure only, no invented numbers).
"""

from __future__ import annotations

import copy

import pytest
from conftest import EARLY, MID, VULKAN, reference_save

from admiralty.academy import predictions
from admiralty.academy.predictions import PredictionError
from admiralty.debrief.frame import date_of, day_number
from admiralty.player import store
from admiralty.player.mastery import Refused

CAUSE = "energy.low_income"


def extract(**progression):
    base = {
        "next_tradition": {"cost": 500, "unity_stockpile": 100, "affordable": False},
        "tradition_tree_slots": {"max": 7, "adopted": 3, "free": 4},
        "ascension_slots": {"unlocked": 1, "cap": 8, "taken": 1, "free": 0},
        "tradition_trees": ["Discovery"],
        "ascension_perks": ["Technological Ascendancy"],
    }
    return {
        "progression": {**base, **progression},
        "military": {"wars": []},
        "planets": [{"id": 1, "name": "Vulkan", "system": "Sol", "designation": "Capital"}],
        "resources": {"energy": {"net": 5}},
    }


def war(name="War of Spoons", side="attacker", start="2250.03.01"):
    return {"name": name, "side": side, "start_date": start, "our_war_goal": "Conquest"}


def add(workspace, **fields):
    args = {"kind": "tradition_tree", "sentence": "More unity.", "made": "2250.01.01"}
    return predictions.add(workspace, **{**args, **fields})


# --- the date helpers ----------------------------------------------------------------------


def test_date_of_is_the_inverse_of_day_number():
    for date in ("2200.01.01", "2259.12.30", "2301.07.15", "0999.02.03"):
        assert date_of(day_number(date)) == date


def test_check_date_proposal_is_two_years_and_capped_at_five():
    assert predictions.propose_check_date("2250.01.01") == "2252.01.01"
    assert predictions.propose_check_date("2250.01.01", years=5) == "2255.01.01"
    for years in (0, -1, 5.5):
        with pytest.raises(Refused):
            predictions.propose_check_date("2250.01.01", years=years)


# --- detection ------------------------------------------------------------------------------


def test_before_unity_for_a_tree_with_a_free_slot_announces_a_tree():
    doc = extract(next_tradition={"cost": 500, "unity_stockpile": 900, "affordable": True})
    [found] = predictions.detect_before(doc)
    assert found["kind"] == "tradition_tree" and found["phase"] == "before"
    assert found["facts"] == {"cost": 500, "unity_stockpile": 900, "free_tree_slots": 4}


def test_before_no_tree_without_unity_or_without_a_free_slot():
    poor = extract()
    full = extract(
        next_tradition={"cost": 1, "unity_stockpile": 9, "affordable": True},
        tradition_tree_slots={"max": 7, "adopted": 7, "free": 0},
    )
    assert predictions.detect_before(poor) == []
    assert predictions.detect_before(full) == []


def test_before_a_free_perk_slot_announces_a_perk():
    doc = extract(ascension_slots={"unlocked": 2, "cap": 8, "taken": 1, "free": 1})
    assert [c["kind"] for c in predictions.detect_before(doc)] == ["ascension_perk"]


def test_before_a_kind_with_an_open_foretold_prediction_is_not_offered_again(tmp_path):
    doc = extract(ascension_slots={"unlocked": 2, "cap": 8, "taken": 1, "free": 1})
    made = add(tmp_path, kind="ascension_perk", sentence="Faster research.")
    assert predictions.detect_before(doc, [made]) == []
    hindsight = {**made, "basis": "hindsight"}
    assert [c["kind"] for c in predictions.detect_before(doc, [hindsight])] == ["ascension_perk"]


def test_after_new_tree_perk_war_and_designation_are_seen():
    old, new = extract(), extract()
    new["progression"]["tradition_trees"] = ["Discovery", "Expansion"]
    new["progression"]["ascension_perks"] = ["Technological Ascendancy", "Executive Vigor"]
    new["military"]["wars"] = [war()]
    new["planets"][0]["designation"] = "Forge World"
    found = predictions.detect_after(old, new)
    seen = {(c["kind"], c["subject"]) for c in found["hindsight"]}
    assert seen == {
        ("tradition_tree", "Expansion"),
        ("ascension_perk", "Executive Vigor"),
        ("war", "War of Spoons"),
        ("world_designation", "Vulkan"),
    }
    designation = next(c for c in found["hindsight"] if c["kind"] == "world_designation")
    assert designation["facts"] == {"from": "Capital", "to": "Forge World", "system": "Sol"}
    assert all(c["phase"] == "after" for c in found["hindsight"])


def test_after_a_war_we_were_attacked_in_or_that_was_there_before_is_no_decision():
    old, new = extract(), extract()
    old["military"]["wars"] = [war("Old War", start="2240.01.01")]
    new["military"]["wars"] = [
        war("Old War", start="2240.01.01"),
        war("Defence", side="defender", start="2251.01.01"),
    ]
    assert predictions.detect_after(old, new)["hindsight"] == []


def test_after_names_what_the_extract_cannot_show():
    found = predictions.detect_after(extract(), extract())
    assert found["not_detectable"] == ["megastructure", "federation"]
    assert set(predictions.NOT_DETECTABLE) <= set(predictions.KINDS)


def test_after_a_decision_with_an_open_foretold_prediction_is_a_match_not_hindsight(tmp_path):
    old, new = extract(), extract()
    new["progression"]["tradition_trees"] = ["Discovery", "Expansion"]
    made = add(tmp_path)
    found = predictions.detect_after(old, new, [made])
    assert found["hindsight"] == []
    [match] = found["matches"]
    assert match["prediction"] == made["id"] and match["decision"]["subject"] == "Expansion"


def test_after_a_decision_with_a_stored_prediction_of_that_subject_is_not_offered_again(tmp_path):
    old, new = extract(), extract()
    new["military"]["wars"] = [war()]
    made = add(tmp_path, kind="war", subject="War of Spoons", basis="hindsight")
    assert predictions.detect_after(old, new, [made])["hindsight"] == []


# --- adding ---------------------------------------------------------------------------------


def test_add_stores_one_file_per_prediction_with_the_proposed_date(tmp_path):
    first = add(tmp_path)
    second = add(tmp_path, kind="war", sentence="The border is safe.")
    assert (first["id"], second["id"]) == ("p001", "p002")
    assert first["check_date"] == "2252.01.01" and first["state"] == "open"
    assert first["basis"] == "foretold" and first["decided_by"] is None
    assert predictions.load(tmp_path, "p002") == second
    assert [p["id"] for p in predictions.listing(tmp_path)] == ["p001", "p002"]
    assert sorted(p.name for p in (tmp_path / "predictions").glob("p*.json")) == [
        "p001.json",
        "p002.json",
    ]


def test_add_the_check_date_is_at_most_five_years_away_and_after_the_decision(tmp_path):
    assert add(tmp_path, check_date="2255.01.01")["check_date"] == "2255.01.01"
    for bad in ("2255.01.02", "2250.01.01", "2249.12.30"):
        with pytest.raises(Refused):
            add(tmp_path, check_date=bad)
    assert len(predictions.listing(tmp_path)) == 1


@pytest.mark.parametrize(
    "fields",
    [
        {"kind": "colonise"},
        {"basis": "guess"},
        {"sentence": "  "},
        {"sentence": "One.\nTwo."},
        {"made": "January 2250"},
    ],
)
def test_add_refuses_what_the_rules_do_not_allow_and_writes_nothing(tmp_path, fields):
    with pytest.raises(Exception) as caught:
        add(tmp_path, **fields)
    assert isinstance(caught.value, ValueError)
    assert predictions.listing(tmp_path) == []


def test_add_checks_concepts_against_the_known_ones(tmp_path):
    with pytest.raises(Refused, match="unknown concept"):
        add(tmp_path, concepts=["nope.nothing"], known={CAUSE})
    assert add(tmp_path, concepts=[CAUSE, CAUSE], known={CAUSE})["concepts"] == [CAUSE]


def test_add_the_expectation_needs_a_path_with_a_number_in_the_snapshot(tmp_path):
    good = {"path": "resources.energy.net", "op": ">", "value": 0}
    assert add(tmp_path, expect=good, extract=extract())["expect"] == good
    for bad in (
        {"path": "resources.energy.stock", "op": ">", "value": 0},
        {"path": "resources.energy.net", "op": "~", "value": 0},
        {"path": "resources.energy.net", "op": ">", "value": "high"},
        {"path": "resources.energy.net", "op": ">"},
    ):
        with pytest.raises(Refused):
            add(tmp_path, expect=bad, extract=extract())


# --- the check ------------------------------------------------------------------------------


def snapshot(date, net):
    doc = extract()
    doc["resources"]["energy"]["net"] = net
    return date, doc


def expecting(tmp_path, **fields):
    expect = {"path": "resources.energy.net", "op": ">", "value": 0}
    return add(tmp_path, expect=expect, concepts=[CAUSE], **fields)


def test_check_before_the_date_nothing_is_decided_and_the_prediction_waits(tmp_path):
    made = expecting(tmp_path)
    result = predictions.check_due(tmp_path, [snapshot("2251.06.01", 9)])
    assert result["decided"] == [] and result["waiting"] == [made["id"]]
    assert predictions.load(tmp_path, made["id"])["state"] == "open"


def test_check_reads_the_first_snapshot_at_or_after_the_date(tmp_path):
    made = expecting(tmp_path)
    result = predictions.check_due(
        tmp_path,
        [snapshot("2253.01.01", -5), snapshot("2252.01.01", 4), snapshot("2251.01.01", -9)],
    )
    [decided] = result["decided"]
    assert decided["id"] == made["id"] and decided["state"] == "confirmed"
    stored = predictions.load(tmp_path, made["id"])
    assert stored["state"] == "confirmed" and stored["decided_by"] == "snapshot"
    assert stored["decided"] == "2252.01.01" and "was 4" in stored["note"]


def test_check_a_prediction_the_data_refutes_is_refuted_and_lifts_nothing(tmp_path):
    expecting(tmp_path)
    [decided] = predictions.check_due(tmp_path, [snapshot("2252.02.01", -1)])["decided"]
    assert decided["state"] == "refuted" and decided["effects"] == []
    assert store.read_model()["concepts"] == {}


def test_check_a_path_without_a_value_is_unclear(tmp_path):
    expecting(tmp_path)
    broken = snapshot("2252.02.01", 1)
    del broken[1]["resources"]["energy"]["net"]
    [decided] = predictions.check_due(tmp_path, [broken])["decided"]
    assert decided["state"] == "unclear" and decided["effects"] == []


def test_check_a_confirmed_prediction_lifts_its_concept_to_evaluate_through_the_store(tmp_path):
    expecting(tmp_path)
    [decided] = predictions.check_due(tmp_path, [snapshot("2252.02.01", 3)], campaign="vulkan")[
        "decided"
    ]
    [effect] = decided["effects"]
    assert (
        effect["effect"] == "level" and effect["level"] == "evaluate" and effect["concept"] == CAUSE
    )
    assert store.state_of(store.read_model(), CAUSE)["level"] == "evaluate"
    events = [e for e in store.events() if e["concept"] == CAUSE]
    assert events[-1]["campaign"] == "vulkan" and "Prediction" in events[-1]["reason"]
    assert (tmp_path / "academy" / "evidence.jsonl").read_text().count(CAUSE) == 1


def test_check_a_concept_already_at_evaluate_is_skipped_not_an_error(tmp_path):
    store.append("level", concept=CAUSE, level="evaluate", previous="new", reason="test setup")
    expecting(tmp_path)
    [decided] = predictions.check_due(tmp_path, [snapshot("2252.02.01", 3)])["decided"]
    assert decided["state"] == "confirmed"
    assert [e["effect"] for e in decided["effects"]] == ["skipped"]


def test_check_a_decided_prediction_is_not_checked_twice(tmp_path):
    expecting(tmp_path)
    shots = [snapshot("2252.02.01", 3)]
    assert len(predictions.check_due(tmp_path, shots)["decided"]) == 1
    assert predictions.check_due(tmp_path, shots) == {
        "decided": [],
        "needs_verdict": [],
        "waiting": [],
        "hindsight": [],
    }


def test_check_without_a_measurable_expectation_asks_for_the_players_verdict(tmp_path):
    made = add(tmp_path, concepts=[CAUSE])
    result = predictions.check_due(tmp_path, [snapshot("2252.02.01", 3)])
    assert result["decided"] == []
    [asked] = result["needs_verdict"]
    assert asked["id"] == made["id"] and asked["snapshot"] == "2252.02.01"
    settled = predictions.decide(tmp_path, made["id"], "confirmed", date="2252.02.01", note="Yes.")
    assert settled["state"] == "confirmed" and settled["decided_by"] == "player"
    assert store.read_model()["concepts"] == {}  # a Player verdict never lifts a level


def test_decide_refuses_unknown_verdicts_unknown_ids_and_a_second_verdict(tmp_path):
    made = add(tmp_path)
    with pytest.raises(Refused):
        predictions.decide(tmp_path, made["id"], "maybe", date="2252.01.01")
    with pytest.raises(PredictionError):
        predictions.decide(tmp_path, "p099", "confirmed", date="2252.01.01")
    predictions.decide(tmp_path, made["id"], "refuted", date="2252.01.01")
    with pytest.raises(PredictionError, match="already refuted"):
        predictions.decide(tmp_path, made["id"], "confirmed", date="2252.01.01")


def test_a_hindsight_expectation_is_never_checked_and_never_lifts_a_level(tmp_path):
    made = expecting(tmp_path, basis="hindsight")
    result = predictions.check_due(tmp_path, [snapshot("2252.02.01", 3)])
    assert result["hindsight"] == [made["id"]] and result["decided"] == []
    assert predictions.load(tmp_path, made["id"])["state"] == "open"
    assert store.read_model()["concepts"] == {}


def test_check_without_predictions_is_empty(tmp_path):
    assert predictions.check_due(tmp_path, [snapshot("2252.02.01", 3)])["decided"] == []


def test_listing_filters_by_state_and_orders_by_number(tmp_path):
    for _ in range(3):
        add(tmp_path)
    predictions.decide(tmp_path, "p002", "refuted", date="2252.01.01")
    assert [p["id"] for p in predictions.listing(tmp_path, state="open")] == ["p001", "p003"]
    assert [p["id"] for p in predictions.listing(tmp_path, state="refuted")] == ["p002"]


# --- real saves -----------------------------------------------------------------------------


def test_detection_runs_on_two_vulkan_saves():
    from admiralty.extract.snapshot import Extractor

    extractor = Extractor()
    old = extractor.extract(reference_save(VULKAN, EARLY), "Plexxi")
    new = extractor.extract(reference_save(VULKAN, MID), "Plexxi")
    found = predictions.detect_after(old, new)
    assert set(found) == {"hindsight", "matches", "not_detectable"}
    assert all(c["kind"] in predictions.KINDS for c in found["hindsight"])
    assert all(c["subject"] for c in found["hindsight"])
    for candidate in predictions.detect_before(new):
        assert candidate["kind"] in {"tradition_tree", "ascension_perk"}
    assert copy.deepcopy(found) == found
