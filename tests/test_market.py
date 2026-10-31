"""The market domain: the extract section on standing trades, the graph and the clone vat link.

The trades in the reference saves were read from the raw save blocks (`market.monthly_trades`),
not from our extractor: vulkan 2259.12.25 has a standing purchase of 70 Energy Credits and a
standing sale of 100 Minerals per month.
"""

from __future__ import annotations

import pytest

from admiralty.extract.snapshot import Extractor
from admiralty.graph.expand import expand_graph
from admiralty.graph.mechanics import MechanicsGraph

GOAL = "market.steady_trade"


@pytest.fixture(scope="module")
def graph() -> MechanicsGraph:
    return MechanicsGraph.load("v4.5.2")


@pytest.fixture(scope="module")
def mid_extract():
    from conftest import MID, VULKAN, reference_save

    return Extractor().extract(str(reference_save(VULKAN, MID)), "Plexxi")


@pytest.fixture(scope="module")
def early_extract():
    from conftest import EARLY, VULKAN, reference_save

    return Extractor().extract(str(reference_save(VULKAN, EARLY)), "Plexxi")


# --- extract ----------------------------------------------------------------------------------


def test_the_standing_trades_of_the_empire_are_listed(mid_extract):
    market = mid_extract["market"]
    assert market["buys"] == {"Energy Credits": 70}
    assert market["sells"] == {"Minerals": 100}
    assert market["count"] == 2


def test_cover_is_stock_divided_by_the_monthly_amount(mid_extract):
    market = mid_extract["market"]
    minerals = mid_extract["resources"]["Minerals".lower()]["stockpile"]
    assert market["sell_cover"] == pytest.approx(minerals / 100, abs=0.1)
    assert market["buy_cover"] > 0, "the purchase drains trade value every month"


def test_no_standing_trade_means_no_cover_to_judge_and_nothing_short(early_extract):
    market = early_extract["market"]
    assert market["count"] == 0
    assert "sell_cover" not in market
    assert "buy_cover" not in market
    assert market["short"] == 0


# --- graph ------------------------------------------------------------------------------------


def test_the_goal_is_a_flag_and_reaches_remedies_with_obstacles(graph):
    assert graph.goal(GOAL)["mark"] == "flag"
    found = graph.reachable(GOAL)
    remedies = [n for n in found if graph.node(n)["type"] == "remedy"]
    assert {"market.drop_standing_trades", "market.keep_reserve", "market.cut_trade_fee"} <= set(
        remedies
    )
    assert "food.staff_farmers" in found, "a deficit the trade covered is fixed in production"


def test_the_fee_remedy_links_the_facts_that_lower_the_fee(graph):
    amounts = {f["id"]: f["amount"] for f in graph.node_facts("market.cut_trade_fee")}
    assert amounts["market.tradition.tr_logistics_4.country_trade_fee"] == -0.1
    assert amounts["market.building.building_galactic_stock_exchange.country_trade_fee"] == -0.05
    assert len(amounts) == 4


def test_clone_vats_are_a_cause_of_the_food_balance(graph):
    assert "food.clone_vats_eat" in graph.goal("food.positive")["causes"]
    ids = {f["id"] for f in graph.node_facts("food.clone_vats_eat")}
    assert "food.building.building_clone_vats.upkeep_food" in ids
    assert "pop_growth.building.building_clone_vats.bonus_pop_growth" in ids
    assert "food.pace_clone_vats" in graph.reachable("food.positive")


def test_building_clone_vats_meets_the_food_deficit(graph):
    assert "pop_growth.food_deficit" in graph.node("pop_growth.growth_buildings")["obstacles"]


def test_the_market_is_reachable_from_the_food_goal_through_the_clone_vats(graph):
    assert "market.drop_standing_trades" in graph.reachable("food.positive")


# --- against a Snapshot -----------------------------------------------------------------------


def states(extract, graph):
    out = expand_graph(graph, [GOAL], extract)
    return {n["id"]: n.get("check", {}).get("state") for n in out.to_dict()["nodes"]}


def test_a_well_stocked_empire_has_no_stalled_trade(graph, mid_extract):
    found = states(mid_extract, graph)
    assert found["market.stock_short"] == "clear"
    assert found["market.deficit_returns"] == "judgement"


def test_a_stock_below_one_month_is_present(graph, mid_extract):
    short = {**mid_extract, "market": {**mid_extract["market"], "short": 1}}
    assert states(short, graph)["market.stock_short"] == "present"


def test_without_trades_the_stock_obstacles_are_clear_and_nothing_is_to_return(
    graph, early_extract
):
    found = states(early_extract, graph)
    assert found["market.stock_short"] == "clear"
    assert found["market.deficit_returns"] == "clear"
