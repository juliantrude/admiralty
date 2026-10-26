"""engine/index.html core: loading, validation, layers, no overlap, identical renders (M6 step 3)."""

from __future__ import annotations

import copy
import random
import re
from importlib import resources

import engine_driver as driver
import pytest
from jsonschema import Draft202012Validator

needs_browser = pytest.mark.skipif(
    driver.skip_reason() is not None, reason=driver.skip_reason() or ""
)


def _node(id_, type_, title, **extra):
    node = {"id": id_, "type": type_, "source": "graph", "title": title}
    if type_ == "goal":
        node |= {"horizon": "short", "crisis": False}
    if type_ == "remedy":
        node |= {
            "status": "actionable",
            "ratings": {"strength": "high", "speed": "medium", "cost": "low"},
        }
    if type_ == "obstacle":
        node |= {"check_state": "present", "evidence": ["pops.unemployed 12 > 0"]}
    return node | extra


def chain_graph() -> dict:
    """Goal -> Cause -> Remedy (Key Action) and Goal -> Cause -> Obstacle -> Remedy."""
    return {
        "schema": 1,
        "game_version": "v4.5.2",
        "date": "2259.12.25",
        "empire": "Plexxi",
        "nodes": [
            _node("energy.more", "goal", "More energy credits"),
            _node("energy.few_producers", "cause", "Too few energy producers"),
            _node("energy.weak_multipliers", "cause", "Weak energy multipliers"),
            _node("energy.staff_technicians", "remedy", "Staff more Technicians"),
            _node("energy.no_spare_pops", "obstacle", "There are no spare pops to staff the jobs"),
            _node("pop_growth.grow_pops", "remedy", "Grow the population"),
            _node(
                "energy.research_multiplier", "remedy", "Research an energy multiplier technology"
            ),
        ],
        "edges": [
            {"from": "energy.more", "to": "energy.few_producers", "kind": "cause"},
            {"from": "energy.more", "to": "energy.weak_multipliers", "kind": "cause"},
            {"from": "energy.few_producers", "to": "energy.staff_technicians", "kind": "remedy"},
            {"from": "energy.staff_technicians", "to": "energy.no_spare_pops", "kind": "obstacle"},
            {"from": "energy.no_spare_pops", "to": "pop_growth.grow_pops", "kind": "remedy"},
            {
                "from": "energy.weak_multipliers",
                "to": "energy.research_multiplier",
                "kind": "remedy",
            },
        ],
        "circles": [],
        "key_actions": [
            {
                "rank": 1,
                "node": "energy.research_multiplier",
                "serves": ["energy.more"],
                "unlocks": [],
                "why": "Needs no spare pops.",
            },
            {
                "rank": 2,
                "node": "pop_growth.grow_pops",
                "serves": ["energy.more"],
                "unlocks": ["energy.staff_technicians"],
                "why": "Unlocks the Technician jobs.",
            },
        ],
        "pruned": [],
    }


def two_goals_graph() -> dict:
    """Two Goals sharing one Remedy."""
    graph = chain_graph()
    graph["nodes"] += [
        _node("minerals.more", "goal", "More minerals"),
        _node("minerals.few_miners", "cause", "Too few miners"),
    ]
    graph["edges"] += [
        {"from": "minerals.more", "to": "minerals.few_miners", "kind": "cause"},
        {"from": "minerals.few_miners", "to": "pop_growth.grow_pops", "kind": "remedy"},
    ]
    graph["key_actions"][1]["serves"] = ["energy.more", "minerals.more"]
    return graph


def circle_graph() -> dict:
    """A two-node Vicious Circle (food needs pops, pops need food) hanging off one Goal."""
    return {
        "schema": 1,
        "game_version": "v4.5.2",
        "date": "2259.12.25",
        "empire": "Plexxi",
        "nodes": [
            _node("food.more", "goal", "More food"),
            _node("food.few_farmers", "cause", "Too few farmers"),
            _node("food.staff_farmers", "remedy", "Staff the farms"),
            _node("food.no_spare_pops", "obstacle", "No spare pops"),
            _node("pop_growth.grow_pops", "remedy", "Grow the population"),
            _node("pop_growth.needs_food", "obstacle", "Growth needs food"),
        ],
        "edges": [
            {"from": "food.more", "to": "food.few_farmers", "kind": "cause"},
            {"from": "food.few_farmers", "to": "food.staff_farmers", "kind": "remedy"},
            {"from": "food.staff_farmers", "to": "food.no_spare_pops", "kind": "obstacle"},
            {"from": "food.no_spare_pops", "to": "pop_growth.grow_pops", "kind": "remedy"},
            {"from": "pop_growth.grow_pops", "to": "pop_growth.needs_food", "kind": "obstacle"},
            {"from": "pop_growth.needs_food", "to": "food.staff_farmers", "kind": "remedy"},
        ],
        "circles": [
            {
                "id": "food_needs_pops",
                "members": [
                    "food.staff_farmers",
                    "food.no_spare_pops",
                    "pop_growth.grow_pops",
                    "pop_growth.needs_food",
                ],
                "break_point": "food.staff_farmers",
            }
        ],
        "key_actions": [
            {
                "rank": 1,
                "node": "food.staff_farmers",
                "serves": ["food.more"],
                "unlocks": [],
                "why": "Breaks the circle.",
            }
        ],
        "pruned": [],
    }


FIXTURES = {"chain": chain_graph, "two_goals": two_goals_graph, "circle": circle_graph}


def shuffled(graph: dict, seed: int) -> dict:
    out = copy.deepcopy(graph)
    rng = random.Random(seed)
    for name in ("nodes", "edges"):
        rng.shuffle(out[name])
    return out


def by_id(state: dict) -> dict:
    return {node["id"]: node for node in state["nodes"]}


# --- the fixtures are real Solution Graphs ----------------------------------------------------------


@pytest.mark.parametrize("name", FIXTURES)
def test_fixture_graphs_satisfy_the_solution_graph_schema(name):
    text = (resources.files("hlidskjalf.graph") / "solution.schema.json").read_text("utf-8")
    import json

    errors = list(Draft202012Validator(json.loads(text)).iter_errors(FIXTURES[name]()))
    assert errors == []


# --- the page itself ----------------------------------------------------------------------------------


def test_index_html_pins_the_three_libraries_and_loads_its_own_script():
    html = (driver.ENGINE / "index.html").read_text(encoding="utf-8")
    assert driver.script_pin_problems(html) == []
    assert html.count("cdn.jsdelivr.net") == 3
    assert '<script src="engine.js"></script>' in html
    assert driver.GRAPH_SLOT in html


def test_engine_script_never_inserts_html():
    js = (driver.ENGINE / "engine.js").read_text(encoding="utf-8")
    assert not re.search(
        r"innerHTML|outerHTML|insertAdjacentHTML|document\.write|\beval\(|new Function", js
    )


# --- headless renders ---------------------------------------------------------------------------------


@needs_browser
@pytest.mark.parametrize("name", FIXTURES)
def test_goals_lie_left_and_every_edge_runs_left_to_right(name):
    graph = FIXTURES[name]()
    state = driver.render_engine(graph)
    assert state["ok"] and state["error"] is None
    nodes = by_id(state)
    assert set(nodes) == {node["id"] for node in graph["nodes"]}
    # a Vicious Circle has no first node, so its members may fall into any column
    in_circle = {m for c in graph["circles"] for m in c["members"]}
    goals = [n["id"] for n in graph["nodes"] if n["type"] == "goal"]
    others = [n["id"] for n in graph["nodes"] if n["type"] != "goal" and n["id"] not in in_circle]
    for goal in goals:
        for other in others:
            assert nodes[goal]["x"] < nodes[other]["x"]
    # a chain reads as a plan: every edge points right, except inside a Vicious Circle
    for edge in graph["edges"]:
        if edge["from"] in in_circle and edge["to"] in in_circle:
            continue
        assert nodes[edge["from"]]["x"] < nodes[edge["to"]]["x"], (edge["from"], edge["to"])


@needs_browser
@pytest.mark.parametrize("name", FIXTURES)
def test_no_node_overlaps_another_and_every_edge_joins_two_drawn_nodes(name):
    state = driver.render_engine(FIXTURES[name]())
    nodes = state["nodes"]
    for i, a in enumerate(nodes):
        for b in nodes[i + 1 :]:
            apart_x = abs(a["x"] - b["x"]) >= (a["width"] + b["width"]) / 2
            apart_y = abs(a["y"] - b["y"]) >= (a["height"] + b["height"]) / 2
            assert apart_x or apart_y, f"{a['id']} overlaps {b['id']}"
    ids = set(by_id(state))
    assert state["edges"]
    assert all(edge["from"] in ids and edge["to"] in ids for edge in state["edges"])


@needs_browser
@pytest.mark.parametrize("name", FIXTURES)
def test_the_same_data_renders_identically_also_when_nodes_and_edges_are_shuffled(name):
    graph = FIXTURES[name]()
    first = driver.render_engine(graph)
    assert driver.render_engine(graph) == first
    for seed in (1, 2):
        assert driver.render_engine(shuffled(graph, seed)) == first


@needs_browser
def test_a_different_date_or_empire_changes_only_the_header():
    graph = chain_graph()
    other = copy.deepcopy(graph) | {"date": "2300.01.01", "empire": "Somebody else"}
    first, second = driver.render_engine(graph), driver.render_engine(other)
    assert first["header"] != second["header"]
    assert "Somebody else" in second["header"]["text"] and "2300.01.01" in second["header"]["text"]
    first.pop("header"), second.pop("header")
    assert first == second


@needs_browser
def test_a_wider_title_gives_a_wider_node_and_a_long_one_is_cut():
    graph = chain_graph()
    graph["nodes"][1]["title"] = "T" * 90
    sizes = by_id(driver.render_engine(graph))
    assert sizes["energy.few_producers"]["width"] > sizes["energy.weak_multipliers"]["width"]
    long = sizes["energy.few_producers"]
    assert long["width"] <= 480 * long["scale"]  # the cap grows with the impact size step


@needs_browser
@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda g: g.pop("edges"), '"edges" is missing'),
        (lambda g: g.update(edges="x"), '"edges" is missing'),
        (
            lambda g: g["edges"].append(
                {"from": "energy.more", "to": "nope.nothing", "kind": "cause"}
            ),
            "nope.nothing",
        ),
        (lambda g: g.update(schema=2), "unsupported schema"),
        (lambda g: g["nodes"].append(dict(g["nodes"][0])), "occurs twice"),
        (lambda g: g["nodes"][0].update(type="monster"), "unknown type"),
        (lambda g: g["key_actions"][0].update(node="nope.nothing"), "nope.nothing"),
        (
            lambda g: g["circles"].append(
                {"id": "c", "members": ["nope.nothing"], "break_point": None}
            ),
            "nope.nothing",
        ),
    ],
)
def test_bad_data_shows_the_reason_and_draws_nothing(mutate, message):
    graph = chain_graph()
    mutate(graph)
    state = driver.render_engine(graph)
    assert state["ok"] is False
    assert message in state["error"]
    assert state["nodes"] == [] and state["edges"] == []


@needs_browser
def test_data_that_is_not_json_is_refused():
    state = driver.render_engine("{not json")
    assert state["ok"] is False and state["nodes"] == []


@needs_browser
def test_without_data_the_page_offers_the_file_picker():
    state = driver.render_engine(None)
    assert state == {"ok": False, "error": "no data", "nodes": [], "edges": []}
