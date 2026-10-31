"""Routes that differ in the empires they cross (docs/plans/reach-target.md, increment 12).

The map is built by hand: no reference save is needed for the routing rules themselves."""

from __future__ import annotations

import pytest

from admiralty.extract.galaxy import Galaxy, Link, System
from admiralty.extract.routes import find_routes, routes_to

HOME, NORTH, SOUTH, TARGET = 1, 2, 3, 4


def galaxy(links, owners, god_mode=False):
    """`owners`: system id -> country id; ids 0..max appear on the map."""
    names = {HOME: "Home", NORTH: "Northern Pact", SOUTH: "Southern League", TARGET: "Swarm"}
    ids = sorted({end for link in links for end in link[:2]} | set(owners))
    systems = {
        i: System(i, f"S{i}", 0.0, 0.0, owners.get(i), names.get(owners.get(i))) for i in ids
    }
    return Galaxy(systems, [Link(a, b, kind, n, req) for a, b, n, kind, req in links], god_mode)


def lane(a, b, length):
    return (a, b, length, "hyperlane", None)


# 0 (home) - 1 (north) - 4 (target Swarm)        length 10 + 10
# 0 (home) - 2 (south) - 3 (open) - 4            length 15 + 15 + 15
# 0 (home) - 5 (open) - 6 (open) - 7 (open) - 4  length 20 + 20 + 20 + 20
LINKS = [
    lane(0, 1, 10), lane(1, 4, 10),
    lane(0, 2, 15), lane(2, 3, 15), lane(3, 4, 15),
    lane(0, 5, 20), lane(5, 6, 20), lane(6, 7, 20), lane(7, 4, 20),
]  # fmt: skip
OWNERS = {0: HOME, 1: NORTH, 2: SOUTH, 4: TARGET}


def test_routes_differ_in_the_empires_they_cross_and_come_shortest_first():
    g = galaxy(LINKS, OWNERS)
    routes = find_routes(g, HOME, {4})
    assert [r.crossed for r in routes] == [(NORTH,), (SOUTH,), ()]
    assert [r.length for r in routes] == [20, 45, 80]
    assert routes[0].systems == (0, 1, 4)


def test_the_target_empire_and_the_own_one_are_not_crossings():
    g = galaxy([lane(0, 3, 5), lane(3, 4, 5)], {0: HOME, 3: HOME, 4: TARGET})
    (route,) = find_routes(g, HOME, {4})
    assert route.crossed == () and route.systems == (3, 4)  # starts at the own system nearest to it


def test_routes_with_the_same_crossed_empires_count_once():
    # two ways through the Northern Pact: only the shorter one is kept
    links = [lane(0, 1, 10), lane(1, 4, 10), lane(0, 5, 30), lane(5, 4, 30)]
    g = galaxy(links, {0: HOME, 1: NORTH, 5: NORTH, 4: TARGET})
    routes = find_routes(g, HOME, {4})
    assert len(routes) == 1 and routes[0].length == 20


def test_the_empire_target_is_reached_at_its_nearest_system():
    links = [lane(0, 1, 10), lane(1, 4, 10), lane(1, 8, 3)]
    g = galaxy(links, {0: HOME, 1: NORTH, 4: TARGET, 8: TARGET})
    result = routes_to(g, HOME, "Swarm", {})
    assert result["target_is"] == "empire"
    assert result["routes"][0]["to"] == "S8" and result["routes"][0]["length"] == 13


def test_a_system_target_may_lie_in_a_third_empire():
    g = galaxy(LINKS, OWNERS)
    result = routes_to(g, HOME, "S1", {})
    assert result["target_is"] == "system"
    assert result["routes"][0]["path"] == ["S0", "S1"]
    assert result["routes"][0]["crosses"] == []


def test_each_crossed_empire_carries_its_attitude_and_its_systems():
    g = galaxy(LINKS, OWNERS)
    attitudes = {NORTH: {"opinion": -40, "hostile": True, "shares_border": True}}
    first, second = routes_to(g, HOME, "Swarm", attitudes)["routes"][:2]
    assert first["crosses"] == [
        {
            "empire": "Northern Pact",
            "systems_on_route": ["S1"],
            "attitude": {"opinion": -40, "hostile": True, "shares_border": True},
        }
    ]
    assert second["crosses"][0]["attitude"] == {"known": False}  # no contact, no entry


def test_a_wormhole_the_empire_cannot_use_yet_is_named_on_the_route():
    links = [lane(0, 1, 10), (1, 4, 0, "wormhole", "tech_wormhole_stabilization")]
    g = galaxy(links, {0: HOME, 4: TARGET})
    (route,) = routes_to(g, HOME, "Swarm", {})["routes"]
    assert route["needs_technology"] == ["tech_wormhole_stabilization"]
    assert route["length"] == 10  # the jump costs nothing


def test_no_path_says_why_and_names_the_bypasses_left_out():
    g = galaxy([lane(0, 1, 10)], {0: HOME, 4: TARGET})
    g.skipped.append({"kind": "wormhole", "system": 1, "why": "locked"})
    result = routes_to(g, HOME, "Swarm", {})
    assert result["routes"] == []
    assert "wormhole at S1 (locked)" in result["unreachable"]
    assert result["knowledge"] == "fair_play"


def test_unknown_target_lists_the_empires_on_the_map():
    g = galaxy(LINKS, OWNERS)
    with pytest.raises(LookupError, match="Swarm"):
        routes_to(g, HOME, "Nowhere", {})
    with pytest.raises(ValueError, match="itself"):
        routes_to(g, HOME, "Home", {})


# --- the reference save ----------------------------------------------------------------------


def test_the_reference_save_routes_to_a_known_empire_with_its_attitude():
    from conftest import LATE, VULKAN, reference_save

    from admiralty.extract import empire as data
    from admiralty.extract.galaxy import read_galaxy
    from admiralty.extract.header import resolve_tracked_empire
    from admiralty.extract.snapshot import Extractor

    ctx = Extractor().context(reference_save(VULKAN, LATE))
    me = resolve_tracked_empire(ctx, "Plexxi")
    galaxy = read_galaxy(ctx, me)
    attitudes = {
        e["country_id"]: {"opinion": e["opinion"], "hostile": e["hostile"]}
        for e in data.known_empires(ctx, me, ctx.countries[me])
    }
    others = sorted({s.owner_name for s in galaxy.systems.values() if s.owner not in (None, me)})
    assert others
    result = routes_to(galaxy, me, others[0], attitudes)
    assert result["routes"], result.get("unreachable")
    lengths = [r["length"] for r in result["routes"]]
    assert lengths == sorted(lengths)
    for route in result["routes"]:
        assert route["path"][0] == route["from"] and route["path"][-1] == route["to"]
        assert others[0] not in [c["empire"] for c in route["crosses"]]
        assert all("attitude" in c for c in route["crosses"])
