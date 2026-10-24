"""Generated facts: what in the game files produces, costs or modifies a key quantity.

The campaign-independent half of the Mechanics Graph (docs/plans/M4.md, "Generated facts").
`extract/computed/modifiers.py` answers "what applies to *this* empire"; this module answers
"what *could* produce this", straight from `common/`, once per game version. Output is
deterministic: facts sorted by id, fixed key order, no timestamps, so the same game build gives
byte-identical files.

How a source is read: every definition of a scanned category (a tradition, a building, a job...)
is walked as a tree. A leaf whose key belongs to a quantity (`country_naval_cap_add = 5`) or an
entry of a `resources` block (`produces = { energy = 3 }`) becomes a fact. Conditions on the way
down (`potential`, `allow`, `trigger` of the source and of the enclosing blocks) are recorded as
flat lines and never evaluated: the Obstacle checks live in the curated graph, where a human
chose which condition matters. A condition the renderer cannot flatten becomes
`unmodelled: <block>` so a reader sees there is one.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from hlidskjalf.extract.names import Localisation
from hlidskjalf.gamefiles import GameData, as_list
from hlidskjalf.graph.quantities import QUANTITIES, QUANTITY_IDS, Quantity

GENERATOR_VERSION = 1

# (kind, common/ category, localisation key prefixes tried in order, empty prefix = the key itself)
CATEGORIES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("technology", "technology", ("",)),
    ("tradition", "traditions", ("",)),
    ("ascension_perk", "ascension_perks", ("",)),
    ("building", "buildings", ("building_", "")),
    ("district", "districts", ("district_", "")),
    ("job", "pop_jobs", ("job_", "")),
    ("starbase_module", "starbase_modules", ("sm_", "")),
    ("starbase_building", "starbase_buildings", ("sm_", "")),
    ("civic", "governments/civics", ("",)),
    ("policy", "policies", ("policy_", "")),
    ("edict", "edicts", ("edict_", "")),
    ("static_modifier", "static_modifiers", ("",)),
    ("trait", "traits", ("trait_", "")),
    ("zone", "zones", ("",)),
    ("megastructure", "megastructures", ("",)),
    ("relic", "relics", ("",)),
    ("deposit", "deposits", ("d_", "")),
)

# Where a bare modifier amount is "per unit" (per job, per building, per module): the definition
# is instantiated many times, unlike a tradition or technology that applies once.
_PER_UNIT_KINDS = frozenset(
    {
        "building",
        "district",
        "job",
        "starbase_module",
        "starbase_building",
        "megastructure",
        "deposit",
    }
)

# Kinds that only count towards some quantities. Species traits matter for pop growth (plan: "pop
# growth, habitability-adjacent modifiers only"); the same file holds hundreds of leader traits
# whose research or upkeep modifiers are not a lever of the empire.
_KIND_QUANTITIES = {"trait": frozenset({"pop_growth"})}

# Blocks that hold conditions, ratings or effects instead of modifiers. They are never walked for
# facts; the first three are rendered as requirements.
_CONDITION_BLOCKS = ("potential", "allow", "trigger")
_SKIP_PREFIXES = ("ai_", "on_", "weight")
_SKIP_KEYS = frozenset(
    {
        "potential",
        "allow",
        "trigger",
        "prerequisites",
        "limit",
        "effect",
        "immediate",
        "destroy_trigger",
        "possible",
        "can_build",
        "is_listed",
        "mod_weight_if_group_picked",
        "icon_frame",
        "triggered_desc",
    }
)
_RESOURCE_SLOTS = {"produces": "produces", "upkeep": "upkeep", "cost": "cost"}
_OPERATOR_SUFFIXES = ("<=", ">=", "!=", "<", ">")
_SCOPE_OPERATORS = frozenset({"AND"})
_LOGIC_OPERATORS = frozenset({"OR", "NOR", "NAND", "NOT"})
_MAX_CONDITION_DEPTH = 4


class UnresolvedSourceName(ValueError):
    """A source with facts but no Display Name, and not on the allow list."""


@dataclass
class Fact:
    id: str
    quantity: str
    effect: str  # produces | costs | modifies
    modifier: str
    amount: int | float | None
    amount_kind: str  # add | mult | per_unit
    source: dict[str, Any]
    requirement: list[str] | None
    amount_expr: str | None = None
    scaled_by: str | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "id": self.id,
            "effect": self.effect,
            "modifier": self.modifier,
            "amount": self.amount,
        }
        if self.amount_expr is not None:
            out["amount_expr"] = self.amount_expr
        out["amount_kind"] = self.amount_kind
        if self.scaled_by is not None:
            out["scaled_by"] = self.scaled_by
        out["source"] = self.source
        out["requirement"] = self.requirement or None
        return out


@dataclass
class Generated:
    game_version: str
    facts: dict[str, list[Fact]]  # quantity id → facts sorted by id
    unresolved: list[str] = field(default_factory=list)  # "kind key (file)" lines
    unnamed_allowed: list[str] = field(default_factory=list)


def game_version(install_dir: Path) -> str:
    settings = json.loads((install_dir / "launcher-settings.json").read_text(encoding="utf-8"))
    return settings["rawVersion"]


# ---------------------------------------------------------------------------------------------
# Requirements


def render_conditions(block: Any, depth: int = 0) -> list[str]:
    """Flatten a condition block to one line per condition.

    `owner = { has_technology = x }` → `owner: has_technology = x`;
    `OR = { a = 1 b = 2 }` → `OR(a = 1 ; b = 2)`; `num_pops > 5` → `num_pops > 5`.
    """
    if not isinstance(block, dict):
        return [str(block)] if isinstance(block, str | int | float) else []
    lines: list[str] = []
    for key, value in block.items():
        for item in as_list(value):
            lines += _render_condition(key, item, depth)
    return lines


def _render_condition(key: str, value: Any, depth: int) -> list[str]:
    if isinstance(value, dict):
        if depth >= _MAX_CONDITION_DEPTH:
            return [f"unmodelled: {key}"]
        inner = render_conditions(value, depth + 1)
        if not inner:
            return [f"unmodelled: {key}"]
        if key in _SCOPE_OPERATORS:
            return inner
        if key in _LOGIC_OPERATORS:
            return [f"{key}({' ; '.join(inner)})"]
        return [f"{key}: {line}" for line in inner]
    if isinstance(value, list):
        return [f"{key} = {{ {' '.join(str(v) for v in value)} }}"]
    for suffix in _OPERATOR_SUFFIXES:
        if key.endswith(suffix):
            return [f"{key.removesuffix(suffix)} {suffix} {_scalar(value)}"]
    return [f"{key} = {_scalar(value)}"]


def _scalar(value: Any) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _requirements(block: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for name in _CONDITION_BLOCKS:
        for condition in as_list(block.get(name)):
            lines += render_conditions(condition)
    return lines


def _prerequisites(definition: dict[str, Any]) -> list[str]:
    prerequisites = definition.get("prerequisites")
    if prerequisites is None:
        return []
    techs = prerequisites if isinstance(prerequisites, list) else [prerequisites]
    return [f"has_technology = {tech}" for tech in techs]


# ---------------------------------------------------------------------------------------------
# Walking a definition


@dataclass(frozen=True)
class _Hit:
    quantity: Quantity
    effect: str
    modifier: str
    value: Any
    requirement: tuple[str, ...]
    scaled_by: str | None
    from_resources: bool


def _walk(
    block: dict[str, Any],
    requirement: tuple[str, ...],
    resource_slot: str | None,
    in_resources: bool,
) -> Iterator[_Hit]:
    requirement = _dedupe(requirement + tuple(_requirements(block)))
    scaled_by = block.get("mult") if isinstance(block.get("mult"), str) else None
    for key, value in block.items():
        if key in _SKIP_KEYS or key.startswith(_SKIP_PREFIXES) or key == "mult":
            continue
        for item in as_list(value):
            if isinstance(item, dict):
                if key == "resources":
                    yield from _walk(item, requirement, None, True)
                elif in_resources and key in _RESOURCE_SLOTS and resource_slot is None:
                    yield from _walk(item, requirement, _RESOURCE_SLOTS[key], True)
                else:
                    yield from _walk(item, requirement, resource_slot, in_resources)
            elif _is_amount(item):
                yield from _leaf(key, item, requirement, scaled_by, resource_slot)


def _leaf(
    key: str,
    value: Any,
    requirement: tuple[str, ...],
    scaled_by: str | None,
    resource_slot: str | None,
) -> Iterator[_Hit]:
    if resource_slot is not None:
        for quantity in QUANTITIES.values():
            if key in quantity.resources:
                effect = "produces" if resource_slot == "produces" else "costs"
                yield _Hit(
                    quantity, effect, f"{resource_slot}_{key}", value, requirement, None, True
                )
        return
    for quantity in QUANTITIES.values():
        if quantity.modifier(key):
            yield _Hit(quantity, "modifies", key, value, requirement, scaled_by, False)


def _is_amount(value: Any) -> bool:
    """A number, or a scripted expression we keep as text (@variable, value:name, @[ maths ])."""
    if isinstance(value, bool):
        return False
    if isinstance(value, int | float):
        return True
    return isinstance(value, str) and (value.startswith(("@", "value:")))


def _dedupe(lines: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(lines))


# ---------------------------------------------------------------------------------------------
# Sources, files and names


def _source_files(game: GameData, category: str) -> dict[str, str]:
    """Top-level key → file (relative to the install dir) that defines it. Later files win,
    as in GameData."""
    pattern = re.compile(r"^([A-Za-z0-9_.:\-]+)\s*=\s*\{", re.MULTILINE)
    files: dict[str, str] = {}
    for path in sorted((game.common / category).glob("*.txt")):
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        for key in pattern.findall(text):
            files[key] = str(path.relative_to(game.install_dir))
    return files


def _display_name(loc: Localisation, key: str, prefixes: tuple[str, ...]) -> str | None:
    for prefix in prefixes:
        if prefix + key in loc:
            name = loc.text(prefix + key).strip()
            if name and not _KEY_LIKE.fullmatch(name):
                return name
    return None


# A localisation text that is still a key ("tr_x_name") is not a Display Name.
_KEY_LIKE = re.compile(r"[a-z0-9_]+")


def _details(kind: str, definition: dict[str, Any]) -> dict[str, Any]:
    """Facts about the source that Obstacle checks need later (tier, levels of a repeatable)."""
    details: dict[str, Any] = {}
    if kind == "technology":
        for key in ("tier", "levels", "cost", "area"):
            value = definition.get(key)
            if isinstance(value, int | float | str) and not isinstance(value, bool):
                details[key] = value
    return details


def load_allow_list(path: Path) -> set[tuple[str, str]]:
    """`kind key  # reason` per line; sources with no player-facing name."""
    allowed: set[tuple[str, str]] = set()
    if not path.exists():
        return allowed
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].split()
        if len(line) >= 2:
            allowed.add((line[0], line[1]))
    return allowed


def generate(
    game: GameData,
    loc: Localisation,
    allow_unnamed: set[tuple[str, str]] = frozenset(),  # type: ignore[assignment]
) -> Generated:
    """Scan every category and return the facts per quantity."""
    result = Generated(
        game_version=game_version(game.install_dir),
        facts={q: [] for q in QUANTITY_IDS},
    )
    seen: dict[str, int] = {}
    for kind, category, prefixes in CATEGORIES:
        definitions = game.category(category)
        files = _source_files(game, category)
        for key, definition in definitions.items():
            if key.startswith("@") or not isinstance(definition, dict):
                continue
            if kind == "trait" and key.startswith("leader_trait_"):
                continue
            only = _KIND_QUANTITIES.get(kind)
            hits = [
                hit
                for hit in _walk(definition, tuple(_prerequisites(definition)), None, False)
                if only is None or hit.quantity.id in only
            ]
            if not hits:
                continue
            name = _display_name(loc, key, prefixes)
            where = f"{kind} {key} ({files.get(key, category)})"
            if name is None:
                if (kind, key) in allow_unnamed:
                    result.unnamed_allowed.append(where)
                else:
                    result.unresolved.append(where)
                continue
            source = {
                "kind": kind,
                "key": key,
                "name": name,
                "file": files.get(key, f"common/{category}"),
            }
            source.update(_details(kind, definition))
            for hit in hits:
                base = f"{hit.quantity.id}.{kind}.{key}.{hit.modifier}"
                seen[base] = seen.get(base, 0) + 1
                fact_id = base if seen[base] == 1 else f"{base}#{seen[base]}"
                result.facts[hit.quantity.id].append(_fact(fact_id, hit, kind, dict(source)))
    for facts in result.facts.values():
        facts.sort(key=_sort_key)
    result.unresolved.sort()
    result.unnamed_allowed.sort()
    return result


def _fact(fact_id: str, hit: _Hit, kind: str, source: dict[str, Any]) -> Fact:
    number = hit.value if not isinstance(hit.value, str) else None
    if hit.modifier.endswith("mult") or hit.modifier.endswith("_speed"):
        amount_kind = "mult"
    elif kind in _PER_UNIT_KINDS or hit.from_resources:
        amount_kind = "per_unit"
    else:
        amount_kind = "add"
    return Fact(
        id=fact_id,
        quantity=hit.quantity.id,
        effect=hit.effect,
        modifier=hit.modifier,
        amount=number,
        amount_kind=amount_kind,
        source=source,
        requirement=list(hit.requirement),
        amount_expr=hit.value if isinstance(hit.value, str) else None,
        scaled_by=hit.scaled_by,
    )


def _sort_key(fact: Fact) -> tuple[str, int]:
    base, _, number = fact.id.partition("#")
    return base, int(number) if number else 1


# ---------------------------------------------------------------------------------------------
# Output


def render_quantity(generated: Generated, quantity: str) -> str:
    document = {
        "game_version": generated.game_version,
        "generator": GENERATOR_VERSION,
        "quantity": quantity,
        "facts": [fact.to_dict() for fact in generated.facts[quantity]],
    }
    return yaml.safe_dump(
        document, sort_keys=False, allow_unicode=True, width=1000, default_flow_style=False
    )


def write(generated: Generated, out_dir: Path) -> list[Path]:
    """Write one file per quantity plus unresolved.txt (only when something is unresolved)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for quantity in QUANTITY_IDS:
        path = out_dir / f"{quantity}.yaml"
        path.write_text(render_quantity(generated, quantity), encoding="utf-8")
        written.append(path)
    unresolved = out_dir / "unresolved.txt"
    if generated.unresolved:
        unresolved.write_text("\n".join(generated.unresolved) + "\n", encoding="utf-8")
    elif unresolved.exists():
        unresolved.unlink()
    return written
