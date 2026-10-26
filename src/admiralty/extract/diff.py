"""Diff of two Snapshot extracts of the same Campaign and Tracked Empire."""

from __future__ import annotations

from typing import Any

from admiralty.extract.context import rounded


class DiffError(ValueError):
    pass


def diff_extracts(older: dict[str, Any], newer: dict[str, Any]) -> dict[str, Any]:
    a, b = older["header"], newer["header"]
    if a["campaign"] != b["campaign"]:
        raise DiffError(f"different Campaigns: {a['campaign']!r} vs {b['campaign']!r}")
    if a["tracked_empire"]["country_id"] != b["tracked_empire"]["country_id"]:
        raise DiffError("different Tracked Empires")
    if a["date"] > b["date"]:
        older, newer = newer, older
        a, b = b, a

    resources = {}
    for resource in sorted(set(older["resources"]) | set(newer["resources"])):
        before = older["resources"].get(resource, {})
        after = newer["resources"].get(resource, {})
        resources[after.get("label") or before.get("label") or resource] = {
            "stockpile": _change(before.get("stockpile", 0), after.get("stockpile", 0)),
            "net": _change(before.get("net", 0), after.get("net", 0)),
        }

    planets_before = {p["id"]: p for p in older["planets"]}
    planets_after = {p["id"]: p for p in newer["planets"]}
    wars_before = {w["name"] for w in older["military"]["wars"]}
    wars_after = {w["name"] for w in newer["military"]["wars"]}
    traditions_before = set(older["progression"]["traditions"])
    perks_before = set(older["progression"]["ascension_perks"])

    return {
        "campaign": b["campaign"],
        "tracked_empire": b["tracked_empire"]["name"],
        "from": a["date"],
        "to": b["date"],
        "resources": resources,
        "pops": _change(older["pops"]["total"], newer["pops"]["total"]),
        "unemployed": _change(older["pops"]["unemployed"], newer["pops"]["unemployed"]),
        "planets_gained": [
            _planet_ref(p) for pid, p in planets_after.items() if pid not in planets_before
        ],
        "planets_lost": [
            _planet_ref(p) for pid, p in planets_before.items() if pid not in planets_after
        ],
        "naval_capacity": {
            "used": _change(older["naval_capacity"]["used"], newer["naval_capacity"]["used"]),
            "max": _change(older["naval_capacity"]["max"], newer["naval_capacity"]["max"]),
        },
        "military_power": _change(
            older["empire"]["military_power"], newer["empire"]["military_power"]
        ),
        "traditions_adopted": [
            t for t in newer["progression"]["traditions"] if t not in traditions_before
        ],
        "ascension_perks_taken": [
            p for p in newer["progression"]["ascension_perks"] if p not in perks_before
        ],
        "wars_started": sorted(wars_after - wars_before),
        "wars_ended": sorted(wars_before - wars_after),
        "timeline": [e for e in newer["timeline"] if a["date"] < e["date"] <= b["date"]],
    }


def _change(before: float, after: float) -> dict[str, Any]:
    return {"from": before, "to": after, "change": rounded(after - before)}


def _planet_ref(planet: dict[str, Any]) -> dict[str, Any]:
    return {"name": planet["name"], "system": planet["system"], "pops": planet["pops"]}
