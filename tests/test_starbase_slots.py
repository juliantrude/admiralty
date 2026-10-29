"""Free module and building slots of starbases (extract/computed/starbase_slots.py).

The invariants hold on every reference save. The golden test reads what the Player sees on a
starbase and skips while no value is entered (tests/golden_values.py, key "starbase_slots":
{system name: (modules, module slots, buildings, building slots)}; steps in
docs/awaiting-julian.md).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from conftest import SAVES_DIR, VULKAN, reference_save
from golden_values import PENDING, value

from admiralty.extract.computed.starbase_slots import starbase_slots
from admiralty.extract.snapshot import Extractor, Snapshot
from admiralty.graph.metrics import evaluate

PLAYER = "Plexxi"
ZYGERRIAN = "zygerrian"


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


def fake_ctx(starbases, queue_items=()):
    """A Context with one starbase (id 1) of the country 7, on a station ship."""
    levels = {
        "starbase_level_outpost": {"ship_size": "starbase_outpost"},
        "starbase_level_starhold": {"module_slots": [1, 2, 3, 4], "building_slots": [1, 2]},
        "starbase_level_civilian_arkship_1": {"module_slots": [1, 2], "building_slots": [1]},
    }
    tables = {"ships": {10: {"fleet": 100}}}
    return SimpleNamespace(
        g={
            "starbase_mgr": {"starbases": starbases},
            "construction": {"item_mgr": {"items": dict(enumerate(queue_items))}},
        },
        game=SimpleNamespace(category=lambda name: levels),
        table=lambda key: tables[key],
        fleet_owner={100: 7},
    )


def starbase(level, modules=None, buildings=None):
    return {"level": level, "station": 10, "modules": modules or [], "buildings": buildings or []}


def test_free_slots_are_the_level_slots_minus_modules_and_buildings():
    ctx = fake_ctx(
        {1: starbase("starbase_level_starhold", {0: "anchorage", 1: "anchorage"}, {0: "x"})}
    )
    result = starbase_slots(ctx, 7)
    assert result["modules"] == {"slots": 4, "used": 2, "queued": 0, "free": 2}
    assert result["buildings"] == {"slots": 2, "used": 1, "queued": 0, "free": 1}
    assert (result["starbases"], result["with_free_slot"], result["free"]) == (1, 1, 3)


def test_a_queued_module_or_building_holds_its_slot():
    queue = [
        {"buildable_starbase_module": {"slot": 2, "starbase_module": "anchorage", "starbase": 1}},
        {"buildable_starbase_building": {"slot": 0, "starbase_building": "x", "starbase": 1}},
        # another starbase's queue and a slot the starbase already fills change nothing
        {"buildable_starbase_module": {"slot": 3, "starbase_module": "anchorage", "starbase": 2}},
        {"buildable_starbase_module": {"slot": 0, "starbase_module": "anchorage", "starbase": 1}},
    ]
    ctx = fake_ctx({1: starbase("starbase_level_starhold", {0: "anchorage"})}, queue)
    result = starbase_slots(ctx, 7)
    assert result["modules"] == {"slots": 4, "used": 1, "queued": 1, "free": 2}
    assert result["buildings"] == {"slots": 2, "used": 0, "queued": 1, "free": 1}


def test_outposts_have_no_slots_and_mobile_starbases_do_not_count():
    ctx = fake_ctx(
        {1: starbase("starbase_level_outpost"), 2: starbase("starbase_level_civilian_arkship_1")}
    )
    result = starbase_slots(ctx, 7)
    assert result["starbases"] == 0
    assert result["unsupported"] == ["starbase_level_civilian_arkship_1"]
    # a sum of 0 next to an unsupported level is not a finding
    assert result["free"] is None


def test_other_countries_starbases_are_left_out():
    ctx = fake_ctx({1: starbase("starbase_level_starhold")})
    assert starbase_slots(ctx, 8)["starbases"] == 0


def test_a_level_the_files_do_not_define_is_reported():
    ctx = fake_ctx({1: starbase("starbase_level_unknown")})
    result = starbase_slots(ctx, 7)
    assert result["unsupported"] == ["starbase_level_unknown"]
    assert result["free"] is None


@pytest.mark.saves
@pytest.mark.parametrize(("campaign", "save"), all_saves())
def test_starbase_slots_on_the_reference_saves(extractor, campaign, save):
    snap = Snapshot(extractor, extractor.context(reference_save(campaign, save)), PLAYER)
    result = starbase_slots(snap.ctx, snap.country_id, detail=True)
    assert result["unsupported"] == []
    assert result["starbases"] == len(result["list"]) > 0
    for kind in ("modules", "buildings"):
        total = result[kind]
        assert total["free"] == total["slots"] - total["used"] - total["queued"] >= 0
    for entry in result["list"]:
        for kind in ("modules", "buildings"):
            assert entry[kind]["used"] + entry[kind]["queued"] <= entry[kind]["slots"], entry
        assert entry["system"], entry
    assert result["free"] == result["modules"]["free"] + result["buildings"]["free"]


def test_the_obstacle_reads_clear_with_free_slots_and_present_without(extractor):
    from admiralty.graph.mechanics import MechanicsGraph

    graph = MechanicsGraph.load()
    check = graph.node("naval_capacity.no_free_starbase_slot")["check"]

    def state(free):
        return evaluate(check, graph.metrics, {"room": {"starbase_slots": {"free": free}}}).state

    assert state(0) == "present"
    assert state(3) == "clear"
    assert state(None) == "unknown"


GOLDEN_SAVES = [(VULKAN, "2298.03.11.sav"), (VULKAN, "2259.12.25.sav")]


@pytest.mark.saves
@pytest.mark.parametrize(("campaign", "save"), GOLDEN_SAVES)
def test_golden_starbase_slots(extractor, campaign, save):
    expected = value(campaign, save, "starbase_slots")
    if expected is PENDING:
        pytest.skip(
            f"pending: read modules and building slots of 2-3 starbases for {campaign}/{save} "
            "off the starbase view (docs/awaiting-julian.md)"
        )
    snap = Snapshot(extractor, extractor.context(reference_save(campaign, save)), PLAYER)
    listing = {e["system"]: e for e in starbase_slots(snap.ctx, snap.country_id, True)["list"]}
    for system, (modules, module_slots, buildings, building_slots) in expected.items():
        entry = listing[system]
        assert (entry["modules"]["used"], entry["modules"]["slots"]) == (modules, module_slots)
        assert (entry["buildings"]["used"], entry["buildings"]["slots"]) == (
            buildings,
            building_slots,
        )
