"""The `retrospective` tool result: frame, series, intervals, Timeline, candidates, findings and
(Consulting only) the Goals' Symptoms at both ends of the frame or (Coaching only) the Predictions
and Player Model changes of the frame.

Everything is assembled from archived extracts by the functions of this package; nothing here is
read from a save. The result is trimmed to the same character budget as `expand_graph`: over it,
the interior dates of the series lose their detail, step by step, and `warnings` says so. The
intervals keep the values of every date, so no figure the answer needs disappears with the trim.
"""

from __future__ import annotations

import json
from typing import Any

from admiralty.debrief.epochs import candidates_for_frame
from admiralty.debrief.findings import build_findings
from admiralty.debrief.frame import Frame, Loaded, years_between
from admiralty.debrief.series import build_series, change
from admiralty.graph.expand import RESULT_BUDGET, catalogue
from admiralty.graph.mechanics import MechanicsGraph


def build_result(
    loaded: Loaded,
    frame: Frame,
    *,
    mode: str,
    god_mode: bool,
    goals: dict[str, Any] | None = None,
    coaching: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
    budget: int = RESULT_BUDGET,
) -> dict[str, Any]:
    """The tool result for `frame`. `goals` is the finished `goals` value (Consulting) or None:
    Coaching Campaigns get no `goals` key at all. `coaching` is `debrief.coaching.coaching_material`
    (Coaching) or None: Consulting Campaigns get no `coaching` key."""
    documents = [loaded.documents[date] for date in frame.dates]
    material = candidates_for_frame(loaded, frame)
    intervals = material["intervals"]
    header = documents[-1]["header"]
    result: dict[str, Any] = {
        "frame": {
            "from": frame.start,
            "to": frame.end,
            "request": frame.request,
            "dates": frame.dates,
            "span_years": years_between(frame.start, frame.end),
            "campaign": header["campaign"],
            "tracked_empire": header["tracked_empire"],
            "mode": mode,
            "knowledge": "god_mode" if god_mode else "fair_play",
            "problems": loaded.problems,
            "timeline_complete": material["timeline"]["complete"],
            "timeline_missing": material["timeline"]["missing"],
        },
        "series": build_series(documents, god_mode),
        "intervals": intervals,
        "timeline": {
            "events": material["timeline"]["events"],
            "before_frame": material["timeline"]["before_frame"],
        },
        "epoch_candidates": material["candidates"],
        "findings": build_findings(intervals),
    }
    if goals is not None:
        result["goals"] = goals
    if coaching is not None:
        result["coaching"] = coaching
    result["warnings"] = [*(warnings or []), *header.get("warnings", [])]
    return _trim(result, budget)


def goal_symptoms(graph: MechanicsGraph, first: dict[str, Any], last: dict[str, Any]) -> dict:
    """Per Goal the Symptom metrics on the first and the last document of the frame, with the
    change between them where both are numbers. A Goal whose metric cannot be resolved on either
    date keeps `null` there, as the catalogue does."""
    ends = {"from": catalogue(graph, first), "to": catalogue(graph, last)}
    out = []
    for before, after in zip(ends["from"], ends["to"], strict=True):
        symptoms = []
        for a, b in zip(before["symptoms"], after["symptoms"], strict=True):
            entry = {"metric": a["metric"], "unit": a["unit"], "from": a["value"], "to": b["value"]}
            if _number(a["value"]) and _number(b["value"]):
                entry = {**entry, **change(a["value"], b["value"])}
            symptoms.append(entry)
        out.append(
            {"id": before["id"], "domain": before["domain"], "title": before["title"],
             "symptoms": symptoms}
        )  # fmt: skip
    return {
        "from": first["header"]["date"],
        "to": last["header"]["date"],
        "version": graph.version,
        "goals": out,
    }


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _size(document: dict[str, Any]) -> int:
    return len(json.dumps(document, ensure_ascii=False))


def _trim(result: dict[str, Any], budget: int) -> dict[str, Any]:
    """Over the budget: the known empires of interior dates go, then those dates' series points.
    The first date, the last date and every date a boundary candidate names stay whole."""
    if _size(result) <= budget:
        return result
    series = result["series"]
    keep = {series[0]["date"], series[-1]["date"]}
    for candidate in result["epoch_candidates"]:
        keep.update({candidate["date"], candidate.get("after"), candidate.get("before")})
    interior = [point for point in series if point["date"] not in keep]
    for point in interior:
        point["known_empires"] = []
    note = (
        f"over {budget} characters: known empires left out of the series on {len(interior)} dates"
    )
    if _size(result) > budget:
        dropped = {point["date"] for point in interior}
        result["series"] = [point for point in series if point["date"] not in dropped]
        note = (
            f"over {budget} characters: {len(dropped)} interior dates left out of the series; "
            "the intervals still hold the values of every date"
        )
    result["warnings"] = [*result["warnings"], note]
    if _size(result) > budget:
        result["warnings"].append(
            f"result is {_size(result)} characters, over the budget of {budget}; ask for a "
            "shorter frame"
        )
    return result
