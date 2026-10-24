"""Snapshot extract tests against the reference saves.

Two kinds: invariants that must hold for every save (names resolve, size and time
budgets, internal consistency), and golden tests against values the Player read off
the game UI (tests/golden_values.py), which skip while a value is pending.
"""

from __future__ import annotations

import json
import time

import pytest
from conftest import SAVES_DIR, VULKAN, budget, reference_save
from golden_values import PENDING, value

from hlidskjalf.extract.diff import DiffError, diff_extracts
from hlidskjalf.extract.snapshot import Extractor

pytestmark = pytest.mark.saves

ZYGERRIAN = "zygerrian"
PLAYER = "Plexxi"


@pytest.fixture(scope="session")
def extractor() -> Extractor:
    return Extractor()


_cache: dict[tuple[str, str], dict] = {}


def extract(extractor: Extractor, campaign: str, save: str) -> dict:
    key = (campaign, save)
    if key not in _cache:
        _cache[key] = extractor.extract(reference_save(campaign, save), PLAYER)
    return _cache[key]


def all_saves() -> list[tuple[str, str]]:
    found = [
        (campaign.name, path.name)
        for campaign in sorted(SAVES_DIR.glob("*"))
        if campaign.is_dir()
        for path in sorted(campaign.glob("*.sav"))
    ]
    return found or [(VULKAN, "2259.12.25.sav")]  # skips with a clear message


# --- invariants ---------------------------------------------------------------------


@pytest.mark.parametrize(("campaign", "save"), all_saves())
def test_every_name_resolves(extractor, campaign, save):
    doc = extract(extractor, campaign, save)
    assert doc["errors"] == []
    text = json.dumps(doc, ensure_ascii=False)
    assert "⟨" not in text, "an unresolved name or label reached the extract"


@pytest.mark.parametrize(("campaign", "save"), all_saves())
def test_extract_stays_compact(extractor, campaign, save):
    doc = extract(extractor, campaign, save)
    assert len(json.dumps(doc, ensure_ascii=False)) < 40_000


@pytest.mark.parametrize(("campaign", "save"), all_saves())
def test_fleets_account_for_used_naval_capacity(extractor, campaign, save):
    doc = extract(extractor, campaign, save)
    used = sum(f["naval_capacity_used"] for f in doc["military"]["fleets"])
    assert used == doc["naval_capacity"]["used"]


def test_extract_under_5_seconds(extractor):
    path = reference_save(VULKAN, "2298.03.11.sav")
    extractor.extract(path, PLAYER)  # warm the localisation and game-file caches
    start = time.process_time()  # CPU time: robust against other load on the machine
    extractor.extract(path, PLAYER)
    assert time.process_time() - start < budget(5.0)


def test_tracked_empire_is_the_players(extractor):
    doc = extract(extractor, VULKAN, "2259.12.25.sav")
    assert doc["header"]["tracked_empire"] == {
        "country_id": 1,
        "name": "Die Borg",
        "player": "Plexxi",
    }
    assert doc["header"]["game_version"] == "4.5.2"
    assert doc["header"]["warnings"] == []


def test_umlauts_survive(extractor):
    doc = extract(extractor, VULKAN, "2259.12.25.sav")
    assert doc["header"]["campaign"] == "Konföderation von Vulkan"
    assert "Konföderation von Vulkan" in [p["empire"] for p in doc["header"]["players"]]


def _planet(doc: dict, name: str, system: str) -> dict:
    matches = [p for p in doc["planets"] if p["name"] == name and p["system"] == system]
    assert matches, f"no planet {name!r} in {system!r}"
    return matches[0]


def test_planet_2_in_helam_has_3_generator_districts(extractor):
    doc = extract(extractor, ZYGERRIAN, "2271.08.25.sav")
    helam = _planet(doc, "2", "Helam")
    assert helam["districts"]["district_generator"]["built"] == 3


def test_planet_11_in_kith_valas_shows_as_11(extractor):
    doc = extract(extractor, ZYGERRIAN, "2271.08.25.sav")
    assert _planet(doc, "11", "Kith'Valas")["name"] == "11"


def test_species_shows_as_kithri(extractor):
    doc = extract(extractor, ZYGERRIAN, "2271.08.25.sav")
    assert "Kithri" in doc["pops"]["by_species"]


def test_planet_detail_on_request(extractor):
    path = reference_save(VULKAN, "2259.12.25.sav")
    doc = extractor.extract(path, PLAYER, planet_detail=True)
    capital = doc["planets"][0]
    assert capital["jobs"] and capital["buildings"] and capital["deposits"]
    assert "jobs" not in extract(extractor, VULKAN, "2259.12.25.sav")["planets"][0]


def test_diff_between_two_saves(extractor):
    older = extract(extractor, VULKAN, "2220.04.22.sav")
    newer = extract(extractor, VULKAN, "2259.12.25.sav")
    diff = diff_extracts(newer, older)  # order does not matter
    assert (diff["from"], diff["to"]) == (older["header"]["date"], newer["header"]["date"])
    assert diff["pops"]["change"] == newer["pops"]["total"] - older["pops"]["total"]
    assert {p["name"] for p in diff["planets_gained"]} <= {p["name"] for p in newer["planets"]}
    dates = (older["header"]["date"], newer["header"]["date"])
    assert all(dates[0] < e["date"] <= dates[1] for e in diff["timeline"])
    with pytest.raises(DiffError):
        diff_extracts(older, extract(extractor, ZYGERRIAN, "2271.08.25.sav"))


# --- golden values from the game UI ---------------------------------------------------


def golden(campaign: str, save: str, *path: str):
    expected = value(campaign, save, *path)
    if expected is PENDING:
        pytest.skip(f"pending: read {'/'.join(path)} for {campaign}/{save} off the game UI")
    return expected


GOLDEN_SAVES = [(VULKAN, "2220.04.22.sav"), (VULKAN, "2259.12.25.sav"), (VULKAN, "2298.03.11.sav")]


@pytest.mark.parametrize(("campaign", "save"), GOLDEN_SAVES)
def test_golden_naval_capacity_max(extractor, campaign, save):
    expected = golden(campaign, save, "naval_capacity_max")
    assert extract(extractor, campaign, save)["naval_capacity"]["max"] == expected


@pytest.mark.parametrize(("campaign", "save"), GOLDEN_SAVES)
def test_golden_naval_capacity_used(extractor, campaign, save):
    expected = golden(campaign, save, "naval_capacity_used")
    assert extract(extractor, campaign, save)["naval_capacity"]["used"] == expected


@pytest.mark.parametrize(("campaign", "save"), GOLDEN_SAVES)
def test_golden_next_tradition_cost(extractor, campaign, save):
    expected = golden(campaign, save, "next_tradition_cost")
    actual = extract(extractor, campaign, save)["progression"]["next_tradition"]["cost"]
    assert actual == expected


@pytest.mark.parametrize(("campaign", "save"), GOLDEN_SAVES)
def test_golden_unity(extractor, campaign, save):
    expected = golden(campaign, save, "unity_stockpile")
    unity = extract(extractor, campaign, save)["resources"]["unity"]
    assert round(unity["stockpile"]) == round(expected)


@pytest.mark.parametrize(("campaign", "save"), GOLDEN_SAVES)
@pytest.mark.parametrize("resource", ["energy", "minerals", "food", "alloys", "influence"])
def test_golden_monthly_net(extractor, campaign, save, resource):
    expected = golden(campaign, save, "monthly_net", resource)
    actual = extract(extractor, campaign, save)["resources"][resource]["net"]
    assert actual == pytest.approx(expected, abs=0.5)


@pytest.mark.parametrize(("campaign", "save"), [*GOLDEN_SAVES, (ZYGERRIAN, "2271.08.25.sav")])
def test_golden_planet_districts(extractor, campaign, save):
    planets = golden(campaign, save, "planets")
    if not planets:
        pytest.skip(f"pending: read two planets for {campaign}/{save} off the game UI")
    doc = extract(extractor, campaign, save)
    for name, expected in planets.items():
        planet = _planet(doc, name, expected["system"])
        for kind, (built, maximum) in expected.get("districts", {}).items():
            assert planet["districts"][kind]["built"] == built, (name, kind)
            if maximum is not PENDING:
                assert planet["districts"][kind].get("max") == maximum, (name, kind)
        for key in ("open_jobs", "unemployed", "designation"):
            if key in expected:
                assert planet[key] == expected[key], (name, key)
