"""Technologies and Traditions an empire still lacks for an unlock; the save stores only what it has.

Formula, per family (the unlocks one Obstacle asks about):
    missing = number of distinct technologies and Traditions the empire lacks, where
      - every technology of the family counts when not researched, and so does each of its
        transitive `prerequisites` that is not researched;
      - a technology of `reached` is a target that is not itself counted (the repeatable
        technology is offered the moment its last prerequisite is done), only its prerequisites;
      - a Tradition counts when it is not in `country.traditions`.
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
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from admiralty.extract.computed.modifiers import Triggers
from admiralty.extract.context import Context, as_list
from admiralty.gamefiles import as_list as script_list


@dataclass(frozen=True)
class Family:
    technologies: tuple[str, ...] = ()
    traditions: tuple[str, ...] = ()
    reached: tuple[str, ...] = ()  # targets whose prerequisites count, not the target
    edicts: tuple[str, ...] = ()  # technologies named by the edict's `potential` count


FAMILIES: dict[str, Family] = {
    "will_to_power": Family(edicts=("will_to_power",)),
    "naval_doctrine": Family(reached=("tech_repeatable_naval_cap",)),
    "growth_techs": Family(technologies=("tech_genome_mapping", "tech_universal_marcophage")),
    "assembly_boosts": Family(
        technologies=("tech_micro_replicators", "tech_self_assembling_components"),
        traditions=("tr_versatility_finish",),
    ),
}


def unlocks(ctx: Context, country: dict[str, Any]) -> dict[str, dict[str, Any]]:
    triggers = Triggers(ctx, country)
    traditions = set(as_list(country.get("traditions")))
    return {name: _family(ctx, triggers, traditions, family) for name, family in FAMILIES.items()}


def _family(
    ctx: Context, triggers: Triggers, traditions: set[str], family: Family
) -> dict[str, Any]:
    definitions = ctx.game.category("technology")
    targets = [*family.technologies]
    for edict in family.edicts:
        potential = ctx.game.category("edicts")[edict].get("potential")
        targets.extend(_required_technologies(potential))
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
    return {
        "missing": None if undecided else len(lacking_technologies) + len(lacking_traditions),
        "technologies": [ctx.label(key) for key in lacking_technologies],
        "traditions": [ctx.label(key) for key in lacking_traditions],
        "undecided": [ctx.label(key) for key in undecided],
    }


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
