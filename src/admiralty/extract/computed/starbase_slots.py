"""Free module and building slots of the empire's starbases, which the save does not store.

The save lists per starbase its `level`, its `modules` and `buildings` ({ slot index = id }) and
nothing about how many slots the level offers. The construction queue holds the modules and
buildings still being built, each with the slot it has reserved.

Formula (per starbase):
    slots    = number of entries in the level's `module_slots` / `building_slots`
    used     = slot indices in the starbase's `modules` / `buildings`
    queued   = slot indices reserved by a `buildable_starbase_module` / `buildable_starbase_building`
               item in the construction queue (`construction.item_mgr.items`)
    free     = slots − |used ∪ queued|
    empire   = sums over the starbases of the country (owner = owner of the station ship's fleet,
               as in computed/modifiers.py)
A starbase level without `module_slots` / `building_slots` (outposts) has none. Mobile levels
(waystations, arkships) fit their own modules only and are left out of the sums, so a free slot
there never clears the Obstacle; the same goes for a level the files do not define. Both are
reported in `unsupported`, and the Mechanics Graph reads a sum of 0 next to an unsupported level
as unknown rather than present (`free` is then None).
Whether something is left to build in a free slot is not decided: a free slot counts as free.

Sources (Stellaris 4.5.2, common/):
    starbase_levels/*.txt    `module_slots`, `building_slots` (00_documentation.txt)
    starbase_modules/*.txt, starbase_buildings/*.txt   what fills the slots
Checked on the saves: every used slot index lies below the level's slot count (15 saves).
Golden values: three starbases of vulkan 2298.03.11, read by the Player (`tests/golden_values.py`).
"""

from __future__ import annotations

from typing import Any

from admiralty.extract.context import Context, as_list, block, slots

# Mobile starbases fit their own modules (starbase_modules/00_arkship_*, 00_waystation_modules.txt).
MOBILE_LEVEL_MARKERS = ("waystation", "arkship")

KINDS = (
    ("modules", "module_slots", "buildable_starbase_module"),
    ("buildings", "building_slots", "buildable_starbase_building"),
)


def starbase_slots(ctx: Context, country_id: int, detail: bool = False) -> dict[str, Any]:
    levels = ctx.game.category("starbase_levels")
    queued = _queued_slots(ctx)
    ships = ctx.table("ships")
    totals = {key: {"slots": 0, "used": 0, "queued": 0, "free": 0} for key, _, _ in KINDS}
    unsupported: set[str] = set()
    listing = []
    counted = with_free = 0
    for starbase_id, starbase in block(block(ctx.g.get("starbase_mgr")).get("starbases")).items():
        if not isinstance(starbase, dict):
            continue
        ship = ships.get(starbase.get("station"))
        if not ship or ctx.fleet_owner.get(ship.get("fleet")) != country_id:
            continue
        level = starbase.get("level")
        definition = levels.get(level)
        if definition is None:
            unsupported.add(str(level))
            continue
        if not any(definition.get(slot_key) for _, slot_key, _ in KINDS):
            continue  # an outpost: no slots to count
        if any(marker in str(level) for marker in MOBILE_LEVEL_MARKERS):
            unsupported.add(str(level))
            continue
        counted += 1
        entry: dict[str, Any] = {}
        any_free = False
        for key, slot_key, _ in KINDS:
            capacity = len(as_list(definition.get(slot_key)))
            used = _indices(starbase.get(key))
            reserved = queued[key].get(starbase_id, set()) - used
            free = max(0, capacity - len(used) - len(reserved))
            any_free = any_free or free > 0
            for name, amount in (
                ("slots", capacity),
                ("used", len(used)),
                ("queued", len(reserved)),
                ("free", free),
            ):
                totals[key][name] += amount
            entry[key] = {"slots": capacity, "used": len(used), "queued": len(reserved)}
        with_free += any_free
        if detail:
            entry.update(id=starbase_id, level=level, system=_system(ctx, ship))
            listing.append(entry)
    result: dict[str, Any] = {
        **totals,
        "starbases": counted,
        "with_free_slot": with_free,
        "free": None,
        "unsupported": sorted(unsupported),
    }
    free = sum(totals[key]["free"] for key, _, _ in KINDS)
    if free > 0 or not unsupported:
        result["free"] = free
    if detail:
        result["list"] = listing
    return result


def _indices(value: Any) -> set[int]:
    """Slot indices of a `{ 0=a 1=b }` block; a list (an empty block) holds none."""
    if isinstance(value, dict):
        return {int(index) for index in value}
    return set(range(len(slots(value))))


def _queued_slots(ctx: Context) -> dict[str, dict[Any, set[int]]]:
    """Slots reserved by queued modules and buildings: kind → starbase id → slot indices."""
    queued: dict[str, dict[Any, set[int]]] = {key: {} for key, _, _ in KINDS}
    items = block(block(ctx.g.get("construction")).get("item_mgr")).get("items")
    for item in block(items).values():
        if not isinstance(item, dict):
            continue
        for key, _, item_key in KINDS:
            order = item.get(item_key)
            if isinstance(order, dict) and "slot" in order:
                queued[key].setdefault(order.get("starbase"), set()).add(int(order["slot"]))
    return queued


def _system(ctx: Context, ship: dict[str, Any]) -> str | None:
    origin = block(ship.get("coordinate")).get("origin")
    system = ctx.g["galactic_object"].get(origin) if origin is not None else None
    return ctx.name(system["name"]) if isinstance(system, dict) and "name" in system else None
