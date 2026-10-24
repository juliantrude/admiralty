"""The curated Unity, influence and research domains of the committed 4.5.2 pack.

Same shape as test_economy_graph: each Goal expands, every Remedy meets an Obstacle, the linked
facts carry the figures the prose leaves out, and the cross-domain links resolve.
"""

from __future__ import annotations

import pytest

from hlidskjalf.graph.mechanics import MechanicsGraph, validate

GOALS = {
    "unity.more": "unity.job.bureaucrat.produces_unity",
    "influence.positive": "influence.ascension_perk.ap_galactic_force_projection.country_power_projection_influence_produces_add",
    "research.more": "research.job.physicist.produces_physics_research",
}


@pytest.fixture(scope="module")
def graph() -> MechanicsGraph:
    return MechanicsGraph.load("v4.5.2")


def test_the_pack_validates_without_errors_or_warnings():
    assert validate("v4.5.2") == []


@pytest.mark.parametrize("goal_id", GOALS)
def test_goal_expands_to_remedies_that_each_have_an_obstacle(graph, goal_id):
    found = graph.reachable(goal_id)
    remedies = [n for n in found if graph.node(n)["type"] == "remedy"]
    assert len(remedies) >= 3, f"{goal_id} reaches too few Remedies"
    for remedy in remedies:
        obstacles = graph.node(remedy).get("obstacles", [])
        assert obstacles, f"{remedy} has no Obstacle"
        assert all(o in found for o in obstacles)


@pytest.mark.parametrize(("goal_id", "fact"), GOALS.items())
def test_the_goal_reaches_a_remedy_that_links_its_key_fact(graph, goal_id, fact):
    found = graph.reachable(goal_id)
    linked = {
        f["id"] for n in found if graph.node(n)["type"] == "remedy" for f in graph.node_facts(n)
    }
    assert fact in linked


def test_linked_facts_resolve_to_the_known_figures(graph):
    amounts = {f["id"]: f["amount"] for n in graph.nodes for f in graph.node_facts(n)}
    assert amounts["unity.job.bureaucrat.produces_unity"] == 3
    assert amounts["unity.ascension_perk.ap_one_vision.country_unity_produces_mult"] == 0.1
    assert amounts["unity.edict.will_to_power.cost_unity"] == 75
    assert amounts["research.job.physicist.produces_physics_research"] == 3
    assert amounts["research.tradition.tr_discovery_finish.all_technology_research_speed"] == 0.1
    assert amounts["influence.edict.will_to_power.country_ambition_influence_produces_add"] == 5


def test_naval_capacity_reaches_the_shared_unity_remedy_through_its_obstacle(graph):
    assert "unity.raise_income" in graph.reachable("naval_capacity.more")
    assert graph.node("naval_capacity.supremacy_needs_unity")["remedies"] == ["unity.raise_income"]


@pytest.mark.parametrize(
    "obstacle",
    [
        "influence.viceroys_needs_unity",
        "influence.diplomacy_needs_unity",
        "influence.decree_costs_unity",
        "research.discovery_needs_unity",
    ],
)
def test_unity_gated_obstacles_hand_over_to_the_unity_remedy(graph, obstacle):
    assert graph.node(obstacle)["remedies"] == ["unity.raise_income"]
    for goal in ("influence.positive", "research.more"):
        if obstacle.split(".")[0] in goal:
            assert "unity.raise_income" in graph.reachable(goal)
