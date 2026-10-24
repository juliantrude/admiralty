"""The curated economy domains (energy, minerals, food, alloys) of the committed 4.5.2 pack.

Same shape as test_naval_capacity_graph: each Goal expands, every Remedy meets an Obstacle, the
linked facts carry the figures the prose leaves out, and the cross-domain Remedies resolve.
"""

from __future__ import annotations

import pytest

from hlidskjalf.graph.mechanics import MechanicsGraph, validate

GOALS = {
    "energy.more": "energy.job.technician.produces_energy",
    "minerals.more": "minerals.job.miner.produces_minerals",
    "food.positive": "food.job.farmer.produces_food",
    "alloys.more": "alloys.job.foundry.produces_alloys",
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


@pytest.mark.parametrize(("goal_id", "job_fact"), GOALS.items())
def test_the_job_remedy_links_the_producer_job_fact(graph, goal_id, job_fact):
    found = graph.reachable(goal_id)
    linked = {
        f["id"] for n in found if graph.node(n)["type"] == "remedy" for f in graph.node_facts(n)
    }
    assert job_fact in linked


def test_linked_facts_resolve_to_the_known_figures(graph):
    amounts = {f["id"]: f["amount"] for n in graph.nodes for f in graph.node_facts(n)}
    assert amounts["energy.job.technician.produces_energy"] == 6
    assert amounts["minerals.job.miner.produces_minerals"] == 4
    assert amounts["food.job.farmer.produces_food"] == 6
    assert amounts["alloys.job.foundry.produces_alloys"] == 3


def test_alloys_reach_the_mineral_and_energy_remedies_through_their_obstacles(graph):
    found = graph.reachable("alloys.more")
    assert "minerals.staff_miners" in found
    assert "energy.staff_technicians" in found
    assert graph.node("alloys.minerals_short")["check"]["metric"] == "minerals.net"
    assert graph.node("alloys.energy_short")["check"]["metric"] == "energy.net"
