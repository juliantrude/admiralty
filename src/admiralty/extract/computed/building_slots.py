"""Free building slots per planet and zone, which the save does not store.

The save stores the zones (`gamestate.zones`: `type`, `buildings`) and links them through the
planet's districts: `colony.districts` → `districts[].zones`, one entry per zone slot of the
district, in the order of the district's `zone_slots`; an empty slot holds the null reference.

Formula:
    capacity of a zone = `max_buildings` of its type, else DEFAULT_MAX_PLANET_BUILDINGS_PER_ZONE (3)
    used             = the buildings in the zone (`zones[].buildings`)
    free             = max(0, capacity − used)
    planet           = sums over the planet's zones
    empty zone slots = zone slots of the planet's districts that hold no zone yet (a zone built
                       there would add its capacity; whether the slot is unlocked is not decided)
The capacity does not depend on the district level: `districts_per_building` is documented but no
zone of 4.5.2 sets it, and zones of one type with levels 1 to 14 hold 3 buildings in the saves.
`zone_building_slots_add = 3` in a zone's `planet_modifier` is a tooltip modifier (a "fake modifier
used for tooltips", scripted_modifiers/00_scripted_modifiers.txt:463); it changes no number.

A zone type whose capacity the rule above does not give is left out of the sums and reported, never
guessed: `max_buildings_planet_class` (the Synaptic Lathe zone: BASE_SYNAPTIC_LATHE_BUILDING_SLOTS
plus `pc_cosmogenesis_world_max_buildings_add` from districts), `districts_per_building` and
`is_capped_by_modifier`.

Sources (Stellaris 4.5.2, common/):
    zones/*.txt, zones/99_HOW_TO_ZONE.txt   `max_buildings`, the three flags above
    inline_scripts/zones/*.txt              zone bodies shared between types (already expanded)
    zone_slots/*.txt, districts/*.txt       the slot a district offers (`zone_slots`) and its unlock
    defines/00_defines.txt                  DEFAULT_MAX_PLANET_BUILDINGS_PER_ZONE = 3
Checked on the saves: every building of `buildings_cache` stands in exactly one zone and no zone
holds more than its capacity (15 saves). Golden values: pending, read by the Player
(`docs/awaiting-julian.md`).
"""

from __future__ import annotations

from typing import Any

from admiralty.extract.computed.naval_capacity import _defines
from admiralty.extract.context import NO_ID, Context, as_list

# Keys of a zone that make its capacity something other than `max_buildings`.
UNSUPPORTED_RULES = (
    "max_buildings_planet_class",
    "districts_per_building",
    "is_capped_by_modifier",
)


def planet_building_slots(
    ctx: Context, planet_id: int, colony: dict[str, Any], detail: bool = False
) -> dict[str, Any]:
    """{"capacity", "used", "free", "empty_zone_slots", "unsupported"} of one planet; with
    `detail` also "zones": one entry per zone."""
    zone_defs = ctx.game.category("zones")
    default = int(_defines(ctx).get("DEFAULT_MAX_PLANET_BUILDINGS_PER_ZONE", 3))
    capacity = used = free = empty = 0
    zones: list[dict[str, Any]] = []
    unsupported: list[str] = []
    for district_id in as_list(colony.get("districts")):
        district = ctx.g["districts"].get(district_id)
        if not isinstance(district, dict):
            continue
        for zone_id in as_list(district.get("zones")):
            if zone_id == NO_ID:
                empty += 1
                continue
            zone = ctx.g["zones"].get(zone_id)
            if not isinstance(zone, dict):
                continue
            kind = zone["type"]
            definition = zone_defs.get(kind)
            if not isinstance(definition, dict):
                ctx.errors.append(f"building slots: zone type {kind!r} not in the game files")
                continue
            rule = next((key for key in UNSUPPORTED_RULES if key in definition), None)
            if rule is not None:
                if kind not in unsupported:
                    unsupported.append(kind)
                    ctx.errors.append(
                        f"building slots: zone type {kind!r} on planet {planet_id} "
                        f"uses {rule}; its slots are not computed"
                    )
                continue
            zone_capacity = int(definition.get("max_buildings", default))
            zone_used = len(as_list(zone.get("buildings")))
            zone_free = max(0, zone_capacity - zone_used)
            capacity += zone_capacity
            used += zone_used
            free += zone_free
            if detail:
                zones.append(
                    {
                        "zone": kind,
                        "label": ctx.label(kind),
                        "capacity": zone_capacity,
                        "used": zone_used,
                        "free": zone_free,
                    }
                )
    out: dict[str, Any] = {
        "capacity": capacity,
        "used": used,
        "free": free,
        "empty_zone_slots": empty,
        "unsupported": unsupported,
    }
    if detail:
        out["zones"] = zones
    return out
