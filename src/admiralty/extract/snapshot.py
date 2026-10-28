"""The Snapshot extract: a compact, typed JSON document per save and Tracked Empire."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import Any

from admiralty.extract import empire as data
from admiralty.extract.computed.ascension_slots import ascension_slots
from admiralty.extract.computed.building_slots import family_zones, planet_building_slots
from admiralty.extract.computed.capital_tier import capital_tiers
from admiralty.extract.computed.max_districts import max_districts, planet_ledger
from admiralty.extract.computed.modifiers import Ledger, Triggers, country_ledger
from admiralty.extract.computed.naval_capacity import naval_capacity
from admiralty.extract.computed.tradition_cost import next_tradition_cost
from admiralty.extract.computed.tradition_trees import (
    DISCOVERY,
    tradition_tree_slots,
    traditions_left,
)
from admiralty.extract.computed.unlocks import unlocks
from admiralty.extract.context import Context
from admiralty.extract.header import build_header, resolve_tracked_empire
from admiralty.extract.names import Localisation
from admiralty.extract.save import Save, load_save
from admiralty.game import GameEnvironment
from admiralty.gamefiles import GameData

SCHEMA_VERSION = 1
# The summary carries the latest Timeline events; the full Timeline is a separate request.
TIMELINE_IN_SUMMARY = 20


@dataclass
class Extractor:
    """Holds what is expensive to load once (localisation, game files) and turns saves
    into Snapshot extracts."""

    env: GameEnvironment = field(default_factory=GameEnvironment.detect)

    @cached_property
    def loc(self) -> Localisation:
        return Localisation.from_files(self.env.localisation_files())

    @cached_property
    def game(self) -> GameData:
        return GameData(self.env.install_dir)

    def context(self, save: Save | str | Path) -> Context:
        if not isinstance(save, Save):
            save = load_save(save)
        return Context(save=save, loc=self.loc, game=self.game)

    def extract(
        self,
        save: Save | str | Path,
        empire: str | int | None = None,
        planet_detail: bool = False,
    ) -> dict[str, Any]:
        return Snapshot(self, self.context(save), empire).document(planet_detail)


class Snapshot:
    """One save seen from one Tracked Empire. Sections can be built on their own, so the
    MCP tools can return just what a question needs."""

    def __init__(self, extractor: Extractor, ctx: Context, empire: str | int | None):
        self.extractor = extractor
        self.ctx = ctx
        self.country_id = resolve_tracked_empire(ctx, empire)
        self.country = ctx.countries[self.country_id]

    @cached_property
    def triggers(self) -> Triggers:
        return Triggers(self.ctx, self.country)

    @cached_property
    def ledger(self) -> Ledger:
        return country_ledger(self.ctx, self.country_id, self.country)

    @cached_property
    def slot_families(self) -> dict[str, frozenset[str] | None]:
        return family_zones(self.ctx, self.triggers)

    @cached_property
    def planet_slots(self) -> list[dict[str, Any]]:
        """Building slots of every planet with the free slots per family, for the empire sums
        of `room` (the planet summaries leave the families out to keep the extract small)."""
        return [
            planet_building_slots(self.ctx, pid, colony, families=self.slot_families)
            for pid, _, colony in self.colonies
        ]

    @cached_property
    def colonies(self) -> list[tuple[int, dict, dict]]:
        return data.owned_colonies(self.ctx, self.country)

    def header(self) -> dict[str, Any]:
        return build_header(self.ctx, self.extractor.env, self.country_id)

    def planets(self, detail: bool = False, planet_id: int | None = None) -> list[dict]:
        out = []
        for pid, planet, colony in self.colonies:
            if planet_id is not None and pid != planet_id:
                continue
            ledger = planet_ledger(self.ctx, self.triggers, self.ledger, planet, colony)
            maxima = max_districts(self.ctx, self.triggers, ledger, planet, colony)
            limit = maxima.pop("_district_limit")
            behind = maxima.pop("_behind_blockers")
            summary = data.planet_summary(self.ctx, pid, planet, colony, maxima)
            summary["district_limit"] = limit
            summary["building_slots"] = planet_building_slots(
                self.ctx, pid, colony, detail, self.slot_families if detail else None
            )
            for kind, count in behind.items():
                summary["districts"][kind]["behind_blockers"] = count
            if detail:
                summary.update(data.planet_detail(self.ctx, pid, planet, colony))
            out.append(summary)
        out.sort(key=lambda p: -p["pops"])
        return out

    def naval_capacity(self) -> dict[str, Any]:
        return naval_capacity(self.ctx, self.country, self.ledger)

    def next_tradition(self) -> dict[str, Any]:
        return next_tradition_cost(self.ctx, self.country, self.ledger)

    def document(self, planet_detail: bool = False) -> dict[str, Any]:
        ctx, country = self.ctx, self.country
        timeline = data.timeline(ctx, country)
        planets = self.planets(detail=planet_detail)
        doc = {
            "schema": SCHEMA_VERSION,
            "header": self.header(),
            "empire": {
                "name": ctx.country_name(self.country_id),
                "empire_size": country.get("empire_size"),
                "military_power": round(country.get("military_power", 0)),
                "economy_power": round(country.get("economy_power", 0)),
                "tech_power": round(country.get("tech_power", 0)),
                "victory_rank": country.get("victory_rank"),
            },
            "resources": data.economy(ctx, country),
            "pops": data.pops(ctx, self.colonies),
            "planets": planets,
            "room": data.room(ctx, planets, self.colonies, self.planet_slots),
            "naval_capacity": self.naval_capacity(),
            "progression": {
                **data.progression(ctx, country),
                "next_tradition": self.next_tradition(),
                "ascension_slots": ascension_slots(ctx, country, self.ledger),
                "tradition_tree_slots": tradition_tree_slots(ctx, country),
                "discovery_traditions": traditions_left(ctx, country, DISCOVERY),
                "capital_tier": capital_tiers(ctx, country),
            },
            "unlocks": unlocks(ctx, country),
            "military": {
                "fleets": data.fleets(ctx, self.country_id, country),
                "wars": data.wars(ctx, self.country_id),
            },
            "timeline": timeline[-TIMELINE_IN_SUMMARY:],
            "timeline_events_total": len(timeline),
            "known_empires": data.known_empires(ctx, self.country_id, country),
        }
        doc["district_labels"] = dict(sorted(ctx.district_labels.items()))
        doc["errors"] = sorted(set(ctx.errors))
        return doc
