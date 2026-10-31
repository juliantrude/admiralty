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
from golden_values import PENDING, matches, value

from admiralty.extract.context import as_list, block
from admiralty.extract.diff import DiffError, diff_extracts
from admiralty.extract.snapshot import Extractor, Snapshot

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
#
# Tolerances, and why: computed values (naval capacity, district maxima) must match
# exactly. The Tradition cost may be off by 2 because the game recomputes empire size
# live after loading. The top bar's monthly net is also recomputed live, so it can differ
# from the save's budget by up to 10 (seen: 9 energy in 2259 and 2298); Unity income by 5.


def golden(campaign: str, save: str, *path):
    expected = value(campaign, save, *path)
    if expected is PENDING:
        pytest.skip(f"pending: read {'/'.join(map(str, path))} for {campaign}/{save} off the UI")
    return expected


GOLDEN_SAVES = [(VULKAN, "2220.04.22.sav"), (VULKAN, "2259.12.25.sav"), (VULKAN, "2298.03.11.sav")]
GOLDEN_PLANET_SAVES = [*GOLDEN_SAVES, (ZYGERRIAN, "2271.08.25.sav")]


@pytest.mark.parametrize(("campaign", "save"), GOLDEN_SAVES)
def test_golden_date(extractor, campaign, save):
    assert extract(extractor, campaign, save)["header"]["date"] == golden(campaign, save, "date")


@pytest.mark.parametrize(("campaign", "save"), GOLDEN_SAVES)
def test_golden_naval_capacity(extractor, campaign, save):
    used, maximum = golden(campaign, save, "naval_capacity")
    naval = extract(extractor, campaign, save)["naval_capacity"]
    assert (naval["used"], naval["max"]) == (used, maximum)


@pytest.mark.parametrize(("campaign", "save"), GOLDEN_SAVES)
def test_golden_next_tradition_cost(extractor, campaign, save):
    expected = golden(campaign, save, "next_tradition_cost")
    actual = extract(extractor, campaign, save)["progression"]["next_tradition"]["cost"]
    assert actual == pytest.approx(expected, abs=2)


@pytest.mark.parametrize(("campaign", "save"), GOLDEN_SAVES)
def test_golden_unity(extractor, campaign, save):
    unity = extract(extractor, campaign, save)["resources"]["unity"]
    assert matches(unity["stockpile"], golden(campaign, save, "unity_stockpile"))
    assert unity["net"] == pytest.approx(golden(campaign, save, "unity_income"), abs=5)


@pytest.mark.parametrize(("campaign", "save"), GOLDEN_SAVES)
@pytest.mark.parametrize("resource", ["energy", "minerals", "food", "alloys", "influence"])
def test_golden_monthly_net(extractor, campaign, save, resource):
    expected = golden(campaign, save, "monthly_net", resource)
    actual = extract(extractor, campaign, save)["resources"][resource]["net"]
    assert actual == pytest.approx(expected, abs=10)


@pytest.mark.parametrize(("campaign", "save"), GOLDEN_SAVES)
def test_golden_intel(extractor, campaign, save):
    for name, expected in golden(campaign, save, "intel").items():
        empire = next(
            e for e in extract(extractor, campaign, save)["known_empires"] if e["name"] == name
        )
        assert int(empire["intel"]) == expected, name


def _normalised(text: str) -> str:
    return text.replace("-", " ").casefold()


@pytest.mark.parametrize(("campaign", "save"), GOLDEN_PLANET_SAVES)
def test_golden_planets(extractor, campaign, save):
    doc = extract(extractor, campaign, save)
    for (name, system), expected in golden(campaign, save, "planets").items():
        planet = _planet(doc, name, system)
        where = f"{name} ({system})"
        assert planet["district_limit"] == expected["district_limit"], where
        for kind, (built, maximum) in expected["districts"].items():
            entry = planet["districts"][kind]
            assert (entry["built"], entry.get("max")) == (built, maximum), (where, kind)
        for key in ("pops", "open_jobs", "unemployed"):
            if key in expected:
                assert matches(planet[key], expected[key]), (where, key)
        if "designation" in expected:
            assert _normalised(planet["designation"]) == _normalised(expected["designation"])


def test_blocked_deposits_show_as_behind_blockers(extractor):
    """'2' in Astarte had three blockers in 2259 covering Rich Mountain (+3 mining),
    Fertile Lands and Black Soil (+5 farming); by 2298 they were cleared."""
    early = _planet(extract(extractor, VULKAN, "2259.12.25.sav"), "2", "Astarte")["districts"]
    assert early["district_mining"]["behind_blockers"] == 3
    assert early["district_farming"]["behind_blockers"] == 5
    late = _planet(extract(extractor, VULKAN, "2298.03.11.sav"), "2", "Astarte")["districts"]
    assert "behind_blockers" not in late["district_mining"]


def test_room_counts_free_district_slots_and_open_jobs(extractor):
    doc = extract(extractor, VULKAN, "2259.12.25.sav")
    expected = sum(
        max(0, int(p["district_limit"]) - sum(d["built"] for d in p["districts"].values()))
        for p in doc["planets"]
    )
    room = doc["room"]
    assert room["districts_free"] == expected
    assert all(0 <= v <= expected for v in room["district_types_free"].values())
    # Golden values: "2" in Astarte has 9 of 10 districts, Unimatrix 1 is full
    astarte = _planet(doc, "2", "Astarte")
    assert (
        int(astarte["district_limit"]) - sum(d["built"] for d in astarte["districts"].values()) == 1
    )
    assert room["open_jobs_by_output"]["energy"] > 0


def test_room_names_the_free_places_planet_by_planet(extractor):
    doc = extract(extractor, VULKAN, "2259.12.25.sav")
    room = doc["room"]
    table = room["by_planet"]
    entries = [dict(zip(table["columns"], row, strict=True)) for row in table["rows"]]
    assert [e["planet"] for e in entries] == [p["name"] for p in doc["planets"]]
    assert sum(e["districts_free"] for e in entries) == room["districts_free"]
    assert sum(e["building_slots_free"] for e in entries) == room["building_slots_free"]
    for kind, total in room["district_types_free"].items():
        assert sum(e[f"district_types_free.{kind}"] for e in entries) == total
    for family, total in room["building_slots_free_by_family"].items():
        if total is not None:
            assert sum(e[f"building_slots_free_by_family.{family}"] for e in entries) == total
    assert sum(e["housing_free"] for e in entries) == pytest.approx(room["housing_free"], abs=0.5)


def test_the_by_planet_paths_of_the_metrics_are_columns_of_the_room_table(extractor):
    from admiralty.graph.mechanics import MechanicsGraph

    doc = extract(extractor, VULKAN, "2259.12.25.sav")
    columns = set(doc["room"]["by_planet"]["columns"])
    paths = {m["by_planet"] for m in MechanicsGraph.load().metrics.values() if "by_planet" in m}
    assert paths
    assert paths - columns == set()


def test_job_functions_follow_the_game_tags():
    from admiralty.extract.empire import job_functions

    assert job_functions({"tags": ["amenities", "trade"]}) == {"amenities"}  # clerk
    assert job_functions({"tags": ["soldier"]}) == {"order"}
    assert job_functions({"tags": ["crime", "enforcer"]}) == {"order"}
    assert job_functions({"tags": ["unity"]}) == set()  # bureaucrat: stability only behind triggers
    assert job_functions({"tags": {}}) == set()
    assert job_functions(None) == set()


@pytest.mark.parametrize(
    "campaign_save", [(VULKAN, "2259.12.25.sav"), (ZYGERRIAN, "2271.08.25.sav")]
)
def test_room_counts_open_jobs_by_function_and_free_housing(extractor, campaign_save):
    doc = extract(extractor, *campaign_save)
    room = doc["room"]
    assert set(room["open_jobs_by_function"]) == {"amenities", "order"}
    assert all(v >= 0 for v in room["open_jobs_by_function"].values())
    # free housing: crowded planets (negative) count 0, every planet carries its own value
    assert all("free_housing" in p for p in doc["planets"])
    assert room["housing_free"] == pytest.approx(
        sum(max(p["free_housing"], 0) for p in doc["planets"]), abs=0.1
    )


@pytest.mark.parametrize(
    "campaign_save",
    [
        (VULKAN, "2298.03.11.sav"),
        (ZYGERRIAN, "2271.08.25.sav"),
        (ZYGERRIAN, "2291.09.26.sav"),  # one unlocked slot not yet filled
        (ZYGERRIAN, "2363.04.17.sav"),
    ],
)
def test_ascension_slots_follow_finished_trees(extractor, campaign_save):
    campaign, save = campaign_save
    doc = extract(extractor, campaign, save)
    slots = doc["progression"]["ascension_slots"]
    ctx = extractor.context(reference_save(campaign, save))
    snapshot = Snapshot(extractor, ctx, PLAYER)
    traditions = as_list(snapshot.country.get("traditions"))
    techs = as_list(block(snapshot.country.get("tech_status")).get("technology"))
    # independent count from save fields: a slot per finished tree, one for Ascension Theory
    finished = sum(1 for t in traditions if t.endswith("_finish"))
    expected = finished + ("tech_ascension_theory" in techs)
    assert slots["unlocked"] == min(expected, slots["cap"])
    assert slots["taken"] == len(doc["progression"]["ascension_perks"])
    assert slots["free"] == max(0, slots["unlocked"] - slots["taken"])
    assert slots["cap"] == 8


def test_a_free_ascension_slot_exists_on_the_reference_saves(extractor):
    free = extract(extractor, ZYGERRIAN, "2291.09.26.sav")["progression"]["ascension_slots"]["free"]
    full = extract(extractor, VULKAN, "2298.03.11.sav")["progression"]["ascension_slots"]["free"]
    assert free == 1
    assert full == 0


@pytest.mark.parametrize(
    "campaign_save", [(VULKAN, "2298.03.11.sav"), (ZYGERRIAN, "2363.04.17.sav")]
)
def test_tradition_tree_slots_and_discovery_traditions(extractor, campaign_save):
    doc = extract(extractor, *campaign_save)
    progression = doc["progression"]
    trees = progression["tradition_tree_slots"]
    assert trees["max"] == 7
    assert trees["adopted"] == len(progression["tradition_trees"])
    assert trees["free"] == 7 - trees["adopted"]
    discovery = progression["discovery_traditions"]
    assert discovery["total"] == 5
    assert discovery["adopted"] + discovery["left"] == 5
    assert 0 <= discovery["left"] <= 5


def test_progression_obstacles_are_checked_on_the_reference_saves(extractor):
    from admiralty.graph.mechanics import MechanicsGraph
    from admiralty.graph.metrics import evaluate

    graph = MechanicsGraph.load()

    def state(node, campaign_save):
        doc = extract(extractor, *campaign_save)
        return evaluate(graph.node(node)["check"], graph.metrics, doc).state

    full, free = (VULKAN, "2298.03.11.sav"), (ZYGERRIAN, "2291.09.26.sav")
    for node in ("unity.no_ascension_slot", "influence.no_ascension_slot"):
        assert state(node, full) == "present"
        assert state(node, free) == "clear"
    assert state("research.discovery_tree_unfinished", full) == "present"
    assert state("research.discovery_tree_unfinished", free) == "clear"  # tree finished
    assert state("naval_capacity.tradition_slot_taken", full) == "clear"  # 4 tree slots free


@pytest.mark.parametrize(
    "campaign_save",
    [
        (VULKAN, "2220.04.22.sav"),
        (VULKAN, "2298.03.11.sav"),
        (ZYGERRIAN, "2271.08.25.sav"),
        (ZYGERRIAN, "2363.04.17.sav"),
    ],
)
def test_unlocks_count_what_the_save_lacks(extractor, campaign_save):
    campaign, save = campaign_save
    doc = extract(extractor, campaign, save)
    ctx = extractor.context(reference_save(campaign, save))
    snapshot = Snapshot(extractor, ctx, PLAYER)
    researched = set(as_list(block(snapshot.country.get("tech_status")).get("technology")))
    unlocks = doc["unlocks"]
    # the Ascension Theory edict needs exactly the technology its `potential` names
    assert (unlocks["will_to_power"]["missing"] == 0) == ("tech_ascension_theory" in researched)
    # the doctrine chain: one missing step per unresearched doctrine technology, because each
    # step needs the one before it
    steps = [f"tech_doctrine_navy_size_{n}" for n in range(1, 5)]
    assert unlocks["naval_doctrine"]["missing"] >= sum(s not in researched for s in steps)
    assert unlocks["naval_doctrine"]["missing"] == len(unlocks["naval_doctrine"]["technologies"])
    # tech_universal_marcophage has weight 0 (never offered), so only genome mapping can be missing
    assert (unlocks["growth_techs"]["missing"] == 0) == ("tech_genome_mapping" in researched)
    traditions = set(as_list(snapshot.country.get("traditions")))
    assembly = unlocks["assembly_boosts"]
    assert len(assembly["traditions"]) == ("tr_versatility_finish" not in traditions)
    for family in unlocks.values():
        assert family["undecided"] == []
        short_of_capital = family["capital_tier_needed"] is not None
        assert family["missing"] == (
            len(family["technologies"]) + len(family["traditions"]) + short_of_capital
        )


def test_unlock_families_name_technologies_that_exist(extractor):
    from admiralty.extract.computed.unlocks import FAMILIES

    ctx = extractor.context(reference_save(VULKAN, "2298.03.11.sav"))
    technologies = ctx.game.category("technology")
    traditions = ctx.game.category("traditions")
    for family in FAMILIES.values():
        for key in (*family.technologies, *family.reached):
            assert key in technologies
        for key in family.traditions:
            assert key in traditions
    # the repeatable technology is reached through the whole doctrine line
    from admiralty.extract.computed.unlocks import _collect

    wanted: dict[str, None] = {}
    _collect(technologies, "tech_repeatable_naval_cap", wanted, include_self=False)
    assert {f"tech_doctrine_navy_size_{n}" for n in range(1, 5)} <= set(wanted)
    assert "tech_repeatable_naval_cap" not in wanted


def test_technology_unlock_obstacles_are_checked_on_the_reference_saves(extractor):
    from admiralty.graph.mechanics import MechanicsGraph
    from admiralty.graph.metrics import evaluate

    graph = MechanicsGraph.load()

    def state(node, campaign_save):
        doc = extract(extractor, *campaign_save)
        return evaluate(graph.node(node)["check"], graph.metrics, doc).state

    early, late = (VULKAN, "2220.04.22.sav"), (ZYGERRIAN, "2363.04.17.sav")
    assert state("influence.decree_locked", late) == "present"  # Ascension Theory missing
    assert state("naval_capacity.doctrine_prerequisites", early) == "present"
    assert state("naval_capacity.doctrine_prerequisites", late) == "clear"
    assert state("pop_growth.growth_tech_locked", early) == "clear"
    assert state("pop_growth.assembly_locked", early) == "present"
    assert state("pop_growth.assembly_locked", late) == "judgement"  # only_present, nothing lacking


@pytest.mark.parametrize(
    "campaign_save",
    [
        (VULKAN, "2220.04.22.sav"),
        (VULKAN, "2298.03.11.sav"),
        (ZYGERRIAN, "2271.08.25.sav"),
        (ZYGERRIAN, "2363.04.17.sav"),
    ],
)
def test_capital_tier_follows_the_capital_buildings(extractor, campaign_save):
    campaign, save = campaign_save
    doc = extract(extractor, campaign, save)
    ctx = extractor.context(reference_save(campaign, save))
    snapshot = Snapshot(extractor, ctx, PLAYER)
    tiers = doc["progression"]["capital_tier"]
    definitions = ctx.game.category("buildings")
    # the capital building named is a capital building of exactly that tier
    building = definitions[tiers["capital_building"]]
    assert building["capital"] == "yes"
    assert building["capital_tier"] == tiers["capital_planet"]
    assert 2 <= tiers["capital_planet"] <= tiers["best"]  # machine line: capital starts at tier 2
    # `best` is the tier of a capital building on one of the empire's planets
    on_planets = {
        ctx.table("buildings")[building_id]["type"]
        for _, _, colony in snapshot.colonies
        for building_id in as_list(colony.get("buildings_cache"))
        if building_id in ctx.table("buildings")
    }
    reached = [
        definitions[kind]["capital_tier"]
        for kind in on_planets
        if kind in definitions and definitions[kind].get("capital") == "yes"
    ]
    assert tiers["best"] == max(reached)


def test_required_tier_is_read_from_the_scripted_triggers(extractor):
    from admiralty.extract.computed.capital_tier import required_tier

    ctx = extractor.context(reference_save(VULKAN, "2298.03.11.sav"))
    buildings = ctx.game.category("buildings")
    assert required_tier(ctx, buildings["building_energy_nexus"]) == 2  # has_upgraded_capital
    assert required_tier(ctx, buildings["building_hypercomms_forum"]) == 3  # major upgraded
    assert required_tier(ctx, buildings["building_energy_grid"]) == 0  # asks for none


def test_building_unlock_families_name_buildings_that_exist(extractor):
    from admiralty.extract.computed.unlocks import FAMILIES

    ctx = extractor.context(reference_save(VULKAN, "2298.03.11.sav"))
    buildings = ctx.game.category("buildings")
    starbase_buildings = ctx.game.category("starbase_buildings")
    for family in FAMILIES.values():
        for key in family.buildings:
            assert key in buildings
        for key in family.starbase_buildings:
            assert key in starbase_buildings


@pytest.mark.parametrize(
    "campaign_save",
    [
        (VULKAN, "2220.04.22.sav"),
        (VULKAN, "2298.03.11.sav"),
        (ZYGERRIAN, "2271.08.25.sav"),
        (ZYGERRIAN, "2363.04.17.sav"),
    ],
)
def test_building_unlocks_count_technologies_of_the_buildings(extractor, campaign_save):
    campaign, save = campaign_save
    doc = extract(extractor, campaign, save)
    ctx = extractor.context(reference_save(campaign, save))
    snapshot = Snapshot(extractor, ctx, PLAYER)
    researched = snapshot.triggers.techs
    unlocks = doc["unlocks"]
    buildings = ctx.game.category("buildings")
    labels = {ctx.label(key): key for key in buildings}
    tier = doc["progression"]["capital_tier"]
    # every building a family counts that asks for a tier above the best one makes the tier short
    for name in ("generator_buildings", "food_processing", "purification", "research_labs"):
        family = unlocks[name]
        keys = [labels[label] for label in family["buildings"] if label in labels]
        assert keys, f"{name} has no buildable building for this empire"
        wanted = max(required(ctx, buildings[key]) for key in keys)
        assert (family["capital_tier_needed"] is not None) == (wanted > tier["best"])
        # a family is complete exactly when every prerequisite of its buildings is researched
        for key in keys:
            lacking = [
                t for t in as_list(buildings[key].get("prerequisites")) if t not in researched
            ]
            if lacking:
                assert family["missing"] > 0
    # the capital's next upgrade needs the technology its building names, nothing else
    upgrade = unlocks["capital_upgrade"]
    for label in upgrade["buildings"]:
        assert buildings[labels[label]].get("capital") == "yes"


def required(ctx, definition):
    from admiralty.extract.computed.capital_tier import required_tier

    return required_tier(ctx, definition)


def test_building_unlock_obstacles_are_checked_on_the_reference_saves(extractor):
    from admiralty.graph.mechanics import MechanicsGraph
    from admiralty.graph.metrics import evaluate

    graph = MechanicsGraph.load()

    def state(node, campaign_save):
        doc = extract(extractor, *campaign_save)
        return evaluate(graph.node(node)["check"], graph.metrics, doc).state

    early, late = (VULKAN, "2298.03.11.sav"), (ZYGERRIAN, "2363.04.17.sav")
    assert state("energy.generator_building_locked", early) == "present"  # Power Hub 2 missing
    assert state("energy.generator_building_locked", late) == "clear"
    assert state("food.processing_locked", late) == "present"  # Advanced Food Processing missing
    assert state("minerals.purification_locked", late) == "clear"
    assert state("research.lab_locked", early) == "present"
    assert state("research.lab_locked", late) == "clear"
    assert state("unity.building_locked", early) == "present"  # only_present, technologies lacking
    assert state("naval_capacity.office_needs_technology", early) == "present"
    assert state("naval_capacity.office_needs_technology", late) == "judgement"  # only_present
    assert state("slots.capital_upgrade_locked", late) == "present"  # Galactic Administration


CHECKED_BY_THE_OBSTACLE_PLAN = (
    # docs/plans/obstacle-checks.md, groups 1 to 4 (the 4 unlocks with a named reason stay grey)
    "influence.no_ascension_slot",
    "unity.no_ascension_slot",
    "naval_capacity.tradition_slot_taken",
    "research.discovery_tree_unfinished",
    "amenities.no_amenity_slot",
    "stability.no_order_slot",
    "pop_growth.no_free_housing",
    "influence.decree_locked",
    "naval_capacity.doctrine_prerequisites",
    "pop_growth.growth_tech_locked",
    "pop_growth.assembly_locked",
    "energy.generator_building_locked",
    "food.processing_locked",
    "minerals.purification_locked",
    "research.lab_locked",
    "unity.building_locked",
    "housing.dwelling_locked",
    "naval_capacity.office_needs_technology",
    "slots.capital_upgrade_locked",
    # group 4, the seven planet-level slot Obstacles with a family (amenities stays grey: no
    # amenity building is buildable for either reference empire)
    "jobs.no_building_room",
    "alloys.no_foundry_slot",
    "research.no_lab_slot",
    "unity.no_building_slot",
    "stability.no_building_slot",
    "housing.no_building_slot",
    "pop_growth.no_growth_building_slot",
)

REFERENCE_SAVES = (
    (VULKAN, "2220.04.22.sav"),
    (VULKAN, "2298.03.11.sav"),
    (ZYGERRIAN, "2271.08.25.sav"),
    (ZYGERRIAN, "2363.04.17.sav"),
)


@pytest.mark.parametrize("campaign_save", REFERENCE_SAVES)
def test_no_checked_obstacle_is_unknown_on_the_reference_saves(extractor, campaign_save):
    """A check whose metric has no value in the extract reports `unknown`; on the reference
    saves every Obstacle with a metric check must have its number."""
    from admiralty.graph.mechanics import MechanicsGraph
    from admiralty.graph.metrics import evaluate

    graph = MechanicsGraph.load()
    doc = extract(extractor, *campaign_save)
    unknown = [
        node_id
        for node_id in graph.nodes
        if graph.node(node_id).get("type") == "obstacle"
        and not graph.node(node_id)["check"].get("judgement_only")
        and evaluate(graph.node(node_id)["check"], graph.metrics, doc).state == "unknown"
    ]
    assert unknown == []


def test_the_planned_obstacles_have_a_metric_check():
    from admiralty.graph.mechanics import MechanicsGraph

    graph = MechanicsGraph.load()
    grey = [n for n in CHECKED_BY_THE_OBSTACLE_PLAN if graph.node(n)["check"].get("judgement_only")]
    assert grey == []
