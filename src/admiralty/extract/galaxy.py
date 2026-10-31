"""The map as the Tracked Empire may use it: systems, hyperlanes, wormholes and gateways.

Nothing here is computed from a formula; it decodes what the save stores (see
docs/plans/reach-target.md for the evidence on Mireesh 2294.01.01):

- `galactic_object[id]`: `name`, `coordinate`, `hyperlane` (`to`, `length`; stored on both ends),
  `bypasses` (ids). A lane with `bridge = yes` is an ordinary lane: the flag marks the lanes that
  joined the map's partitions at generation (`map/setup_scenarios/*.txt`, `min_bridges`).
- Owner of a system: the owner of its starbase's station ship (`starbase_mgr.starbases[id].station`
  -> `ships[station].fleet` -> the country whose `fleets_manager` lists the fleet). Every system of
  the `sectors` table agrees. Only countries of type `default` are empires.
- Known systems: `country[id].terra_incognita.systems` is what the empire has found. Fair Play
  routes only over those; God Mode sees the whole map. (`terra_incognita.data` is a run-length
  coded fog bitmap and says nothing more that routing needs.)
- `bypasses[id]`: `type`, `active`, `linked_to` (wormhole), `active_connections` (gateway),
  `lock_remaining_days`, `is_manual_lock`. `common/bypass/00_bypasses.txt`: a wormhole needs
  `tech_wormhole_stabilization` and has to be explored first (we take: both ends known); a gateway
  needs `tech_gateway_activation` and works only while the save marks it `active`. A link whose
  technology is missing stays in the map with `requires`. Travel through
  a bypass is instant (`ftl_multiplier = 0`), so it has no length.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from admiralty.extract.context import NO_ID, Context, as_list, block

WORMHOLE_TECH = "tech_wormhole_stabilization"  # common/technology/00_phys_tech.txt
GATEWAY_TECH = "tech_gateway_activation"  # common/technology/00_megastructures.txt
BYPASS_TECH = {"wormhole": WORMHOLE_TECH, "gateway": GATEWAY_TECH}


@dataclass(frozen=True)
class System:
    id: int
    name: str
    x: float
    y: float
    owner: int | None  # country id of an empire, None when no empire holds a starbase there
    owner_name: str | None


@dataclass(frozen=True)
class Link:
    a: int
    b: int
    kind: str  # "hyperlane", "wormhole" or "gateway"
    length: float  # 0 for a bypass: the jump is instant
    requires: str | None = None  # technology the empire still has to research before using it


@dataclass
class Galaxy:
    """Systems and the links between them that the knowledge mode lets the empire use.
    `skipped` names, per bypass kind, the links left out and why."""

    systems: dict[int, System]
    links: list[Link]
    god_mode: bool
    skipped: list[dict[str, Any]] = field(default_factory=list)

    def neighbours(self) -> dict[int, list[Link]]:
        """Every system's links, each seen from that system (so `a` is the system itself)."""
        out: dict[int, list[Link]] = {sid: [] for sid in self.systems}
        for link in self.links:
            out[link.a].append(link)
            out[link.b].append(Link(link.b, link.a, link.kind, link.length, link.requires))
        return out


def system_owners(ctx: Context) -> dict[int, int]:
    """System id -> country id of the empire whose starbase holds it."""
    stations = {
        base_id: base.get("station")
        for base_id, base in block(ctx.g.get("starbase_mgr")).get("starbases", {}).items()
        if isinstance(base, dict)
    }
    ships = ctx.g.get("ships") or {}
    owners: dict[int, int] = {}
    for system_id, system in ctx.g["galactic_object"].items():
        for base_id in as_list(system.get("starbases")):
            ship = ships.get(stations.get(base_id))
            owner = ctx.fleet_owner.get(ship.get("fleet")) if isinstance(ship, dict) else None
            if owner is not None and ctx.countries[owner].get("type") in (None, "default"):
                owners[system_id] = owner
                break
    return owners


def owned_system_count(ctx: Context, country_id: int) -> int:
    """How many systems the empire holds through a starbase (the Systems series of Debrief)."""
    return sum(1 for owner in system_owners(ctx).values() if owner == country_id)


def known_systems(country: dict[str, Any]) -> set[int]:
    return set(as_list(block(country.get("terra_incognita")).get("systems")))


def read_galaxy(ctx: Context, country_id: int, god_mode: bool = False) -> Galaxy:
    country = ctx.countries[country_id]
    raw = ctx.g["galactic_object"]
    known = set(raw) if god_mode else known_systems(country)
    owners = system_owners(ctx)
    systems = {
        sid: System(
            id=sid,
            name=ctx.name(raw[sid]["name"]),
            x=raw[sid]["coordinate"]["x"],
            y=raw[sid]["coordinate"]["y"],
            owner=owners.get(sid),
            owner_name=ctx.country_name(owners[sid]) if sid in owners else None,
        )
        for sid in sorted(known & set(raw))
    }
    links = [
        Link(sid, lane["to"], "hyperlane", lane["length"])
        for sid in systems
        for lane in as_list(raw[sid].get("hyperlane"))
        if lane["to"] in systems and sid < lane["to"]
    ]
    bypass_links, skipped = _bypass_links(ctx, country, raw, set(systems))
    return Galaxy(systems=systems, links=links + bypass_links, god_mode=god_mode, skipped=skipped)


def _bypass_links(
    ctx: Context,
    country: dict[str, Any],
    raw: dict[int, dict[str, Any]],
    known: set[int],
) -> tuple[list[Link], list[dict[str, Any]]]:
    """One link per usable wormhole pair and per pair of systems joined by an active gateway,
    and the bypasses left out with the reason (one entry per system and kind). A bypass whose
    technology is not researched yet stays in, with `requires`: it is a route the empire can open."""
    researched = set(as_list(block(country.get("tech_status")).get("technology")))
    bypasses = ctx.table("bypasses")
    system_of = {
        bypass_id: sid
        for sid, system in raw.items()
        for bypass_id in as_list(system.get("bypasses"))
    }
    links: dict[tuple[str, int, int], Link] = {}
    skipped: dict[tuple[str, int], str] = {}
    for bypass_id, bypass in bypasses.items():
        kind = bypass.get("type")
        here = system_of.get(bypass_id)
        if kind not in BYPASS_TECH or here is None:
            continue
        partners = as_list(bypass.get("linked_to") if kind == "wormhole" else None) or as_list(
            bypass.get("active_connections")
        )
        # a jump needs both ends in working order
        why = _out_of_order(bypass) or next(
            (
                _out_of_order(bypasses[p])
                for p in partners
                if p in bypasses and _out_of_order(bypasses[p])
            ),
            None,
        )
        if why:
            skipped[kind, here] = why
            continue
        for other_id in partners:
            there = system_of.get(other_id)
            if there is None or other_id == NO_ID or other_id == bypass_id:
                continue
            if here not in known or there not in known:
                skipped[kind, here] = "far end not known"
                continue
            a, b = sorted((here, there))
            tech = BYPASS_TECH[kind]
            links[(kind, a, b)] = Link(a, b, kind, 0, None if tech in researched else tech)
    left_out = [
        {"kind": kind, "system": sid, "why": why}
        for (kind, sid), why in sorted(skipped.items(), key=lambda item: (item[0][1], item[0][0]))
    ]
    return list(links.values()), left_out


def _out_of_order(bypass: dict[str, Any]) -> str | None:
    if bypass.get("active") != "yes":
        return "not active"
    if bypass.get("is_manual_lock") == "yes" or bypass.get("lock_remaining_days", -1) >= 0:
        return "locked"
    return None
