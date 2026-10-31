"""engine/ encodings, legend, header, lists and the click panel (M6 step 4)."""

from __future__ import annotations

import copy
import json
from html.parser import HTMLParser
from importlib import resources

import engine_driver as driver
import pytest
from jsonschema import Draft202012Validator
from test_engine_page import _node, chain_graph, circle_graph, needs_browser

SCRIPT_TEXT = "<script>window.pwned = 1</script>"


def two_circles_graph() -> dict:
    """The food circle plus a second one (housing), so circle colours can be told apart."""
    graph = circle_graph()
    graph["nodes"] += [
        _node("housing.more", "goal", "More housing"),
        _node("housing.few_districts", "cause", "Too few districts"),
        _node("housing.build_districts", "remedy", "Build districts"),
        _node("housing.needs_alloys", "obstacle", "Districts need alloys"),
        _node("alloys.more_alloys", "remedy", "Make more alloys"),
        _node("alloys.needs_housing", "obstacle", "Alloy jobs need housing"),
    ]
    graph["edges"] += [
        {"from": "housing.more", "to": "housing.few_districts", "kind": "cause"},
        {"from": "housing.few_districts", "to": "housing.build_districts", "kind": "remedy"},
        {"from": "housing.build_districts", "to": "housing.needs_alloys", "kind": "obstacle"},
        {"from": "housing.needs_alloys", "to": "alloys.more_alloys", "kind": "remedy"},
        {"from": "alloys.more_alloys", "to": "alloys.needs_housing", "kind": "obstacle"},
        {"from": "alloys.needs_housing", "to": "housing.build_districts", "kind": "remedy"},
    ]
    graph["circles"].append(
        {
            "id": "housing_needs_alloys",
            "members": [
                "housing.build_districts",
                "housing.needs_alloys",
                "alloys.more_alloys",
                "alloys.needs_housing",
            ],
            "break_point": None,
        }
    )
    return graph


def rich_graph() -> dict:
    """A model node, every Remedy status and Obstacle check state, a Crisis Goal and Playbook Rule ids."""
    graph = chain_graph()
    graph["nodes"][0] |= {"crisis": True}
    graph["nodes"][3] |= {"rules": ["unemployed-before-colonies"], "text": "Put pops on the jobs."}
    graph["nodes"][5] |= {"status": "obstructed"}
    graph["nodes"][6] |= {"status": "pending"}
    graph["nodes"] += [
        _node("energy.credits_clear", "obstacle", "Credits are fine", check_state="clear"),
        _node(
            "energy.unknown_obstacle",
            "obstacle",
            "Something unknown",
            check_state="unknown",
            evidence=[],
        ),
        _node(
            "energy.judged",
            "obstacle",
            "Needs judgement",
            check_state="judgement",
            evidence=["Julian has to look"],
        ),
        {
            "id": "model.edict_swap",
            "type": "remedy",
            "source": "model",
            "title": "Swap an edict",
            "reason": "The save shows an idle edict slot.",
            "ratings": {"strength": "low", "speed": "high", "cost": "low"},
        },
    ]
    graph["edges"] += [
        {"from": "energy.staff_technicians", "to": "energy.credits_clear", "kind": "obstacle"},
        {"from": "energy.staff_technicians", "to": "energy.unknown_obstacle", "kind": "obstacle"},
        {"from": "energy.staff_technicians", "to": "energy.judged", "kind": "obstacle"},
        {"from": "energy.weak_multipliers", "to": "model.edict_swap", "kind": "remedy"},
    ]
    graph["pruned"] = [{"id": "energy.old_idea", "reason": "Not useful at this stage."}]
    return graph


def script_graph() -> dict:
    """Every free-text field carries markup that must only ever be shown as text."""
    graph = chain_graph()
    graph["nodes"][3]["title"] = "<b>Staff</b> technicians"
    graph["nodes"][3]["text"] = "<img src=x onerror=alert(1)>"
    graph["nodes"][4]["evidence"] = [SCRIPT_TEXT, "pops.unemployed 12 > 0"]
    graph["key_actions"][0]["why"] = "<i>Because</i> " + SCRIPT_TEXT
    graph["pruned"] = [{"id": "energy.old_idea", "reason": "<u>cut</u>"}]
    return graph


FIXTURES = {
    "two_circles": two_circles_graph,
    "rich": rich_graph,
    "script": script_graph,
}


class Tags(HTMLParser):
    def __init__(self, html: str):
        super().__init__()
        self.tags: list[str] = []
        self.ids: dict[str, str] = {}
        self._open: list[str | None] = []
        self.text: dict[str, list[str]] = {}
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        ident = dict(attrs).get("id")
        if tag not in ("meta", "link", "input", "br", "img"):
            self._open.append(ident)

    def handle_endtag(self, tag):
        if self._open:
            self._open.pop()

    def handle_data(self, data):
        for ident in self._open:
            if ident:
                self.text.setdefault(ident, []).append(data)


@pytest.mark.parametrize("name", FIXTURES)
def test_fixture_graphs_satisfy_the_solution_graph_schema(name):
    text = (resources.files("admiralty.graph") / "solution.schema.json").read_text("utf-8")
    errors = list(Draft202012Validator(json.loads(text)).iter_errors(FIXTURES[name]()))
    assert errors == []


def nodes_of(state: dict) -> dict:
    return {node["id"]: node for node in state["nodes"]}


# --- Vicious Circles ----------------------------------------------------------------------------------


@needs_browser
def test_each_circle_has_its_own_colour_its_members_and_inner_edges_share_it():
    graph = two_circles_graph()
    state = driver.render_engine(graph)
    colours = {c["id"]: c["color"] for c in state["circles"]}
    assert len(set(colours.values())) == 2
    nodes = nodes_of(state)
    for circle in graph["circles"]:
        for member in circle["members"]:
            assert nodes[member]["color"] == colours[circle["id"]]
    members = {m for c in graph["circles"] for m in c["members"]}
    assert all(n["color"] is None for i, n in nodes.items() if i not in members)
    for edge in state["edges"]:
        circle = next(
            (
                c
                for c in graph["circles"]
                if edge["from"] in c["members"] and edge["to"] in c["members"]
            ),
            None,
        )
        assert edge["color"] == (colours[circle["id"]] if circle else None)
    assert any(edge["color"] for edge in state["edges"])


@needs_browser
def test_the_break_point_is_marked_and_a_circle_without_one_marks_nothing():
    state = driver.render_engine(two_circles_graph())
    nodes = nodes_of(state)
    assert [i for i, n in nodes.items() if n["break_point"]] == ["food.staff_farmers"]
    assert "break point" in nodes["food.staff_farmers"]["tag"]
    assert all("break point" not in n["tag"] for i, n in nodes.items() if i != "food.staff_farmers")
    assert [e["id"] for e in state["legend"] if e["id"].startswith("circle:")] == [
        "circle:food_needs_pops",
        "circle:housing_needs_alloys",
    ]
    assert any(e["id"] == "break_point" for e in state["legend"])


@needs_browser
def test_a_legend_circle_click_selects_its_members_and_shows_the_circle():
    graph = two_circles_graph()
    dom = driver.engine_dom(
        graph,
        after_ready="document.querySelector('[data-legend=\"circle:food_needs_pops\"]').click()",
    )
    state = driver.read_state(dom)
    assert state["selected"] == sorted(graph["circles"][0]["members"])
    assert state["panel"]["kind"] == "circle"
    assert [m["id"] for m in state["panel"]["members"]] == graph["circles"][0]["members"]
    assert state["panel"]["break_point"]["id"] == "food.staff_farmers"


# --- model nodes, status, Crisis, legend --------------------------------------------------------------


@needs_browser
def test_model_nodes_are_marked_and_graph_nodes_are_not():
    state = driver.render_engine(rich_graph())
    nodes = nodes_of(state)
    assert nodes["model.edict_swap"]["model"] is True
    assert nodes["model.edict_swap"]["tag"].startswith("model")
    assert all(n["model"] is False for i, n in nodes.items() if i != "model.edict_swap")
    assert all(
        not n["tag"].startswith("model") for i, n in nodes.items() if i != "model.edict_swap"
    )
    assert any(e["id"] == "model" for e in state["legend"])


@needs_browser
def test_status_check_state_and_crisis_are_in_words_and_the_legend_lists_only_what_occurs():
    state = driver.render_engine(rich_graph())
    nodes = nodes_of(state)
    assert nodes["energy.research_multiplier"]["status"] == "pending"
    assert nodes["energy.research_multiplier"]["tag"].endswith("pending")
    assert nodes["pop_growth.grow_pops"]["status"] == "obstructed"
    assert nodes["energy.staff_technicians"]["status"] == "actionable"
    assert nodes["energy.no_spare_pops"]["check_state"] == "present"
    # checked and clear: not in the way, so not drawn
    assert "energy.credits_clear" not in nodes
    assert nodes["energy.more"]["crisis"] is True and "CRISIS" in nodes["energy.more"]["tag"]
    legend = [e["id"] for e in state["legend"]]
    assert legend == [
        "type:goal",
        "type:cause",
        "type:remedy",
        "type:obstacle",
        "status:actionable",
        "status:pending",
        "status:obstructed",
        "check:present",
        "check:unknown",
        "check:judgement",
        "size",
        "crisis",
        "model",
    ]
    plain = driver.render_engine(chain_graph())
    assert [e["id"] for e in plain["legend"]] == [
        "type:goal",
        "type:cause",
        "type:remedy",
        "type:obstacle",
        "status:actionable",
        "check:present",
        "size",
    ]
    assert all(e["label"].strip() for e in state["legend"])


# --- header and lists ---------------------------------------------------------------------------------


@needs_browser
def test_header_and_lists_show_counts_key_actions_and_the_pruned_reasons():
    graph = rich_graph()
    dom = driver.engine_dom(graph)
    state = driver.read_state(dom)
    assert state["header"]["counts"] == {
        "nodes": len(graph["nodes"]),
        "model_nodes": 1,
        "circles": 0,
        "key_actions": 2,
        "pruned": 1,
    }
    for part in ("Plexxi", "2259.12.25", "v4.5.2"):
        assert part in state["header"]["text"]
    assert [a["rank"] for a in state["key_actions"]] == [1, 2]
    assert state["key_actions"][0]["text"].startswith("1. Research an energy multiplier technology")
    assert state["pruned"] == [{"id": "energy.old_idea", "reason": "Not useful at this stage."}]
    page = Tags(dom)
    assert "".join(page.text["header-text"]) == state["header"]["text"]
    assert "Not useful at this stage." in "".join(page.text["pruned"])
    assert "Key Actions, ranked" in "".join(page.text["actions-section"])


@needs_browser
def test_a_key_action_in_the_list_selects_its_node():
    graph = chain_graph()
    state = driver.render_engine(
        graph, after_ready="document.querySelector('#key-actions li:nth-child(2)').click()"
    )
    assert state["selected"] == ["pop_growth.grow_pops"]
    assert state["panel"]["rank"] == 2


# --- the click panel ----------------------------------------------------------------------------------


@needs_browser
def test_a_click_shows_what_the_json_says_about_the_node():
    graph = rich_graph()
    node = next(n for n in graph["nodes"] if n["id"] == "energy.staff_technicians")
    state = driver.render_engine(
        graph, after_ready='AdmiraltyEngine.click("energy.staff_technicians")'
    )
    panel = state["panel"]
    assert state["selected"] == ["energy.staff_technicians"]
    assert (panel["type"], panel["title"], panel["text"]) == ("remedy", node["title"], node["text"])
    assert panel["status"] == "actionable" and panel["ratings"] == node["ratings"]
    assert panel["rules"] == ["unemployed-before-colonies"]
    assert [r["id"] for r in panel["serves"]] == ["energy.more"]
    assert [(e["id"], e["kind"]) for e in panel["edges_in"]] == [("energy.few_producers", "remedy")]
    assert {e["id"] for e in panel["edges_out"]} == {
        "energy.no_spare_pops",
        "energy.credits_clear",
        "energy.unknown_obstacle",
        "energy.judged",
    }
    assert "rank" not in panel and "reason" not in panel


@needs_browser
def test_a_goal_shows_its_mark_in_the_node_and_the_panel():
    graph = rich_graph()
    goal = next(n for n in graph["nodes"] if n["id"] == "energy.more")
    goal["mark"] = "flag"
    state = driver.render_engine(graph, after_ready='AdmiraltyEngine.click("energy.more")')
    assert next(n for n in state["nodes"] if n["id"] == "energy.more")["mark"] == "flag"
    assert state["panel"]["mark"] == "flag"
    assert "mark" not in next(n for n in state["nodes"] if n["id"] == "energy.few_producers")


@needs_browser
def test_an_unresolved_cause_is_in_words_in_the_legend_and_in_the_panel():
    graph = chain_graph()
    cause = next(n for n in graph["nodes"] if n["id"] == "energy.few_producers")
    cause["unresolved"] = True
    state = driver.render_engine(graph, after_ready='AdmiraltyEngine.click("energy.few_producers")')
    node = nodes_of(state)["energy.few_producers"]
    assert node["unresolved"] is True and node["tag"].endswith("unresolved")
    assert state["panel"]["unresolved"] is True
    assert "unresolved" in [e["id"] for e in state["legend"]]
    plain = driver.render_engine(chain_graph())
    assert "unresolved" not in [e["id"] for e in plain["legend"]]
    assert all("unresolved" not in n for n in plain["nodes"])


@needs_browser
def test_a_click_on_an_obstacle_shows_check_state_and_evidence_strings_unchanged():
    graph = rich_graph()
    obstacle = next(n for n in graph["nodes"] if n["id"] == "energy.judged")
    dom = driver.engine_dom(graph, after_ready='AdmiraltyEngine.click("energy.judged")')
    state = driver.read_state(dom)
    assert state["panel"]["check_state"] == "judgement"
    assert state["panel"]["evidence"] == obstacle["evidence"]
    page = Tags(dom)
    shown = "".join(page.text["panel-body"])
    assert "Julian has to look" in shown and "judgement" in shown


@needs_browser
def test_a_click_on_a_model_node_shows_its_reason_and_a_key_action_its_rank_and_why():
    graph = rich_graph()
    model = driver.render_engine(graph, after_ready='AdmiraltyEngine.click("model.edict_swap")')
    assert model["panel"]["reason"] == "The save shows an idle edict slot."
    assert model["panel"]["source"] == "model"
    action = driver.render_engine(
        graph, after_ready='AdmiraltyEngine.click("pop_growth.grow_pops")'
    )
    key = graph["key_actions"][1]
    assert (action["panel"]["rank"], action["panel"]["why"]) == (key["rank"], key["why"])
    assert [r["id"] for r in action["panel"]["unlocks"]] == key["unlocks"]
    assert [r["id"] for r in action["panel"]["serves"]] == key["serves"]


@needs_browser
def test_a_second_click_replaces_the_first_and_a_click_on_the_background_clears_it():
    state = driver.render_engine(
        chain_graph(),
        after_ready=(
            'AdmiraltyEngine.click("energy.more"); AdmiraltyEngine.click("energy.no_spare_pops");'
        ),
    )
    assert state["selected"] == ["energy.no_spare_pops"]
    assert state["panel"]["id"] == "energy.no_spare_pops"
    state = driver.render_engine(
        chain_graph(),
        after_ready='AdmiraltyEngine.click("energy.more"); AdmiraltyEngine.clickBackground();',
    )
    assert state["selected"] == [] and state["panel"] is None


# --- no injected HTML ---------------------------------------------------------------------------------


@needs_browser
def test_markup_in_the_data_is_shown_as_text_and_adds_no_element():
    clicks = (
        'AdmiraltyEngine.click("energy.no_spare_pops");'
        'document.querySelector("#key-actions li").click();'
        'AdmiraltyEngine.click("energy.staff_technicians");'
    )
    baseline = copy.deepcopy(script_graph())
    baseline["nodes"][3]["title"] = "Staff technicians"
    baseline["nodes"][3]["text"] = "plain"
    baseline["nodes"][4]["evidence"] = ["plain"]
    baseline["key_actions"][0]["why"] = "plain"
    baseline["pruned"] = [{"id": "energy.old_idea", "reason": "plain"}]
    plain = Tags(driver.engine_dom(baseline, after_ready=clicks))

    dom = driver.engine_dom(script_graph(), after_ready=clicks)
    page = Tags(dom)
    assert sorted(page.tags) == sorted(plain.tags)
    assert "<b>Staff</b> technicians" in "".join(page.text["panel-body"])
    assert "<i>Because</i>" in "".join(page.text["key-actions"])
    assert "<u>cut</u>" in "".join(page.text["pruned"])
    state = driver.read_state(dom)
    assert state["panel"]["text"] == "<img src=x onerror=alert(1)>"

    evidence = Tags(
        driver.engine_dom(
            script_graph(), after_ready='AdmiraltyEngine.click("energy.no_spare_pops")'
        )
    )
    assert SCRIPT_TEXT in "".join(evidence.text["panel-body"])
    assert evidence.tags.count("script") == plain.tags.count("script")


# --- focus, ranks, icons (docs/plans/M6-revision.md) ---------------------------------------------------


def _chain(graph: dict, start: str) -> set[str]:
    chain = {start}
    for here, there in (("to", "from"), ("from", "to")):
        queue, seen = [start], {start}
        while queue:
            current = queue.pop()
            for edge in graph["edges"]:
                if edge[here] == current and edge[there] not in seen:
                    seen.add(edge[there])
                    chain.add(edge[there])
                    queue.append(edge[there])
    return chain


@needs_browser
def test_a_click_focuses_the_whole_chain_and_fades_the_rest():
    graph = chain_graph()
    target = graph["key_actions"][0]["node"]
    state = driver.render_engine(graph, after_ready=f'AdmiraltyEngine.click("{target}")')
    expected = _chain(graph, target)
    assert set(state["focus"]) == expected
    assert {n["id"] for n in state["nodes"] if not n["faded"]} == expected


@needs_browser
def test_a_click_on_the_background_ends_the_focus():
    graph = chain_graph()
    target = graph["key_actions"][0]["node"]
    state = driver.render_engine(
        graph,
        after_ready=f'AdmiraltyEngine.click("{target}"); AdmiraltyEngine.clickBackground()',
    )
    assert state["focus"] == [] and not any(n["faded"] for n in state["nodes"])


@needs_browser
def test_a_key_action_in_the_list_focuses_its_chain():
    graph = chain_graph()
    state = driver.render_engine(
        graph, after_ready="document.querySelector('#key-actions li:nth-child(2)').click()"
    )
    assert set(state["focus"]) == _chain(graph, "pop_growth.grow_pops")


@needs_browser
def test_node_size_follows_the_weighted_impact_on_the_goals():
    graph = chain_graph()
    cause_edges = [e for e in graph["edges"] if e["kind"] == "cause"]
    assert len(cause_edges) >= 2
    strong, weak = cause_edges[0], cause_edges[1]
    strong |= {"weight": "high", "weight_reason": "Most of the gap."}
    weak |= {"weight": "low", "weight_reason": "A small share."}
    for edge in cause_edges[2:]:
        edge |= {"weight": "medium", "weight_reason": "Some."}
    state = driver.render_engine(graph)
    nodes = {n["id"]: n for n in state["nodes"]}
    assert nodes[strong["to"]]["scale"] > nodes[weak["to"]]["scale"]
    assert nodes[strong["to"]]["impact"] == 1
    assert {n["scale"] for n in state["nodes"] if n["type"] == "goal"} == {1}
    for edge in graph["edges"]:
        if edge["kind"] == "obstacle":
            assert nodes[edge["to"]]["impact"] >= nodes[edge["from"]]["impact"]


@needs_browser
def test_dark_is_the_default_theme_and_the_toggle_switches_to_light():
    graph = chain_graph()
    assert driver.render_engine(graph)["theme"] == "dark"
    switched = driver.render_engine(
        graph, after_ready="document.getElementById('theme-toggle').click()"
    )
    assert switched["theme"] == "light"


@needs_browser
def test_a_clear_obstacle_is_listed_in_its_remedys_details_instead_of_drawn():
    state = driver.render_engine(
        rich_graph(), after_ready='AdmiraltyEngine.click("energy.staff_technicians")'
    )
    assert state["panel"]["checked_clear"] == ["Credits are fine"]
    assert all(e["to"] != "energy.credits_clear" for e in state["edges"])


@needs_browser
def test_a_node_shows_its_title_alone():
    graph = chain_graph()
    state = driver.render_engine(graph)
    titles = {n["id"]: n["title"] for n in graph["nodes"]}
    for node in state["nodes"]:
        title = titles[node["id"]]
        assert "\n" not in node["label"]
        assert node["label"] == title


@needs_browser
def test_the_line_legend_explains_the_kinds_of_line_in_the_graph():
    graph = chain_graph()
    edge = next(e for e in graph["edges"] if e["kind"] == "cause")
    edge |= {"weight": "high", "weight_reason": "Most of it."}
    state = driver.render_engine(graph)
    ids = [e["id"] for e in state["edge_legend"]]
    assert "edge:high" in ids and "edge:present" in ids and "edge:serves" not in ids
    assert all(e["label"].strip() for e in state["edge_legend"])


@needs_browser
def test_a_selection_adds_no_lines():
    graph = chain_graph()
    before = driver.render_engine(graph)["edges"]
    target = graph["key_actions"][0]["node"]
    after = driver.render_engine(graph, after_ready=f'AdmiraltyEngine.click("{target}")')["edges"]
    assert after == before


FLAG_PNG = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4z8DwHwAFAAH/"
    "iZk9HQAAAABJRU5ErkJggg=="
)


@needs_browser
def test_a_node_about_an_empire_shows_its_flag_and_names_it_in_the_panel():
    graph = rich_graph()
    node = next(n for n in graph["nodes"] if n["id"] == "energy.few_producers")
    node |= {"empire": "Pallyrian Accord", "flag": FLAG_PNG}
    state = driver.render_engine(graph, after_ready='AdmiraltyEngine.click("energy.few_producers")')
    assert next(n for n in state["nodes"] if n["id"] == "energy.few_producers")["flag"] is True
    assert state["panel"]["empire"] == "Pallyrian Accord"
    assert not any(n.get("flag") for n in state["nodes"] if n["id"] != "energy.few_producers")


@needs_browser
def test_an_empire_without_a_drawable_flag_keeps_the_placeholder_of_its_type():
    graph = rich_graph()
    node = next(n for n in graph["nodes"] if n["id"] == "energy.few_producers")
    node |= {"empire": "Pallyrian Accord", "flag": "javascript:alert(1)"}
    state = driver.render_engine(graph)
    assert "flag" not in next(n for n in state["nodes"] if n["id"] == "energy.few_producers")
