"""Solution Graph (M5): validator on good and bad documents, `compose` from an expansion and an
overlay, determinism, the two CLI commands, and the real graph on the reference save."""

from __future__ import annotations

import copy
import itertools
import json

import pytest
from conftest import MID, VULKAN, reference_save
from test_expand import (
    CLEAR,
    EXTRACT,
    JUDGEMENT,
    PRESENT,
    build,
    cause,
    circle_pack,
    goal,
    obstacle,
    remedy,
)

from admiralty.cli import main
from admiralty.graph.expand import expand_graph
from admiralty.graph.mechanics import MechanicsGraph
from admiralty.graph.solution import SolutionInvalid, validate_solution_graph
from admiralty.graph.solution import compose as compose_exact

NODES = [
    cause("c", remedies=["ok", "blocked", "judged"], rules=["a-rule"]),
    remedy("ok", strength="high", rules=["a-rule"]),
    remedy("blocked", ["o"]),
    obstacle("o", PRESENT, remedies=["helper"]),
    remedy("helper", strength="low", speed="low"),
    remedy("judged", ["j"], strength="medium"),
    obstacle("j", JUDGEMENT),
    cause("d", remedies=["fine"]),
    remedy("fine", ["gone"], strength="medium", speed="high"),
    obstacle("gone", CLEAR, remedies=["unused"]),
    remedy("unused"),
]
OVERLAY = {
    "empire": "Plexxi's Empire",
    "goals": {"t.g": {"horizon": "short"}},
    "why": {
        "t.ok": "Costs nothing.",
        "t.fine": "No Obstacle holds.",
        "t.helper": "Unlocks the blocked Remedy.",
        "t.judged": "Nothing in the numbers stands against it.",
    },
    "weights": [
        {"from": "t.g", "to": "t.c", "weight": "high", "reason": "Most of the gap."},
        {"from": "t.g", "to": "t.d", "weight": "low", "reason": "A small share."},
    ],
}


def weigh(expansion, overlay):
    """The overlay with a weight on every edge into a Cause: its own where it gives one for an
    edge of this expansion, medium otherwise. Tests about something else need not spell them out."""
    causes = {n["id"] for n in expansion["nodes"] if n["type"] == "cause"}
    causes |= {n["id"] for n in overlay.get("add_nodes", []) if n.get("type") == "cause"}
    edges = {(e["from"], e["to"]) for e in expansion["edges"]}
    edges |= {(e["from"], e["to"]) for e in overlay.get("add_edges", [])}
    wanted = sorted((a, b) for a, b in edges if b in causes)
    given = {(w["from"], w["to"]): w for w in overlay.get("weights", [])}
    weights = [
        given.get((a, b), {"from": a, "to": b, "weight": "medium", "reason": "Not under test."})
        for a, b in wanted
    ]
    return {**overlay, "weights": weights}


def compose(expansion, overlay, graph, *args):
    return compose_exact(expansion, weigh(expansion, overlay), graph, *args)


@pytest.fixture
def graph(tmp_path):
    return build(tmp_path, [goal("g", ["c", "d"])], NODES)


@pytest.fixture
def expansion(graph):
    return expand_graph(graph, ["t.g"], EXTRACT).to_dict()


def overlay(**changes):
    return {**copy.deepcopy(OVERLAY), **changes}


def errors(graph, doc):
    return [str(p) for p in validate_solution_graph(doc, graph, graph.rules)]


def node(doc, node_id):
    return next(n for n in doc["nodes"] if n["id"] == node_id)


def composed(graph, expansion, **changes):
    return compose(expansion, overlay(**changes), graph)


def refused(graph, expansion, **changes) -> str:
    with pytest.raises(SolutionInvalid) as caught:
        composed(graph, expansion, **changes)
    return "\n".join(str(p) for p in caught.value.problems)


# --- compose ----------------------------------------------------------------------------------


def test_compose_gives_a_valid_graph_with_the_ranking_from_the_code(graph, expansion):
    doc = composed(graph, expansion)
    assert errors(graph, doc) == []
    assert doc["empire"] == "Plexxi's Empire"
    assert [a["node"] for a in doc["key_actions"]] == [
        "t.ok",
        "t.fine",
        "t.judged",
        "t.helper",
    ]
    assert [a["rank"] for a in doc["key_actions"]] == [1, 2, 3, 4]
    assert node(doc, "t.blocked")["status"] == "obstructed"
    assert "t.blocked" not in {a["node"] for a in doc["key_actions"]}
    helper = next(a for a in doc["key_actions"] if a["node"] == "t.helper")
    assert helper["unlocks"] == ["t.blocked"]
    assert helper["serves"] == ["t.g"]
    assert node(doc, "t.g")["horizon"] == "short"


def test_graph_nodes_keep_what_the_code_computed(graph, expansion):
    doc = composed(graph, expansion)
    obstacle_node = node(doc, "t.o")
    assert obstacle_node["check_state"] == "present"
    assert obstacle_node["evidence"] == ["m.a 1 < 5 (present)"]
    assert node(doc, "t.blocked")["evidence"] == ["obstructed by t.o"]
    assert node(doc, "t.ok")["rules"] == ["a-rule"]
    assert node(doc, "t.j")["check_state"] == "judgement"
    assert "not checked against numbers: t.j" in node(doc, "t.judged")["evidence"]
    assert node(doc, "t.g")["evidence"] == ["m.a 1 things"]


def test_compose_is_deterministic_across_runs_and_why_order(graph):
    texts = set()
    for order in itertools.permutations(OVERLAY["why"]):
        expansion = expand_graph(graph, ["t.g"], EXTRACT).to_dict()
        why = {key: OVERLAY["why"][key] for key in order}
        texts.add(json.dumps(compose(expansion, overlay(why=why), graph)))
    assert len(texts) == 1


def test_a_key_action_needs_a_why_or_an_exclusion(graph, expansion):
    why = {k: v for k, v in OVERLAY["why"].items() if k != "t.ok"}
    assert "no reason for Key Action 't.ok'" in refused(graph, expansion, why=why)
    doc = composed(
        graph,
        expansion,
        why=why,
        exclude_key_actions=[{"id": "t.ok", "reason": "Already done in this empire."}],
    )
    assert "t.ok" not in {a["node"] for a in doc["key_actions"]}
    assert doc["excluded_key_actions"] == [{"id": "t.ok", "reason": "Already done in this empire."}]
    assert errors(graph, doc) == []


def test_a_why_for_something_that_is_not_a_key_action_is_refused(graph, expansion):
    why = {**OVERLAY["why"], "t.blocked": "Obstructed, so no."}
    assert "'t.blocked' is not a Key Action" in refused(graph, expansion, why=why)


def test_pruning_drops_what_only_hung_on_it_and_records_it(graph, expansion):
    doc = composed(graph, expansion, prune=[{"id": "t.blocked", "reason": "Not for this empire."}])
    ids = {n["id"] for n in doc["nodes"]}
    assert not ids & {"t.blocked", "t.o", "t.helper"}
    pruned = {p["id"]: p["reason"] for p in doc["pruned"]}
    assert pruned["t.blocked"] == "Not for this empire."
    assert pruned["t.o"] == pruned["t.helper"] == "only reachable through pruned nodes"
    assert all(a["node"] != "t.helper" for a in doc["key_actions"])
    assert errors(graph, doc) == []


def test_a_node_with_another_parent_survives_pruning_one_parent(tmp_path):
    nodes = [
        cause("c", causes=["a", "b"]),
        cause("a", remedies=["r"]),
        cause("b", remedies=["r"]),
        remedy("r"),
    ]
    graph = build(tmp_path, [goal("g", ["c"])], nodes)
    expansion = expand_graph(graph, ["t.g"], EXTRACT).to_dict()
    doc = compose(
        expansion,
        {**OVERLAY, "why": {"t.r": "Still reachable."}, "prune": [{"id": "t.a", "reason": "No."}]},
        graph,
    )
    assert "t.r" in {n["id"] for n in doc["nodes"]}
    assert [p["id"] for p in doc["pruned"]] == ["t.a"]


def test_a_present_obstacle_cannot_be_pruned(graph, expansion):
    message = refused(graph, expansion, prune=[{"id": "t.o", "reason": "Ignore it."}])
    assert "Obstacle 't.o' holds on this Snapshot" in message


def test_pruning_a_clear_obstacle_or_an_unknown_node(graph, expansion):
    doc = composed(graph, expansion, prune=[{"id": "t.gone", "reason": "Irrelevant."}])
    assert "t.gone" not in {n["id"] for n in doc["nodes"]}
    assert "'t.nope' is not a node" in refused(
        graph, expansion, prune=[{"id": "t.nope", "reason": "?"}]
    )


def test_every_goal_needs_a_horizon(graph, expansion):
    assert "no Horizon for Goal 't.g'" in refused(graph, expansion, goals={})
    bad = {"t.g": {"horizon": "soon"}}
    assert "goals.t.g.horizon must be short, medium or long" in refused(graph, expansion, goals=bad)


def test_crisis_goal_from_the_overlay_ranks_first(tmp_path):
    goals = [goal("calm", ["c1"]), goal("fire", ["c2"])]
    nodes = [
        cause("c1", remedies=["strong"]),
        cause("c2", remedies=["weak"]),
        remedy("strong", strength="high", speed="high", cost="low"),
        remedy("weak", strength="low", speed="low", cost="high"),
    ]
    graph = build(tmp_path, goals, nodes)
    expansion = expand_graph(graph, ["t.calm", "t.fire"], EXTRACT).to_dict()
    both = {"t.strong": "Strong.", "t.weak": "Weak."}
    plain = compose(
        expansion,
        {
            "empire": "E",
            "goals": {"t.calm": {"horizon": "short"}, "t.fire": {"horizon": "short"}},
            "why": both,
        },
        graph,
    )
    fire = compose(
        expansion,
        {
            "empire": "E",
            "goals": {
                "t.calm": {"horizon": "short"},
                "t.fire": {"horizon": "short", "crisis": True},
            },
            "why": both,
        },
        graph,
    )
    assert [a["node"] for a in plain["key_actions"]] == ["t.strong", "t.weak"]
    assert [a["node"] for a in fire["key_actions"]] == ["t.weak", "t.strong"]


def test_unknown_overlay_fields_are_refused(graph, expansion):
    assert "unknown overlay field 'prunes'" in refused(graph, expansion, prunes=[])


# --- model nodes ------------------------------------------------------------------------------


MODEL_CAUSE = {
    "id": "model.fleet_upkeep",
    "type": "cause",
    "title": "Fleet upkeep eats the budget",
    "reason": "The Mechanics Graph has no upkeep Cause for this Goal.",
}


def test_a_model_node_is_marked_and_joins_the_graph(graph, expansion):
    doc = composed(
        graph,
        expansion,
        add_nodes=[MODEL_CAUSE],
        add_edges=[
            {"from": "t.g", "to": "model.fleet_upkeep"},
            {"from": "model.fleet_upkeep", "to": "t.ok"},
        ],
    )
    added = node(doc, "model.fleet_upkeep")
    assert added["source"] == "model"
    assert added["reason"].startswith("The Mechanics Graph has no")
    plain = [{k: e[k] for k in ("from", "to", "kind")} for e in doc["edges"]]
    assert {"from": "model.fleet_upkeep", "to": "t.ok", "kind": "remedy"} in plain
    assert errors(graph, doc) == []


def test_a_model_remedy_with_ratings_and_evidence_is_a_ranked_key_action(graph, expansion):
    remedy_node = {
        "id": "model.scrap_ships",
        "type": "remedy",
        "title": "Scrap obsolete ships",
        "reason": "Not in the Mechanics Graph.",
        "ratings": {"strength": "high", "speed": "high", "cost": "low"},
        "evidence": ["military: 12 obsolete corvettes in the fleet list"],
    }
    doc = composed(
        graph,
        expansion,
        add_nodes=[remedy_node],
        add_edges=[{"from": "t.c", "to": "model.scrap_ships"}],
        why={**OVERLAY["why"], "model.scrap_ships": "Cheap and fast."},
    )
    assert doc["key_actions"][0]["node"] == "model.scrap_ships"
    assert errors(graph, doc) == []


def test_a_model_node_left_without_a_path_is_an_orphan(graph, expansion):
    message = refused(graph, expansion, add_nodes=[MODEL_CAUSE])
    assert "model.fleet_upkeep: orphan" in message


def test_a_model_node_without_a_reason_is_refused(graph, expansion):
    bare = {k: v for k, v in MODEL_CAUSE.items() if k != "reason"}
    message = refused(
        graph,
        expansion,
        add_nodes=[bare],
        add_edges=[{"from": "t.g", "to": "model.fleet_upkeep"}],
    )
    assert "'reason' is a required property" in message


# --- validator on hand-made documents ---------------------------------------------------------


@pytest.fixture
def good(graph, expansion):
    return composed(graph, expansion)


def test_the_good_document_is_clean(graph, good):
    assert errors(graph, good) == []


def mutate(good, change):
    doc = copy.deepcopy(good)
    change(doc)
    return doc


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        (lambda d: d.update(extra=1), "Additional properties"),
        (lambda d: node(d, "t.ok").update(colour="red"), "Additional properties"),
        (lambda d: node(d, "t.ok").pop("status"), "'status' is a required property"),
        (lambda d: node(d, "t.g").pop("horizon"), "'horizon' is a required property"),
        (lambda d: node(d, "t.g").update(horizon="soon"), "is not one of"),
        (lambda d: d["key_actions"][0].update(why=""), "non-empty"),
        (lambda d: d.update(schema=2), "was expected"),
    ],
)
def test_schema_rejects(graph, good, change, expected):
    assert expected in "\n".join(errors(graph, mutate(good, change)))


def add_model_node(doc, **fields):
    doc["nodes"].append(
        {
            "id": "model.x",
            "type": "cause",
            "source": "model",
            "title": "X",
            "reason": "Why.",
            **fields,
        }
    )


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        (lambda d: add_model_node(d, id="x.plain"), "does not match"),
        (lambda d: add_model_node(d, reason=""), "non-empty"),
        (lambda d: add_model_node(d, status="actionable"), "Additional properties"),
        (lambda d: add_model_node(d, rules=["a-rule"]), "Additional properties"),
        (lambda d: add_model_node(d, facts=["t.fact.1"]), "Additional properties"),
    ],
)
def test_a_model_node_cannot_look_like_graph_evidence(graph, good, change, expected):
    assert expected in "\n".join(errors(graph, mutate(good, change)))


def test_a_graph_node_the_graph_does_not_have(graph, good):
    doc = mutate(good, lambda d: node(d, "t.ok").update(id="t.invented"))
    assert "the Mechanics Graph has no remedy 't.invented'" in "\n".join(errors(graph, doc))


def test_a_graph_node_of_the_wrong_type(graph, good):
    doc = mutate(
        good,
        lambda d: node(d, "t.c").update(
            type="remedy", status="actionable", ratings=node(d, "t.ok")["ratings"]
        ),
    )
    assert "the Mechanics Graph has no remedy 't.c'" in "\n".join(errors(graph, doc))


def test_an_invented_playbook_rule_id(graph, good):
    doc = mutate(good, lambda d: node(d, "t.ok").update(rules=["made-up-rule"]))
    assert "rules: 'made-up-rule' is not a Playbook Rule" in "\n".join(errors(graph, doc))


def test_a_dangling_edge(graph, good):
    doc = mutate(
        good, lambda d: d["edges"].append({"from": "t.c", "to": "t.zzz", "kind": "remedy"})
    )
    assert "'t.zzz' is not a node" in "\n".join(errors(graph, doc))


def test_an_orphan_node(graph, good):
    doc = mutate(
        good, lambda d: d["edges"].remove(next(e for e in d["edges"] if e["to"] == "t.ok"))
    )
    assert "t.ok: orphan" in "\n".join(errors(graph, doc))


def test_a_graph_edge_the_graph_does_not_have(graph, good):
    doc = mutate(
        good, lambda d: d["edges"].append({"from": "t.c", "to": "t.helper", "kind": "remedy"})
    )
    assert "has no such link" in "\n".join(errors(graph, doc))


def test_the_grammar_is_enforced(graph, good):
    doc = mutate(good, lambda d: d["edges"].append({"from": "t.g", "to": "t.ok", "kind": "remedy"}))
    assert "a goal cannot lead to a remedy" in "\n".join(errors(graph, doc))
    wrong_kind = mutate(good, lambda d: d["edges"][1].update(kind="cause"))
    assert "kind is cause" in "\n".join(errors(graph, wrong_kind))


def test_an_obstructed_key_action(graph, good):
    doc = mutate(
        good,
        lambda d: d["key_actions"].append(
            {"rank": 99, "node": "t.blocked", "serves": ["t.g"], "unlocks": [], "why": "Try."}
        ),
    )
    messages = "\n".join(errors(graph, doc))
    assert "t.blocked: obstructed" in messages
    assert "ranks must be unique and run 1..n" in messages


def test_a_key_action_must_be_a_remedy_that_leads_from_its_goal(graph, good):
    doc = mutate(good, lambda d: d["key_actions"][0].update(node="t.c"))
    assert "a Key Action is a Remedy node" in "\n".join(errors(graph, doc))
    doc = mutate(good, lambda d: d["key_actions"][0].update(serves=["t.ok"]))
    assert "which is not a Goal node" in "\n".join(errors(graph, doc))


def test_duplicate_ranks_and_nodes(graph, good):
    doc = mutate(good, lambda d: d["key_actions"][1].update(rank=1))
    assert "ranks must be unique" in "\n".join(errors(graph, doc))
    doc = mutate(good, lambda d: d["nodes"].append(copy.deepcopy(node(d, "t.ok"))))
    assert "node id appears twice" in "\n".join(errors(graph, doc))


def test_a_model_remedy_without_evidence_is_no_key_action(graph, good):
    def change(d):
        add_model_node(d, id="model.r", type="remedy")
        d["edges"].append({"from": "t.c", "to": "model.r", "kind": "remedy"})
        d["key_actions"].append(
            {
                "rank": len(d["key_actions"]) + 1,
                "node": "model.r",
                "serves": ["t.g"],
                "unlocks": [],
                "why": "Hmm.",
            }
        )

    assert "needs evidence to be a Key Action" in "\n".join(errors(graph, mutate(good, change)))


def test_circle_members_and_break_point_must_exist(graph, good):
    doc = mutate(
        good,
        lambda d: d["circles"].append(
            {"id": "loop", "members": ["t.ok", "t.zzz"], "break_point": "t.fine"}
        ),
    )
    messages = "\n".join(errors(graph, doc))
    assert "member 't.zzz' is not a node" in messages
    assert "break_point 't.fine' is not a member" in messages


def test_pruned_entries_must_be_graph_nodes_and_gone(graph, good):
    doc = mutate(
        good,
        lambda d: d["pruned"].extend(
            [{"id": "t.ok", "reason": "x"}, {"id": "t.zzz", "reason": "y"}]
        ),
    )
    messages = "\n".join(errors(graph, doc))
    assert "pruned t.ok: pruned but still a node" in messages
    assert "pruned t.zzz: is not a node of the Mechanics Graph" in messages


def test_a_document_without_goal_or_of_the_wrong_version(graph, good):
    doc = mutate(good, lambda d: d.update(game_version="v9.9.9"))
    assert "game_version is v9.9.9" in "\n".join(errors(graph, doc))
    assert validate_solution_graph("not a document", graph, graph.rules)


# --- circles ----------------------------------------------------------------------------------


def test_a_circle_survives_into_the_solution_graph_with_its_break_point(tmp_path):
    goals, nodes = circle_pack(PRESENT)
    graph = build(tmp_path, goals, nodes)
    expansion = expand_graph(graph, ["t.g"], EXTRACT, depth_limit=8).to_dict()
    doc = compose(expansion, {**OVERLAY, "why": {"t.way_out": "The exit."}}, graph)
    assert doc["circles"] == [
        {
            "id": "circle:t.o1",
            "members": ["t.o1", "t.o2", "t.r1", "t.r2"],
            "break_point": "t.r2",
        }
    ]
    assert errors(graph, doc) == []
    pruned = compose(
        expansion,
        {**OVERLAY, "why": {"t.way_out": "The exit."}, "prune": [{"id": "t.r2", "reason": "No."}]},
        graph,
    )
    assert pruned["circles"] == []


# --- command line -----------------------------------------------------------------------------


def test_cli_compose_and_check_solution(graph, expansion, tmp_path, capsys):
    root = tmp_path  # `build` wrote the pack to tmp_path/4.5.2
    files = {"expansion.json": expansion, "overlay.json": OVERLAY}
    for name, content in files.items():
        (tmp_path / name).write_text(json.dumps(content))
    out = tmp_path / "briefings" / "2250.01.01" / "solution-graph.json"
    base = ["--knowledge-root", str(root)]
    status = main(
        ["briefing", "compose", str(tmp_path / "expansion.json"), str(tmp_path / "overlay.json"),
         "--out", str(out), *base]
    )  # fmt: skip
    assert status == 0
    assert json.loads(capsys.readouterr().out)["key_actions"][0] == "t.ok"
    doc = json.loads(out.read_text())
    assert errors(graph, doc) == []
    assert main(["graph", "check-solution", str(out), *base]) == 0
    assert "0 error(s)" in capsys.readouterr().out

    doc["key_actions"][0]["node"] = "t.c"
    out.write_text(json.dumps(doc))
    assert main(["graph", "check-solution", str(out), *base]) == 1
    assert "a Key Action is a Remedy node" in capsys.readouterr().out


def test_cli_compose_without_out_updates_the_current_briefing(graph, expansion, tmp_path, capsys):
    (tmp_path / "expansion.json").write_text(json.dumps(expansion))
    (tmp_path / "overlay.json").write_text(json.dumps(OVERLAY))
    command = ["briefing", "compose", str(tmp_path / "expansion.json"),
               str(tmp_path / "overlay.json"), "--workspace", str(tmp_path),
               "--knowledge-root", str(tmp_path)]  # fmt: skip
    assert main(command) == 0
    first = json.loads(capsys.readouterr().out)
    current = tmp_path / "briefings" / "current"
    assert first["out"] == str(current / "solution-graph.json") and first["replaced"] is None
    assert json.loads((current / "overlay.json").read_text()) == OVERLAY
    assert main(command) == 0
    second = json.loads(capsys.readouterr().out)
    assert second["replaced"] == str(next((tmp_path / "briefings" / "history").iterdir()))
    assert (current / "solution-graph.json").is_file()


def test_cli_compose_opens_the_current_briefing_but_not_an_out_file(
    graph, expansion, tmp_path, capsys, monkeypatch
):
    from admiralty.graph import view

    shown = []
    monkeypatch.setattr(
        view,
        "show_current",
        lambda ws, g: shown.append((ws, g)) or {"url": "http://x", "opened": True},
    )
    (tmp_path / "expansion.json").write_text(json.dumps(expansion))
    (tmp_path / "overlay.json").write_text(json.dumps(OVERLAY))
    command = ["briefing", "compose", str(tmp_path / "expansion.json"),
               str(tmp_path / "overlay.json"), "--knowledge-root", str(tmp_path)]  # fmt: skip
    workspace = ["--workspace", str(tmp_path)]
    assert main([*command, *workspace]) == 0
    result = json.loads(capsys.readouterr().out)
    current = tmp_path / "briefings" / "current" / "solution-graph.json"
    assert shown == [(tmp_path, current)]
    assert result["view"] == {"url": "http://x", "opened": True}
    assert main([*command, *workspace, "--no-open"]) == 0
    assert "view" not in json.loads(capsys.readouterr().out) and len(shown) == 1
    assert main([*command, "--out", str(tmp_path / "x.json")]) == 0
    assert "view" not in json.loads(capsys.readouterr().out) and len(shown) == 1


def test_cli_compose_refuses_without_replacing_the_current_briefing(
    graph, expansion, tmp_path, capsys
):
    (tmp_path / "expansion.json").write_text(json.dumps(expansion))
    (tmp_path / "overlay.json").write_text(json.dumps(OVERLAY))
    command = ["briefing", "compose", str(tmp_path / "expansion.json"),
               str(tmp_path / "overlay.json"), "--workspace", str(tmp_path),
               "--knowledge-root", str(tmp_path)]  # fmt: skip
    assert main(command) == 0
    capsys.readouterr()
    (tmp_path / "overlay.json").write_text(json.dumps({"empire": "E", "goals": {}}))
    assert main(command) == 1
    assert not (tmp_path / "briefings" / "history").exists()


def test_cli_compose_refuses_a_bad_overlay_without_writing(graph, expansion, tmp_path, capsys):
    (tmp_path / "expansion.json").write_text(json.dumps(expansion))
    (tmp_path / "overlay.json").write_text(json.dumps({"empire": "E", "goals": {}}))
    out = tmp_path / "solution-graph.json"
    status = main(
        ["briefing", "compose", str(tmp_path / "expansion.json"), str(tmp_path / "overlay.json"),
         "--out", str(out), "--knowledge-root", str(tmp_path)]
    )  # fmt: skip
    assert status == 1
    assert "no Horizon for Goal 't.g'" in capsys.readouterr().err
    assert not out.exists()


def test_compose_takes_dropped_text_from_the_graph(graph, tmp_path):
    full = expand_graph(graph, ["t.g"], EXTRACT).to_dict()
    squeezed = expand_graph(graph, ["t.g"], EXTRACT).to_dict(budget=1)
    assert any("text" not in n for n in squeezed["nodes"])  # the compact form dropped some
    assert any("over the budget" in w for w in squeezed["warnings"])
    assert composed(graph, squeezed) == composed(graph, full)


def test_cli_compose_reads_the_expansion_from_the_turn_log(graph, expansion, tmp_path, capsys):
    workspace = tmp_path / "ws"
    (workspace / ".admiralty").mkdir(parents=True)
    entries = [
        {"tool": "economy", "args": {}, "result": {}},
        {"tool": "expand_graph", "args": {}, "result": expansion},
    ]
    log = workspace / ".admiralty" / "turn-log.jsonl"
    log.write_text("".join(json.dumps(e) + "\n" for e in entries))
    (tmp_path / "overlay.json").write_text(json.dumps(OVERLAY))
    out = tmp_path / "solution-graph.json"
    command = ["briefing", "compose", str(tmp_path / "overlay.json"), "--out", str(out)]
    command += ["--workspace", str(workspace), "--knowledge-root", str(tmp_path)]
    assert main([*command, "--expansion-id", "2"]) == 0
    assert json.loads(out.read_text())["key_actions"][0]["node"] == "t.ok"
    capsys.readouterr()
    for wrong in ("1", "9"):  # not an expansion; no such entry
        with pytest.raises(SystemExit, match="cannot read expansion|not an expansion"):
            main([*command, "--expansion-id", wrong])
    with pytest.raises(SystemExit, match="either an expansion file or --expansion-id"):
        main(command)


# --- the real graph on the reference save -----------------------------------------------------


@pytest.fixture(scope="module")
def reference():
    from admiralty.extract.snapshot import Extractor

    return Extractor().extract(str(reference_save(VULKAN, MID)), "Plexxi")


def test_the_real_graph_composes_into_a_valid_solution_graph(reference):
    real = MechanicsGraph.load("v4.5.2")
    chosen = ["naval_capacity.more", "unity.more"]
    expansion = expand_graph(real, chosen, reference, crisis_goals=["unity.more"]).to_dict()
    why = {c["node"]: "Test overlay." for c in expansion["key_action_candidates"]}
    doc = compose(
        expansion,
        {
            "empire": "Plexxi",
            "goals": {g: {"horizon": "short"} for g in chosen},
            "why": why,
        },
        real,
    )
    assert errors(real, doc) == []
    assert [a["node"] for a in doc["key_actions"]] == [
        c["node"] for c in expansion["key_action_candidates"]
    ]
    assert all(
        node(doc, a["node"])["status"] in ("actionable", "pending") for a in doc["key_actions"]
    )
    assert {n["id"] for n in doc["nodes"]} == {g["id"] for g in expansion["goals"]} | {
        n["id"] for n in expansion["nodes"]
    }


# --- weights (docs/plans/M6-revision.md) ------------------------------------------------------


def test_edges_into_causes_carry_the_models_weight_and_into_remedies_the_strength(graph, expansion):
    doc = composed(graph, expansion)
    edges = {(e["from"], e["to"]): e for e in doc["edges"]}
    assert edges[("t.g", "t.c")]["weight"] == "high"
    assert edges[("t.g", "t.c")]["weight_reason"] == "Most of the gap."
    assert edges[("t.g", "t.d")]["weight"] == "low"
    assert edges[("t.c", "t.ok")]["weight"] == "high"
    assert "weight" not in edges[("t.blocked", "t.o")]


def test_a_missing_weight_into_a_cause_is_refused(graph, expansion):
    weights = [w for w in OVERLAY["weights"] if w["to"] != "t.d"]
    with pytest.raises(SolutionInvalid) as caught:
        compose_exact(expansion, overlay(weights=weights), graph)
    assert "no weight for t.g > t.d" in str(caught.value.problems)


def test_a_weight_on_no_cause_edge_or_without_reason_is_refused(graph, expansion):
    stale = [*OVERLAY["weights"], {"from": "t.c", "to": "t.ok", "weight": "high", "reason": "x"}]
    for weights, message in (
        (stale, "t.c > t.ok is not an edge into a Cause"),
        ([{**OVERLAY["weights"][0], "reason": " "}, OVERLAY["weights"][1]], "every entry needs"),
    ):
        with pytest.raises(SolutionInvalid) as caught:
            compose_exact(expansion, overlay(weights=weights), graph)
        assert message in str(caught.value.problems)


def test_unchecked_obstacles_speak_in_the_conditional():
    from admiralty.extract.snapshot import Extractor

    mechanics = MechanicsGraph.load("v4.5.2")
    extract = Extractor().extract(str(reference_save(VULKAN, MID)), "Plexxi")
    expansion = expand_graph(mechanics, ["alloys.more", "energy.more"], extract).to_dict()
    doc = compose(
        expansion,
        {
            "empire": "Plexxi",
            "goals": {"alloys.more": {"horizon": "medium"}, "energy.more": {"horizon": "short"}},
            "why": {c["node"]: "x" for c in expansion["key_action_candidates"]},
        },
        mechanics,
    )
    unchecked = [n for n in doc["nodes"] if n.get("check_state") in ("judgement", "unknown")]
    checked = [n for n in doc["nodes"] if n.get("check_state") in ("present", "clear")]
    assert unchecked and all(" may " in n["title"] for n in unchecked)
    assert all(n["title"] == mechanics.nodes[n["id"]]["title"] for n in checked)
