"""Maximum districts per type on a planet, which the save does not store.

Rules, from common/districts/*.txt and its 00_DOCUMENTATION.txt:
- A district type with an `is_uncapped` trigger is capped unless that trigger holds.
  Its maximum comes from the modifier pool named by `shared_capacity_modifier`
  (default: the type itself):
      max = Σ district_<pool>_max_add × (1 + Σ district_<pool>_max_mult)
  Types sharing a pool (generator, geothermal, photosynthesis fields) share the maximum:
  each one built lowers what is left for the others.
- district_<pool>_max_add comes mostly from deposits (common/deposits, planet_modifier),
  plus resource buildings (common/buildings), planet modifiers (common/static_modifiers)
  and country-wide modifiers that apply to all planets.
- Types without `is_uncapped` (city, nexus, hive and their specialisations) have no
  per-type maximum in the files. HYPOTHESIS, pinned by golden tests: they are limited by
  the planet's district limit,
      district_limit = (planet_size + Σ planet_max_districts_add) × (1 + Σ planet_max_districts_mult)
  where blockers (common/deposits, category deposit_cat_blockers*) carry the negative
  planet_max_districts_add. We report district_limit and leave urban maxima open.
Pinned by golden tests: the Player reads built/max per district type off the planet view.
"""

from __future__ import annotations

from typing import Any

from hlidskjalf.extract.computed.modifiers import Ledger, Triggers, add_definition
from hlidskjalf.extract.context import Context, as_list, block, rounded


def planet_ledger(
    ctx: Context, triggers: Triggers, country_ledger: Ledger, planet: dict, colony: dict
) -> Ledger:
    """Planet-scope modifiers: the empire's country-wide ones plus the planet's own."""
    ledger = Ledger({key: list(values) for key, values in country_ledger.entries.items()})
    districts = {
        ctx.g["districts"][d]["type"]
        for d in as_list(colony.get("districts"))
        if isinstance(ctx.g["districts"].get(d), dict)
    }
    buildings_table = ctx.table("buildings")
    buildings = [
        buildings_table[b]["type"]
        for b in as_list(colony.get("buildings_cache"))
        if b in buildings_table
    ]
    deposits_table = ctx.table("deposit")
    deposits = [
        deposits_table[d]["type"] for d in as_list(planet.get("deposits")) if d in deposits_table
    ]
    triggers.local = {
        "planet_class": planet.get("planet_class"),
        "districts": districts,
        "buildings": set(buildings),
        "deposits": set(deposits),
    }
    planet_keys = ("planet_modifier",)
    planet_triggered = ("triggered_planet_modifier",)
    deposit_defs = ctx.game.category("deposits")
    for kind in deposits:
        add_definition(
            ledger, triggers, deposit_defs.get(kind), f"Deposit: {ctx.label(kind)}",
            modifier_keys=planet_keys, triggered_keys=planet_triggered,
        )  # fmt: skip
    building_defs = ctx.game.category("buildings")
    for kind in buildings:
        add_definition(
            ledger, triggers, building_defs.get(kind), f"Building: {ctx.label(kind)}",
            modifier_keys=planet_keys, triggered_keys=planet_triggered,
        )  # fmt: skip
    static = ctx.game.category("static_modifiers")
    for item in as_list(block(planet.get("timed_modifier")).get("items")):
        name = item.get("modifier")
        if name in static:
            ledger.add_block(static[name], f"Planet modifier: {ctx.label(name)}")
    for name in as_list(planet.get("planet_modifier")):
        if isinstance(name, str) and name in static:
            ledger.add_block(static[name], f"Planet modifier: {ctx.label(name)}")
    designation = colony.get("final_designation") or colony.get("designation")
    colony_types = ctx.game.category("colony_types")
    if designation in colony_types:
        add_definition(
            ledger, triggers, colony_types[designation], f"Designation: {ctx.label(designation)}",
            modifier_keys=planet_keys, triggered_keys=planet_triggered,
        )  # fmt: skip
    triggers.local = {}
    return ledger


def max_districts(
    ctx: Context, triggers: Triggers, ledger: Ledger, planet: dict, colony: dict
) -> dict[str, Any]:
    """{district type: max} for capped types present on or possible for this planet, plus
    the planet's district limit under the urban hypothesis."""
    definitions = ctx.game.category("districts")
    built: dict[str, int] = {}
    for district_id in as_list(colony.get("districts")):
        district = ctx.g["districts"].get(district_id)
        if isinstance(district, dict):
            built[district["type"]] = built.get(district["type"], 0) + district.get("level", 0)

    triggers.local = {"planet_class": planet.get("planet_class"), "districts": set(built)}
    out: dict[str, Any] = {}
    pools_seen: dict[str, float] = {}
    candidates = set(built) | {"district_generator", "district_mining", "district_farming"}
    for kind in sorted(candidates):
        definition = definitions.get(kind)
        if not isinstance(definition, dict) or "is_uncapped" not in definition:
            continue
        uncapped = triggers.evaluate(definition["is_uncapped"])
        if uncapped is True:
            out[kind] = "uncapped"
            continue
        pool = definition.get("shared_capacity_modifier") or kind
        if pool not in pools_seen:
            add = ledger.total(f"{pool}_max_add")
            mult = ledger.total(f"{pool}_max_mult")
            pools_seen[pool] = max(0, add * (1 + mult))
        if kind not in built and pools_seen[pool] == 0:
            continue
        out[kind] = int(pools_seen[pool])
    triggers.local = {}
    add = ledger.total("planet_max_districts_add")
    if not _is_artificial(ctx, planet):
        add += ledger.total("planet_non_artificial_max_districts_add")
    limit = (planet.get("planet_size", 0) + add) * (1 + ledger.total("planet_max_districts_mult"))
    out["_district_limit"] = rounded(limit, 1)
    return out


def _is_artificial(ctx: Context, planet: dict) -> bool:
    """Habitats, ring worlds and other constructed worlds (planet class flag)."""
    definition = ctx.game.category("planet_classes").get(planet.get("planet_class"), {})
    return isinstance(definition, dict) and definition.get("is_artificial_planet") == "yes"
