"""Metrics: named Snapshot values the Mechanics Graph checks, and the comparisons built on them.

`knowledge/<version>/graph/metrics.yaml` registers each metric as a dotted `path` into the
Snapshot extract, a `sum` of paths or a `ratio` of two. `resolve_metric` reads one, `evaluate`
runs an Obstacle's `check` (or a Remedy's `pending_when`) and keeps the numbers it compared, so a
Briefing can state them from a tool result.

A value missing from the extract resolves to None, never raises: the Obstacle is then `unknown`
and the model weighs it. A ratio with a zero or missing denominator is None for the same reason.
"""

from __future__ import annotations

import operator
from dataclasses import dataclass, field
from typing import Any

_OPERATORS = {
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
    "==": operator.eq,
    "!=": operator.ne,
}


def dig(document: dict[str, Any], path: str):
    """The value at a dotted path, None when any step is missing."""
    value: Any = document
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def resolve_metric(spec: dict[str, Any], extract: dict[str, Any]):
    """One registered metric's value in a Snapshot extract; None when the extract lacks it."""
    if "path" in spec:
        return dig(extract, spec["path"])
    if "sum" in spec:
        parts = [dig(extract, path) for path in spec["sum"]]
        return None if None in parts else sum(parts)
    ratio = spec["ratio"]
    top, bottom = dig(extract, ratio["numerator"]), dig(extract, ratio["denominator"])
    # rounded: a ratio is shown to the Player, and 1.0062893081761006 helps nobody
    return None if top is None or not bottom else round(top / bottom, 3)


@dataclass(frozen=True)
class Check:
    """The outcome of one comparison against a Snapshot.

    `present`: the comparison is true (an Obstacle holds). `clear`: it is false. `unknown`: a
    metric has no value in the extract. `judgement`: nothing to compare, the model decides.
    """

    state: str
    metric: str | None = None
    op: str | None = None
    compare_to: float | str | None = None  # a number, or the name of the other metric
    values: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        if self.metric is None:
            return {"state": self.state}
        return {
            "state": self.state,
            "metric": self.metric,
            "op": self.op,
            "compare_to": self.compare_to,
            "values": dict(self.values),
        }


JUDGEMENT = Check("judgement")


def evaluate(
    comparison: dict[str, Any], metrics: dict[str, dict[str, Any]], extract: dict[str, Any]
) -> Check:
    """Run `{metric, op, compare_to}` (or `{judgement_only: true}`) against one extract."""
    if comparison.get("judgement_only"):
        return JUDGEMENT
    name, op, target = comparison["metric"], comparison["op"], comparison["compare_to"]
    values = {name: resolve_metric(metrics[name], extract)}
    if isinstance(target, dict):
        other = target["metric"]
        values[other] = resolve_metric(metrics[other], extract)
        right, compare_to = values[other], other
    else:
        right, compare_to = target, target
    left = values[name]
    if not _is_number(left) or not _is_number(right):
        state = "unknown"
    else:
        state = "present" if _OPERATORS[op](left, right) else "clear"
        if state == "present" and comparison.get("only_clears"):
            state = "judgement"  # the numbers cover only part of the Obstacle
    return Check(state, name, op, compare_to, values)


def _is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)
