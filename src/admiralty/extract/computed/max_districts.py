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
- Blockers (common/deposits, category deposit_cat_blockers*) carry a negative
  planet_max_districts_add and keep the deposit they cover as swap_type in the save. The
  game counts that covered deposit in the per-type maximum already; we report it again
  as behind_blockers, the places that open once the blocker is cleared.
- All districts together stay within the planet's district limit
      district_limit = (planet_size + Σ planet_max_districts_add
                        [+ Σ planet_non_artificial_max_districts_add on natural planets])
                       × (1 + Σ planet_max_districts_mult)
- Types without `is_uncapped` (city, nexus, hive and their specialisations) may each
  reach the district limit plus one per blocker on the planet (fitted, see below).
Confirmed by golden values on 2026-10-24 (planet views in the vulkan and zygerrian saves).
Pinned by golden tests: the Player reads built/max per district type off the planet view.
"""

from __future__ import annotations

from typing import Any

from admiralty.extract.computed.modifiers import Ledger, Triggers, add_definition
from admiralty.extract.context import Context, as_list, block, rounded

# Source prefixes that mark blocker effects in the ledger.
BLOCKER = "Blocker"
UNDER_BLOCKER = "Deposit under blocker"


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
    records = [deposits_table[d] for d in as_list(planet.get("deposits")) if d in deposits_table]
    deposits = [record["type"] for record in records]
    # A blocker keeps the deposit it covers as swap_type; the game already counts that
    # deposit's district capacity in the per-type maximum (golden values, 2026-10-24).
    hidden = [record["swap_type"] for record in records if record.get("swap_type")]
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
        definition = deposit_defs.get(kind)
        category = str(definition.get("category", "")) if isinstance(definition, dict) else ""
        prefix = BLOCKER if "blocker" in category else "Deposit"
        add_definition(
            ledger, triggers, definition, f"{prefix}: {ctx.label(kind)}",
            modifier_keys=planet_keys, triggered_keys=planet_triggered,
        )  # fmt: skip
    for kind in hidden:
        add_definition(
            ledger, triggers, deposit_defs.get(kind), f"{UNDER_BLOCKER}: {ctx.label(kind)}",
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
    hidden_by_pool: dict[str, float] = {}
    behind: dict[str, int] = {}
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
            under = sum(
                c.amount
                for c in ledger.contributions(f"{pool}_max_add")
                if c.certain and c.source.startswith(UNDER_BLOCKER)
            )
            hidden_by_pool[pool] = max(0, under * (1 + mult))
        if kind not in built and pools_seen[pool] == 0:
            continue
        out[kind] = int(pools_seen[pool])
        if hidden_by_pool[pool]:
            behind[kind] = int(hidden_by_pool[pool])
    triggers.local = {}

    mult = 1 + ledger.total("planet_max_districts_mult")
    add = ledger.total("planet_max_districts_add")
    blockers = sum(
        1
        for c in ledger.contributions("planet_max_districts_add")
        if c.certain and c.amount < 0 and c.source.startswith(BLOCKER + ":")
    )
    if not _is_artificial(ctx, planet):
        add += ledger.total("planet_non_artificial_max_districts_add")
    size = planet.get("planet_size", 0)
    limit = (size + add) * mult
    # Urban types (no is_uncapped trigger): the district limit plus one per blocker. Fitted
    # to four planet views (golden values): three blockers of -1 give +3, while Prototype
    # Machinery (-2) on a machine world gives +1, so it is the count, not the penalty.
    urban_max = int(limit + blockers)
    for kind in built:
        definition = definitions.get(kind)
        if isinstance(definition, dict) and "is_uncapped" not in definition:
            out[kind] = urban_max
    out["_district_limit"] = rounded(limit, 1)
    out["_behind_blockers"] = behind
    return out


def _is_artificial(ctx: Context, planet: dict) -> bool:
    """Habitats, ring worlds and other constructed worlds (planet class flag)."""
    definition = ctx.game.category("planet_classes").get(planet.get("planet_class"), {})
    return isinstance(definition, dict) and definition.get("is_artificial_planet") == "yes"
