"""The topics of a Drill: which Causes the Coach asks about, in which order (M9, `docs/plans/M9.md` 20e).

`build_topics` takes a Snapshot extract and the Player's own Goals (asked at the first Drill and every
Rendezvous, kept in `drill.json`), expands them with `graph.expand.expand_graph` and turns the Causes it
reaches into the list `academy/drill.open_drill` takes: `concept`, `crisis`, `open_question`, and further
fields that the Drill keeps as they are.

Order: Crisis topics first, then by Key Action weight (the best rank, in `expansion.candidates`, of a Remedy
of the Cause; a Cause whose Remedies are all obstructed has no weight and comes after those that have one),
then nearer to a Goal, then the id.

    crisis           the Cause is reached from a Goal of a resource that runs out (`player/evidence.crisis`).
                     Those Goals are expanded even when the Player did not name them: a Crisis comes first
                     whatever the Player asked for.
    open_question    the concept is at Analyse: only an open question that does not name the domain is asked.
    hidden_knowledge a metric that chose the topic (the Cause's `present_when`, the Obstacle checks and
                     `pending_when` of its Remedies, which decide the weight) reads God Mode data.
    pointers         the figures the Coach may point at, `{metric, value, unit, why}`: the Cause's
                     presence metrics and the symptoms of the Goals that reach it. Never a title, a Remedy
                     or a description of the Cause: that is the answer, and the Hint Ladder decides when
                     it is given.

Skipped, and counted in `skipped`: concepts at Evaluate or above (`mastered`) and Causes whose
`present_when` says they are not there (`not_present`; `unknown` and `unmeasured` stay, the Coach asks).

Fair Play: what the model is told is what the Tracked Empire can see. A metric is hidden when its path reads
the other empires' facts without their `visible` part (`known_empires`). Under Fair Play hidden pointers are
left out and the topic carries `hidden_knowledge`, so the Coach does not give a reason that rests on
them; under God Mode pointers may carry everything. No metric of the 4.5.2 pack reads other empires today, so
no topic is flagged; the rule is what keeps it so when one does.

The `concept` is the key of the Player Model and names the Cause; the tools of 20h must keep it out of what
the model sees until the Ladder reaches the answer.

Choices where the plan is silent, each pinned by a test:
- A Goal the pack does not know is reported in `unknown_goals`; with no known Goal left the call is refused.
- A Cause reached from two Goals is one topic that lists both (`goals`).
- Only direct Remedies of a Cause give it a weight; sub-Causes are topics of their own.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable, Iterator
from typing import Any

from admiralty.graph.expand import expand_graph
from admiralty.graph.mechanics import MechanicsGraph
from admiralty.graph.metrics import resolve_metric
from admiralty.player import evidence, store

HIDDEN_ROOT = "known_empires"
VISIBLE_PART = "visible"
MASTERED_FROM = store.LEVELS.index("evaluate")
OPEN_QUESTION_AT = "analyse"


class TopicError(ValueError):
    """No topic can be built (no Goal the pack knows)."""


def build_topics(
    graph: MechanicsGraph,
    extract: dict[str, Any],
    goals: Iterable[str],
    *,
    model: dict[str, Any] | None = None,
    god_mode: bool = False,
) -> dict[str, Any]:
    """The topic list for a Drill on this Snapshot.

    `model` is the Player Model (`store.read_model`, read when not given). Returns `date`, `goals` (the ids
    expanded, Crisis Goals included), `unknown_goals`, `crisis` (`player/evidence.crisis`), `topics`, `count`
    and `skipped`. Raises `TopicError` when none of `goals` is a Goal of the pack.
    """
    wanted = list(dict.fromkeys(goals))
    known = [g for g in wanted if g in graph.goals]
    if not known:
        raise TopicError(
            "name at least one Goal of the Mechanics Graph to build topics from; "
            f"Goals: {', '.join(sorted(graph.goals))}"
        )
    if model is None:
        model = store.read_model()
    state = evidence.crisis(extract)
    short = {entry["resource"] for entry in state["resources"]}
    crisis_goals = sorted(g for g in graph.goals if g.split(".", 1)[0] in short)
    expanded = sorted({*known, *crisis_goals})
    expansion = expand_graph(graph, expanded, extract, crisis_goals=crisis_goals)

    onward: dict[str, list[str]] = {}
    for edge in expansion.edges:
        onward.setdefault(edge["from"], []).append(edge["to"])
    reached = {goal: _reach(goal, onward) for goal in expanded}
    crisis_nodes = set().union(*(reached[g] for g in crisis_goals)) if crisis_goals else set()
    rank = {c.node: position for position, c in enumerate(expansion.candidates, 1)}

    found: list[tuple[tuple, dict[str, Any]]] = []
    skipped = {"mastered": 0, "not_present": 0}
    for node in expansion.nodes:
        if node["type"] != "cause":
            continue
        concept = node["id"]
        level = store.level_of(model, concept)
        if store.LEVELS.index(level) >= MASTERED_FROM:
            skipped["mastered"] += 1
            continue
        if evidence.cause_presence(graph, concept, extract) == "clear":
            skipped["not_present"] += 1
            continue
        serving = [g for g in expanded if concept in reached[g]]
        topic = _topic(
            graph,
            extract,
            concept,
            level,
            serving,
            crisis=concept in crisis_nodes,
            weight=_weight(graph, concept, rank),
            god_mode=god_mode,
        )
        order = (not topic["crisis"], topic["weight"] is None, topic["weight"] or 0, node["depth"])
        found.append(((*order, concept), topic))
    topics = [topic for _, topic in sorted(found, key=lambda item: item[0])]
    return {
        "date": expansion.date,
        "goals": expanded,
        "unknown_goals": [g for g in wanted if g not in graph.goals],
        "crisis": state,
        "topics": topics,
        "count": len(topics),
        "skipped": skipped,
    }


def is_hidden(path: str) -> bool:
    """True when the path reads other empires' facts without their `visible` part (God Mode only)."""
    parts = path.split(".")
    return parts[0] == HIDDEN_ROOT and VISIBLE_PART not in parts


def metric_paths(spec: dict[str, Any]) -> Iterator[str]:
    """Every extract path a registered metric reads."""
    if "path" in spec:
        yield spec["path"]
    yield from spec.get("sum", [])
    if "contains" in spec:
        yield spec["contains"]["path"]
    if "ratio" in spec:
        yield spec["ratio"]["numerator"]
        yield spec["ratio"]["denominator"]


def _reach(start: str, onward: dict[str, list[str]]) -> set[str]:
    seen: set[str] = set()
    queue = deque([start])
    while queue:
        for target in onward.get(queue.popleft(), []):
            if target not in seen:
                seen.add(target)
                queue.append(target)
    return seen


def _weight(graph: MechanicsGraph, concept: str, rank: dict[str, int]) -> int | None:
    ranks = [rank[r] for r in graph.node(concept).get("remedies", []) if r in rank]
    return min(ranks) if ranks else None


def _topic(
    graph: MechanicsGraph,
    extract: dict[str, Any],
    concept: str,
    level: str,
    serving: list[str],
    *,
    crisis: bool,
    weight: int | None,
    god_mode: bool,
) -> dict[str, Any]:
    choosing = _choosing_metrics(graph, concept)
    hidden = any(is_hidden(p) for name in choosing for p in metric_paths(graph.metrics[name]))
    pointers = []
    shown: set[str] = set()
    figures = [(m, "presence") for m in _presence_metrics(graph, concept)]
    figures += [(m, "symptom") for g in serving for m in graph.goals[g].get("symptom_metrics", [])]
    for name, why in figures:
        spec = graph.metrics[name]
        if name in shown or (not god_mode and any(is_hidden(p) for p in metric_paths(spec))):
            continue
        value = resolve_metric(spec, extract)
        if value is None:
            continue
        shown.add(name)
        pointers.append({"metric": name, "value": value, "unit": spec.get("unit"), "why": why})
    return {
        "concept": concept,
        "domain": concept.split(".", 1)[0],
        "level": level,
        "crisis": crisis,
        "open_question": level == OPEN_QUESTION_AT,
        "goals": serving,
        "weight": weight,
        "hidden_knowledge": hidden,
        "pointers": pointers,
    }


def _presence_metrics(graph: MechanicsGraph, concept: str) -> list[str]:
    return list(_names(graph.node(concept).get("present_when")))


def _choosing_metrics(graph: MechanicsGraph, concept: str) -> list[str]:
    """Metrics whose values decided that the Cause is a topic and where it stands: presence, and the Obstacle
    checks and `pending_when` of its Remedies (they decide the Key Action weight)."""
    node = graph.node(concept)
    names = list(_names(node.get("present_when")))
    for remedy_id in node.get("remedies", []):
        remedy = graph.node(remedy_id)
        names += _names(remedy.get("pending_when"))
        for obstacle_id in remedy.get("obstacles", []):
            names += _names(graph.node(obstacle_id).get("check"))
    return list(dict.fromkeys(names))


def _names(comparison: dict[str, Any] | None) -> list[str]:
    if not comparison or "metric" not in comparison:
        return []
    target = comparison.get("compare_to")
    return [comparison["metric"], *([target["metric"]] if isinstance(target, dict) else [])]
