"""Shared lookups for building a Snapshot extract from one parsed save."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import cached_property
from typing import Any

from admiralty.extract.names import Localisation, UnresolvedName
from admiralty.extract.save import Save
from admiralty.gamefiles import GameData

NO_ID = 4294967295  # the save's null reference


def as_list(value: Any) -> list[Any]:
    """The save parser turns a repeated key into a list and leaves a single one bare."""
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def slots(value: Any) -> list[Any]:
    """Values of a slot block such as a starbase's modules, stored as { 0=a 1=b }."""
    if isinstance(value, dict):
        return list(value.values())
    return as_list(value)


def block(value: Any) -> dict[str, Any]:
    """A nested block, or an empty one: the save writes an empty block as '{}', which the
    parser returns as an empty list."""
    return value if isinstance(value, dict) else {}


def rounded(value: float, digits: int = 2) -> float | int:
    value = round(float(value), digits)
    return int(value) if value.is_integer() else value


_DATE_LINE = re.compile(r"\n.*\[GetDate\].*$")


@dataclass
class Context:
    save: Save
    loc: Localisation
    game: GameData
    errors: list[str] = field(default_factory=list)
    district_labels: dict[str, str] = field(default_factory=dict)

    @property
    def g(self) -> dict[str, Any]:
        return self.save.gamestate

    # --- names -----------------------------------------------------------------

    def name(self, block: Any) -> str:
        """Display Name of a name block from the save. Unresolvable names are recorded as
        errors and returned as a visible marker, never as the raw key."""
        try:
            return self.loc.render(block)
        except UnresolvedName as error:
            self.errors.append(f"name: {error}")
            return "⟨unresolved name⟩"

    def label(self, object_id: str, *candidates: str) -> str:
        """Display Name of a game object type (district, job, tradition, ...), trying
        localisation keys in order. Default candidates: the id, then id_name."""
        keys = candidates or (object_id, f"{object_id}_name")
        for key in keys:
            text = self.loc.text_or_none(key)
            if text:
                return _DATE_LINE.sub("", text).strip()
        self.errors.append(f"label: no localisation for {object_id!r} (tried {', '.join(keys)})")
        return f"⟨{object_id}⟩"

    # --- lookups -----------------------------------------------------------------

    @cached_property
    def planets(self) -> dict[int, dict[str, Any]]:
        return {k: v for k, v in self.g["planets"]["planet"].items() if isinstance(v, dict)}

    @cached_property
    def countries(self) -> dict[int, dict[str, Any]]:
        return {k: v for k, v in self.g["country"].items() if isinstance(v, dict)}

    def table(self, key: str) -> dict[int, Any]:
        value = self.g.get(key) or {}
        return {k: v for k, v in value.items() if isinstance(v, dict)}

    @cached_property
    def colonies(self) -> dict[int, dict[str, Any]]:
        return self.table("colony")

    def system_of(self, planet: dict[str, Any]) -> dict[str, Any]:
        return self.g["galactic_object"][planet["coordinate"]["origin"]]

    def country_name(self, country_id: int) -> str:
        country = self.countries.get(country_id)
        if country is None:
            return "⟨unknown empire⟩"
        return self.name(country["name"])

    @cached_property
    def player_by_country(self) -> dict[int, str]:
        return {p["country"]: p["name"] for p in as_list(self.g.get("player"))}

    @cached_property
    def fleet_owner(self) -> dict[int, int]:
        """fleet id → owning country, from each country's fleets_manager."""
        owners = {}
        for country_id, country in self.countries.items():
            for entry in as_list(block(country.get("fleets_manager")).get("owned_fleets")):
                owners[entry["fleet"]] = country_id
        return owners
