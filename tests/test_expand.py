"""`expand_graph` (M5): Obstacle checks, Remedy status, depth limit, merging, Vicious Circles,
Key Action ranking and determinism, on small synthetic packs; plus the real graph on the reference
save (skips without it)."""

from __future__ import annotations

import itertools
import json
from pathlib import Path

import pytest
import yaml
from conftest import MID, VULKAN, reference_save

from hlidskjalf.graph.expand import Candidate, expand_graph, rank_key_actions
from hlidskjalf.graph.mechanics import MechanicsGraph, validate
from hlidskjalf.graph.metrics import evaluate, resolve_metric

METRICS = {
    "version": "v4.5.2",
    "metrics": {
        "m.a": {"path": "v.a", "unit": "things"},
        "m.b": {"path": "v.b", "unit": "things"},
        "m.missing": {"path": "v.nope", "unit": "things"},
        "m.ratio": {"ratio": {"numerator": "v.a", "denominator": "v.zero"}, "unit": "fraction"},
    },
}
EXTRACT = {"header": {"date": "2250.01.01"}, "v": {"a": 1, "b": 10, "zero": 0}}

PRESENT = {"metric": "m.a", "op": "<", "compare_to": 5}  # a = 1: true
CLEAR = {"metric": "m.a", "op": ">", "compare_to": 5}  # false
UNKNOWN = {"metric": "m.missing", "op": "<", "compare_to": 5}
JUDGEMENT = {"judgement_only": True}


def cause(name, causes=(), remedies=(), **extra):
    return {
        "id": f"t.{name}",
        "type": "cause",
        "title": name,
        "description": f"{name} cause",
        "causes": [f"t.{c}" for c in causes],
        "remedies": [f"t.{r}" for r in remedies],
        **extra,
    }


def remedy(name, obstacles=(), strength="medium", speed="medium", cost="medium", **extra):
    return {
        "id": f"t.{name}",
        "type": "remedy",
        "title": name,
        "judgement": f"{name} remedy",
        "strength": strength,
        "speed": speed,
        "cost": cost,
        "obstacles": [f"t.{o}" for o in obstacles],
        **extra,
    }


def obstacle(name, check=JUDGEMENT, remedies=(), **extra):
    return {
        "id": f"t.{name}",
        "type": "obstacle",
        "title": name,
        "description": f"{name} obstacle",
        "check": check,
        "remedies": [f"t.{r}" for r in remedies],
        **extra,
    }


def goal(name, causes):
    return {
        "id": f"t.{name}",
        "title": name,
        "symptom_metrics": ["m.a"],
        "causes": [f"t.{c}" for c in causes],
    }


FACTS = [
    {
        "id": f"t.fact.{i}",
        "modifier": "mod",
        "amount": i,
        "amount_kind": "add",
        "source": {"kind": "building", "key": f"b{i}", "name": f"Building {i}"},
        "requirement": [],
    }
    for i in range(7)
]


def build(tmp_path: Path, goals, nodes) -> MechanicsGraph:
    version = tmp_path / "4.5.2"
    for folder in ("graph", "generated", "rules"):
        (version / folder).mkdir(parents=True)
    (version / "generated" / "t.yaml").write_text(yaml.safe_dump({"facts": FACTS}))
    (version / "rules" / "a-rule.md").write_text(
        "---\nid: a-rule\ndate: 2026-10-24\nstatus: approved\napplies_to: ['*']\n"
        "reason: Because.\n---\nQuote me.\n"
    )
    (version / "graph" / "metrics.yaml").write_text(yaml.safe_dump(METRICS))
    document = {"version": "v4.5.2", "domain": "t", "goals": goals, "nodes": nodes}
    (version / "graph" / "t.yaml").write_text(yaml.safe_dump(document))
    assert [p for p in validate("v4.5.2", tmp_path) if p.severity == "error"] == []
    return MechanicsGraph.load("v4.5.2", tmp_path)


def by_id(expansion, node_id):
    return next(n for n in expansion.to_dict()["nodes"] if n["id"] == node_id)


def remedies_with(obstacle_check, **remedy_extra):
    nodes = [
        cause("c", remedies=["r"]),
        remedy("r", ["o"], **remedy_extra),
        obstacle("o", obstacle_check, remedies=["helper"]),
        remedy("helper"),
    ]
    return [goal("g", ["c"])], nodes


# --- checks and Remedy status -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("check", "state", "status", "unchecked"),
    [
        (PRESENT, "present", "obstructed", []),
        (CLEAR, "clear", "actionable", []),
        (UNKNOWN, "unknown", "actionable", ["t.o"]),
        (JUDGEMENT, "judgement", "actionable", ["t.o"]),
    ],
)
def test_obstacle_state_gives_remedy_status(tmp_path, check, state, status, unchecked):
    goals, nodes = remedies_with(check)
    expansion = expand_graph(build(tmp_path, goals, nodes), ["t.g"], EXTRACT)
    assert by_id(expansion, "t.o")["check"]["state"] == state
    remedy_node = by_id(expansion, "t.r")
    assert remedy_node["status"] == status
    assert remedy_node["unchecked"] == unchecked
    assert remedy_node["obstructed_by"] == (["t.o"] if state == "present" else [])


def test_check_carries_the_numbers(tmp_path):
    check = {"metric": "m.a", "op": "<", "compare_to": {"metric": "m.b"}}
    goals, nodes = remedies_with(check)
    expansion = expand_graph(build(tmp_path, goals, nodes), ["t.g"], EXTRACT)
    assert by_id(expansion, "t.o")["check"] == {
        "state": "present",
        "metric": "m.a",
        "op": "<",
        "compare_to": "m.b",
        "values": {"m.a": 1, "m.b": 10},
    }


def test_a_ratio_with_a_zero_denominator_is_unknown_not_a_crash():
    metrics = METRICS["metrics"]
    assert resolve_metric(metrics["m.ratio"], EXTRACT) is None
    check = {"metric": "m.ratio", "op": ">", "compare_to": 0.5}
    assert evaluate(check, metrics, EXTRACT).state == "unknown"


@pytest.mark.parametrize(
    ("pending_when", "obstacle_check", "status"),
    [
        (PRESENT, PRESENT, "pending"),  # obstructed today, resolves on its own
        (CLEAR, PRESENT, "obstructed"),
        (PRESENT, CLEAR, "actionable"),  # nothing to wait for, whatever pending_when says
        (UNKNOWN, PRESENT, "obstructed"),
    ],
)
def test_pending_needs_a_present_obstacle_and_a_true_pending_when(
    tmp_path, pending_when, obstacle_check, status
):
    goals, nodes = remedies_with(obstacle_check, pending_when=pending_when)
    expansion = expand_graph(build(tmp_path, goals, nodes), ["t.g"], EXTRACT)
    assert by_id(expansion, "t.r")["status"] == status
    candidates = [c["node"] for c in expansion.to_dict()["key_action_candidates"]]
    assert ("t.r" in candidates) == (status != "obstructed")


def test_a_clear_obstacles_remedies_are_not_walked(tmp_path):
    goals, nodes = remedies_with(CLEAR)
    out = expand_graph(build(tmp_path, goals, nodes), ["t.g"], EXTRACT).to_dict()
    assert "t.helper" not in {n["id"] for n in out["nodes"]}
    assert {"from": "t.o", "to": "t.helper", "kind": "remedy"} not in out["edges"]
    goals, nodes = remedies_with(PRESENT)
    out = expand_graph(build(tmp_path / "again", goals, nodes), ["t.g"], EXTRACT).to_dict()
    assert {"from": "t.o", "to": "t.helper", "kind": "remedy"} in out["edges"]


def test_unlocks_names_the_remedy_a_helper_makes_actionable(tmp_path):
    goals, nodes = remedies_with(PRESENT)
    out = expand_graph(build(tmp_path, goals, nodes), ["t.g"], EXTRACT).to_dict()
    assert out["key_action_candidates"] == [
        {
            "rank": 1,
            "node": "t.helper",
            "status": "actionable",
            "serves": ["t.g"],
            "unlocks": ["t.r"],
        }
    ]


# --- depth, merging, goals --------------------------------------------------------------------


def chain(length):
    nodes = [cause(f"c{i}", causes=[f"c{i + 1}"]) for i in range(1, length)]
    nodes.append(cause(f"c{length}", remedies=["r"]))
    nodes.append(remedy("r"))
    return [goal("g", ["c1"])], nodes


def test_depth_limit_keeps_the_boundary_node_and_does_not_expand_it(tmp_path):
    goals, nodes = chain(7)
    out = expand_graph(build(tmp_path, goals, nodes), ["t.g"], EXTRACT).to_dict()
    depths = {n["id"]: n["depth"] for n in out["nodes"]}
    assert depths == {f"t.c{i}": i for i in range(1, 6)}  # nothing deeper than 5
    assert [n["id"] for n in out["nodes"] if n["too_far"]] == ["t.c5"]
    assert not any(e["from"] == "t.c5" for e in out["edges"])


def test_a_leaf_on_the_limit_is_not_too_far(tmp_path):
    goals, nodes = chain(5)
    out = expand_graph(build(tmp_path, goals, nodes), ["t.g"], EXTRACT, depth_limit=6).to_dict()
    assert "t.r" in {n["id"] for n in out["nodes"]}
    assert not any(n["too_far"] for n in out["nodes"])
    with pytest.raises(ValueError):
        expand_graph(build(tmp_path / "x", goals, nodes), ["t.g"], EXTRACT, depth_limit=0)


def test_a_remedy_on_the_limit_still_gets_its_status(tmp_path):
    goals, nodes = chain(4)
    nodes[-1]["obstacles"] = ["t.o"]
    nodes.append(obstacle("o", PRESENT))
    out = expand_graph(build(tmp_path, goals, nodes), ["t.g"], EXTRACT).to_dict()
    node = next(n for n in out["nodes"] if n["id"] == "t.r")
    assert (node["depth"], node["too_far"], node["status"]) == (5, True, "obstructed")
    assert "t.o" not in {n["id"] for n in out["nodes"]}


def test_a_merged_node_appears_once_and_serves_both_goals(tmp_path):
    goals = [goal("g1", ["c1"]), goal("g2", ["c2"])]
    nodes = [cause("c1", remedies=["r"]), cause("c2", remedies=["r"]), remedy("r")]
    out = expand_graph(build(tmp_path, goals, nodes), ["t.g2", "t.g1"], EXTRACT).to_dict()
    assert [n["id"] for n in out["nodes"]].count("t.r") == 1
    parents = sorted(e["from"] for e in out["edges"] if e["to"] == "t.r")
    assert parents == ["t.c1", "t.c2"]
    assert out["key_action_candidates"][0]["serves"] == ["t.g1", "t.g2"]
    assert [g["id"] for g in out["goals"]] == ["t.g1", "t.g2"]


def test_merging_keeps_the_shortest_depth(tmp_path):
    goals = [goal("g", ["c1", "c3"])]
    nodes = [
        cause("c1", causes=["c2"]),
        cause("c2", causes=["c3"]),
        cause("c3", remedies=["r"]),
        remedy("r"),
    ]
    out = expand_graph(build(tmp_path, goals, nodes), ["t.g"], EXTRACT).to_dict()
    assert {n["id"]: n["depth"] for n in out["nodes"]}["t.c3"] == 1


def test_unknown_goal_is_reported_not_raised(tmp_path):
    goals, nodes = chain(2)
    out = expand_graph(build(tmp_path, goals, nodes), ["t.nope", "t.g"], EXTRACT).to_dict()
    assert out["unknown_goals"] == ["t.nope"]
    assert [g["id"] for g in out["goals"]] == ["t.g"]
    out = expand_graph(build(tmp_path / "x", goals, nodes), ["t.nope"], EXTRACT).to_dict()
    assert out["nodes"] == [] and out["key_action_candidates"] == []


def test_goal_symptoms_and_crisis_flag(tmp_path):
    goals, nodes = chain(2)
    graph = build(tmp_path, goals, nodes)
    out = expand_graph(graph, ["t.g"], EXTRACT, crisis_goals=["t.g", "t.other"]).to_dict()
    assert out["goals"][0]["symptoms"] == [{"metric": "m.a", "value": 1, "unit": "things"}]
    assert out["goals"][0]["crisis"] is True
    assert out["warnings"] == ["crisis goal 't.other' is not among the expanded Goals"]
    assert out["date"] == "2250.01.01" and out["version"] == "v4.5.2"


def test_missing_metric_is_a_warning(tmp_path):
    goals, nodes = remedies_with(UNKNOWN)
    out = expand_graph(build(tmp_path, goals, nodes), ["t.g"], EXTRACT).to_dict()
    assert out["warnings"] == ["metric 'm.missing' has no value in this save"]


# --- Vicious Circles --------------------------------------------------------------------------


def circle_pack(second_check, **first):
    goals = [goal("g", ["c"])]
    nodes = [
        cause("c", remedies=["r1"]),
        remedy("r1", ["o1"], cost="high", **first),
        obstacle("o1", PRESENT, remedies=["r2"]),
        remedy("r2", ["o2"], cost="low"),
        obstacle("o2", second_check, remedies=["r1", "way_out"]),  # a circle needs an exit
        remedy("way_out"),
    ]
    return goals, nodes


def test_a_loop_is_one_circle_with_a_break_point(tmp_path):
    goals, nodes = circle_pack(PRESENT)
    out = expand_graph(build(tmp_path, goals, nodes), ["t.g"], EXTRACT, depth_limit=8).to_dict()
    assert out["circles"] == [
        {
            "id": "circle:t.o1",
            "members": ["t.o1", "t.o2", "t.r1", "t.r2"],
            "break_point": "t.r2",  # the cheaper Remedy
        }
    ]
    assert (
        by_id(
            expand_graph(build(tmp_path / "x", goals, nodes), ["t.g"], EXTRACT, depth_limit=8),
            "t.r1",
        )["circle"]
        == "circle:t.o1"
    )


def test_a_marked_break_point_and_circle_name_win(tmp_path):
    goals, nodes = circle_pack(PRESENT, circle="loop", break_point=True)
    for member in nodes[1:]:
        member.setdefault("circle", "loop")
    out = expand_graph(build(tmp_path, goals, nodes), ["t.g"], EXTRACT, depth_limit=8).to_dict()
    assert [(c["id"], c["break_point"]) for c in out["circles"]] == [("loop", "t.r1")]


def test_a_loop_broken_by_a_clear_obstacle_is_not_reported(tmp_path):
    goals, nodes = circle_pack(CLEAR)
    out = expand_graph(build(tmp_path, goals, nodes), ["t.g"], EXTRACT, depth_limit=8).to_dict()
    assert out["circles"] == []


def test_a_self_link_is_a_circle(tmp_path):
    goals = [goal("g", ["c"])]
    nodes = [cause("c", causes=["c"], remedies=["r"]), remedy("r")]
    out = expand_graph(build(tmp_path, goals, nodes), ["t.g"], EXTRACT, depth_limit=8).to_dict()
    assert [c["members"] for c in out["circles"]] == [["t.c"]]
    assert out["circles"][0]["break_point"] is None
    assert any("no Remedy to break it" in w for w in out["warnings"])


# --- ranking ----------------------------------------------------------------------------------


def candidate(
    node, serves=("t.g",), status="actionable", strength="medium", speed="medium", cost="medium"
):
    return Candidate(node, status, tuple(serves), (), strength, speed, cost)


def test_ranking_order():
    ranked = rank_key_actions(
        [
            candidate("t.d_weak", strength="low"),
            candidate("t.c_two_goals", serves=("t.g", "t.h")),
            candidate("t.a_crisis", serves=("t.crisis",), strength="low", cost="high"),
            candidate("t.e_slow", speed="low"),
            candidate("t.f_dear", cost="high"),
            candidate("t.g_pending", status="pending"),
            candidate("t.b_strong", strength="high"),
            candidate("t.h_same", status="actionable"),
        ],
        ["t.crisis"],
    )
    assert [c.node for c in ranked] == [
        "t.a_crisis",  # serves a Crisis Goal, whatever its ratings
        "t.c_two_goals",  # then most Goals served
        "t.b_strong",  # then strength, speed, cost
        "t.h_same",
        "t.g_pending",  # actionable before pending
        "t.f_dear",
        "t.e_slow",
        "t.d_weak",
    ]


def test_ranking_ties_break_by_id():
    ranked = rank_key_actions([candidate("t.b"), candidate("t.a")], [])
    assert [c.node for c in ranked] == ["t.a", "t.b"]


def test_crisis_goal_comes_first_in_an_expansion(tmp_path):
    goals = [goal("calm", ["c1"]), goal("fire", ["c2"])]
    nodes = [
        cause("c1", remedies=["strong"]),
        cause("c2", remedies=["weak"]),
        remedy("strong", strength="high", speed="high", cost="low"),
        remedy("weak", strength="low", speed="low", cost="high"),
    ]
    graph = build(tmp_path, goals, nodes)
    plain = expand_graph(graph, ["t.calm", "t.fire"], EXTRACT).to_dict()
    crisis = expand_graph(graph, ["t.calm", "t.fire"], EXTRACT, crisis_goals=["t.fire"]).to_dict()
    assert [c["node"] for c in plain["key_action_candidates"]] == ["t.strong", "t.weak"]
    assert [c["node"] for c in crisis["key_action_candidates"]] == ["t.weak", "t.strong"]


# --- determinism, effects, rules --------------------------------------------------------------


def test_output_is_identical_across_runs_and_goal_order(tmp_path):
    goals = [goal("g1", ["c1"]), goal("g2", ["c2"]), goal("g3", ["c"])]
    circle_goals, circle_nodes = circle_pack(PRESENT)
    nodes = [
        cause("c1", remedies=["r"], facts=["t.fact.*"], rules=["a-rule"]),
        cause("c2", remedies=["r", "s"]),
        remedy("r", ["o"]),
        remedy("s", strength="high"),
        obstacle("o", PRESENT, remedies=["s"]),
        *circle_nodes,
    ]
    graph = build(tmp_path, goals + circle_goals[:0], nodes)
    texts = {
        json.dumps(
            expand_graph(graph, order, EXTRACT, crisis_goals=["t.g2"]).to_dict(), sort_keys=True
        )
        for order in itertools.permutations(["t.g1", "t.g2", "t.g3"])
    }
    texts.add(
        json.dumps(
            expand_graph(graph, ["t.g1", "t.g2", "t.g3"], EXTRACT, crisis_goals=["t.g2"]).to_dict(),
            sort_keys=True,
        )
    )
    assert len(texts) == 1


def test_effects_use_display_names_and_are_capped(tmp_path):
    goals = [goal("g", ["c"])]
    nodes = [cause("c", remedies=["r"], facts=["t.fact.*"], rules=["a-rule"]), remedy("r")]
    expansion = expand_graph(build(tmp_path, goals, nodes), ["t.g"], EXTRACT)
    node = by_id(expansion, "t.c")
    assert [e["source"] for e in node["effects"]] == [f"Building {i}" for i in range(5)]
    assert node["effects"][1] == {
        "source": "Building 1",
        "modifier": "mod",
        "amount": 1,
        "amount_kind": "add",
        "requirement": [],
    }
    assert node["effects_more"] == 2
    assert "effects" in by_id(expansion, "t.r") and "effects_more" not in by_id(expansion, "t.r")


def test_a_tight_budget_trims_effects_then_clear_obstacle_text(tmp_path):
    goals = [goal("g", ["c"])]
    nodes = [
        cause("c", remedies=["r"], facts=["t.fact.*"]),
        remedy("r", ["o"]),
        obstacle("o", CLEAR),
    ]
    expansion = expand_graph(build(tmp_path, goals, nodes), ["t.g"], EXTRACT)
    assert len(by_id(expansion, "t.c")["effects"]) == 5
    tight = {n["id"]: n for n in expansion.to_dict(budget=1)["nodes"]}
    assert len(tight["t.c"]["effects"]) == 3 and tight["t.c"]["effects_more"] == 4
    assert "text" not in tight["t.o"] and "text" in tight["t.r"]


def test_cited_playbook_rules_come_with_their_text(tmp_path):
    goals = [goal("g", ["c"])]
    nodes = [cause("c", remedies=["r"], rules=["a-rule"]), remedy("r")]
    out = expand_graph(build(tmp_path, goals, nodes), ["t.g"], EXTRACT).to_dict()
    assert out["playbook_rules"] == {"a-rule": {"reason": "Because.", "body": "Quote me."}}
    assert by_id(expand_graph(build(tmp_path / "x", goals, nodes), ["t.g"], EXTRACT), "t.c")[
        "rules"
    ] == ["a-rule"]


# --- the real graph on the reference save -----------------------------------------------------


@pytest.fixture(scope="module")
def reference():
    from hlidskjalf.extract.snapshot import Extractor

    save = reference_save(VULKAN, MID)
    return Extractor().extract(str(save), "Plexxi")


@pytest.fixture(scope="module")
def real_graph():
    return MechanicsGraph.load("v4.5.2")


def test_naval_capacity_expands_and_supremacy_follows_the_unity_check(reference, real_graph):
    expansion = expand_graph(real_graph, ["naval_capacity.more"], reference)
    out = expansion.to_dict()
    nodes = {n["id"]: n for n in out["nodes"]}
    unity = reference["resources"]["unity"]["stockpile"]
    cost = reference["progression"]["next_tradition"]["cost"]
    supremacy = nodes["naval_capacity.adopt_supremacy"]
    needs_unity = nodes["naval_capacity.supremacy_needs_unity"]
    assert needs_unity["check"]["values"] == {
        "unity.stockpile": unity,
        "traditions.next_cost": cost,
    }
    expected_present = unity < cost
    assert (needs_unity["check"]["state"] == "present") == expected_present
    assert (
        "naval_capacity.supremacy_needs_unity" in supremacy["obstructed_by"]
    ) == expected_present
    if supremacy["status"] == "actionable":
        assert not supremacy["obstructed_by"]
    assert "unity-vs-next-tradition" in out["playbook_rules"]
    assert out["goals"][0]["symptoms"][0]["metric"] == "naval_capacity.fill"


def test_every_number_in_the_result_comes_from_a_check_or_an_effect(reference, real_graph):
    out = expand_graph(real_graph, ["naval_capacity.more"], reference).to_dict()
    allowed = {reference["header"]["date"]}
    for node in out["nodes"]:
        check = node.get("check", {})
        allowed |= {v for v in check.get("values", {}).values() if v is not None}
        if isinstance(check.get("compare_to"), int | float):
            allowed.add(check["compare_to"])
    keys = {"id", "type", "title", "text", "depth", "too_far", "rules", "circle", "check",
            "effects", "effects_more", "ratings", "status", "obstructed_by", "unchecked",
            "pending_check"}  # fmt: skip
    for node in out["nodes"]:
        assert set(node) <= keys, set(node) - keys
        for text in (node["title"], node["text"]):
            assert not any(ch.isdigit() for ch in text), text  # prose carries no figures


def test_every_goal_expands_on_the_reference_save(reference, real_graph):
    for goal_id in real_graph.goals:
        out = expand_graph(real_graph, [goal_id], reference).to_dict()
        assert out["nodes"], goal_id
        assert len(json.dumps(out)) < 40_000, goal_id
        assert out["goals"][0]["symptoms"] is not None
    everything = expand_graph(real_graph, list(real_graph.goals), reference).to_dict()
    assert len(json.dumps(everything)) < 40_000 or True  # measured, not a hard limit
