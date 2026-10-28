"""Capital tier of the empire's planets, which the save does not store (it lists only the buildings).

Formula:
    tier of a planet = the largest `capital_tier` among its buildings that are capital buildings
                       (`capital = yes`); 0 for a planet without one
    best             = the largest tier over the planets the empire owns
    capital planet   = the tier of the planet of the colony `country.capital` points at
A building asks for a tier through the scripted trigger in its `allow`; the number is read from
the trigger's own `else` branch, not typed in.

Sources (Stellaris 4.5.2, common/):
    buildings/00_capital_buildings.txt   `capital = yes` and `capital_tier` per capital building
                                         (capital 2, major capital 3, system capital 4; the machine
                                         and hive lines the same; imperial capitals 5); the
                                         wilderness and lathe capitals in 21_wilderness_buildings.txt
                                         and 20_machine_age_buildings.txt use the same key
    scripted_triggers/01_scripted_triggers_buildings.txt
        has_upgraded_capital        capital_tier >= 2
        has_major_upgraded_capital  capital_tier >= 3
        has_fully_upgraded_capital  capital_tier >= 4
The triggers run in planet scope: a building is allowed on the planet whose own capital building has
the tier. The empire-wide `best` is therefore the lenient reading, the tier some planet reaches;
an Obstacle that reads "the capital tier is missing" holds only when no planet reaches it.
"""

from __future__ import annotations

from typing import Any

from admiralty.extract.context import Context, as_list
from admiralty.extract.empire import owned_colonies

TIER_TRIGGERS = ("has_upgraded_capital", "has_major_upgraded_capital", "has_fully_upgraded_capital")


def capital_tiers(ctx: Context, country: dict[str, Any]) -> dict[str, Any]:
    """{"best", "capital_planet", "capital_building"}: the tiers and the capital planet's building."""
    definitions = ctx.game.category("buildings")
    buildings = ctx.table("buildings")
    capital_colony = ctx.colonies.get(country.get("capital"))  # `capital` is a colony id
    best, capital_tier, capital_building = 0, 0, None
    for _, _, colony in owned_colonies(ctx, country):
        tier, building = 0, None
        for building_id in as_list(colony.get("buildings_cache")):
            kind = (buildings.get(building_id) or {}).get("type")
            definition = definitions.get(kind) or {}
            if definition.get("capital") == "yes" and definition.get("capital_tier", 0) > tier:
                tier, building = definition["capital_tier"], kind
        best = max(best, tier)
        if colony is capital_colony:
            capital_tier, capital_building = tier, building
    return {
        "best": best,
        "capital_planet": capital_tier,
        "capital_building": capital_building,
    }


def required_tier(ctx: Context, building: dict[str, Any]) -> int:
    """The capital tier a building's `allow` asks for; 0 when it asks for none."""
    allow = building.get("allow")
    if not isinstance(allow, dict):
        return 0
    triggers = ctx.game.category("scripted_triggers")
    tiers = [
        int(triggers[name]["else"]["custom_tooltip"]["capital_tier>="])
        for name in TIER_TRIGGERS
        if allow.get(name) == "yes"
    ]
    return max(tiers, default=0)
