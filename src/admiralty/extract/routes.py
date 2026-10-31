"""Static routes through the known map that differ in the empires they cross.

Nothing here is a game formula: it is shortest-path search on the links of `galaxy.py`, so it
inherits what the knowledge mode lets the Tracked Empire use. Travel time is not computed
(speed, FTL and jump drives are not modelled); a route's `length` is the sum of its hyperlane
lengths, a wormhole or gateway jump is free (`ftl_multiplier = 0`).

Method (docs/plans/reach-target.md, increment 12):

1. Shortest path from any system the Tracked Empire holds to the nearest system of the target.
2. The empires that path crosses are the ones its systems belong to, bar the Tracked Empire and
   the target's own. For each such empire, forbid its systems and search again; the new route
   crosses other empires (or fails). Repeat on the new routes until no new set of crossed empires
   turns up or the limit is reached.
3. Routes that cross the same set of empires are one route: the shortest one.

Systems without an owner are open space. A target given as an empire is reached at its nearest
system; a target given as a system is exempt from the ban on its owner.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass
from typing import Any

from admiralty.extract.galaxy import Galaxy

MAX_ROUTES = 5


@dataclass(frozen=True)
class Route:
    systems: tuple[int, ...]  # first = a system the Tracked Empire holds, last = in the target
    length: float
    crossed: tuple[int, ...]  # country ids in order of first contact
    needs: tuple[str, ...]  # technologies the empire still has to research to use the path


def find_routes(
    galaxy: Galaxy,
    own: int,
    targets: set[int],
    limit: int = MAX_ROUTES,
) -> list[Route]:
    """Routes from the systems of empire `own` to any system in `targets`, one per distinct set of
    crossed empires, shortest first. Empty when no path exists."""
    sources = {sid for sid, s in galaxy.systems.items() if s.owner == own}
    neighbours = galaxy.neighbours()
    target_owner = {galaxy.systems[t].owner for t in targets} - {None}
    # forbidding the target's own empire would make an empire target unreachable by definition
    exempt = frozenset(target_owner) if len(target_owner) == 1 else frozenset()
    by_crossed: dict[tuple[int, ...], Route] = {}
    seen_bans: set[frozenset[int]] = set()
    queue: list[frozenset[int]] = [frozenset()]
    while queue and len(seen_bans) < 40:
        banned = queue.pop(0)
        if banned in seen_bans:
            continue
        seen_bans.add(banned)
        route = _shortest(galaxy, neighbours, own, sources, targets, banned, exempt)
        if route is None:
            continue
        known = by_crossed.get(route.crossed)
        if known is None or route.length < known.length:
            by_crossed[route.crossed] = route
        for empire in route.crossed:
            if empire not in exempt:
                queue.append(banned | {empire})
    routes = sorted(by_crossed.values(), key=lambda r: (r.length, len(r.crossed)))
    return routes[:limit]


def _shortest(
    galaxy: Galaxy,
    neighbours: dict[int, list[Any]],
    own: int,
    sources: set[int],
    targets: set[int],
    banned: frozenset[int],
    exempt: frozenset[int],
) -> Route | None:
    def blocked(sid: int) -> bool:
        owner = galaxy.systems[sid].owner
        return owner in banned and owner not in exempt and sid not in targets

    best: dict[int, float] = {}
    came: dict[int, tuple[int, str | None]] = {}
    heap: list[tuple[float, int]] = []
    for sid in sorted(sources):
        best[sid] = 0.0
        heapq.heappush(heap, (0.0, sid))
    while heap:
        cost, sid = heapq.heappop(heap)
        if cost > best.get(sid, float("inf")):
            continue
        if sid in targets:
            return _route(galaxy, own, sid, cost, came)
        for link in neighbours[sid]:
            if blocked(link.b):
                continue
            new = cost + link.length
            if new < best.get(link.b, float("inf")):
                best[link.b] = new
                came[link.b] = (sid, link.requires)
                heapq.heappush(heap, (new, link.b))
    return None


def _route(
    galaxy: Galaxy,
    own: int,
    end: int,
    cost: float,
    came: dict[int, tuple[int, str | None]],
) -> Route:
    path = [end]
    needs: list[str] = []
    while path[-1] in came:
        before, requires = came[path[-1]]
        if requires and requires not in needs:
            needs.append(requires)
        path.append(before)
    path.reverse()
    target_owner = galaxy.systems[end].owner
    crossed: list[int] = []
    for sid in path:
        owner = galaxy.systems[sid].owner
        if owner not in (None, own, target_owner) and owner not in crossed:
            crossed.append(owner)
    return Route(tuple(path), round(cost, 1), tuple(crossed), tuple(sorted(needs)))


def routes_to(
    galaxy: Galaxy,
    own: int,
    target: str,
    attitudes: dict[int, dict[str, Any]],
    limit: int = MAX_ROUTES,
) -> dict[str, Any]:
    """The tool's answer: `target` is an empire's Display Name or a system's Display Name.
    `attitudes` maps a country id to what is known about it (opinion, hostile, borders, power
    band); an empire without contact has no entry and is named as such."""
    empires = {s.owner_name: s.owner for s in galaxy.systems.values() if s.owner is not None}
    by_system = [s.id for s in galaxy.systems.values() if s.name == target]
    if target in empires:
        if empires[target] == own:
            raise ValueError(f"{target} is the Tracked Empire itself")
        ids = {sid for sid, s in galaxy.systems.items() if s.owner == empires[target]}
        kind = "empire"
    elif by_system:
        ids, kind = set(by_system), "system"
    else:
        known = ", ".join(sorted(n for n in empires if n))
        raise LookupError(
            f"{target!r} is neither a system nor an empire on the known map. Empires: {known}"
        )
    base = {
        "target": target,
        "target_is": kind,
        "knowledge": "god_mode" if galaxy.god_mode else "fair_play",
        "known_systems": len(galaxy.systems),
    }
    if not any(s.owner == own for s in galaxy.systems.values()):
        raise LookupError("the Tracked Empire holds no known system to start from")
    routes = find_routes(galaxy, own, ids, limit)
    if not routes:
        return {**base, "routes": [], "unreachable": _why_unreachable(galaxy)}
    return {**base, "routes": [_describe(galaxy, r, attitudes) for r in routes]}


def _describe(galaxy: Galaxy, route: Route, attitudes: dict[int, dict[str, Any]]) -> dict[str, Any]:
    systems = galaxy.systems
    crossed = []
    for empire in route.crossed:
        inside = [systems[s].name for s in route.systems if systems[s].owner == empire]
        name = next(systems[s].owner_name for s in route.systems if systems[s].owner == empire)
        crossed.append(
            {
                "empire": name,
                "systems_on_route": inside,
                "attitude": attitudes.get(empire, {"known": False}),
            }
        )
    out: dict[str, Any] = {
        "length": route.length,
        "jumps": len(route.systems) - 1,
        "from": systems[route.systems[0]].name,
        "to": systems[route.systems[-1]].name,
        "crosses": crossed,
        "path": [systems[s].name for s in route.systems],
    }
    if route.needs:
        out["needs_technology"] = list(route.needs)
    return out


def _why_unreachable(galaxy: Galaxy) -> str:
    if galaxy.god_mode:
        return "no path on the whole map (locked or inactive bypasses are left out)"
    why = "no path over the systems the Tracked Empire has found"
    if galaxy.skipped:
        why += "; bypasses left out: " + ", ".join(
            f"{s['kind']} at {galaxy.systems[s['system']].name} ({s['why']})"
            for s in galaxy.skipped[:5]
            if s["system"] in galaxy.systems
        )
    return why
