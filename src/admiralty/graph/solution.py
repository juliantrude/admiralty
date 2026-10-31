"""The Solution Graph: the Briefing's merged network, validated, and `compose` that builds it.

`compose` takes the expansion (what the code walked and checked, `Expansion.to_dict()`) and a small
overlay from the model (Horizons, what to prune with a reason, nodes it adds, why each Key Action),
and returns the document `validate_solution_graph` accepts. The model never hand-copies the graph,
and the Key Action order is never its guess: the ranking is recomputed here with the same function
`expand_graph` uses (`rank_key_actions`); the model can only prune or exclude, each with a reason,
and both are recorded in the document. Format and rationale: docs/plans/M5.md "Solution Graph".

Source marking is the heart of it: a node is `graph` (it exists in the Mechanics Graph, with the
status the code computed) or `model` (id `model.*`, a reason why the graph does not have it, no
code-computed field), so a reader and M6's renderer can always tell evidence from judgement.
"""

from __future__ import annotations

import json
from collections import deque
from collections.abc import Iterable
from functools import cache
from importlib import resources
from typing import Any

from jsonschema import Draft202012Validator

from admiralty.graph.expand import Candidate, _break_point, _components, rank_key_actions
from admiralty.graph.mechanics import MechanicsGraph, Problem
from admiralty.graph.playbook import Rule

SCHEMA_VERSION = 1
WHERE = "solution-graph"
_NEXT = {  # the grammar: which node type may follow which
    "goal": {"cause"},
    "cause": {"cause", "remedy"},
    "remedy": {"obstacle"},
    "obstacle": {"remedy"},
}
_LINKS = ("causes", "remedies", "obstacles")
_OVERLAY_KEYS = {
    "empire",
    "goals",
    "prune",
    "add_nodes",
    "add_edges",
    "exclude_key_actions",
    "why",
    "weights",
}
_RATINGS = ("high", "medium", "low")


class SolutionInvalid(ValueError):
    """The Solution Graph (or the overlay it is composed from) has errors; `problems` lists them."""

    def __init__(self, problems: list[Problem]):
        self.problems = problems
        errors = [p for p in problems if p.severity == "error"]
        super().__init__(f"{len(errors)} error(s) in the Solution Graph, first: {errors[0]}")


@cache
def _schema() -> Draft202012Validator:
    text = (resources.files("admiralty.graph") / "solution.schema.json").read_text("utf-8")
    schema = json.loads(text)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


# --- validation --------------------------------------------------------------------------------


def validate_solution_graph(
    doc: Any, graph: MechanicsGraph, rules: dict[str, Rule]
) -> list[Problem]:
    """Every problem of a Solution Graph against the Mechanics Graph and the Playbook Rules;
    empty when it is sound. Never raises on a malformed document."""
    errors = sorted(_schema().iter_errors(doc), key=lambda e: list(map(str, e.path)))
    if errors:
        # the cross rules assume a document of the right shape
        return [Problem("error", WHERE, f"{_location(e.absolute_path)}{e.message}") for e in errors]
    problems: list[Problem] = []

    def error(where: str, message: str) -> None:
        problems.append(Problem("error", where, message))

    if doc["game_version"] != graph.version:
        error(WHERE, f"game_version is {doc['game_version']}, the Mechanics Graph {graph.version}")

    nodes: dict[str, dict[str, Any]] = {}
    for node in doc["nodes"]:
        if node["id"] in nodes:
            error(f"{WHERE} {node['id']}", "node id appears twice")
            continue
        nodes[node["id"]] = node
        problems += _node_problems(node, graph, rules)
    goals = [n for n in nodes.values() if n["type"] == "goal"]
    if not goals:
        error(WHERE, "no Goal: every Solution Graph starts at a Goal")

    onward = _check_edges(doc["edges"], nodes, graph, error)
    reach = {g["id"]: _reach(g["id"], onward) for g in goals}
    reached = set().union(*reach.values()) if reach else set()
    for node_id, node in nodes.items():
        if node["type"] != "goal" and node_id not in reached:
            error(f"{WHERE} {node_id}", "orphan: not reachable from any Goal")

    for circle in doc["circles"]:
        where = f"{WHERE} circle {circle['id']}"
        for member in circle["members"]:
            if member not in nodes:
                error(where, f"member '{member}' is not a node")
        if circle["break_point"] is not None and circle["break_point"] not in circle["members"]:
            error(where, f"break_point '{circle['break_point']}' is not a member")

    problems += _key_action_problems(doc, nodes, reach)
    for entry in doc["pruned"]:
        where = f"{WHERE} pruned {entry['id']}"
        if entry["id"] in nodes:
            error(where, "pruned but still a node")
        if entry["id"] not in graph.nodes:
            error(where, "is not a node of the Mechanics Graph")
    return problems


def _location(path) -> str:
    return "/".join(str(part) for part in path) + ": " if path else ""


def _node_problems(node: dict[str, Any], graph: MechanicsGraph, rules) -> list[Problem]:
    where = f"{WHERE} {node['id']}"
    problems: list[Problem] = []

    def error(message: str) -> None:
        problems.append(Problem("error", where, message))

    kind = node["type"]
    for field_name, only in (
        ("horizon", "goal"),
        ("crisis", "goal"),
        ("mark", "goal"),
        ("status", "remedy"),
        ("ratings", "remedy"),
        ("check_state", "obstacle"),
    ):
        if field_name in node and kind != only:
            error(f"{field_name} belongs to a {only}, this is a {kind}")
    if node["source"] == "graph":
        known = graph.goals if kind == "goal" else graph.nodes
        if node["id"] not in known or (kind != "goal" and known[node["id"]]["type"] != kind):
            error(f"source is graph but the Mechanics Graph has no {kind} '{node['id']}'")
        elif kind == "goal" and node.get("mark") not in (None, known[node["id"]]["mark"]):
            error(
                f"mark is {node['mark']}, the Mechanics Graph marks this Goal {known[node['id']]['mark']}"
            )
    for rule_id in node.get("rules", []):
        if rule_id not in rules:
            error(f"rules: '{rule_id}' is not a Playbook Rule")
    return problems


def _check_edges(edges, nodes, graph: MechanicsGraph, error) -> dict[str, list[str]]:
    onward: dict[str, list[str]] = {}
    seen: set[tuple[str, str]] = set()
    for edge in edges:
        a, b = edge["from"], edge["to"]
        where = f"{WHERE} edge {a} -> {b}"
        if (a, b) in seen:
            error(where, "edge appears twice")
            continue
        seen.add((a, b))
        missing = [x for x in (a, b) if x not in nodes]
        if missing:
            error(where, f"'{missing[0]}' is not a node")
            continue
        types = nodes[a]["type"], nodes[b]["type"]
        if types[1] not in _NEXT[types[0]]:
            error(where, f"a {types[0]} cannot lead to a {types[1]}")
        if edge["kind"] != types[1]:
            error(where, f"kind is {edge['kind']}, the target is a {types[1]}")
        if nodes[a]["source"] == nodes[b]["source"] == "graph" and not _linked(graph, a, b):
            error(where, "both nodes are from the Mechanics Graph, which has no such link")
        onward.setdefault(a, []).append(b)
    return onward


def _linked(graph: MechanicsGraph, a: str, b: str) -> bool:
    if a in graph.goals:
        return b in graph.goals[a]["causes"]
    return a in graph.nodes and any(b in graph.nodes[a].get(kind, []) for kind in _LINKS)


def _reach(start: str, onward: dict[str, list[str]]) -> set[str]:
    seen: set[str] = set()
    queue = deque([start])
    while queue:
        for target in onward.get(queue.popleft(), []):
            if target not in seen:
                seen.add(target)
                queue.append(target)
    return seen


def _key_action_problems(doc, nodes, reach) -> list[Problem]:
    problems: list[Problem] = []

    def error(where: str, message: str) -> None:
        problems.append(Problem("error", where, message))

    actions = doc["key_actions"]
    if sorted(a["rank"] for a in actions) != list(range(1, len(actions) + 1)):
        error(f"{WHERE} key_actions", "ranks must be unique and run 1..n")
    named: set[str] = set()
    for action in actions:
        node = nodes.get(action["node"])
        where = f"{WHERE} key action {action['node']}"
        if node is None or node["type"] != "remedy":
            error(where, "a Key Action is a Remedy node of the graph")
            continue
        if action["node"] in named:
            error(where, "named twice")
        named.add(action["node"])
        if node["source"] == "graph" and node["status"] == "obstructed":
            error(where, "obstructed: its Obstacle holds, name what unlocks it instead")
        if node["source"] == "model" and not node.get("evidence"):
            error(where, "a Remedy the model added needs evidence to be a Key Action")
        for goal in action["serves"]:
            if nodes.get(goal, {}).get("type") != "goal":
                error(where, f"serves '{goal}', which is not a Goal node")
            elif action["node"] not in reach.get(goal, ()):
                error(where, f"serves '{goal}', which does not lead to it")
        for other in action["unlocks"]:
            if nodes.get(other, {}).get("type") != "remedy":
                error(where, f"unlocks '{other}', which is not a Remedy node")
    for entry in doc.get("excluded_key_actions", []):
        where = f"{WHERE} excluded {entry['id']}"
        if nodes.get(entry["id"], {}).get("type") != "remedy":
            error(where, "only a Remedy node can be excluded from the Key Actions")
        if entry["id"] in named:
            error(where, "excluded but also a Key Action")
    return problems


# --- composing ---------------------------------------------------------------------------------


def compose(
    expansion: dict[str, Any],
    overlay: dict[str, Any],
    graph: MechanicsGraph,
    rules: dict[str, Rule] | None = None,
) -> dict[str, Any]:
    """The Solution Graph for `expansion` (an `Expansion.to_dict()`) and the model's `overlay`.

    Overlay: `{empire, goals: {id: {horizon, crisis?}}, prune: [{id, reason}], add_nodes: [{id,
    type, title, reason, ...}], add_edges: [{from, to}], exclude_key_actions: [{id, reason}],
    why: {remedy_id: text}, weights: [{from, to, weight, reason}]}`. `weights` must give every
    edge into a Cause (from a Goal or a Cause) a weight, high, medium or low: how much of the
    problem above this Cause explains, with the reason from the numbers. Edges into a Remedy take
    the Remedy's strength. The graph engine sizes nodes by these weights. Raises `SolutionInvalid` with every problem found; the result of a
    successful call has passed `validate_solution_graph`.
    """
    rules = graph.rules if rules is None else rules
    problems: list[Problem] = []

    def error(message: str, where: str = "overlay") -> None:
        problems.append(Problem("error", where, message))

    shape = _overlay_shape(overlay)
    for message in shape:
        error(message)
    if shape:
        raise SolutionInvalid(problems)

    by_id = {n["id"]: n for n in expansion["nodes"]}
    goal_settings = overlay.get("goals", {})
    for goal in expansion["goals"]:
        if goal["id"] not in goal_settings:
            error(f"no Horizon for Goal '{goal['id']}': goals.{goal['id']}.horizon is required")
    for goal_id in goal_settings:
        if goal_id not in {g["id"] for g in expansion["goals"]} | {
            n["id"] for n in overlay.get("add_nodes", []) if isinstance(n, dict)
        }:
            error(f"goals: '{goal_id}' is not a Goal of the expansion or an added Goal")

    nodes: list[dict[str, Any]] = [
        _goal_node(g, goal_settings.get(g["id"], {}), graph.goals[g["id"]]["mark"])
        for g in expansion["goals"]
    ]
    nodes += [_graph_node(n, graph) for n in expansion["nodes"]]
    edges = {(e["from"], e["to"]) for e in expansion["edges"]}

    pruned: list[dict[str, str]] = []
    gone: set[str] = set()
    for entry in overlay.get("prune", []):
        node = by_id.get(entry["id"])
        if node is None:
            error(f"prune: '{entry['id']}' is not a node of the expansion")
        elif node["type"] == "obstacle" and node["check"]["state"] == "present":
            error(
                f"prune: Obstacle '{entry['id']}' holds on this Snapshot; prune the Remedy it "
                "blocks instead"
            )
        elif entry["id"] not in gone:
            gone.add(entry["id"])
            pruned.append({"id": entry["id"], "reason": entry["reason"]})
    nodes = [n for n in nodes if n["id"] not in gone]
    edges = {(a, b) for a, b in edges if a not in gone and b not in gone}

    added = [_model_node(n, goal_settings) for n in overlay.get("add_nodes", [])]
    nodes_by_id = {n["id"]: n for n in nodes}
    for node in added:
        if node["id"] in nodes_by_id or node["id"] in by_id:
            error(f"add_nodes: '{node['id']}' clashes with an existing id")
        else:
            nodes_by_id[node["id"]] = node
    for edge in overlay.get("add_edges", []):
        edges.add((edge["from"], edge["to"]))

    # what only hung on pruned nodes goes with them (graph nodes only: a model node left without
    # a path is the model's mistake and the validator reports it as an orphan)
    onward: dict[str, list[str]] = {}
    for a, b in sorted(edges):
        onward.setdefault(a, []).append(b)
    roots = [n["id"] for n in nodes_by_id.values() if n["type"] == "goal"]
    reached = set(roots).union(*[_reach(r, onward) for r in roots]) if roots else set()
    for node_id in sorted(nodes_by_id):
        node = nodes_by_id[node_id]
        if node["source"] == "graph" and node_id not in reached:
            pruned.append({"id": node_id, "reason": "only reachable through pruned nodes"})
            del nodes_by_id[node_id]
    edges = {(a, b) for a, b in edges if a in nodes_by_id and b in nodes_by_id}

    ordered = [n for n in nodes if n["id"] in nodes_by_id]
    ordered += [n for n in nodes_by_id.values() if n["source"] == "model"]
    types = {n["id"]: n["type"] for n in ordered}
    edge_docs = [
        {"from": a, "to": b, "kind": types[b]}
        for a, b in sorted(edges)
        if a in types and b in types
    ]
    known = {(e["from"], e["to"]) for e in expansion["edges"]}
    known |= {(e["from"], e["to"]) for e in overlay.get("add_edges", [])}
    _weigh(edge_docs, {n["id"]: n for n in ordered}, overlay.get("weights", []), known, error)
    circles = _circles(expansion["circles"], nodes_by_id, edges, graph)
    key_actions, excluded = _key_actions(
        ordered, edges, overlay, graph, error, {p["id"] for p in pruned}
    )
    if problems:
        raise SolutionInvalid(problems)

    doc = {
        "schema": SCHEMA_VERSION,
        "game_version": expansion["version"],
        "date": expansion["date"],
        "empire": overlay["empire"],
        "nodes": ordered,
        "edges": edge_docs,
        "circles": circles,
        "key_actions": key_actions,
        "excluded_key_actions": excluded,
        "pruned": pruned,
    }
    problems += validate_solution_graph(doc, graph, rules)
    if problems:
        raise SolutionInvalid(problems)
    return doc


def _weigh(
    edge_docs: list[dict], nodes: dict[str, dict], weights: list[dict], known: set, error
) -> None:
    """Weights onto the edges: the model's for edges into a Cause, the Remedy's strength for
    edges into a Remedy. Every edge into a Cause needs one. A weight on an edge that pruning
    removed is ignored; one on an edge that never existed, or that leads to no Cause, is an
    error, so a stale overlay cannot slip through."""
    given = {(w["from"], w["to"]): w for w in weights}
    used: set[tuple[str, str]] = set()
    for edge in edge_docs:
        key = (edge["from"], edge["to"])
        if edge["kind"] == "cause":
            entry = given.get(key)
            if entry is None:
                error(
                    f"weights: no weight for {edge['from']} > {edge['to']}; give high, medium or "
                    "low and the reason from the numbers"
                )
                continue
            used.add(key)
            edge["weight"] = entry["weight"]
            edge["weight_reason"] = entry["reason"]
        elif edge["kind"] == "remedy":
            strength = nodes[edge["to"]].get("ratings", {}).get("strength")
            if strength:
                edge["weight"] = strength
    kinds = {(e["from"], e["to"]): e["kind"] for e in edge_docs}
    for key in sorted(set(given) - used):
        if key in known and key not in kinds:
            continue  # the edge went with a pruned node
        error(f"weights: {key[0]} > {key[1]} is not an edge into a Cause of this graph")


def _overlay_shape(overlay: Any) -> list[str]:
    if not isinstance(overlay, dict):
        return ["the overlay must be a JSON object"]
    found = [f"unknown overlay field '{k}'" for k in sorted(set(overlay) - _OVERLAY_KEYS)]
    if not isinstance(overlay.get("empire"), str) or not overlay["empire"].strip():
        found.append("empire is required (the Tracked Empire's name)")
    goals = overlay.get("goals", {})
    if not isinstance(goals, dict):
        found.append("goals must be an object keyed by Goal id")
    else:
        for goal_id, setting in goals.items():
            if not isinstance(setting, dict) or setting.get("horizon") not in (
                "short",
                "medium",
                "long",
            ):
                found.append(f"goals.{goal_id}.horizon must be short, medium or long")
            elif set(setting) - {"horizon", "crisis"}:
                found.append(f"goals.{goal_id}: only horizon and crisis are allowed")
    for name in ("prune", "exclude_key_actions"):
        for entry in _list(overlay, name, found):
            if not _reasoned(entry):
                found.append(f"{name}: every entry needs an id and a reason")
    for name, keys in (("add_nodes", None), ("add_edges", {"from", "to"})):
        for entry in _list(overlay, name, found):
            if not isinstance(entry, dict) or (keys and set(entry) != keys):
                found.append(f"{name}: malformed entry {entry!r}")
            elif name == "add_nodes" and not isinstance(entry.get("id"), str):
                found.append("add_nodes: every node needs an id")
    for entry in _list(overlay, "weights", found):
        if (
            not isinstance(entry, dict)
            or set(entry) != {"from", "to", "weight", "reason"}
            or entry["weight"] not in _RATINGS
            or not isinstance(entry["reason"], str)
            or not entry["reason"].strip()
        ):
            found.append(
                f"weights: every entry needs from, to, weight (high, medium, low) and a reason: {entry!r}"
            )
    why = overlay.get("why", {})
    if not isinstance(why, dict) or not all(isinstance(v, str) and v.strip() for v in why.values()):
        found.append("why must map Remedy ids to non-empty text")
    return found


def _list(overlay: dict[str, Any], name: str, found: list[str]) -> list[Any]:
    value = overlay.get(name, [])
    if not isinstance(value, list):
        found.append(f"{name} must be a list")
        return []
    return value


def _reasoned(entry: Any) -> bool:
    return (
        isinstance(entry, dict)
        and set(entry) == {"id", "reason"}
        and isinstance(entry["id"], str)
        and isinstance(entry["reason"], str)
        and bool(entry["reason"].strip())
    )


def _goal_node(goal: dict[str, Any], setting: dict[str, Any], mark: str) -> dict[str, Any]:
    evidence = [
        f"{s['metric']} {s['value']}{_unit(s)}"
        if s["value"] is not None
        else f"{s['metric']} has no value in this save"
        for s in goal["symptoms"]
    ]
    return {
        "id": goal["id"],
        "type": "goal",
        "source": "graph",
        "title": goal["title"],
        "horizon": setting.get("horizon", "short"),
        "crisis": setting.get("crisis", goal["crisis"]),
        "mark": mark,
        "evidence": evidence,
    }


def _unit(symptom: dict[str, Any]) -> str:
    return f" {symptom['unit']}" if symptom.get("unit") else ""


def _graph_text(node: dict[str, Any], graph: MechanicsGraph) -> str:
    source = graph.nodes.get(node["id"], {})
    return source.get("judgement" if node["type"] == "remedy" else "description", "")


def _graph_node(node: dict[str, Any], graph: MechanicsGraph) -> dict[str, Any]:
    # The expansion drops node text when it is over the size budget; the graph has it.
    text = node.get("text") or _graph_text(node, graph)
    out: dict[str, Any] = {
        "id": node["id"],
        "type": node["type"],
        "source": "graph",
        "title": node["title"],
        "text": text,
    }
    evidence: list[str] = []
    if node["type"] == "obstacle":
        out["check_state"] = node["check"]["state"]
        evidence.append(_check_evidence(node["check"]))
        # not checked against the numbers: say it in the conditional ("may have no free slot")
        uncertain = graph.nodes.get(node["id"], {}).get("uncertain_title")
        if uncertain and out["check_state"] in ("judgement", "unknown"):
            out["title"] = uncertain
    if node.get("places"):
        evidence += _places_evidence(node["places"])
    if node["type"] == "remedy":
        out["status"] = node["status"]
        out["ratings"] = dict(node["ratings"])
        evidence += [f"obstructed by {o}" for o in node["obstructed_by"]]
        evidence += [f"not checked against numbers: {o}" for o in node["unchecked"]]
        if "pending_check" in node:
            evidence.append(f"pending when {_check_evidence(node['pending_check'])}")
    out["evidence"] = evidence
    if node["rules"]:
        out["rules"] = list(node["rules"])
    return out


def _places_evidence(places: dict[str, Any]) -> list[str]:
    """One line per planet the expansion named for a node about the whole empire: `Astarte: 0
    building slots`. The planets with the fewest free places come first."""
    unit = places.get("unit") or "free places"
    lines = [f"{p['planet']}: {p['free']} {unit}" for p in places["planets"]]
    if places.get("more"):
        lines.append(f"and {places['more']} more planets with more room")
    return lines


def _check_evidence(check: dict[str, Any]) -> str:
    """One line from the numbers the code compared: `unity.stockpile 412 < traditions.next_cost 650`."""
    state = check["state"]
    if state == "judgement":
        return "not checkable against numbers (judgement)"
    values = check["values"]
    if any(v is None for v in values.values()):
        return f"{check['metric']} has no value in this save (unknown)"
    target = check["compare_to"]
    right = f"{target} {values[target]}" if isinstance(target, str) else str(target)
    return f"{check['metric']} {values[check['metric']]} {check['op']} {right} ({state})"


def _model_node(node: dict[str, Any], goals: dict[str, Any]) -> dict[str, Any]:
    out = {k: v for k, v in node.items() if k != "source"}
    if node.get("source", "model") != "model":
        out["source"] = node["source"]  # the schema rejects it with a clear message
        return out
    out["source"] = "model"
    if out.get("type") == "goal":
        setting = goals.get(out["id"], {})
        out.setdefault("horizon", setting.get("horizon", "short"))
        out.setdefault("crisis", setting.get("crisis", False))
    return out


def _circles(circles, nodes, edges, graph: MechanicsGraph) -> list[dict[str, Any]]:
    """The expansion's circles that still loop after pruning: a circle is re-derived from the
    edges between its remaining members, so one that pruning opened is dropped, one that split
    gets a numbered id."""
    kept = []
    for circle in circles:
        members = {m for m in circle["members"] if m in nodes}
        adjacency = {m: [b for a, b in sorted(edges) if a == m and b in members] for m in members}
        loops = [c for c in _components(adjacency) if len(c) > 1 or c[0] in adjacency[c[0]]]
        for number, component in enumerate(loops, 1):
            break_point = circle["break_point"]
            if break_point not in component:
                remedies = [m for m in component if nodes[m]["type"] == "remedy"]
                break_point = _break_point(graph, remedies)
            name = circle["id"] if number == 1 else f"{circle['id']}-{number}"
            kept.append({"id": name, "members": component, "break_point": break_point})
    return kept


def _key_actions(nodes, edges, overlay, graph: MechanicsGraph, error, pruned: set[str]):
    by_id = {n["id"]: n for n in nodes}
    onward: dict[str, list[str]] = {}
    for a, b in sorted(edges):
        onward.setdefault(a, []).append(b)
    goals = [n["id"] for n in nodes if n["type"] == "goal"]
    reach = {g: _reach(g, onward) for g in goals}
    crisis = [n["id"] for n in nodes if n["type"] == "goal" and n.get("crisis")]

    unlocks: dict[str, set[str]] = {}
    for blocked, node in by_id.items():
        if node["type"] != "remedy" or node.get("status") != "obstructed":
            continue
        for obstacle in graph.nodes[blocked].get("obstacles", []):
            if by_id.get(obstacle, {}).get("check_state") != "present":
                continue
            for helper in graph.nodes[obstacle].get("remedies", []):
                if (obstacle, helper) in edges:
                    unlocks.setdefault(helper, set()).add(blocked)

    excluded = []
    out_ids: set[str] = set()
    for entry in overlay.get("exclude_key_actions", []):
        if by_id.get(entry["id"], {}).get("type") != "remedy":
            error(f"exclude_key_actions: '{entry['id']}' is not a Remedy of the Solution Graph")
        elif entry["id"] not in out_ids:
            out_ids.add(entry["id"])
            excluded.append({"id": entry["id"], "reason": entry["reason"]})

    candidates = []
    for node_id, node in by_id.items():
        if node["type"] != "remedy" or node_id in out_ids:
            continue
        status = node.get("status", "actionable")
        if status == "obstructed" or "ratings" not in node:
            continue
        if node["source"] == "model" and not node.get("evidence"):
            continue
        serves = tuple(g for g in goals if node_id in reach[g])
        candidates.append(
            Candidate(
                node_id, status, serves, tuple(sorted(unlocks.get(node_id, ()))), **node["ratings"]
            )
        )
    ranked = rank_key_actions(candidates, crisis)
    why = overlay.get("why", {})
    actions = []
    for rank, candidate in enumerate(ranked, 1):
        if candidate.node not in why:
            error(
                f"why: no reason for Key Action '{candidate.node}'; write one or list it in "
                "exclude_key_actions"
            )
        entry = candidate.to_dict(rank)
        del entry["status"]
        actions.append({**entry, "why": why.get(candidate.node, "")})
    for node_id in sorted(set(why) - {c.node for c in ranked} - pruned - out_ids):
        error(f"why: '{node_id}' is not a Key Action of this Solution Graph")
    return actions, excluded


def problems_text(problems: Iterable[Problem]) -> str:
    return "\n".join(str(p) for p in problems)
