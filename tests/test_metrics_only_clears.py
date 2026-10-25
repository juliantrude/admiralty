"""`only_clears`: a metric that covers only part of an Obstacle can rule it out, never confirm it."""

from hlidskjalf.graph.metrics import evaluate

METRICS = {"room.generator_free": {"path": "room.district_types_free.generator"}}


def check(free: int):
    comparison = {"metric": "room.generator_free", "op": "==", "compare_to": 0, "only_clears": True}
    return evaluate(comparison, METRICS, {"room": {"district_types_free": {"generator": free}}})


def test_free_district_places_clear_the_obstacle():
    assert check(2).state == "clear"


def test_no_free_district_place_leaves_the_obstacle_to_judgement():
    assert check(0).state == "judgement"
