"""Finding candidates per interval: what moved most, for the model to call good or bad.

Not verdicts. The code lists what the numbers show between two archived dates, ordered by size, and
the model decides which finding is good or bad and why. No Benchmark is used (all are still null):
a finding compares the Campaign with its own earlier state only.

Order inside an interval: the discrete findings first (a stockpile at zero, a resource net turned
negative, a rank change, planets lost, a war that cost military power, unemployed pops outgrowing
pops), then the percent movers (`gain` / `loss`), each group by `abs(change_pct)` and then
`abs(change)`. At most `MAX_PER_INTERVAL` per interval.
"""

from __future__ import annotations

from typing import Any

MAX_PER_INTERVAL = 12

# Series values that are not a gain or a loss in themselves: the rank has its own finding (lower is
# better), wars running is a state.
NOT_MOVERS = ("victory_rank", "wars_running")


def build_findings(intervals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Finding candidates of every interval, oldest interval first."""
    findings: list[dict[str, Any]] = []
    for index, interval in enumerate(intervals):
        last = index == len(intervals) - 1
        found = _discrete(interval, last) + _movers(interval)
        findings.extend(found[:MAX_PER_INTERVAL])
    return findings


def _finding(kind: str, interval: dict, subject: str, values: dict, **extra: Any) -> dict[str, Any]:
    out = {
        "kind": kind,
        "interval": {"from": interval["from"], "to": interval["to"]},
        "subject": subject,
        **values,
    }
    out.update(extra)
    return out


def _size(finding: dict[str, Any]) -> tuple[float, float]:
    return (-abs(finding.get("change_pct", 0)), -abs(finding["change"]))


def _discrete(interval: dict[str, Any], last: bool) -> list[dict[str, Any]]:
    values = interval["values"]
    found: list[dict[str, Any]] = []
    for name, value in values.items():
        label, _, part = name.rpartition(" ")
        if part == "stockpile" and value["to"] == 0 and _at_zero(values, label, value, last):
            found.append(_finding("stockpile_zero", interval, name, value))
        if part == "net" and value["from"] >= 0 > value["to"]:
            found.append(_finding("net_negative", interval, name, value))
    rank = values.get("victory_rank")
    if rank and rank["change"]:
        found.append(_finding("rank_change", interval, "victory_rank", rank))
    planets = values.get("planets")
    if planets and interval["planets_lost"]:
        found.append(
            _finding("planets_lost", interval, "planets", planets, names=interval["planets_lost"])
        )
    power, wars = values.get("military_power"), values.get("wars_running")
    if power and power["change"] < 0 and wars and (wars["from"] or wars["to"]):
        found.append(
            _finding(
                "war_cost",
                interval,
                "military_power",
                power,
                wars_started=interval["wars_started"],
                wars_ended=interval["wars_ended"],
            )
        )
    unemployed, pops = values.get("unemployed"), values.get("pops")
    if unemployed and pops and unemployed["change"] > 0 and _outgrew(unemployed, pops):
        extra = {"pops_change_pct": pops["change_pct"]} if "change_pct" in pops else {}
        found.append(
            _finding("unemployed_outgrew_pops", interval, "unemployed", unemployed, **extra)
        )
    return sorted(found, key=_size)


def _at_zero(values: dict, label: str, stockpile: dict, last: bool) -> bool:
    """A stockpile that reached zero, or in the frame's last interval sits at zero with a negative net."""
    if stockpile["from"] > 0:
        return True
    net = values.get(f"{label} net")
    return last and net is not None and net["to"] < 0


def _outgrew(unemployed: dict[str, Any], pops: dict[str, Any]) -> bool:
    if "change_pct" not in unemployed:  # grew from zero: faster than anything
        return True
    return unemployed["change_pct"] > pops.get("change_pct", 0)


def _movers(interval: dict[str, Any]) -> list[dict[str, Any]]:
    found = []
    for name, value in interval["values"].items():
        if name in NOT_MOVERS or "change_pct" not in value or not value["change"]:
            continue
        found.append(_finding("gain" if value["change"] > 0 else "loss", interval, name, value))
    return sorted(found, key=_size)
