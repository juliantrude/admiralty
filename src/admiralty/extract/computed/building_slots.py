"""Free building slots per planet and zone, which the save does not store.

The save stores the zones (`gamestate.zones`: `type`, `buildings`) and links them through the
planet's districts: `colony.districts` → `districts[].zones`, one entry per zone slot of the
district, in the order of the district's `zone_slots`; an empty slot holds the null reference.

Formula:
    capacity of a zone = `max_buildings` of its type, else DEFAULT_MAX_PLANET_BUILDINGS_PER_ZONE (3)
    used             = the buildings in the zone (`zones[].buildings`), as the planet view counts
    queued           = new buildings for the zone in the construction queue
                       (`construction.item_mgr.items`, `buildable_planet_building`); a replacement
                       or an upgrade keeps its slot and is no such item
    free             = max(0, capacity − used − queued)
    planet           = sums over the planet's zones
    empty zone slots = zone slots of the planet's districts that hold no zone yet (a zone built
                       there would add its capacity; whether the slot is unlocked is not decided)
The capacity does not depend on the district level: `districts_per_building` is documented but no
zone of 4.5.2 sets it, and zones of one type with levels 1 to 14 hold 3 buildings in the saves.
`zone_building_slots_add = 3` in a zone's `planet_modifier` is a tooltip modifier (a "fake modifier
used for tooltips", scripted_modifiers/00_scripted_modifiers.txt:463); it changes no number.

Families: the slots a Remedy can use are those of zones that admit one of its buildings.
    zone admits a building = (`include` has `all` or the building, or one of the building's
                              `building_sets` is in `included_building_sets`)
                             and the building is not in `exclude` and none of its `building_sets`
                             is in `excluded_building_sets` (zones/99_HOW_TO_ZONE.txt)
    free slots of a family on a planet = free slots of its zones that admit a building of the family
                             that the empire can build at all (computed/unlocks.py `is_buildable`)
Per-planet limits (`planet_limit`) and the `allow` of a building are not read: a family counts the
room, not whether the building is allowed on that very planet. A family with no buildable
building (e.g. amenity buildings for machine empires) has no value, so its Obstacle is unknown
rather than present.

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
holds more than its capacity (15 saves). Golden values: three planets of vulkan 2298.03.11, read by
the Player (`tests/golden_values.py`).
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from admiralty.extract.computed.modifiers import Triggers
from admiralty.extract.computed.naval_capacity import _defines
from admiralty.extract.computed.unlocks import is_buildable
from admiralty.extract.context import NO_ID, Context, as_list, block

# Keys of a zone that make its capacity something other than `max_buildings`.
UNSUPPORTED_RULES = (
    "max_buildings_planet_class",
    "districts_per_building",
    "is_capped_by_modifier",
)

# The buildings a Remedy of each Obstacle builds (the facts of the Remedies in the Mechanics Graph;
# files common/buildings/03_resource_buildings.txt, 04_manufacturing_buildings.txt,
# 05_research_buildings.txt, 07_amenity_buildings.txt, 08_unity_buildings.txt,
# 01_pop_assembly_buildings.txt, 02_government_buildings.txt).
SLOT_FAMILIES: dict[str, tuple[str, ...]] = {
    "foundry": ("building_foundry_1", "building_foundry_2", "building_foundry_3"),
    "research": (
        "building_research_lab_1",
        "building_physics_lab_1",
        "building_biolab_1",
        "building_engineering_facility_1",
        "building_nanolab_1",
    ),
    "unity": (
        "building_heritage_site",
        "building_hypercomms_forum",
        "building_simulation_1",
        "building_sensorium_1",
        "building_galactic_memorial_1",
    ),
    "order": ("building_order_keep", "building_psi_corps", "building_chamber_of_silence"),
    "amenities": (
        "building_luxury_residence",
        "building_paradise_dome",
        "building_communal_housing",
        "building_communal_housing_large",
    ),
    "housing": (
        "building_luxury_residence",
        "building_paradise_dome",
        "building_communal_housing",
        "building_communal_housing_large",
        "building_drone_storage",
        "building_drone_megastorage",
        "building_hive_warren",
        "building_expanded_warren",
    ),
    "growth": ("building_clone_vats", "building_genomic_facility", "building_spawning_pool"),
}


def _names(value: Any) -> set[str]:
    """The names of a list block; a key written twice (the arcology zones list two blocks of
    `included_building_sets`) gives both blocks, and both count."""
    return {
        name
        for item in as_list(value)
        for name in (_names(item) if isinstance(item, list) else {item})
    }


def zone_admits(zone: dict[str, Any], key: str, building: dict[str, Any]) -> bool:
    """Whether a zone definition lets a building of this key and `building_sets` stand in it."""
    sets = _names(building.get("building_sets"))
    included = _names(zone.get("include"))
    listed = (
        "all" in included
        or key in included
        or bool(sets & _names(zone.get("included_building_sets")))
    )
    barred = key in _names(zone.get("exclude")) or bool(
        sets & _names(zone.get("excluded_building_sets"))
    )
    return listed and not barred


def family_zones(ctx: Context, triggers: Triggers) -> dict[str, frozenset[str] | None]:
    """Per family, the zone types that admit a building of it the empire can build; None when the
    empire can build none of the family."""
    buildings = ctx.game.category("buildings")
    zones = ctx.game.category("zones")
    out: dict[str, frozenset[str] | None] = {}
    for family, keys in SLOT_FAMILIES.items():
        usable = [
            key for key in keys if key in buildings and is_buildable(buildings, key, triggers)
        ]
        out[family] = (
            frozenset(
                kind
                for kind, zone in zones.items()
                if isinstance(zone, dict)
                and any(zone_admits(zone, key, buildings[key]) for key in usable)
            )
            if usable
            else None
        )
    return out


def queued_buildings(ctx: Context) -> Counter[Any]:
    """Zone id → new buildings queued for that zone."""
    items = block(block(ctx.g.get("construction")).get("item_mgr")).get("items")
    orders = (
        item.get("buildable_planet_building")
        for item in block(items).values()
        if isinstance(item, dict)
    )
    return Counter(order.get("zone") for order in orders if isinstance(order, dict))


def planet_building_slots(
    ctx: Context,
    planet_id: int,
    colony: dict[str, Any],
    detail: bool = False,
    families: dict[str, frozenset[str] | None] | None = None,
) -> dict[str, Any]:
    """{"capacity", "used", "queued", "free", "empty_zone_slots", "unsupported"} of one planet; with
    `families` (family_zones) also "free_by_family"; with `detail` also "zones": one entry per
    zone."""
    zone_defs = ctx.game.category("zones")
    default = int(_defines(ctx).get("DEFAULT_MAX_PLANET_BUILDINGS_PER_ZONE", 3))
    queue = queued_buildings(ctx)
    capacity = used = queued = free = empty = 0
    by_family: dict[str, int | None] = {
        name: (None if kinds is None else 0) for name, kinds in (families or {}).items()
    }
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
            zone_queued = queue[zone_id]
            zone_free = max(0, zone_capacity - zone_used - zone_queued)
            capacity += zone_capacity
            used += zone_used
            queued += zone_queued
            free += zone_free
            for name, kinds in (families or {}).items():
                if kinds is not None and kind in kinds:
                    by_family[name] = (by_family[name] or 0) + zone_free
            if detail:
                zones.append(
                    {
                        "zone": kind,
                        "label": ctx.label(kind),
                        "capacity": zone_capacity,
                        "used": zone_used,
                        "queued": zone_queued,
                        "free": zone_free,
                    }
                )
    out: dict[str, Any] = {
        "capacity": capacity,
        "used": used,
        "queued": queued,
        "free": free,
        "empty_zone_slots": empty,
        "unsupported": unsupported,
    }
    if families is not None:
        out["free_by_family"] = by_family
    if detail:
        out["zones"] = zones
    return out
