"""Series per archived date, the change between neighbouring dates, and the merged Timeline.

Pure functions over archived extract documents. Every figure the retrospective states comes out
of these, including percent changes and spans in years, so the Unverified Claim check finds its
evidence in the tool result (M7 derives sums, differences and `a / b * 100`, not a growth rate).

A value is one flat name: the table `SCALARS` or `<resource label> stockpile` / `<resource label>
net` with the Display Name label of the extract. Between two archived dates the archive holds
nothing, so an interval reports the two ends and the change, never a curve.
"""

from __future__ import annotations

from typing import Any

from admiralty.debrief.frame import years_between
from admiralty.extract.context import rounded
from admiralty.extract.diff import diff_extracts
from admiralty.graph.metrics import dig

# Series value -> dotted path into the extract. `len:` counts a list.
SCALARS: dict[str, str] = {
    "planets": "len:planets",
    "pops": "pops.total",
    "unemployed": "pops.unemployed",
    "military_power": "empire.military_power",
    "economy_power": "empire.economy_power",
    "tech_power": "empire.tech_power",
    "victory_rank": "empire.victory_rank",
    "naval_capacity_used": "naval_capacity.used",
    "naval_capacity_max": "naval_capacity.max",
    "traditions": "len:progression.traditions",
    "ascension_perks": "len:progression.ascension_perks",
    "wars_running": "len:military.wars",
}
RESOURCE_PARTS = ("stockpile", "net")


def series_values(doc: dict[str, Any]) -> dict[str, float]:
    """The flat numeric values of one extract; a value the extract lacks is left out."""
    values: dict[str, float] = {}
    for name, path in SCALARS.items():
        counted = path.startswith("len:")
        found = dig(doc, path.removeprefix("len:"))
        if counted and isinstance(found, list):
            values[name] = len(found)
        elif not counted and isinstance(found, (int, float)) and not isinstance(found, bool):
            values[name] = found
    for key, resource in (doc.get("resources") or {}).items():
        label = resource.get("label") or key
        for part in RESOURCE_PARTS:
            if isinstance(resource.get(part), (int, float)):
                values[f"{label} {part}"] = resource[part]
    return values


def known_empires(doc: dict[str, Any], god_mode: bool) -> list[dict[str, Any]]:
    """The other empires as the extract knows them; `full` only in God Mode, like `military`."""
    kept = []
    for other in doc.get("known_empires") or []:
        entry = {k: v for k, v in other.items() if k != "full"}
        if god_mode and "full" in other:
            entry["full"] = other["full"]
        kept.append(entry)
    return kept


def build_series(documents: list[dict[str, Any]], god_mode: bool) -> list[dict[str, Any]]:
    """One point per archived date: its values and the known empires."""
    return [
        {
            "date": doc["header"]["date"],
            "values": series_values(doc),
            "known_empires": known_empires(doc, god_mode),
        }
        for doc in documents
    ]


def change(before: float, after: float) -> dict[str, Any]:
    """`from`, `to`, `change` and `change_pct` (one decimal; absent when `from` is 0)."""
    out: dict[str, Any] = {"from": before, "to": after, "change": rounded(after - before)}
    if before:
        out["change_pct"] = rounded((after - before) / abs(before) * 100, 1)
    return out


def build_intervals(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The change between every two neighbouring documents (oldest first)."""
    intervals = []
    for older, newer in zip(documents, documents[1:], strict=False):
        diff = diff_extracts(older, newer)
        before, after = series_values(older), series_values(newer)
        intervals.append(
            {
                "from": diff["from"],
                "to": diff["to"],
                "years": years_between(diff["from"], diff["to"]),
                "values": {
                    name: change(before[name], after[name]) for name in after if name in before
                },
                "planets_gained": [p["name"] for p in diff["planets_gained"]],
                "planets_lost": [p["name"] for p in diff["planets_lost"]],
                "traditions_adopted": diff["traditions_adopted"],
                "ascension_perks_taken": diff["ascension_perks_taken"],
                "wars_started": diff["wars_started"],
                "wars_ended": diff["wars_ended"],
            }
        )
    return intervals


def merge_timeline(documents: list[dict[str, Any]]) -> dict[str, Any]:
    """Every Timeline event any extract holds, once, oldest first.

    An extract keeps only its last events, so the newest one lacks the oldest; the older ones still
    hold them. Of two readings of one event the one with more names wins. `missing` counts the events the newest extract says exist (`timeline_events_total`)
    that no extract holds any more, and `complete` is true when none is missing.
    """
    events: list[dict[str, Any]] = []
    for doc in documents:
        for event in doc.get("timeline") or []:
            twin = next((i for i, kept in enumerate(events) if _same_event(kept, event)), None)
            if twin is None:
                events.append(event)
            elif _unresolved(events[twin]) > _unresolved(event):
                events[twin] = event
    events.sort(key=lambda e: (e["date"], e["event"], tuple(e.get("involves") or ())))
    total = documents[-1].get("timeline_events_total") if documents else None
    missing = max(0, total - len(events)) if isinstance(total, int) else 0
    return {"events": events, "complete": missing == 0, "missing": missing}


def _unresolved(event: dict[str, Any]) -> int:
    """How many `involves` entries are a bare id: the extract could not name that planet any more."""
    return sum(1 for item in event.get("involves") or () if str(item).isdigit())


def _same_event(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """Same date, event and `involves`, where a bare id matches the name it later lost.

    An extract names a planet only while the Tracked Empire owns it, so the same event can read
    `Menkar Prime` in an older extract and `6` in a newer one (probed on the reference Campaign).
    """
    first, second = a.get("involves") or [], b.get("involves") or []
    if (a["date"], a["event"], len(first)) != (b["date"], b["event"], len(second)):
        return False
    return all(
        x == y or str(x).isdigit() or str(y).isdigit() for x, y in zip(first, second, strict=True)
    )


def timeline_in_frame(events: list[dict[str, Any]], start: str, end: str) -> dict[str, Any]:
    """The events from `start` to `end` inclusive, and how many lie before the frame."""
    return {
        "events": [e for e in events if start <= e["date"] <= end],
        "before_frame": sum(1 for e in events if e["date"] < start),
    }
