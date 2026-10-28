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

from admiralty.extract.computed.building_slots import planet_building_slots
from admiralty.extract.context import NO_ID, as_list
from admiralty.extract.snapshot import Extractor, Snapshot

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
        assert {k: v for k, v in detail[planet_id].items() if k != "zones"} == slots
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
