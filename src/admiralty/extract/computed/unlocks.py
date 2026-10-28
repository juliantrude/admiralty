"""Technologies and Traditions an empire still lacks for an unlock; the save stores only what it has.

Formula, per family (the unlocks one Obstacle asks about):
    missing = number of distinct technologies and Traditions the empire lacks, where
      - every technology of the family counts when not researched, and so does each of its
        transitive `prerequisites` that is not researched;
      - a technology of `reached` is a target that is not itself counted (the repeatable
        technology is offered the moment its last prerequisite is done), only its prerequisites;
      - a Tradition counts when it is not in `country.traditions`;
      - a building counts through its `prerequisites` (technologies, with their own), when the
        empire can build it at all; the capital tier its `allow` asks for adds 1 when no planet of
        the empire reaches it (computed/capital_tier.py).
A building is left out when the empire can never build it: its `potential` evaluates false for
the country (`owner = { is_regular_empire = yes }`), or it needs `has_building = X` of a building
that is itself left out. A `potential` only a planet can decide (zones, modifiers) does not leave
a building out. For a family that asks for "the next upgrade of the capital", the buildings are
the `upgrades` of the capital building on the capital planet.
A technology is left out when it cannot be researched by this empire: its `potential`
(common/technology/*.txt) evaluates false for the country, or its `weight` is 0 (an event or
rare technology that research never offers, e.g. tech_universal_marcophage). When a `potential`
cannot be decided (Triggers returns None) the family's `missing` is None, never a guess.

Sources (Stellaris 4.5.2, common/):
    will_to_power   edicts/02_ambitions.txt: `potential = { has_technology = tech_ascension_theory }`;
                    the technology is read from the edict, not typed in
    naval_doctrine  technology/00_soc_tech.txt:3600-3697 (tech_doctrine_navy_size_1..4, each with
                    `prerequisites` of the one before), 00_soc_tech_repeatable.txt:216
                    (tech_repeatable_naval_cap, prerequisites tech_doctrine_navy_size_4)
    growth_techs    technology/00_soc_tech.txt:2241 (tech_genome_mapping),
                    00_strange_worlds_tech.txt:14 (tech_universal_marcophage, weight 0)
    assembly_boosts technology/00_synthetic_dawn_tech.txt:405 and :436 (tech_micro_replicators,
                    tech_self_assembling_components), traditions/00_versatility.txt:8
                    (tr_versatility_finish). The civic is a start-of-game choice and is not counted.
    generator_buildings, food_processing, purification, research_labs, housing_buildings,
    unity_buildings
                    buildings/03_resource_buildings.txt, 05_research_buildings.txt,
                    08_unity_buildings.txt:
                    `prerequisites` and `allow = { has_upgraded_capital = yes }` per building
    logistics_office
                    starbase_buildings/00_starbase_buildings.txt:439: the technology sits in
                    `potential = { owner = { has_technology = tech_interstellar_fleet_traditions } }`;
                    the Anchorage it also needs (`possible`) is not counted
    capital_upgrade buildings/00_capital_buildings.txt: `upgrades` of the capital building, each
                    with its `prerequisites`; the alloy cost and the population are not counted
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from admiralty.extract.computed.capital_tier import capital_tiers, required_tier
from admiralty.extract.computed.modifiers import Triggers
from admiralty.extract.context import Context, as_list
from admiralty.gamefiles import as_list as script_list


@dataclass(frozen=True)
class Family:
    technologies: tuple[str, ...] = ()
    traditions: tuple[str, ...] = ()
    reached: tuple[str, ...] = ()  # targets whose prerequisites count, not the target
    edicts: tuple[str, ...] = ()  # technologies named by the edict's `potential` count
    buildings: tuple[str, ...] = ()  # prerequisites and capital tier of the buildings it holds
    starbase_buildings: tuple[str, ...] = ()  # technologies of the `potential`'s owner block
    capital_upgrade: bool = False  # the `upgrades` of the capital planet's capital building


FAMILIES: dict[str, Family] = {
    "will_to_power": Family(edicts=("will_to_power",)),
    "naval_doctrine": Family(reached=("tech_repeatable_naval_cap",)),
    "growth_techs": Family(technologies=("tech_genome_mapping", "tech_universal_marcophage")),
    "assembly_boosts": Family(
        technologies=("tech_micro_replicators", "tech_self_assembling_components"),
        traditions=("tr_versatility_finish",),
    ),
    "generator_buildings": Family(buildings=("building_energy_grid", "building_energy_nexus")),
    "food_processing": Family(
        buildings=("building_food_processing_facility", "building_food_processing_center")
    ),
    "purification": Family(
        buildings=("building_mineral_purification_plant", "building_mineral_purification_hub")
    ),
    "research_labs": Family(
        buildings=(
            "building_physics_lab_2",
            "building_physics_lab_3",
            "building_biolab_2",
            "building_biolab_3",
            "building_engineering_facility_2",
            "building_engineering_facility_3",
            "building_nanolab_2",
        )
    ),
    "unity_buildings": Family(
        buildings=(
            "building_autochthon_monument",
            "building_heritage_site",
            "building_hypercomms_forum",
            "building_simulation_1",
            "building_simulation_2",
            "building_simulation_3",
            "building_sensorium_1",
            "building_sensorium_2",
            "building_sensorium_3",
            "building_corporate_monument",
            "building_corporate_site",
            "building_corporate_forum",
            "building_galactic_memorial_1",
            "building_galactic_memorial_2",
            "building_galactic_memorial_3",
        )
    ),
    "housing_buildings": Family(
        buildings=(
            "building_communal_housing_large",
            "building_drone_megastorage",
            "building_expanded_warren",
        )
    ),
    "logistics_office": Family(starbase_buildings=("naval_logistics_office",)),
    "capital_upgrade": Family(capital_upgrade=True),
}


def unlocks(ctx: Context, country: dict[str, Any]) -> dict[str, dict[str, Any]]:
    triggers = Triggers(ctx, country)
    traditions = set(as_list(country.get("traditions")))
    tiers = capital_tiers(ctx, country)
    return {
        name: _family(ctx, triggers, traditions, tiers, family) for name, family in FAMILIES.items()
    }


def _family(
    ctx: Context, triggers: Triggers, traditions: set[str], tiers: dict[str, Any], family: Family
) -> dict[str, Any]:
    definitions = ctx.game.category("technology")
    targets = [*family.technologies]
    for edict in family.edicts:
        potential = ctx.game.category("edicts")[edict].get("potential")
        targets.extend(_required_technologies(potential))
    starbase_defs = ctx.game.category("starbase_buildings")
    for key in family.starbase_buildings:
        owner = starbase_defs[key].get("potential", {}).get("owner")
        targets.extend(_required_technologies(owner))
    building_defs = ctx.game.category("buildings")
    building_keys = list(family.buildings)
    if family.capital_upgrade:
        capital = building_defs.get(tiers["capital_building"], {})
        building_keys.extend(as_list(capital.get("upgrades")))
    tier_needed = 0
    buildable = [key for key in building_keys if _buildable(building_defs, key, triggers)]
    for key in buildable:
        targets.extend(as_list(building_defs[key].get("prerequisites")))
        tier_needed = max(tier_needed, required_tier(ctx, building_defs[key]))
    wanted: dict[str, None] = {}  # ordered, de-duplicated
    for key in targets:
        _collect(definitions, key, wanted, include_self=True)
    for key in family.reached:
        _collect(definitions, key, wanted, include_self=False)

    lacking_technologies, undecided = [], []
    for key in wanted:
        if key in triggers.techs:
            continue
        verdict = _researchable(definitions[key], triggers)
        if verdict is None:
            undecided.append(key)
        elif verdict:
            lacking_technologies.append(key)
    lacking_traditions = [key for key in family.traditions if key not in traditions]
    capital_short = tier_needed > tiers["best"]
    count = len(lacking_technologies) + len(lacking_traditions) + capital_short
    return {
        "missing": None if undecided else count,
        "technologies": [ctx.label(key) for key in lacking_technologies],
        "traditions": [ctx.label(key) for key in lacking_traditions],
        "capital_tier_needed": tier_needed if capital_short else None,
        "buildings": [ctx.label(key) for key in buildable],
        "undecided": [ctx.label(key) for key in undecided],
    }


def _buildable(definitions: dict[str, Any], key: str, triggers: Triggers) -> bool:
    """False when the empire can never build the building: its `potential` is false for the
    country, or it needs a building (`has_building`) that is itself unbuildable."""
    if key not in definitions:
        raise KeyError(f"building {key!r} not in the game files")
    potential = definitions[key].get("potential")
    if not isinstance(potential, dict):
        return True
    if triggers.evaluate(potential) is False:
        return False
    return all(
        _buildable(definitions, needed, triggers)
        for needed in script_list(potential.get("has_building"))
        if needed in definitions
    )


def _collect(
    definitions: dict[str, Any], key: str, wanted: dict[str, None], include_self: bool
) -> None:
    if key not in definitions:
        raise KeyError(f"technology {key!r} not in the game files")
    if include_self:
        wanted.setdefault(key)
    for prerequisite in as_list(definitions[key].get("prerequisites")):
        _collect(definitions, prerequisite, wanted, include_self=True)


def _researchable(definition: dict[str, Any], triggers: Triggers) -> bool | None:
    """False when research never offers the technology to this empire, None when undecidable."""
    if definition.get("weight") == 0:
        return False
    potential = definition.get("potential")
    if potential is None:
        return True
    verdict = triggers.evaluate(potential)
    return None if verdict is None else verdict


def _required_technologies(potential: Any) -> list[str]:
    """Technologies a `potential` block demands with has_technology at its top level."""
    if not isinstance(potential, dict):
        return []
    return [str(key) for key in script_list(potential.get("has_technology"))]
