"""`only_clears` and `only_present`: a metric that covers only part of an Obstacle can rule it out
(`only_clears`) or confirm it (`only_present`), never the other."""

from admiralty.graph.metrics import evaluate

METRICS = {"room.generator_free": {"path": "room.district_types_free.generator"}}


def check(free: int):
    comparison = {"metric": "room.generator_free", "op": "==", "compare_to": 0, "only_clears": True}
    return evaluate(comparison, METRICS, {"room": {"district_types_free": {"generator": free}}})


def test_free_district_places_clear_the_obstacle():
    assert check(2).state == "clear"


def test_no_free_district_place_leaves_the_obstacle_to_judgement():
    assert check(0).state == "judgement"


def check_missing(missing: int):
    metrics = {"unlocks.x.missing": {"path": "unlocks.x.missing"}}
    comparison = {
        "metric": "unlocks.x.missing",
        "op": ">",
        "compare_to": 0,
        "only_present": True,
    }
    return evaluate(comparison, metrics, {"unlocks": {"x": {"missing": missing}}})


def test_a_missing_unlock_proves_the_obstacle():
    assert check_missing(2).state == "present"


def test_nothing_missing_leaves_the_obstacle_to_judgement():
    assert check_missing(0).state == "judgement"
