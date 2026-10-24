"""Expanding the Mechanics Graph from chosen Goals against one Snapshot: M5's `expand_graph`.

The code does what must come out identical every time (docs/plans/M5.md): it walks the graph from
the Goals, checks each Obstacle against the Snapshot, marks every Remedy Actionable, Pending or
obstructed, finds the Vicious Circles and ranks the Key Action candidates by a fixed rule. The
model then picks the Goals, weighs what the code cannot check and writes the Strategy. The
function is pure and deterministic: no clock, no randomness, every set is sorted before it is
walked, the YAML file order breaks ties.

Reading of the glossary (one line to change, see `_remedy_status`):

- `obstructed`: some Obstacle of the Remedy holds (`present`) and `pending_when` does not.
- `pending`: some Obstacle holds, but the Remedy's `pending_when` is true, i.e. the Obstacle
  resolves on its own within the Horizon. Pending counts as Actionable for Key Actions.
- `actionable`: no Obstacle holds. Obstacles that are `unknown` or `judgement` do not change the
  status; the Remedy lists them in `unchecked` so the model weighs them and says so.

A `clear` Obstacle is a leaf with its evidence and its Remedies are not walked, so a Vicious Circle
that a clear Obstacle breaks is not reported. Fair Play: only the metrics registry is read, and it
has no path into other empires' data.
"""

from __future__ import annotations

import json
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from hlidskjalf.graph.mechanics import MechanicsGraph
from hlidskjalf.graph.metrics import Check, evaluate, resolve_metric

DEFAULT_DEPTH_LIMIT = 5
RESULT_BUDGET = 40_000  # characters, the size budget of an extract-sized tool result
EFFECTS_PER_NODE = 5
EFFECTS_PER_NODE_TIGHT = 3

_LINKS = ("causes", "remedies", "obstacles")
_KIND = {"causes": "cause", "remedies": "remedy", "obstacles": "obstacle"}
_BEST_FIRST = {"high": 0, "medium": 1, "low": 2}  # strength, speed
_CHEAPEST_FIRST = {"low": 0, "medium": 1, "high": 2}  # cost


@dataclass(frozen=True)
class Candidate:
    """A Remedy that can be done now (or soon): what it serves, what it unlocks, how it rates."""

    node: str
    status: str  # actionable | pending
    serves: tuple[str, ...]
    unlocks: tuple[str, ...]
    strength: str
    speed: str
    cost: str

    def to_dict(self, rank: int) -> dict[str, Any]:
        return {
            "rank": rank,
            "node": self.node,
            "status": self.status,
            "serves": list(self.serves),
            "unlocks": list(self.unlocks),
        }


def rank_key_actions(
    candidates: Iterable[Candidate], crisis_goals: Iterable[str]
) -> list[Candidate]:
    """Best first: serves a Crisis Goal, then number of Goals served, strength, speed, lower cost,
    actionable before pending, node id. The one ranking `compose` reuses (M5 increment 3)."""
    crisis = set(crisis_goals)

    def key(c: Candidate):
        return (
            not crisis.intersection(c.serves),
            -len(c.serves),
            _BEST_FIRST[c.strength],
            _BEST_FIRST[c.speed],
            _CHEAPEST_FIRST[c.cost],
            c.status != "actionable",
            c.node,
        )

    return sorted(candidates, key=key)


@dataclass
class Expansion:
    version: str
    date: str
    goals: list[dict[str, Any]]
    unknown_goals: list[str]
    nodes: list[dict[str, Any]]
    edges: list[dict[str, str]]
    circles: list[dict[str, Any]]
    candidates: list[Candidate]
    playbook_rules: dict[str, dict[str, str]]
    warnings: list[str]
    effects: dict[str, list[dict[str, Any]]] = field(default_factory=dict, repr=False)

    def to_dict(self, budget: int = RESULT_BUDGET) -> dict[str, Any]:
        """Plain JSON. Over the budget, effects drop to three per node, then the text of clear
        Obstacles goes (their title and evidence stay)."""
        out = self._render(EFFECTS_PER_NODE)
        if len(json.dumps(out)) > budget:
            out = self._render(EFFECTS_PER_NODE_TIGHT)
        if len(json.dumps(out)) > budget:
            for node in out["nodes"]:
                if node.get("check", {}).get("state") == "clear":
                    node.pop("text", None)
        return out

    def _render(self, effects_per_node: int) -> dict[str, Any]:
        nodes = []
        for node in self.nodes:
            effects = self.effects.get(node["id"], [])
            shown = {"effects": effects[:effects_per_node]}
            if len(effects) > effects_per_node:
                shown["effects_more"] = len(effects) - effects_per_node
            nodes.append({**node, **shown})
        return {
            "version": self.version,
            "date": self.date,
            "goals": self.goals,
            "unknown_goals": self.unknown_goals,
            "nodes": nodes,
            "edges": self.edges,
            "circles": self.circles,
            "key_action_candidates": [c.to_dict(i) for i, c in enumerate(self.candidates, 1)],
            "playbook_rules": self.playbook_rules,
            "warnings": self.warnings,
        }


def expand_graph(
    graph: MechanicsGraph,
    goals: Iterable[str],
    extract: dict[str, Any],
    *,
    crisis_goals: Iterable[str] = (),
    depth_limit: int = DEFAULT_DEPTH_LIMIT,
) -> Expansion:
    """Walk the graph from `goals` (ids), breadth first so a node's depth is its shortest distance
    from any Goal, evaluate it against `extract` and return the Expansion. An unknown Goal id is
    returned in `unknown_goals` and never raises."""
    if depth_limit < 1:
        raise ValueError("depth_limit must be at least 1")
    wanted = sorted(set(goals))
    known = [g for g in wanted if g in graph.goals]
    crisis = sorted(set(crisis_goals))
    warnings: list[str] = []
    for goal_id in crisis:
        if goal_id not in known:
            warnings.append(f"crisis goal '{goal_id}' is not among the expanded Goals")

    checks: dict[str, Check] = {}

    def check_of(obstacle_id: str) -> Check:
        if obstacle_id not in checks:
            checks[obstacle_id] = evaluate(graph.node(obstacle_id)["check"], graph.metrics, extract)
        return checks[obstacle_id]

    depth, edges, too_far = _walk(graph, known, check_of, depth_limit)
    nodes = {
        nid: _node(graph, nid, d, nid in too_far, check_of, extract)
        for nid, d in depth.items()
        if nid not in graph.goals
    }
    circles = _circles(graph, nodes, edges, warnings)
    for circle in circles:
        for member in circle["members"]:
            nodes[member]["circle"] = circle["id"]

    reached = _reached(known, edges)
    candidates = _candidates(graph, nodes, edges, reached, crisis)
    rules = {
        rule_id: {"reason": graph.rules[rule_id].reason, "body": graph.rules[rule_id].body}
        for rule_id in sorted({r for n in nodes.values() for r in n["rules"]})
        if rule_id in graph.rules
    }
    ordered = sorted(nodes.values(), key=lambda n: (n["depth"], n["id"]))
    unknown_metrics = sorted(
        {
            name
            for n in ordered
            for check in (n.get("check"), n.get("pending_check"))
            for name, value in (check or {}).get("values", {}).items()
            if value is None
        }
    )
    warnings += [f"metric '{name}' has no value in this save" for name in unknown_metrics]
    header = extract.get("header", {})
    return Expansion(
        version=graph.version,
        date=header.get("date", ""),
        goals=[_goal(graph, g, g in crisis, extract) for g in known],
        unknown_goals=[g for g in wanted if g not in graph.goals],
        nodes=ordered,
        edges=[
            {"from": a, "to": b, "kind": nodes[b]["type"]} for a, b in sorted(edges) if b in nodes
        ],
        circles=circles,
        candidates=candidates,
        playbook_rules=rules,
        warnings=warnings,
        effects={nid: _effects(graph, nid) for nid in nodes if graph.node(nid).get("facts")},
    )


# --- the walk ----------------------------------------------------------------------------------


def _walk(graph: MechanicsGraph, goals: list[str], check_of, depth_limit: int):
    """Breadth first from the Goals. Returns node depths (Goals 0, their Causes 1), the edges
    found and the nodes that stopped at the depth limit with something left to expand."""
    depth: dict[str, int] = {g: 0 for g in goals}
    edges: set[tuple[str, str]] = set()
    too_far: set[str] = set()
    queue: deque[str] = deque(goals)
    while queue:
        current = queue.popleft()
        children = _children(graph, current, check_of)
        if depth[current] >= depth_limit and current not in graph.goals:
            if children:
                too_far.add(current)
            continue
        for child in children:
            edges.add((current, child))
            if child not in depth:
                depth[child] = depth[current] + 1
                queue.append(child)
    return depth, edges, too_far


def _children(graph: MechanicsGraph, current: str, check_of) -> list[str]:
    """Links to follow from a node; a clear Obstacle is a leaf (its Remedies are not walked)."""
    if current in graph.goals:
        return list(graph.goals[current]["causes"])
    node = graph.node(current)
    if node["type"] == "obstacle" and check_of(current).state == "clear":
        return []
    return [target for kind in _LINKS for target in node.get(kind, [])]


# --- nodes -------------------------------------------------------------------------------------


def _goal(graph: MechanicsGraph, goal_id: str, crisis: bool, extract: dict[str, Any]):
    goal = graph.goals[goal_id]
    symptoms = []
    for name in goal.get("symptom_metrics", []):
        spec = graph.metrics[name]
        symptoms.append(
            {"metric": name, "value": resolve_metric(spec, extract), "unit": spec.get("unit")}
        )
    return {"id": goal_id, "title": goal["title"], "symptoms": symptoms, "crisis": crisis}


def _node(graph: MechanicsGraph, node_id: str, depth: int, too_far: bool, check_of, extract):
    node = graph.node(node_id)
    kind = node["type"]
    out: dict[str, Any] = {
        "id": node_id,
        "type": kind,
        "title": node["title"],
        "text": node["judgement"] if kind == "remedy" else node["description"],
        "depth": depth,
        "too_far": too_far,
        "rules": list(node.get("rules", [])),
        "circle": None,
    }
    if kind == "obstacle":
        out["check"] = check_of(node_id).to_dict()
    if kind == "remedy":
        out["ratings"] = {k: node[k] for k in ("strength", "speed", "cost")}
        out.update(_remedy_status(graph, node, check_of, extract))
    return out


def _remedy_status(graph: MechanicsGraph, remedy: dict[str, Any], check_of, extract):
    """Status from the Remedy's Obstacles, evaluated directly so it holds even for a Remedy that
    sits on the depth limit and whose Obstacles are not part of the expansion."""
    obstacles = remedy.get("obstacles", [])
    present = [o for o in obstacles if check_of(o).state == "present"]
    unchecked = [o for o in obstacles if check_of(o).state in ("unknown", "judgement")]
    result: dict[str, Any] = {"obstructed_by": present, "unchecked": unchecked}
    if not present:
        result["status"] = "actionable"
        return result
    result["status"] = "obstructed"
    if "pending_when" in remedy:
        pending = evaluate(remedy["pending_when"], graph.metrics, extract)
        result["pending_check"] = pending.to_dict()
        if pending.state == "present":
            result["status"] = "pending"
    return result


def _effects(graph: MechanicsGraph, node_id: str) -> list[dict[str, Any]]:
    effects = []
    for fact in graph.node_facts(node_id):
        name = fact.get("source", {}).get("name")
        if not name:
            raise ValueError(f"fact {fact['id']} has no Display Name for its source")
        effects.append(
            {
                "source": name,
                "modifier": fact.get("modifier"),
                "amount": fact.get("amount"),
                "amount_kind": fact.get("amount_kind"),
                "requirement": fact.get("requirement", []),
            }
        )
    return effects


# --- circles and Key Actions -------------------------------------------------------------------


def _circles(graph, nodes, edges, warnings: list[str]) -> list[dict[str, Any]]:
    adjacency: dict[str, list[str]] = {nid: [] for nid in nodes}
    for a, b in sorted(edges):
        if a in nodes and b in nodes:
            adjacency[a].append(b)
    circles = []
    for component in _components(adjacency):
        only = component[0]
        if len(component) == 1 and only not in adjacency[only]:
            continue
        circle_id = _circle_name(graph, component)
        remedies = [m for m in component if nodes[m]["type"] == "remedy"]
        break_point = _break_point(graph, remedies)
        if break_point is None:
            warnings.append(f"circle '{circle_id}' has no Remedy to break it; judgement needed")
        circles.append({"id": circle_id, "members": component, "break_point": break_point})
    return sorted(circles, key=lambda c: (c["id"], c["members"]))


def _circle_name(graph: MechanicsGraph, members: list[str]) -> str:
    names: dict[str, int] = {}
    for member in members:
        name = graph.node(member).get("circle")
        if name:
            names[name] = names.get(name, 0) + 1
    if not names:
        return f"circle:{members[0]}"
    return sorted(names, key=lambda n: (-names[n], n))[0]


def _break_point(graph: MechanicsGraph, remedies: list[str]) -> str | None:
    if not remedies:
        return None
    marked = [r for r in remedies if graph.node(r).get("break_point")]
    if marked:
        return sorted(marked)[0]

    def key(remedy_id: str):
        node = graph.node(remedy_id)
        return (_CHEAPEST_FIRST[node["cost"]], _BEST_FIRST[node["strength"]], remedy_id)

    return min(remedies, key=key)


def _components(adjacency: dict[str, list[str]]) -> list[list[str]]:
    """Strongly connected components, Tarjan without recursion; each sorted, in stable order."""
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    result: list[list[str]] = []
    for root in sorted(adjacency):
        if root in index:
            continue
        work = [(root, iter(adjacency[root]))]
        index[root] = low[root] = len(index)
        stack.append(root)
        on_stack.add(root)
        while work:
            name, targets = work[-1]
            advanced = False
            for target in targets:
                if target not in index:
                    index[target] = low[target] = len(index)
                    stack.append(target)
                    on_stack.add(target)
                    work.append((target, iter(adjacency[target])))
                    advanced = True
                    break
                if target in on_stack:
                    low[name] = min(low[name], index[target])
            if advanced:
                continue
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[name])
            if low[name] == index[name]:
                component = []
                while True:
                    member = stack.pop()
                    on_stack.discard(member)
                    component.append(member)
                    if member == name:
                        break
                result.append(sorted(component))
    return result


def _reached(goals: list[str], edges: set[tuple[str, str]]) -> dict[str, set[str]]:
    """For each Goal, every node reachable through the expansion's edges."""
    onward: dict[str, list[str]] = {}
    for a, b in sorted(edges):
        onward.setdefault(a, []).append(b)
    reached = {}
    for goal in goals:
        seen: set[str] = set()
        queue = deque([goal])
        while queue:
            for target in onward.get(queue.popleft(), []):
                if target not in seen:
                    seen.add(target)
                    queue.append(target)
        reached[goal] = seen
    return reached


def _candidates(graph, nodes, edges, reached, crisis) -> list[Candidate]:
    """Every actionable or pending Remedy; `unlocks` = the obstructed Remedies for which it
    is a Remedy of a present Obstacle (the next step on the Strategy path)."""
    unlocks: dict[str, set[str]] = {}
    for blocked, node in nodes.items():
        if node["type"] != "remedy" or node["status"] != "obstructed":
            continue
        for obstacle in node["obstructed_by"]:
            for helper in graph.node(obstacle).get("remedies", []):
                if (obstacle, helper) in edges:
                    unlocks.setdefault(helper, set()).add(blocked)
    found = []
    for node_id, node in nodes.items():
        if node["type"] != "remedy" or node["status"] not in ("actionable", "pending"):
            continue
        serves = tuple(g for g in sorted(reached) if node_id in reached[g])
        found.append(
            Candidate(
                node=node_id,
                status=node["status"],
                serves=serves,
                unlocks=tuple(sorted(unlocks.get(node_id, ()))),
                **node["ratings"],
            )
        )
    return rank_key_actions(found, crisis)
