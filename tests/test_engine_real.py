"""The engine on a real Solution Graph (M6 verification): built by `expand_graph` and `compose` from the
reference mid-save with a fixed overlay, then rendered headless. The identical-render, overlap and speed
checks of the small fixtures, repeated on the biggest realistic input; the shipped bundle offline."""

from __future__ import annotations

import re

import engine_driver as driver
import pytest
from conftest import MID, VULKAN, reference_save
from test_engine_page import by_id, chain_graph, needs_browser, shuffled

from admiralty.graph.expand import expand_graph
from admiralty.graph.mechanics import MechanicsGraph
from admiralty.graph.solution import compose, validate_solution_graph

GOALS = ["energy.more", "alloys.more", "research.more"]
LAYOUT_BUDGET_MS = 20000


@pytest.fixture(scope="module")
def real_graph():
    from admiralty.extract.snapshot import Extractor

    extract = Extractor().extract(str(reference_save(VULKAN, MID)), "Plexxi")
    mechanics = MechanicsGraph.load("v4.5.2")
    expansion = expand_graph(mechanics, GOALS, extract).to_dict()
    overlay = {
        "empire": "Plexxi",
        "goals": {goal: {"horizon": "medium"} for goal in GOALS},
        "why": {
            c["node"]: "Fixed overlay for the render test."
            for c in expansion["key_action_candidates"]
        },
        "weights": [
            {"from": e["from"], "to": e["to"], "weight": "medium", "reason": "Fixed for the test."}
            for e in expansion["edges"]
            if any(n["id"] == e["to"] and n["type"] == "cause" for n in expansion["nodes"])
        ],
    }
    doc = compose(expansion, overlay, mechanics)
    assert validate_solution_graph(doc, mechanics, mechanics.rules) == []
    return doc


@needs_browser
def test_the_real_solution_graph_renders_identically_also_when_shuffled(real_graph):
    assert len(real_graph["nodes"]) > 30
    first = driver.render_engine(real_graph)
    assert first["nodes"] and first["edges"]
    assert driver.render_engine(real_graph) == first
    assert driver.render_engine(shuffled(real_graph, 1)) == first


@needs_browser
def test_no_node_of_the_real_solution_graph_overlaps_another(real_graph):
    state = driver.render_engine(real_graph)
    nodes = state["nodes"]
    for i, a in enumerate(nodes):
        for b in nodes[i + 1 :]:
            apart_x = abs(a["x"] - b["x"]) >= (a["width"] + b["width"]) / 2
            apart_y = abs(a["y"] - b["y"]) >= (a["height"] + b["height"]) / 2
            assert apart_x or apart_y, f"{a['id']} overlaps {b['id']}"
    placed = by_id(state)
    assert all(goal in placed for goal in GOALS)
    assert all(
        placed[goal]["x"] < placed[action["node"]]["x"]
        for goal in GOALS
        for action in real_graph["key_actions"]
    )


@needs_browser
def test_the_layout_of_the_real_solution_graph_stays_within_its_budget(real_graph):
    hook = 'document.body.setAttribute("data-layout-ms", String(window.engineLayoutMs));'
    dom = driver.engine_dom(real_graph, after_ready=hook)
    elapsed = int(re.search(r'data-layout-ms="(\d+)"', dom).group(1))
    print(f"layout of {len(real_graph['nodes'])} nodes: {elapsed} ms")
    assert elapsed < LAYOUT_BUDGET_MS


@needs_browser
def test_the_bundled_page_runs_offline_with_its_own_libraries_and_font(tmp_path):
    """The shipped file as it is, with name resolution off: layout from the inlined libraries, Exo 2 from its data URIs."""
    bundled = driver.ENGINE / "dist" / "index.html"
    hook = (
        'document.body.setAttribute("data-fonts", ["400", "600"].map('
        '(w) => document.fonts.check(`${w} 15px "Exo 2"`)).join());'
    )
    dom = driver.engine_dom(chain_graph(), index=bundled, after_ready=hook)
    state = driver.read_state(dom)
    assert [n["id"] for n in state["nodes"]] == sorted(n["id"] for n in chain_graph()["nodes"])
    assert 'data-fonts="true,true"' in dom
