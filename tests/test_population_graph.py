"""The curated pop growth, housing, amenities, stability and slots domains of the 4.5.2 pack.

Same shape as test_progress_graph, plus the shared nodes that tie the economy together:
`pop_growth.grow_pops` for every "no spare pops" Obstacle, `jobs.free_jobs` for every "no free job
slot" one, and the circle food -> pops -> food that M5 names a Vicious Circle.
"""

from __future__ import annotations

import pytest

from hlidskjalf.graph.mechanics import MechanicsGraph, validate

GOALS = {
    "pop_growth.faster": "pop_growth.technology.tech_genome_mapping.logistic_growth_mult",
    "housing.enough": "housing.district.district_city.planet_housing_add",
    "amenities.enough": "amenities.job.entertainer.planet_amenities_add",
    "stability.up": "stability.building.building_order_keep.planet_stability_add",
    "slots.more": "building_slots.zone.zone_default.max_buildings",
}

NO_SPARE_POPS = [
    "energy.no_spare_pops",
    "minerals.no_spare_pops",
    "food.no_spare_pops",
    "alloys.no_spare_pops",
    "unity.no_spare_pops",
    "research.no_spare_pops",
    "naval_capacity.no_spare_pops",
    "amenities.no_spare_pops",
    "stability.no_spare_pops",
]

NO_JOB_SLOT = [
    "energy.no_generator_slot",
    "minerals.no_mining_slot",
    "food.no_farming_slot",
    "alloys.no_foundry_slot",
    "unity.no_unity_job_slot",
    "research.no_researcher_slot",
    "amenities.no_amenity_slot",
    "stability.no_order_slot",
]


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
    assert amounts["pop_growth.technology.tech_genome_mapping.logistic_growth_mult"] == 0.1
    assert amounts["pop_growth.technology.tech_micro_replicators.planet_pop_assembly_mult"] == 0.1
    assert amounts["housing.district.district_city.planet_housing_add"] == 1000
    assert amounts["housing.building.building_urban_dwellings.planet_housing_add"] == 2400
    assert amounts["stability.building.building_order_keep.planet_stability_add"] == 5
    assert amounts["stability.job.soldier.planet_stability_add"] == 1
    assert amounts["building_slots.zone.zone_default.max_buildings"] == 6
    assert amounts["district_slots.building.building_capital.planet_max_districts_add"] == 1


@pytest.mark.parametrize("obstacle", NO_SPARE_POPS)
def test_every_no_spare_pops_obstacle_hands_over_to_pop_growth(graph, obstacle):
    assert graph.node(obstacle)["remedies"] == ["pop_growth.grow_pops"]


@pytest.mark.parametrize("obstacle", NO_JOB_SLOT)
def test_every_job_slot_obstacle_hands_over_to_the_shared_jobs_remedy(graph, obstacle):
    assert graph.node(obstacle)["remedies"] == ["jobs.free_jobs"]


def test_the_shared_jobs_remedy_reaches_the_slot_remedies(graph):
    assert {"slots.more_district_slots", "slots.more_building_slots"} <= set(
        graph.reachable("energy.more")
    )


def test_pop_growth_lists_housing_as_the_answer_to_a_full_planet(graph):
    assert graph.node("pop_growth.no_room")["remedies"] == ["housing.free_housing"]
    assert "housing.free_housing" in graph.reachable("pop_growth.faster")


def test_the_food_circle_is_marked_and_has_a_break_point(graph):
    members = {
        "food.staff_farmers",
        "food.no_spare_pops",
        "pop_growth.grow_pops",
        "pop_growth.food_deficit",
    }
    assert {graph.node(m).get("circle") for m in members} == {"food_needs_pops"}
    assert [m for m in members if graph.node(m).get("break_point")] == ["food.staff_farmers"]
    assert members <= set(graph.reachable("food.positive"))
    assert members <= set(graph.reachable("energy.more"))
