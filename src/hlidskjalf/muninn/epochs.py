"""Where an epoch border can lawfully lie, and the check of the epochs the model proposes.

The code cannot name an epoch (Timeline titles are localised, the extract does not classify them), but
it knows where a border has evidence: a Timeline event (exact), an interval between two archived
dates in which a war began or ended or the growth of the Campaign changed its pace (between), or an
end of the frame. `check_epochs` refuses a border without such evidence. Pure functions.

An exact candidate is one date; a `between` candidate says the border lies after one archived date
and before another, because the archive holds nothing in between.
"""

from __future__ import annotations

import re
from typing import Any

from hlidskjalf.muninn.frame import Frame, FrameError, Loaded, day_number, years_between
from hlidskjalf.muninn.series import build_intervals, merge_timeline, timeline_in_frame

# The regime change rule: the growth per year of one of these series values in an interval differs
# from the interval before by more than REGIME_FACTOR (both nonzero), or its sign flips.
REGIME_SERIES = ("planets", "pops", "military_power", "economy_power")
REGIME_FACTOR = 2

# An epoch longer than this with a candidate strictly inside it draws a warning.
LONG_EPOCH_YEARS = 15

EXACT = "exact"
BETWEEN = "between"

FRAME_START = "frame start"
FRAME_END = "frame end"


def build_candidates(
    events: list[dict[str, Any]], intervals: list[dict[str, Any]], start: str, end: str
) -> list[dict[str, Any]]:
    """Boundary candidates for a frame, in date order; none is merged with a neighbour.

    `events` are the Timeline events of the frame, `intervals` the output of `build_intervals`.
    Candidates of the same date and precision (or of the same two archived dates) share one entry.
    """
    found: dict[tuple, dict[str, Any]] = {}

    def add(precision: str, after: str, before: str, reason: str) -> None:
        key = (precision, after, before)
        if key not in found:
            entry: dict[str, Any] = {"date": after, "precision": precision, "reasons": []}
            if precision == BETWEEN:
                entry.update(after=after, before=before)
            found[key] = entry
        if reason not in found[key]["reasons"]:
            found[key]["reasons"].append(reason)

    add(EXACT, start, start, FRAME_START)
    add(EXACT, end, end, FRAME_END)
    for event in events:
        add(EXACT, event["date"], event["date"], event["event"])
    for interval in intervals:
        for name in interval["wars_started"]:
            add(BETWEEN, interval["from"], interval["to"], f"war started: {name}")
        for name in interval["wars_ended"]:
            add(BETWEEN, interval["from"], interval["to"], f"war ended: {name}")
    for before, after in zip(intervals, intervals[1:], strict=False):
        for name in REGIME_SERIES:
            reason = _regime_change(name, before, after)
            if reason:
                add(BETWEEN, before["from"], after["to"], reason)
    return sorted(found.values(), key=lambda c: (c["date"], c["precision"], c.get("before", "")))


def _growth_per_year(name: str, interval: dict[str, Any]) -> float | None:
    value = interval["values"].get(name)
    if value is None or not interval["years"]:
        return None
    return round(value["change"] / interval["years"], 2)


def _regime_change(name: str, before: dict[str, Any], after: dict[str, Any]) -> str | None:
    old, new = _growth_per_year(name, before), _growth_per_year(name, after)
    if not old or not new:
        return None
    flipped = (old < 0) != (new < 0)
    if flipped or max(abs(new) / abs(old), abs(old) / abs(new)) > REGIME_FACTOR:
        return f"{name} {old:g}/yr -> {new:g}/yr"
    return None


def candidates_for_frame(loaded: Loaded, frame: Frame) -> dict[str, Any]:
    """The Timeline (merged over every archived extract, cut to the frame), the intervals and the
    candidates of a frame."""
    documents = [loaded.documents[date] for date in frame.dates]
    merged = merge_timeline(list(loaded.documents.values()))
    timeline = timeline_in_frame(merged["events"], frame.start, frame.end)
    intervals = build_intervals(documents)
    return {
        "timeline": {**timeline, "complete": merged["complete"], "missing": merged["missing"]},
        "intervals": intervals,
        "candidates": build_candidates(timeline["events"], intervals, frame.start, frame.end),
    }


def check_epochs(
    epochs: Any, candidates: list[dict[str, Any]], start: str, end: str
) -> dict[str, list[str]]:
    """Errors and warnings for the epochs a model proposes over the frame `start` to `end`.

    An epoch is `{title, from, to, anchor, why}`. The epochs must be contiguous and cover the frame;
    every `from` after the first needs an `anchor` naming a candidate: `{"date", "event"}` for a
    Timeline event, `{"after", "before"}` for the two archived dates of a `between` border (the
    epoch's `from` then lies from `after` to `before`).
    """
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(epochs, list) or not epochs:
        return {
            "errors": ["epochs must be a non-empty list of {title, from, to, anchor, why}"],
            "warnings": [],
        }
    valid = [e for i, e in enumerate(epochs) if _check_shape(i, e, errors, warnings)]
    if len(valid) != len(epochs):
        return {"errors": errors, "warnings": warnings}

    if epochs[0]["from"] != start:
        errors.append(f"the first epoch starts {epochs[0]['from']}, the frame starts {start}")
    if epochs[-1]["to"] != end:
        errors.append(f"the last epoch ends {epochs[-1]['to']}, the frame ends {end}")
    for number, epoch in enumerate(epochs, 1):
        if day_number(epoch["from"]) >= day_number(epoch["to"]):
            errors.append(
                f"{_label(number, epoch)}: from {epoch['from']} is not before to {epoch['to']}"
            )
    for number, (earlier, later) in enumerate(zip(epochs, epochs[1:], strict=False), 1):
        if later["from"] > earlier["to"]:
            errors.append(
                f"gap between epoch {number} (ends {earlier['to']}) and epoch {number + 1} "
                f"(starts {later['from']})"
            )
        elif later["from"] < earlier["to"]:
            errors.append(
                f"epochs {number} and {number + 1} overlap: {earlier['to']} is after {later['from']}"
            )
    for number, epoch in enumerate(epochs[1:], 2):
        _check_anchor(_label(number, epoch), epoch, candidates, errors)
    for number, epoch in enumerate(epochs, 1):
        _warn_long_epoch(_label(number, epoch), epoch, candidates, warnings)
    return {"errors": errors, "warnings": warnings}


def _label(number: int, epoch: dict[str, Any]) -> str:
    return f"epoch {number} ({epoch['title']!r})"


def _check_shape(index: int, epoch: Any, errors: list[str], warnings: list[str]) -> bool:
    where = f"epoch {index + 1}"
    if not isinstance(epoch, dict):
        errors.append(f"{where}: must be an object with title, from, to, anchor, why")
        return False
    ok = True
    for key in ("title", "why"):
        if not isinstance(epoch.get(key), str) or not epoch[key].strip():
            errors.append(f"{where}: {key} is missing or empty")
            ok = False
    for key in ("from", "to"):
        try:
            day_number(epoch.get(key))
        except FrameError:
            errors.append(
                f"{where}: {key} must be an in-game date (YYYY.MM.DD), got {epoch.get(key)!r}"
            )
            ok = False
    if ok and re.search(r"\d", epoch["title"]):
        warnings.append(
            f"{where} ({epoch['title']!r}): digits in a title; a figure belongs in a sentence "
            "the claim check sees"
        )
    return ok


def _check_anchor(
    label: str, epoch: dict[str, Any], candidates: list[dict], errors: list[str]
) -> None:
    anchor, border = epoch.get("anchor"), epoch["from"]
    nothing = f"{label}: no Timeline event or archived interval at {border}"
    if not isinstance(anchor, dict):
        errors.append(
            f"{label}: the border {border} has no anchor (a Timeline event or two archived dates)"
        )
        return
    if "event" in anchor or "date" in anchor:
        if anchor.get("date") != border:
            errors.append(
                f"{label}: the anchor date {anchor.get('date')!r} is not the border {border}"
            )
            return
        here = [c for c in candidates if c["precision"] == EXACT and c["date"] == border]
        if not any(anchor.get("event") in c["reasons"] for c in here):
            known = sorted({r for c in here for r in c["reasons"]})
            errors.append(
                nothing
                if not known
                else f"{nothing} named {anchor.get('event')!r}; it holds: {known}"
            )
        return
    after, before = anchor.get("after"), anchor.get("before")
    held = [
        c
        for c in candidates
        if c["precision"] == BETWEEN and (c["after"], c["before"]) == (after, before)
    ]
    if not held:
        errors.append(nothing)
    elif not after <= border <= before:
        errors.append(f"{label}: the border {border} lies outside the interval {after} to {before}")


def _warn_long_epoch(
    label: str, epoch: dict[str, Any], candidates: list[dict], warnings: list[str]
) -> None:
    if years_between(epoch["from"], epoch["to"]) <= LONG_EPOCH_YEARS:
        return
    inside = []
    for c in candidates:
        first, last = c.get("after", c["date"]), c.get("before", c["date"])
        if epoch["from"] < first and last < epoch["to"]:
            inside.extend(
                f"{first} {reason}" if first == last else f"{first} to {last} {reason}"
                for reason in c["reasons"]
            )
    if inside:
        shown = "; ".join(inside[:3]) + (f"; and {len(inside) - 3} more" if len(inside) > 3 else "")
        warnings.append(
            f"{shown} lie inside {label}, which spans {years_between(epoch['from'], epoch['to'])} years"
        )
