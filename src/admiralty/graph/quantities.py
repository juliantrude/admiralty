"""The key quantities of the Mechanics Graph and which game keys count towards each.

Why a table and not a search over everything: "what produces energy" is not answerable by
grepping the word, because the game spreads it over resource blocks (`produces = { energy = 3 }`)
and a family of modifier names (`country_energy_produces_mult`, `planet_technician_energy_produces_add`,
`starbase_collected_system_energy_add`, ...). Each quantity lists exactly the keys that count; a
curated node that needs a fact the table misses is a reason to extend the table here, nowhere else.

Quantities and their keys come from Appendix A of docs/build-plan.md and were checked against
the names that occur in the 4.5.2 files (common/technology, traditions, buildings, pop_jobs,
districts, ascension_perks, policies, edicts, starbase_modules, static_modifiers, governments).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

# Order is the order of the files and of the plan; ids are the file names.
QUANTITY_IDS = (
    "naval_capacity",
    "energy",
    "minerals",
    "food",
    "alloys",
    "unity",
    "influence",
    "research",
    "pop_growth",
    "stability",
    "amenities",
    "housing",
    "building_slots",
    "district_slots",
)


@dataclass(frozen=True)
class Quantity:
    id: str
    # resource names whose `produces` / `upkeep` / `cost` entries in a `resources` block count
    resources: frozenset[str]
    # does a modifier key (e.g. "country_naval_cap_add") count towards this quantity?
    modifier: Callable[[str], bool]


def _exact(*keys: str) -> Callable[[str], bool]:
    wanted = frozenset(keys)
    return wanted.__contains__


def _pattern(*patterns: str) -> Callable[[str], bool]:
    compiled = [re.compile(p) for p in patterns]
    return lambda key: any(p.search(key) for p in compiled)


def _resource_modifiers(*names: str) -> Callable[[str], bool]:
    """country_energy_produces_mult, planet_technician_energy_produces_add,
    planet_bureaucrats_energy_upkeep_add, starbase_collected_system_energy_add, ..."""
    alternatives = "|".join(names)
    return _pattern(
        rf"(?:^|_)(?:{alternatives})_(?:produces|upkeep)_(?:add|mult)$",
        rf"^starbase_collected_system_(?:{alternatives})_(?:add|mult)$",
    )


def _resource(quantity: str, *names: str, extra: Callable[[str], bool] | None = None) -> Quantity:
    counts = _resource_modifiers(*names)
    if extra is None:
        return Quantity(quantity, frozenset(names), counts)
    return Quantity(quantity, frozenset(names), lambda key: counts(key) or extra(key))


QUANTITIES: dict[str, Quantity] = {
    q.id: q
    for q in (
        Quantity(
            "naval_capacity",
            frozenset(),
            _exact("country_naval_cap_add", "country_naval_cap_mult"),
        ),
        _resource("energy", "energy"),
        _resource("minerals", "minerals"),
        _resource("food", "food"),
        _resource("alloys", "alloys"),
        _resource("unity", "unity"),
        _resource("influence", "influence"),
        _resource(
            "research",
            "physics_research",
            "society_research",
            "engineering_research",
            extra=_pattern(
                r"^all_technology_research_speed$", r"^country_\w+_tech_research_speed$"
            ),
        ),
        Quantity(
            "pop_growth",
            frozenset(),
            _pattern(
                r"(?:^|_)logistic_growth_mult$",
                r"^bonus_pop_growth(?:_mult)?$",
                r"^founder_species_growth_mult$",
                r"^planet_pop_assembly\w*$",
            ),
        ),
        Quantity("stability", frozenset(), _pattern(r"^planet_stability_(?:add|mult)")),
        Quantity(
            "amenities",
            frozenset(),
            _pattern(r"^planet_amenities_", r"^pop_amenities_usage_", r"^job_\w+_amenities_add$"),
        ),
        Quantity(
            "housing",
            frozenset(),
            _pattern(r"^planet_housing_", r"^pop_housing_usage_", r"_housing_add$"),
        ),
        Quantity(
            "building_slots",
            frozenset(),
            _pattern(r"building_slots", r"^max_buildings$"),
        ),
        Quantity(
            "district_slots",
            frozenset(),
            _pattern(r"(?:^|_)max_districts_", r"^free_district_slots$", r"_districts_max_"),
        ),
    )
}

assert tuple(QUANTITIES) == QUANTITY_IDS
