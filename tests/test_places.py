"""Nodes about the whole empire name the planets they concern (docs/proposals/ops.md entry 8):
the expansion carries `places` from `room.by_planet`, the Solution Graph turns them into evidence
lines, and the titles of such nodes speak of planets, not of "the planet"."""

from __future__ import annotations

import re

import pytest
from test_expand import (
    METRICS,
    build,
    by_id,
    cause,
    goal,
    obstacle,
    remedy,
)
from test_solution import weigh

from admiralty.graph.expand import PLACES_SHOWN, expand_graph
from admiralty.graph.mechanics import MechanicsGraph
from admiralty.graph.solution import compose

BY_PLANET = {
    "m.slots": {"path": "room.free", "unit": "building slots", "by_planet": "free"},
}
EMPTY = {"metric": "m.slots", "op": "==", "compare_to": 0}


def extract(frees, total=None):
    table = {"columns": ["planet", "free"], "rows": [[name, free] for name, free in frees.items()]}
    return {
        "header": {"date": "2250.01.01"},
        "v": {"a": 1, "b": 10, "zero": 0},
        "room": {"free": sum(frees.values()) if total is None else total, "by_planet": table},
    }


@pytest.fixture
def graph(tmp_path, monkeypatch):
    for name, spec in BY_PLANET.items():
        monkeypatch.setitem(METRICS["metrics"], name, spec)
    nodes = [
        cause("c", remedies=["r"], causes=["wide"], places="m.slots"),
        cause("wide", remedies=["r"]),
        remedy("r", ["o"]),
        obstacle("o", EMPTY, remedies=["helper"]),
        remedy("helper"),
    ]
    return build(tmp_path, [goal("g", ["c"])], nodes)


def test_an_obstacle_and_a_cause_name_their_planets_fewest_free_first(graph):
    out = expand_graph(graph, ["t.g"], extract({"Beta": 2, "Alpha": 0, "Gamma": 0}))
    expected = {
        "unit": "building slots",
        "planets": [
            {"planet": "Alpha", "free": 0},
            {"planet": "Gamma", "free": 0},
            {"planet": "Beta", "free": 2},
        ],
        "more": 0,
    }
    assert by_id(out, "t.c")["places"] == expected
    assert "places" not in by_id(out, "t.wide")


def test_a_clear_obstacle_names_no_planets(graph):
    out = expand_graph(graph, ["t.g"], extract({"Alpha": 3}))
    assert by_id(out, "t.o")["check"]["state"] == "clear"
    assert "places" not in by_id(out, "t.o")


def test_only_the_first_planets_are_named_and_the_rest_counted(graph):
    frees = {f"P{i:02}": i for i in range(PLACES_SHOWN + 3)}
    out = expand_graph(graph, ["t.g"], extract(frees))
    places = by_id(out, "t.c")["places"]
    assert [p["free"] for p in places["planets"]] == list(range(PLACES_SHOWN))
    assert places["more"] == 3


def test_a_planet_without_a_known_value_is_left_out_and_no_planets_means_no_places(graph):
    doc = extract({"Alpha": 0, "Beta": 0})
    doc["room"]["by_planet"]["rows"][1][1] = None
    out = expand_graph(graph, ["t.g"], doc)
    assert [p["planet"] for p in by_id(out, "t.c")["places"]["planets"]] == ["Alpha"]
    doc["room"]["by_planet"] = {"columns": [], "rows": []}
    assert "places" not in by_id(expand_graph(graph, ["t.g"], doc), "t.c")
    del doc["room"]
    assert "places" not in by_id(expand_graph(graph, ["t.g"], doc), "t.c")


def test_the_solution_graph_lists_the_planets_as_evidence(graph):
    frees = {f"P{i:02}": i for i in range(PLACES_SHOWN + 2)}
    expansion = expand_graph(graph, ["t.g"], extract(frees)).to_dict()
    overlay = weigh(
        expansion,
        {
            "empire": "Test Empire",
            "goals": {"t.g": {"horizon": "short"}},
            "why": {"t.r": "Opens slots."},
        },
    )
    doc = compose(expansion, overlay, graph)
    evidence = next(n for n in doc["nodes"] if n["id"] == "t.c")["evidence"]
    assert evidence[:2] == ["P00: 0 building slots", "P01: 1 building slots"]
    assert evidence[-1] == "and 2 more planets with more room"
    assert len(evidence) == PLACES_SHOWN + 1


# --- the real graph ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def real():
    return MechanicsGraph.load()


def test_every_place_metric_has_a_by_planet_path(real):
    wanted = {n["places"] for n in real.nodes.values() if "places" in n}
    assert wanted, "no node names its planets"
    assert [m for m in wanted if "by_planet" not in real.metrics[m]] == []


def test_nodes_about_the_whole_empire_do_not_speak_of_the_planet(real):
    """A check on a sum over the planets is a check on the empire; its title says planets."""
    empire_wide = [
        n
        for n in real.nodes.values()
        if "by_planet" in real.metrics.get(n.get("check", {}).get("metric", ""), {})
        or "places" in n
    ]
    assert len(empire_wide) >= 6
    singular = re.compile(r"\b(the|a) planet\b", re.IGNORECASE)
    for node in empire_wide:
        for field in ("title", "uncertain_title"):
            assert not singular.search(node.get(field, "")), (node["id"], field)
