"""Wording rules for the titles of the curated graph (docs/plans/titles.md).

Decisions: docs/plans/grilling.md topic 2 and docs/plans/M6-revision.md "Agreed but not done yet".
Titles are English, carry no figures, and name game objects as the English interface does. Beyond the
decided limits (Goals and Remedies at most five words) the Cause and Obstacle caps are house limits that
keep a tile readable.
"""

from __future__ import annotations

import re

GOAL_WORDS = 5
REMEDY_WORDS = 5
CAUSE_WORDS = 6
OBSTACLE_WORDS = 12

# a Remedy is an instruction: its first word is one of these verbs
REMEDY_VERBS = frozenset(
    "Add Adopt Build Buy Convert Deal Drop Enact Finish Grow Keep Lower Open Raise Replace "
    "Research Spread Staff Take Trim".split()
)

_DIGIT = re.compile(r"\d")


def title_problems(kind: str, title: str, uncertain: str | None = None) -> list[str]:
    """What is wrong with one title; `kind` is goal, cause, remedy or obstacle."""
    found: list[str] = []
    words = title.split()
    if _DIGIT.search(title):
        found.append("digits in the title; figures belong in the facts a node links to")
    limit = {
        "goal": GOAL_WORDS,
        "remedy": REMEDY_WORDS,
        "cause": CAUSE_WORDS,
        "obstacle": OBSTACLE_WORDS,
    }[kind]
    if len(words) > limit:
        found.append(f"{len(words)} words, at most {limit} for a {kind}")
    if kind == "remedy" and words and words[0] not in REMEDY_VERBS:
        found.append(f"a Remedy starts with an imperative verb, not '{words[0]}'")
    if kind == "obstacle":
        if uncertain is None:
            found.append("an Obstacle needs an uncertain_title")
        else:
            if _DIGIT.search(uncertain):
                found.append("digits in the uncertain_title")
            if not re.search(r"\bmay\b", uncertain):
                found.append("the uncertain_title must say 'may'")
            if re.search(r"\bmay\b", title):
                found.append("the title of a checked Obstacle states, it does not say 'may'")
    return found


def lint(graph) -> list[str]:
    """Every wording problem in a loaded MechanicsGraph, as `<id>: <problem>`."""
    out: list[str] = []
    for goal_id, goal in graph.goals.items():
        out += [f"{goal_id}: {p}" for p in title_problems("goal", goal["title"])]
    for node_id, node in graph.nodes.items():
        out += [
            f"{node_id}: {p}"
            for p in title_problems(node["type"], node["title"], node.get("uncertain_title"))
        ]
    return out
