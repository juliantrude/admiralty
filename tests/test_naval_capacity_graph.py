"""The curated naval capacity domain (M4 criterion) and walk properties of the whole real graph.

Runs against the committed pack in knowledge/4.5.2/, which carries its own generated facts, so
neither the game install nor a reference save is needed.
"""

from __future__ import annotations

import re

import pytest

from hlidskjalf.graph.mechanics import MechanicsGraph

GOAL = "naval_capacity.more"


@pytest.fixture(scope="module")
def graph() -> MechanicsGraph:
    return MechanicsGraph.load("v4.5.2")


def remedies_linking(graph: MechanicsGraph, found: list[str], fact_prefix: str) -> list[str]:
    """Reachable Remedies that link at least one fact starting with `fact_prefix`."""
    return [
        node_id
        for node_id in found
        if graph.node(node_id)["type"] == "remedy"
        and any(fact.startswith(fact_prefix) for fact in graph.node(node_id).get("facts", []))
    ]


def test_expanding_the_goal_yields_the_four_sources_each_with_obstacles(graph):
    found = graph.reachable(GOAL)
    expected = {
        "Supremacy": "naval_capacity.tradition.tr_supremacy_adopt.",
        "Anchorages": "naval_capacity.starbase_module.anchorage.",
        "naval capacity technologies": "naval_capacity.technology.tech_repeatable_naval_cap.",
        "Soldier jobs": "naval_capacity.job.soldier.",
    }
    for label, prefix in expected.items():
        remedies = remedies_linking(graph, found, prefix)
        assert remedies, f"no Remedy for {label} is reachable from {GOAL}"
        for remedy in remedies:
            obstacles = graph.node(remedy).get("obstacles", [])
            assert obstacles, f"{remedy} ({label}) has no Obstacle"
            assert all(o in found for o in obstacles)


def test_linked_facts_resolve_to_the_known_figures(graph):
    """The node text states no figures; the facts it links carry them."""

    def amounts(node_id):
        return {f["id"]: f["amount"] for f in graph.node_facts(node_id)}

    assert amounts("naval_capacity.adopt_supremacy") == {
        "naval_capacity.tradition.tr_supremacy_adopt.country_naval_cap_add": 20
    }
    assert (
        amounts("naval_capacity.build_anchorages")[
            "naval_capacity.starbase_module.anchorage.country_naval_cap_add"
        ]
        == 5
    )
    assert amounts("naval_capacity.build_logistics_offices") == {
        "naval_capacity.starbase_module.anchorage.country_naval_cap_add#2": 3
    }
    assert (
        amounts("naval_capacity.staff_soldier_jobs")[
            "naval_capacity.job.soldier.country_naval_cap_add"
        ]
        == 4
    )


def test_obstacles_checked_against_numbers_outnumber_none_of_the_remedies(graph):
    """Every Obstacle in the domain is either a metric comparison or an honest judgement-only."""
    obstacles = [n for n in graph.nodes.values() if n["type"] == "obstacle"]
    checked = [o for o in obstacles if "metric" in o["check"]]
    assert checked, "at least one Obstacle must be checkable against the Snapshot"
    for obstacle in obstacles:
        assert "metric" in obstacle["check"] or obstacle["check"] == {"judgement_only": True}


def test_node_text_has_no_figures(graph):
    for node in graph.nodes.values():
        for name in ("description", "judgement"):
            assert not re.search(r"(?<!\w)\d", node.get(name, "")), f"{node['id']}: {name}"


def test_every_goal_walk_terminates_and_stays_in_the_graph(graph):
    for goal_id in graph.goals:
        found = graph.reachable(goal_id)
        assert len(found) == len(set(found)), f"{goal_id}: a node was visited twice"
        assert set(found) <= set(graph.nodes)
        assert found == graph.reachable(goal_id), "the walk must be deterministic"


def test_every_remedy_is_reachable_from_some_goal(graph):
    reached = {n for goal_id in graph.goals for n in graph.reachable(goal_id)}
    orphans = sorted(
        node_id
        for node_id, node in graph.nodes.items()
        if node["type"] in ("remedy", "obstacle") and node_id not in reached
    )
    assert orphans == []


def test_the_walk_terminates_on_a_cycle(graph):
    """A cycle is legal in the graph; the walk must not loop on it."""
    looped = MechanicsGraph(
        version="v4.5.2",
        goals={"d.g": {"id": "d.g", "title": "g", "causes": ["d.a"]}},
        nodes={
            "d.a": {"id": "d.a", "type": "cause", "remedies": ["d.r"]},
            "d.r": {"id": "d.r", "type": "remedy", "obstacles": ["d.o"]},
            "d.o": {"id": "d.o", "type": "obstacle", "remedies": ["d.r"]},
        },
        metrics={},
    )
    assert looped.reachable("d.g") == ["d.a", "d.r", "d.o"]
