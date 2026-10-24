"""The generated facts (M4): known facts pinned against the game files and the committed YAML.

Two layers, as in docs/plans/M4.md: the committed knowledge/4.5.2/generated/*.yaml is what the
graph links to and is tested without the game install; a regeneration test (skipped without the
install) shows the files are current and the generator is deterministic.
"""

from __future__ import annotations

import re
import sys
from functools import cache
from pathlib import Path

import pytest
import yaml

from hlidskjalf.gamefiles import GameData
from hlidskjalf.gamefiles.script import parse
from hlidskjalf.graph.generator import (
    _walk,
    game_version,
    generate,
    load_allow_list,
    render_conditions,
    render_quantity,
)
from hlidskjalf.graph.quantities import QUANTITIES, QUANTITY_IDS

ROOT = Path(__file__).resolve().parent.parent
GENERATED = ROOT / "knowledge" / "4.5.2" / "generated"
ALLOW_UNNAMED = ROOT / "tools" / "gen_mechanics_allow_unnamed.txt"


@cache
def _document(quantity: str) -> dict:
    # the C loader: 3.5 MB of YAML takes seconds with the pure Python one
    text = (GENERATED / f"{quantity}.yaml").read_text(encoding="utf-8")
    return yaml.load(text, Loader=yaml.CSafeLoader)


def facts(quantity: str) -> dict[str, dict]:
    document = _document(quantity)
    assert document["quantity"] == quantity
    return {fact["id"]: fact for fact in document["facts"]}


# --- committed facts -------------------------------------------------------------------------


def test_every_quantity_has_a_file_with_facts():
    for quantity in QUANTITY_IDS:
        assert facts(quantity), quantity


def test_supremacy_adoption_gives_twenty_naval_capacity():
    fact = facts("naval_capacity")[
        "naval_capacity.tradition.tr_supremacy_adopt.country_naval_cap_add"
    ]
    assert (fact["amount"], fact["amount_kind"], fact["effect"]) == (20, "add", "modifies")
    assert fact["source"]["name"] == "Supremacy Traditions"
    assert fact["source"]["file"] == "common/traditions/00_supremacy.txt"
    assert fact["requirement"] is None


def test_fleet_logistics_corps_is_a_multiplier():
    fact = facts("naval_capacity")[
        "naval_capacity.tradition.tr_supremacy_fleet_logistical_corps.country_naval_cap_mult"
    ]
    assert (fact["amount"], fact["amount_kind"]) == (0.2, "mult")


def test_anchorage_gives_five_and_the_logistics_office_three_more():
    naval = facts("naval_capacity")
    base = naval["naval_capacity.starbase_module.anchorage.country_naval_cap_add"]
    assert (base["amount"], base["amount_kind"], base["source"]["name"]) == (
        5,
        "per_unit",
        "Anchorage",
    )
    office = naval["naval_capacity.starbase_module.anchorage.country_naval_cap_add#2"]
    assert office["amount"] == 3
    assert "has_starbase_building = naval_logistics_office" in office["requirement"]


def test_naval_capacity_technology_is_a_repeatable_with_levels():
    fact = facts("naval_capacity")[
        "naval_capacity.technology.tech_repeatable_naval_cap.country_naval_cap_add"
    ]
    assert fact["amount"] == 20
    assert fact["source"]["name"] == "Fleet Management Procedures"
    assert fact["source"]["levels"] == 5
    assert "has_technology = tech_doctrine_navy_size_4" in fact["requirement"]


def test_soldier_job_gives_naval_capacity_per_job():
    naval = facts("naval_capacity")
    base = naval["naval_capacity.job.soldier.country_naval_cap_add"]
    assert (base["amount"], base["amount_kind"], base["source"]["name"]) == (
        4,
        "per_unit",
        "Soldier",
    )
    bellicose = [
        fact
        for fact in naval.values()
        if fact["source"]["key"] == "soldier"
        and fact.get("scaled_by") == "value:bellicose_naval_cap"
    ]
    assert bellicose, "the bellicose-councilor bonus keeps its scaling value"


def test_resource_blocks_become_produces_and_costs_facts():
    energy = facts("energy")
    technician = energy["energy.job.technician.produces_energy"]
    assert (technician["effect"], technician["amount_kind"]) == ("produces", "per_unit")
    assert any(
        f["effect"] == "costs" and f["modifier"].startswith("upkeep_") for f in energy.values()
    )


def test_building_slots_come_from_zones():
    kinds = {fact["source"]["kind"] for fact in facts("building_slots").values()}
    assert "zone" in kinds


def test_every_fact_has_a_display_name_that_is_not_a_key():
    key_like = re.compile(r"[a-z0-9_]+")
    for quantity in QUANTITY_IDS:
        for fact in facts(quantity).values():
            name = fact["source"]["name"]
            assert name and not key_like.fullmatch(name), (fact["id"], name)


def test_ids_follow_the_format_and_are_unique():
    for quantity in QUANTITY_IDS:
        found = facts(quantity)
        for fact_id, fact in found.items():
            source = fact["source"]
            expected = f"{quantity}.{source['kind']}.{source['key']}.{fact['modifier']}"
            assert fact_id == expected or re.fullmatch(re.escape(expected) + r"#\d+", fact_id)
        assert len(found) == len(_document(quantity)["facts"]), "duplicate fact ids"


def test_no_unresolved_names_are_left_behind():
    assert not (GENERATED / "unresolved.txt").exists()


# --- the rules of the walk, on synthetic definitions ----------------------------------------


def hits(definition: dict) -> list[tuple[str, str, object, tuple[str, ...]]]:
    return [
        (hit.quantity.id, hit.modifier, hit.value, hit.requirement)
        for hit in _walk(definition, (), None, False)
    ]


def test_conditions_are_flattened_and_not_evaluated():
    block = {
        "owner": {"has_technology": "tech_x", "num_pops>": 5},
        "OR": {"is_ai": "yes", "has_ethic": "ethic_materialist"},
        "NOT": {"has_trait": "trait_a"},
    }
    assert render_conditions(block) == [
        "owner: has_technology = tech_x",
        "owner: num_pops > 5",
        "OR(is_ai = yes ; has_ethic = ethic_materialist)",
        "NOT(has_trait = trait_a)",
    ]


def test_deeply_nested_conditions_are_marked_unmodelled():
    deep = {"a": {"b": {"c": {"d": {"e": {"f": "g"}}}}}}
    assert (
        render_conditions(deep)[0].endswith("unmodelled: e")
        or "unmodelled" in render_conditions(deep)[0]
    )


def test_a_trigger_applies_to_the_entries_of_its_block_only():
    definition = parse(
        """
        potential = { is_ai = no }
        resources = {
            category = planet_jobs
            produces = { energy = 3 }
            upkeep = { minerals = 1 }
            upkeep = { trigger = { has_x = yes } minerals = 2 }
        }
        """
    )
    found = hits(definition)
    assert ("energy", "produces_energy", 3, ("is_ai = no",)) in found
    assert ("minerals", "upkeep_minerals", 1, ("is_ai = no",)) in found
    assert ("minerals", "upkeep_minerals", 2, ("is_ai = no", "has_x = yes")) in found


def test_modifier_keys_and_ai_weights_are_told_apart():
    definition = {
        "modifier": {"country_naval_cap_add": 20, "army_damage_mult": 0.2},
        "ai_weight": {"weight": 1, "country_naval_cap_add": 99},
        "triggered_country_modifier": {
            "potential": {"has_x": "yes"},
            "country_naval_cap_add": "@some_variable",
            "mult": "value:scaling",
        },
    }
    assert hits(definition) == [
        ("naval_capacity", "country_naval_cap_add", 20, ()),
        ("naval_capacity", "country_naval_cap_add", "@some_variable", ("has_x = yes",)),
    ]


@pytest.mark.parametrize(
    ("quantity", "key", "counts"),
    [
        ("energy", "country_energy_produces_mult", True),
        ("energy", "planet_technician_energy_produces_add", True),
        ("energy", "weapon_type_energy_weapon_damage_mult", False),
        ("food", "planet_pops_organics_food_upkeep_mult", True),
        ("research", "country_physics_research_produces_mult", True),
        ("research", "all_technology_research_speed", True),
        ("research", "category_biology_research_speed_mult", False),
        ("housing", "planet_housing_add", True),
        ("district_slots", "planet_max_districts_add", True),
        ("stability", "planet_stability_add", True),
        ("naval_capacity", "mod_ship_naval_cap_usage_mult", False),
    ],
)
def test_quantity_key_tables(quantity, key, counts):
    assert QUANTITIES[quantity].modifier(key) is counts


# --- regeneration against the game install ---------------------------------------------------


@pytest.fixture(scope="module")
def regenerated():
    from hlidskjalf.extract.names import Localisation
    from hlidskjalf.game import GameEnvironment

    try:
        env = GameEnvironment.detect()
    except FileNotFoundError:
        pytest.skip("Stellaris installation not found (set HLIDSKJALF_GAME_DIR)")
    if game_version(env.install_dir) != "v4.5.2":
        pytest.skip("the installed game is not 4.5.2; the committed facts are for 4.5.2")
    game = GameData(env.install_dir)
    loc = Localisation.from_files(env.localisation_files())
    return generate(game, loc, load_allow_list(ALLOW_UNNAMED))


def test_committed_facts_match_the_game_files(regenerated):
    assert not regenerated.unresolved
    for quantity in QUANTITY_IDS:
        committed = (GENERATED / f"{quantity}.yaml").read_text(encoding="utf-8")
        assert render_quantity(regenerated, quantity) == committed, (
            f"{quantity}.yaml is stale: run `uv run python tools/gen_mechanics.py`"
        )


def test_known_facts_hold_in_the_raw_game_files():
    """Pin the numbers to the game files themselves, not only to our output."""
    from hlidskjalf.game import GameEnvironment

    try:
        game = GameData(GameEnvironment.detect().install_dir)
    except FileNotFoundError:
        pytest.skip("Stellaris installation not found (set HLIDSKJALF_GAME_DIR)")
    assert (
        game.category("traditions")["tr_supremacy_adopt"]["modifier"]["country_naval_cap_add"] == 20
    )
    anchorage = game.category("starbase_modules")["anchorage"]
    assert anchorage["country_modifier"]["country_naval_cap_add"] == 5
    assert anchorage["triggered_country_modifier"]["country_naval_cap_add"] == 3
    assert (
        game.category("technology")["tech_repeatable_naval_cap"]["modifier"][
            "country_naval_cap_add"
        ]
        == 20
    )


def test_generator_script_is_importable_without_side_effects():
    sys.path.insert(0, str(ROOT / "tools"))
    try:
        import gen_mechanics
    finally:
        sys.path.remove(str(ROOT / "tools"))
    assert callable(gen_mechanics.main)
