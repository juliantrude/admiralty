"""A ledger of the modifiers acting on one empire, collected from the save plus the game
files, for the values the save does not store (naval capacity, tradition cost, district
maximums).

The game evaluates every modifier's trigger in its own engine. We evaluate only the
triggers we understand (see Triggers); a modifier behind a trigger we cannot decide is
kept in the ledger as *uncertain* and reported as such, never silently counted or
dropped. Golden tests against values read off the game UI tell us when this matters.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from admiralty.extract.context import Context, as_list, block, slots
from admiralty.gamefiles import as_list as script_list

# Game-file keys that carry an unconditional modifier block, per object category.
_MODIFIER_KEYS = ("modifier", "country_modifier")


@dataclass(frozen=True)
class Contribution:
    source: str  # Display Name of where it comes from, e.g. "Technology: Doctrine: Fleet Size"
    amount: float
    certain: bool = True


@dataclass
class Ledger:
    entries: dict[str, list[Contribution]] = field(default_factory=dict)

    def add(self, key: str, amount: float, source: str, certain: bool = True) -> None:
        if amount:
            self.entries.setdefault(key, []).append(Contribution(source, amount, certain))

    def add_block(self, block: Any, source: str, certain: bool = True, times: float = 1) -> None:
        if not isinstance(block, dict):
            return
        for key, value in block.items():
            if isinstance(value, int | float) and not isinstance(value, bool):
                self.add(key, value * times, source, certain)

    def total(self, key: str, certain_only: bool = True) -> float:
        return sum(c.amount for c in self.entries.get(key, []) if c.certain or not certain_only)

    def contributions(self, key: str) -> list[Contribution]:
        return self.entries.get(key, [])


class Triggers:
    """A small evaluator for country-scope triggers. Returns True, False, or None when
    the trigger uses anything we do not model."""

    def __init__(self, ctx: Context, country: dict[str, Any]):
        self.ctx = ctx
        self.country = country
        government = block(country.get("government"))
        self.civics = set(as_list(government.get("civics")))
        self.origin = government.get("origin")
        self.authority = government.get("authority")
        self.ethics = set(as_list(block(country.get("ethos")).get("ethics")))
        self.traditions = set(as_list(country.get("traditions")))
        self.perks = set(as_list(country.get("ascension_perks")))
        self.techs = set(as_list(block(country.get("tech_status")).get("technology")))
        self.policies = {
            p["policy"]: p["selected"] for p in as_list(country.get("active_policies"))
        }
        self.edicts = {e["edict"] for e in as_list(country.get("edicts"))}
        self.flags = set(block(country.get("flags")))
        self.gestalt = "ethic_gestalt_consciousness" in self.ethics
        self.machine = self.authority == "auth_machine_intelligence"
        self.hive = self.authority == "auth_hive_mind"
        # facts of the object being evaluated (a starbase, a planet), set by the caller
        self.local: dict[str, Any] = {}

    def evaluate(self, trigger: Any) -> bool | None:
        if not isinstance(trigger, dict):
            return None
        results = [self._one(key, value) for key, value in trigger.items()]
        return _all(results)

    def _one(self, key: str, value: Any) -> bool | None:
        values = script_list(value)
        if len(values) > 1:
            return _all([self._one(key, v) for v in values])
        value = values[0] if values else value
        yes = value == "yes"
        match key:
            case "AND" | "owner" | "owner?" | "from" | "from?" | "root" | "root?":
                return self.evaluate(value)
            case "OR":
                return _any([self._one(k, v) for k, v in value.items()])
            case "NOT" | "NOR":
                inner = _any([self._one(k, v) for k, v in value.items()])
                return None if inner is None else not inner
            case "NAND":
                inner = self.evaluate(value)
                return None if inner is None else not inner
            case "always":
                return yes
            case "has_civic":
                return value in self.civics
            case "has_origin":
                return value == self.origin
            case "has_authority":
                return value == self.authority
            case "has_ethic":
                return value in self.ethics
            case "has_tradition" | "has_active_tradition":
                return value in self.traditions
            case "has_edict":
                return value in self.edicts
            case "has_country_flag":
                return value in self.flags
            case "has_ascension_perk":
                return value in self.perks
            case "has_technology":
                return value in self.techs
            case "has_policy_flag":
                return None
            case "is_gestalt":
                return self.gestalt == yes
            case "is_machine_empire":
                return self.machine == yes
            case "is_hive_empire":
                return self.hive == yes
            case "is_regular_empire":
                return (not self.gestalt) == yes
            case "is_wilderness_empire" | "is_nomadic" | "is_fallen_empire" | "is_subject":
                return not yes if self._plain_empire() else None
            case "exists":
                return True if value == "owner" else None
            case "is_country_type":
                return value == self.country.get("type", "default")
            case _ if key.startswith("is_") and key.endswith("_authority"):
                kind = key.removeprefix("is_").removesuffix("_authority")
                return (self.authority == f"auth_{kind}") == yes
            case "is_scope_valid":
                return yes
            case "has_starbase_building":
                if "starbase_buildings" in self.local:
                    return value in self.local["starbase_buildings"]
            case "is_normal_starbase":
                return yes if "starbase_buildings" in self.local else None
            case "is_planet_class":
                if "planet_class" in self.local:
                    return value == self.local["planet_class"]
            case "has_district":
                if "districts" in self.local:
                    return value in self.local["districts"]
            case "has_building":
                if "buildings" in self.local:
                    return value in self.local["buildings"]
            case "has_deposit":
                if "deposits" in self.local:
                    return value in self.local["deposits"]
            case "planet" | "planet?" | "solar_system" if "planet_class" in self.local:
                return self.evaluate(value) if key.startswith("planet") else None
        return None

    def _plain_empire(self) -> bool:
        """A regular playable empire that is not one of the special kinds."""
        return self.country.get("type", "default") == "default" and not any(
            c.startswith(("civic_wilderness", "civic_nomad")) for c in self.civics
        )


def _all(results: Iterable[bool | None]) -> bool | None:
    results = list(results)
    if any(r is False for r in results):
        return False
    if any(r is None for r in results):
        return None
    return True


def _any(results: Iterable[bool | None]) -> bool | None:
    results = list(results)
    if any(r is True for r in results):
        return True
    if any(r is None for r in results):
        return None
    return False


def add_definition(
    ledger: Ledger,
    triggers: Triggers,
    definition: Any,
    source: str,
    times: float = 1,
    modifier_keys: tuple[str, ...] = _MODIFIER_KEYS,
    triggered_keys: tuple[str, ...] = ("triggered_modifier", "triggered_country_modifier"),
) -> None:
    """Add a game object's modifier blocks to the ledger: unconditional blocks as certain,
    triggered blocks by their evaluated potential (uncertain when undecidable)."""
    if not isinstance(definition, dict):
        return
    for key in modifier_keys:
        for mod_block in script_list(definition.get(key)):
            ledger.add_block(mod_block, source, times=times)
    for key in triggered_keys:
        for mod_block in script_list(definition.get(key)):
            if not isinstance(mod_block, dict):
                continue
            outcome = triggers.evaluate(mod_block.get("potential", {"always": "yes"}))
            if outcome is False:
                continue
            numbers = {k: v for k, v in mod_block.items() if k not in ("potential", "mult")}
            scale = mod_block.get("mult", 1)
            if isinstance(scale, int | float):
                ledger.add_block(numbers, source, certain=outcome is True, times=times * scale)
            else:
                # scaled by a script value we cannot compute ("modifier:job_..._add")
                ledger.add_block(numbers, source, certain=False, times=times)


def country_ledger(ctx: Context, country_id: int, country: dict[str, Any]) -> Ledger:
    """Country-scope modifiers from everything the empire has adopted or built."""
    ledger = Ledger()
    triggers = Triggers(ctx, country)
    game = ctx.game

    def from_category(category: str, ids: Iterable[str], kind: str) -> None:
        definitions = game.category(category)
        for object_id in ids:
            definition = definitions.get(object_id)
            if definition is not None:
                add_definition(ledger, triggers, definition, f"{kind}: {ctx.label(object_id)}")

    from_category("technology", triggers.techs, "Technology")
    from_category("traditions", triggers.traditions, "Tradition")
    from_category("ascension_perks", triggers.perks, "Ascension Perk")
    from_category("governments/civics", [*triggers.civics, triggers.origin or ""], "Civic")
    from_category("ethics", triggers.ethics, "Ethic")
    from_category("governments/authorities", [triggers.authority or ""], "Authority")
    edicts = [e["edict"] for e in as_list(country.get("edicts"))]
    edict_defs = game.category("edicts")
    for edict in edicts:
        if edict in edict_defs:
            add_definition(
                ledger, triggers, edict_defs[edict],
                f"Edict: {ctx.label(edict, f'edict_{edict}', edict)}",
            )  # fmt: skip
    policy_defs = game.category("policies")
    for policy, selected in triggers.policies.items():
        for option in script_list(policy_defs.get(policy, {}).get("option")):
            if isinstance(option, dict) and option.get("name") == selected:
                add_definition(
                    ledger, triggers, option, f"Policy: {ctx.label(selected)}",
                    modifier_keys=("modifier", "policy_modifier"),
                )  # fmt: skip
    static = game.category("static_modifiers")
    for item in as_list(block(country.get("timed_modifier")).get("items")):
        name = item.get("modifier")
        if name in static:
            ledger.add_block(static[name], f"Modifier: {ctx.label(name)}")
    _add_starbases(ctx, ledger, triggers, country_id)
    _add_planets(ctx, ledger, triggers, country)
    return ledger


def _add_starbases(ctx: Context, ledger: Ledger, triggers: Triggers, country_id: int) -> None:
    modules = ctx.game.category("starbase_modules")
    buildings = ctx.game.category("starbase_buildings")
    levels = ctx.game.category("starbase_levels")
    ships = ctx.table("ships")
    fleets = ctx.table("fleet")
    for starbase in block(block(ctx.g.get("starbase_mgr")).get("starbases")).values():
        if not isinstance(starbase, dict):
            continue
        ship = ships.get(starbase.get("station"))
        fleet = fleets.get(ship.get("fleet")) if ship else None
        if not fleet or ctx.fleet_owner.get(ship["fleet"]) != country_id:
            continue
        triggers.local = {"starbase_buildings": set(slots(starbase.get("buildings")))}
        level = starbase.get("level")
        if level in levels:
            short = str(level).removeprefix("starbase_level_")
            name = ctx.label(level, f"starbase_{short}", level)
            add_definition(ledger, triggers, levels[level], f"Starbase: {name}")
        for module in slots(starbase.get("modules")):
            if module in modules:
                add_definition(
                    ledger, triggers, modules[module], f"Starbase module: {_sm(ctx, module)}"
                )
        for building in slots(starbase.get("buildings")):
            if building in buildings:
                add_definition(
                    ledger, triggers, buildings[building],
                    f"Starbase building: {_sm(ctx, building)}",
                )  # fmt: skip
        triggers.local = {}


def _sm(ctx: Context, object_id: str) -> str:
    return ctx.label(object_id, f"sm_{object_id}", object_id)


# Jobs carry their modifiers per job; a job holds this much workforce (pop size units).
WORKFORCE_PER_JOB = 100


def _add_planets(ctx: Context, ledger: Ledger, triggers: Triggers, country: dict) -> None:
    """Country modifiers that planets contribute: buildings and filled jobs."""
    from admiralty.extract.empire import owned_colonies

    building_defs = ctx.game.category("buildings")
    job_defs = ctx.game.category("pop_jobs")
    buildings_table = ctx.table("buildings")
    jobs_table = ctx.table("pop_jobs")
    for _, _, colony in owned_colonies(ctx, country):
        for building_id in as_list(colony.get("buildings_cache")):
            building = buildings_table.get(building_id)
            if building and building["type"] in building_defs:
                add_definition(
                    ledger, triggers, building_defs[building["type"]],
                    f"Building: {ctx.label(building['type'])}",
                    modifier_keys=("country_modifier",),
                    triggered_keys=("triggered_country_modifier",),
                )  # fmt: skip
        for job_id in as_list(colony.get("pop_jobs")):
            job = jobs_table.get(job_id)
            if not job or job.get("workforce", -1) <= 0:
                continue
            definition = job_defs.get(job["type"])
            if definition is None:
                continue
            add_definition(
                ledger, triggers, definition,
                f"Job: {ctx.label(job['type'], 'job_' + job['type'])}",
                times=job["workforce"] / WORKFORCE_PER_JOB,
                modifier_keys=("country_modifier",),
                triggered_keys=("triggered_country_modifier",),
            )  # fmt: skip
