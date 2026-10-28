"""Free building slots per planet (extract/computed/building_slots.py).

Invariants hold on every reference save. The golden test reads what the Player sees on the
planet view and skips while no value is entered (tests/golden_values.py, key "building_slots":
{(planet name, system): (buildings, building slots)}; steps in docs/awaiting-julian.md).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from conftest import SAVES_DIR, VULKAN, reference_save
from golden_values import PENDING, value

from admiralty.extract.computed.building_slots import (
    SLOT_FAMILIES,
    planet_building_slots,
    zone_admits,
)
from admiralty.extract.context import NO_ID, as_list
from admiralty.extract.empire import _slots_free
from admiralty.extract.snapshot import Extractor, Snapshot
from admiralty.graph.metrics import evaluate

pytestmark = pytest.mark.saves

ZYGERRIAN = "zygerrian"
PLAYER = "Plexxi"


@pytest.fixture(scope="session")
def extractor() -> Extractor:
    return Extractor()


def all_saves() -> list[tuple[str, str]]:
    found = [
        (campaign.name, path.name)
        for campaign in sorted(SAVES_DIR.glob("*"))
        if campaign.is_dir()
        for path in sorted(campaign.glob("*.sav"))
    ]
    return found or [(VULKAN, "2259.12.25.sav")]  # skips with a clear message


def snapshot(extractor: Extractor, campaign: str, save: str) -> Snapshot:
    return Snapshot(extractor, extractor.context(reference_save(campaign, save)), PLAYER)


@pytest.mark.parametrize(("campaign", "save"), all_saves())
def test_every_building_stands_in_one_zone_within_its_capacity(extractor, campaign, save):
    snap = snapshot(extractor, campaign, save)
    ctx = snap.ctx
    assert snap.colonies
    for planet_id, _, colony in snap.colonies:
        slots = planet_building_slots(ctx, planet_id, colony, detail=True)
        assert slots["unsupported"] == []
        in_zones = [
            building
            for district_id in as_list(colony.get("districts"))
            for zone_id in as_list(ctx.g["districts"][district_id].get("zones"))
            if zone_id != NO_ID
            for building in as_list(ctx.g["zones"][zone_id].get("buildings"))
        ]
        assert sorted(in_zones) == sorted(as_list(colony.get("buildings_cache"))), planet_id
        assert slots["used"] == len(in_zones)
        assert slots["capacity"] == sum(z["capacity"] for z in slots["zones"])
        assert slots["free"] == sum(z["free"] for z in slots["zones"])
        assert all(z["used"] <= z["capacity"] for z in slots["zones"]), planet_id
    assert ctx.errors == []


def test_capacity_is_read_from_the_zone_definitions(extractor):
    zones = extractor.game.category("zones")
    assert zones["zone_default"]["max_buildings"] == 6  # the government zone
    assert "max_buildings" not in zones["zone_foundry"]  # falls back to the define, 3
    defines = {}
    for group in extractor.game.defines().values():
        defines.update(group)
    assert defines["DEFAULT_MAX_PLANET_BUILDINGS_PER_ZONE"] == 3
    one_slot = [k for k, v in zones.items() if isinstance(v, dict) and v.get("max_buildings") == 1]
    assert one_slot, "the files have zones with a single slot"


def test_summary_and_detail_agree(extractor):
    snap = snapshot(extractor, VULKAN, "2298.03.11.sav")
    summary = {p["id"]: p["building_slots"] for p in snap.planets()}
    detail = {p["id"]: p["building_slots"] for p in snap.planets(detail=True)}
    assert summary.keys() == detail.keys()
    for planet_id, slots in summary.items():
        assert "zones" not in slots
        assert detail[planet_id].keys() - slots.keys() == {"zones", "free_by_family"}
        assert {k: v for k, v in detail[planet_id].items() if k in slots} == slots
    # Golden-free facts from the game UI notes: the capital is full, so no slot is free there
    capital = next(p for p in snap.planets() if p["name"] == "Unimatrix 1")
    assert capital["building_slots"]["free"] == 0
    assert capital["building_slots"]["used"] == capital["building_slots"]["capacity"]


def _stub(zone_defs: dict, zones: dict, district_zones: list, defines: dict | None = None):
    game = SimpleNamespace(
        category=lambda name: zone_defs,
        defines=lambda: {"NGameplay": defines or {"DEFAULT_MAX_PLANET_BUILDINGS_PER_ZONE": 3}},
    )
    return SimpleNamespace(
        game=game,
        errors=[],
        label=lambda key: key,
        g={"districts": {1: {"zones": district_zones}}, "zones": zones},
    )


def test_zone_rules_in_isolation():
    defs = {
        "zone_default": {"max_buildings": 6},
        "zone_plain": {},
        "zone_single": {"max_buildings": 1},
    }
    zones = {
        10: {"type": "zone_default", "buildings": [1, 2]},
        11: {"type": "zone_plain", "buildings": [3, 4, 5]},
        12: {"type": "zone_single", "buildings": []},
    }
    ctx = _stub(defs, zones, [10, 11, 12, NO_ID])
    slots = planet_building_slots(ctx, 7, {"districts": [1]})
    assert slots == {
        "capacity": 10,
        "used": 5,
        "free": 5,
        "empty_zone_slots": 1,
        "unsupported": [],
    }


@pytest.mark.parametrize("rule", ["max_buildings_planet_class", "districts_per_building"])
def test_zones_with_other_capacity_rules_are_reported_not_guessed(rule):
    defs = {"zone_plain": {}, "zone_odd": {"max_buildings": 1, rule: "yes"}}
    zones = {
        10: {"type": "zone_plain", "buildings": [1]},
        11: {"type": "zone_odd", "buildings": [2]},
        12: {"type": "zone_odd", "buildings": []},
    }
    ctx = _stub(defs, zones, [10, 11, 12])
    slots = planet_building_slots(ctx, 7, {"districts": [1]})
    assert (slots["capacity"], slots["used"], slots["free"]) == (3, 1, 2)
    assert slots["unsupported"] == ["zone_odd"]
    assert len(ctx.errors) == 1 and "zone_odd" in ctx.errors[0] and rule in ctx.errors[0]


def test_a_zone_admits_by_sets_include_and_exclude():
    building = {"building_sets": ["government", "urban"]}
    assert zone_admits({"include": ["all"]}, "b", building)
    assert not zone_admits({"include": ["all"], "excluded_building_sets": ["urban"]}, "b", building)
    assert not zone_admits({"include": ["all"], "exclude": ["b"]}, "b", building)
    assert zone_admits({"include": ["b"]}, "b", {})
    assert zone_admits({"included_building_sets": ["urban"]}, "b", building)
    assert not zone_admits({"included_building_sets": ["research"]}, "b", building)
    assert not zone_admits({}, "b", building)
    # the arcology zones write `included_building_sets` twice: both blocks count
    twice = {"included_building_sets": [["industrial", "origin"], ["urban"]]}
    assert zone_admits(twice, "b", building)


@pytest.mark.parametrize(("campaign", "save"), all_saves())
def test_every_building_in_a_zone_is_admitted_by_the_zone_rule(extractor, campaign, save):
    """The rule that decides which zones a family can use reproduces what the game let the
    players build: no building stands in a zone the rule would bar it from."""
    ctx = extractor.context(reference_save(campaign, save))
    zone_defs = extractor.game.category("zones")
    building_defs = extractor.game.category("buildings")
    barred = set()
    for zone in ctx.g["zones"].values():
        if not isinstance(zone, dict):
            continue
        for building_id in as_list(zone.get("buildings")):
            key = ctx.g["buildings"][building_id]["type"]
            if not zone_admits(zone_defs[zone["type"]], key, building_defs[key]):
                barred.add((zone["type"], key))
    assert barred == set()


def test_the_slot_families_name_buildings_of_the_game_files(extractor):
    buildings = extractor.game.category("buildings")
    assert [key for keys in SLOT_FAMILIES.values() for key in keys if key not in buildings] == []


@pytest.mark.parametrize(("campaign", "save"), all_saves())
def test_family_slots_never_exceed_the_free_slots(extractor, campaign, save):
    snap = snapshot(extractor, campaign, save)
    room = snap.document()["room"]
    planets = [p["building_slots"] for p in snap.planets(detail=True)]
    assert room["building_slots_free"] == sum(p["free"] for p in planets)
    assert set(room["building_slots_free_by_family"]) == set(SLOT_FAMILIES)
    for family, free in room["building_slots_free_by_family"].items():
        if free is None:
            assert all(p["free_by_family"][family] is None for p in planets)
            continue
        assert free <= room["building_slots_free"], family
        assert free == sum(p["free_by_family"][family] for p in planets)
        for planet in planets:
            assert planet["free_by_family"][family] <= planet["free"]


def _planet(free, by_family=None, unsupported=()):
    return {"free": free, "free_by_family": by_family or {}, "unsupported": list(unsupported)}


def test_the_empire_sum_is_unknown_where_it_could_wrongly_read_zero():
    assert _slots_free([_planet(2, {"unity": 1}), _planet(0, {"unity": 0})], "unity") == 1
    assert _slots_free([_planet(0), _planet(0)], None) == 0
    # no buildable building in the family
    assert _slots_free([_planet(3, {"unity": None})], "unity") is None
    # a zone whose slots are not computed may hold the free slot
    assert _slots_free([_planet(0, {"unity": 0}, ["zone_lathe"])], "unity") is None
    assert _slots_free([_planet(0, unsupported=["zone_lathe"])], None) is None
    assert _slots_free([_planet(2, unsupported=["zone_lathe"])], None) == 2


def test_the_slot_obstacles_read_the_empire_sums():
    from admiralty.graph.mechanics import MechanicsGraph

    graph = MechanicsGraph.load()

    def state(node, family_free, free=5):
        room = {
            "building_slots_free": free,
            "building_slots_free_by_family": {family: family_free for family in SLOT_FAMILIES},
        }
        return evaluate(graph.node(node)["check"], graph.metrics, {"room": room}).state

    assert state("jobs.no_building_room", 3, free=0) == "present"
    assert state("jobs.no_building_room", 3) == "clear"
    assert state("stability.no_building_slot", 0) == "present"
    assert state("housing.no_building_slot", 2) == "clear"
    assert state("pop_growth.no_growth_building_slot", 0) == "present"
    # a family that needs a zone of its own: more zones may still be built
    for node in ("alloys.no_foundry_slot", "research.no_lab_slot", "unity.no_building_slot"):
        assert state(node, 0) == "judgement", node
        assert state(node, 1) == "clear", node
    assert state("unity.no_building_slot", None) == "unknown"


GOLDEN_SLOT_SAVES = [
    (VULKAN, "2298.03.11.sav"),
    (VULKAN, "2259.12.25.sav"),
    (VULKAN, "2220.04.22.sav"),
]


@pytest.mark.parametrize(("campaign", "save"), GOLDEN_SLOT_SAVES)
def test_golden_building_slots(extractor, campaign, save):
    expected = value(campaign, save, "building_slots")
    if expected is PENDING:
        pytest.skip(
            f"pending: read buildings and building slots of 2-3 planets for {campaign}/{save} "
            "off the planet view (docs/awaiting-julian.md)"
        )
    doc = extractor.extract(reference_save(campaign, save), PLAYER)
    for (name, system), (used, capacity) in expected.items():
        planet = next(p for p in doc["planets"] if (p["name"], p["system"]) == (name, system))
        slots = planet["building_slots"]
        assert (slots["used"], slots["capacity"]) == (used, capacity), (name, system)
