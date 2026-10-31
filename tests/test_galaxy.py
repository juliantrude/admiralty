"""The map the Tracked Empire may use (docs/plans/reach-target.md): known systems for Fair Play,
owners through starbases, names resolved, hyperlanes, wormholes and gateways."""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import LATE, VULKAN, reference_save

from admiralty.extract.context import NO_ID, Context
from admiralty.extract.galaxy import GATEWAY_TECH, WORMHOLE_TECH, read_galaxy
from admiralty.extract.header import resolve_tracked_empire
from admiralty.extract.names import UnresolvedName
from admiralty.extract.save import Save
from admiralty.extract.snapshot import Extractor


class Names:
    def render(self, block):
        if "literal" in block:
            return block["key"]
        raise UnresolvedName(block["key"])


def system(name, x, hyperlane=(), bypasses=(), starbase=NO_ID):
    entry = {
        "name": {"key": name, "literal": "yes"},
        "coordinate": {"x": x, "y": 0.0},
        "hyperlane": [{"to": to, "length": length} for to, length in hyperlane],
        "starbases": [starbase],
    }
    if bypasses:
        entry["bypasses"] = list(bypasses)
    return entry


def country(name, known=(), techs=(), kind="default", fleets=()):
    return {
        "name": {"key": name, "literal": "yes"},
        "type": kind,
        "terra_incognita": {"systems": list(known)},
        "tech_status": {"technology": list(techs)},
        "fleets_manager": {"owned_fleets": [{"fleet": f} for f in fleets]},
    }


def build(known, techs=(), bypasses=None, god_mode=False):
    """Five systems in a row 0-1-2-3-4 (lengths 10), a wormhole 0<->4, system 2 held by empire 7."""
    gamestate = {
        "galactic_object": {
            0: system("Alpha", 0, [(1, 10)], bypasses=[100]),
            1: system("Beta", 10, [(0, 10), (2, 10)]),
            2: system("Gamma", 20, [(1, 10), (3, 10)], starbase=50),
            3: system("Delta", 30, [(2, 10), (4, 10)]),
            4: system("Epsilon", 40, [(3, 10)], bypasses=[101]),
        },
        "starbase_mgr": {"starbases": {50: {"station": 60}}},
        "ships": {60: {"fleet": 70}},
        "country": {
            0: country("Home", known, techs),
            7: country("Neighbour", fleets=[70]),
            9: country("Fauna", kind="fauna", fleets=[]),
        },
        "bypasses": bypasses
        or {
            100: {"type": "wormhole", "active": "yes", "linked_to": 101, "lock_remaining_days": -1},
            101: {"type": "wormhole", "active": "yes", "linked_to": 100, "lock_remaining_days": -1},
        },
    }
    ctx = Context(save=Save(Path("x.sav"), {}, gamestate), loc=Names(), game=None)
    return read_galaxy(ctx, 0, god_mode)


ALL = [0, 1, 2, 3, 4]


def test_fair_play_keeps_only_known_systems_and_lanes_between_them():
    galaxy = build(known=[0, 1, 2, 4])
    assert sorted(galaxy.systems) == [0, 1, 2, 4]
    lanes = {(link.a, link.b) for link in galaxy.links if link.kind == "hyperlane"}
    assert lanes == {(0, 1), (1, 2)}  # 3 is unknown, so 2-3 and 3-4 are out


def test_god_mode_sees_the_whole_map():
    galaxy = build(known=[0], god_mode=True)
    assert sorted(galaxy.systems) == ALL
    assert len([link for link in galaxy.links if link.kind == "hyperlane"]) == 4


def test_every_lane_appears_once_but_is_walkable_from_both_ends():
    galaxy = build(known=ALL)
    assert len([link for link in galaxy.links if link.kind == "hyperlane"]) == 4
    neighbours = galaxy.neighbours()
    assert {link.b for link in neighbours[1]} == {0, 2}
    assert all(link.a == sid for sid, links in neighbours.items() for link in links)


def test_names_are_resolved_and_an_unresolvable_one_is_an_error():
    assert build(known=ALL).systems[2].name == "Gamma"
    gamestate_ctx = {"galactic_object": {0: system("Alpha", 0)}}
    gamestate_ctx["galactic_object"][0]["name"] = {"key": "RAW_KEY"}
    gamestate_ctx.update(starbase_mgr={}, ships={}, country={0: country("Home", [0])}, bypasses={})
    ctx = Context(save=Save(Path("x.sav"), {}, gamestate_ctx), loc=Names(), game=None)
    galaxy = read_galaxy(ctx, 0)
    assert galaxy.systems[0].name != "RAW_KEY"
    assert ctx.errors  # recorded, not hidden


def test_owner_comes_from_the_starbase_and_only_empires_count():
    galaxy = build(known=ALL)
    assert galaxy.systems[2].owner == 7 and galaxy.systems[2].owner_name == "Neighbour"
    assert galaxy.systems[0].owner is None


def test_a_wormhole_with_both_ends_known_links_the_systems_and_names_the_missing_tech():
    link = next(link for link in build(known=ALL).links if link.kind == "wormhole")
    assert (link.a, link.b, link.length) == (0, 4, 0)
    assert link.requires == WORMHOLE_TECH
    link = next(
        link for link in build(known=ALL, techs=[WORMHOLE_TECH]).links if link.kind == "wormhole"
    )
    assert link.requires is None


def test_a_wormhole_to_an_unknown_system_is_left_out_with_the_reason():
    galaxy = build(known=[0, 1, 2, 3])
    assert not [link for link in galaxy.links if link.kind == "wormhole"]
    assert {"kind": "wormhole", "system": 0, "why": "far end not known"} in galaxy.skipped


@pytest.mark.parametrize(
    ("change", "why"),
    [({"active": "no"}, "not active"), ({"is_manual_lock": "yes"}, "locked")],
)
def test_an_inactive_or_locked_bypass_is_no_link(change, why):
    bypasses = {
        100: {"type": "wormhole", "active": "yes", "linked_to": 101, "lock_remaining_days": -1},
        101: {"type": "wormhole", "active": "yes", "linked_to": 100, "lock_remaining_days": -1},
    }
    bypasses[100].update(change)
    galaxy = build(known=ALL, bypasses=bypasses)
    assert not [link for link in galaxy.links if link.kind == "wormhole"]
    assert {"kind": "wormhole", "system": 0, "why": why} in galaxy.skipped


def test_active_gateways_join_all_their_systems():
    bypasses = {
        100: {"type": "gateway", "active": "yes", "active_connections": [101]},
        101: {"type": "gateway", "active": "yes", "active_connections": [100]},
    }
    galaxy = build(known=ALL, techs=[GATEWAY_TECH], bypasses=bypasses)
    links = [link for link in galaxy.links if link.kind == "gateway"]
    assert [(link.a, link.b, link.requires) for link in links] == [(0, 4, None)]


# --- the reference save ----------------------------------------------------------------------


@pytest.fixture(scope="module")
def late_galaxy():
    ctx = Extractor().context(reference_save(VULKAN, LATE))
    country_id = resolve_tracked_empire(ctx, "Plexxi")
    return ctx, country_id


def test_the_reference_map_is_consistent_and_names_resolve(late_galaxy):
    ctx, country_id = late_galaxy
    fair = read_galaxy(ctx, country_id)
    god = read_galaxy(ctx, country_id, god_mode=True)
    assert 0 < len(fair.systems) <= len(god.systems) == len(ctx.g["galactic_object"])
    assert set(fair.systems) <= set(god.systems)
    assert all(name for name in (s.name for s in god.systems.values()))
    assert not [e for e in ctx.errors if e.startswith("name")]
    # the empire knows every system it holds a starbase in
    own = {sid for sid, s in fair.systems.items() if s.owner == country_id}
    assert own and own == {sid for sid, s in god.systems.items() if s.owner == country_id}
    # every link joins two systems of the map
    for link in fair.links:
        assert link.a in fair.systems and link.b in fair.systems
