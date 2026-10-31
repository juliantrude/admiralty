"""Snapshot evidence for the Mastery Levels (M9, 20c): Apply, `ask_once`, Create, the drop and the Crisis flag.

Synthetic packs and extracts; the vulkan saves are used for the real pack's coverage and a smoke run.
"""

from __future__ import annotations

import copy

import pytest
from conftest import reference_save
from test_mechanics_graph import GRAPH, METRICS, node, write_pack

from admiralty.graph.mechanics import MechanicsGraph
from admiralty.graph.metrics import resolve_metric
from admiralty.player import evidence, store
from admiralty.player.evidence import (
    coverage,
    crisis,
    evaluate_snapshots,
    record_evidence,
    remedies_shown,
)

CONCEPT = "naval_capacity.few_sources"
REMEDY = "naval_capacity.adopt_supremacy"
OTHER = "naval_capacity.take_one_vision"


def pack(tmp_path, *, present=True, applied=True, second=True):
    graph = copy.deepcopy(GRAPH)
    metrics = copy.deepcopy(METRICS)
    metrics["metrics"]["traditions.supremacy_tree"] = {
        "contains": {"path": "progression.tradition_trees", "label": "Supremacy"},
        "unit": "1 when adopted",
    }
    metrics["metrics"]["perks.one_vision"] = {
        "contains": {"path": "progression.ascension_perks", "label": "One Vision"},
        "unit": "1 when taken",
    }
    cause, remedy = node(graph, "few_sources"), node(graph, "adopt_supremacy")
    if applied:
        remedy["applied_when"] = {
            "metric": "traditions.supremacy_tree",
            "op": "==",
            "compare_to": 1,
        }
    if present:
        cause["present_when"] = {"metric": "naval_capacity.fill", "op": ">=", "compare_to": 0.9}
    if second:
        twin = copy.deepcopy(remedy)
        twin.update(id=OTHER, title="Take One Vision")
        twin["applied_when"] = {"metric": "perks.one_vision", "op": "==", "compare_to": 1}
        graph["nodes"].append(twin)
        cause["remedies"].append(OTHER)
    return MechanicsGraph.load("4.5.2", write_pack(tmp_path, graph=graph, metrics=metrics))


def extract(*, trees=(), perks=(), fill=0.5, **resources):
    document = {
        "progression": {"tradition_trees": list(trees), "ascension_perks": list(perks)},
        "naval_capacity": {"used": fill * 100, "max": 100},
        "resources": {},
    }
    for name, (net, stock) in resources.items():
        document["resources"][name] = {"net": net, "stockpile": stock}
    return document


def state(level="understand", peak=None, last=None, **extra):
    return {
        "level": level,
        "peak": peak or level,
        "last_change": {"date": last} if last else None,
        "drops": 0,
        "hatch_uses": 0,
        **extra,
    }


def kinds(effects):
    return [(e["effect"], e.get("level")) for e in effects]


# --- the metric kind behind the Remedies ---------------------------------------------------------


def test_contains_metric_is_one_when_the_label_is_listed_zero_when_not_none_without_a_list():
    spec = {"contains": {"path": "progression.ascension_perks", "label": "One Vision"}}
    assert resolve_metric(spec, {"progression": {"ascension_perks": ["One Vision"]}}) == 1
    assert resolve_metric(spec, {"progression": {"ascension_perks": ["Other"]}}) == 0
    assert resolve_metric(spec, {"progression": {}}) is None


# --- the Crisis flag --------------------------------------------------------------------------------


def test_crisis_is_a_negative_net_whose_stockpile_lasts_under_twelve_months():
    result = crisis(extract(energy=(-100, 1100), minerals=(-100, 1200), alloys=(5, 0)))
    assert result["crisis"] is True
    assert [r["resource"] for r in result["resources"]] == ["energy"]
    assert result["resources"][0]["reserve_months"] == 11.0


def test_no_crisis_for_a_positive_net_a_long_reserve_or_a_resource_that_does_not_count():
    assert crisis(extract(energy=(-100, 1200)))["crisis"] is False  # exactly twelve months
    assert crisis(extract(energy=(10, 0)))["crisis"] is False
    assert crisis(extract(trade=(-50, 0), unity=(-5, 0)))["crisis"] is False
    assert crisis(extract(food=(None, 5)))["crisis"] is False
    assert crisis({})["crisis"] is False


def test_an_empty_stockpile_with_a_negative_net_is_a_crisis():
    result = crisis(extract(influence=(-0.5, 0)))
    assert result["crisis"] and result["resources"][0]["reserve_months"] == 0


# --- shown and present --------------------------------------------------------------------------------


def test_remedies_shown_lists_the_remedies_whose_applied_when_holds(tmp_path):
    graph = pack(tmp_path)
    assert remedies_shown(graph, CONCEPT, extract()) == []
    assert remedies_shown(graph, CONCEPT, extract(trees=["Supremacy"])) == [REMEDY]
    both = extract(trees=["Supremacy"], perks=["One Vision"])
    assert remedies_shown(graph, CONCEPT, both) == [REMEDY, OTHER]


def test_presence_is_unmeasured_without_present_when_and_unknown_without_the_metric(tmp_path):
    assert evidence.cause_presence(pack(tmp_path / "a", present=False), CONCEPT, extract()) == (
        "unmeasured"
    )
    graph = pack(tmp_path / "b")
    assert evidence.cause_presence(graph, CONCEPT, extract(fill=0.95)) == "present"
    assert evidence.cause_presence(graph, CONCEPT, extract(fill=0.5)) == "clear"
    assert evidence.cause_presence(graph, CONCEPT, {}) == "unknown"


# --- Apply and ask_once ---------------------------------------------------------------------------------


def run(graph, level="understand", **kw):
    snaps = kw.pop("snaps")
    return evaluate_snapshots(graph, CONCEPT, state(level, **kw.pop("state", {})), snaps, **kw)


def test_a_remedy_shown_after_the_topic_was_raised_lifts_understand_to_apply(tmp_path):
    graph = pack(tmp_path)
    snaps = [
        ("2250.01.01", extract()),
        ("2252.06.01", extract()),
        ("2254.03.15", extract(trees=["Supremacy"])),
    ]
    effects = run(graph, snaps=snaps, raised="2250.01.01")
    assert kinds(effects) == [("level", "apply")]
    assert effects[0]["date"] == "2254.03.15" and REMEDY in effects[0]["reason"]


def test_a_remedy_already_shown_when_the_topic_was_raised_is_no_answer_to_it(tmp_path):
    graph = pack(tmp_path)
    snaps = [
        ("2250.01.01", extract(trees=["Supremacy"])),
        ("2252.01.01", extract(trees=["Supremacy"])),
    ]
    assert run(graph, snaps=snaps, raised="2250.01.01") == []


def test_a_remedy_shown_after_the_five_year_window_does_not_count_and_asks_once(tmp_path):
    graph = pack(tmp_path)
    snaps = [
        ("2250.01.01", extract()),
        ("2255.06.01", extract(trees=["Supremacy"])),  # five years and five months later
    ]
    effects = run(graph, snaps=snaps, raised="2250.01.01")
    assert kinds(effects) == [("ask_once", None)] and effects[0]["raised"] == "2250.01.01"


def test_the_window_includes_its_last_day(tmp_path):
    graph = pack(tmp_path)
    snaps = [("2250.01.01", extract()), ("2255.01.01", extract(trees=["Supremacy"]))]
    assert kinds(run(graph, snaps=snaps, raised="2250.01.01")) == [("level", "apply")]


def test_inside_the_window_without_the_remedy_nothing_happens_yet(tmp_path):
    graph = pack(tmp_path)
    snaps = [("2250.01.01", extract()), ("2253.01.01", extract())]
    assert run(graph, snaps=snaps, raised="2250.01.01") == []


def test_without_a_snapshot_of_the_raising_nothing_is_decided(tmp_path):
    graph = pack(tmp_path)
    snaps = [("2252.01.01", extract(trees=["Supremacy"]))]
    assert run(graph, snaps=snaps, raised="2250.01.01") == []
    assert run(graph, snaps=snaps, raised=None) == []


def test_only_understand_is_lifted_to_apply(tmp_path):
    graph = pack(tmp_path)
    snaps = [("2250.01.01", extract()), ("2252.01.01", extract(trees=["Supremacy"]))]
    for level in ("new", "apply", "analyse"):
        assert run(graph, level, snaps=snaps, raised="2250.01.01") == []


def test_a_cause_without_any_applied_when_never_reaches_apply_and_never_asks_early(tmp_path):
    graph = pack(tmp_path, applied=False, second=False)
    snaps = [("2250.01.01", extract()), ("2252.01.01", extract(trees=["Supremacy"]))]
    assert run(graph, snaps=snaps, raised="2250.01.01") == []


def test_snapshots_may_come_in_any_order(tmp_path):
    graph = pack(tmp_path)
    snaps = [("2252.01.01", extract(trees=["Supremacy"])), ("2250.01.01", extract())]
    assert kinds(run(graph, snaps=snaps, raised="2250.01.01")) == [("level", "apply")]


# --- Create ---------------------------------------------------------------------------------------------


CREATE_SNAPS = [
    ("2250.01.01", extract()),
    ("2252.01.01", extract(trees=["Supremacy"])),  # first application
    ("2255.01.01", extract(trees=["Supremacy"], perks=["One Vision"])),  # second application
    ("2260.01.01", extract(trees=["Supremacy"], perks=["One Vision"])),
]


def test_two_unprompted_applications_and_five_quiet_years_lift_apply_to_create(tmp_path):
    graph = pack(tmp_path)
    effects = run(graph, "apply", snaps=CREATE_SNAPS)
    assert kinds(effects) == [("level", "create")]
    assert effects[0]["date"] == "2260.01.01" and "twice without prompting" in effects[0]["reason"]


def test_a_drill_topic_on_the_cause_before_an_application_makes_it_prompted(tmp_path):
    graph = pack(tmp_path)
    assert run(graph, "apply", snaps=CREATE_SNAPS, prompts=["2251.06.01"]) == []
    # a topic raised long before the five-year window leaves the application unprompted
    assert kinds(run(graph, "apply", snaps=CREATE_SNAPS, prompts=["2240.01.01"])) == [
        ("level", "create")
    ]


def test_create_waits_for_the_full_five_years_after_the_second_application(tmp_path):
    graph = pack(tmp_path)
    assert run(graph, "apply", snaps=CREATE_SNAPS[:3]) == []
    short = [*CREATE_SNAPS[:3], ("2259.12.30", extract(trees=["Supremacy"], perks=["One Vision"]))]
    assert run(graph, "apply", snaps=short) == []


def test_the_cause_reappearing_inside_the_five_years_blocks_create(tmp_path):
    graph = pack(tmp_path)
    snaps = [
        *CREATE_SNAPS[:3],
        ("2257.01.01", extract(trees=["Supremacy"], perks=["One Vision"], fill=0.95)),
        CREATE_SNAPS[3],
    ]
    assert run(graph, "apply", snaps=snaps) == []


def test_create_needs_a_cause_the_snapshots_can_see(tmp_path):
    graph = pack(tmp_path, present=False)
    assert run(graph, "apply", snaps=CREATE_SNAPS) == []


@pytest.mark.parametrize("level", ["new", "understand", "create"])
def test_create_needs_apply_or_better_and_stops_at_create(tmp_path, level):
    graph = pack(tmp_path)
    assert run(graph, level, snaps=CREATE_SNAPS) == []


def test_one_application_that_stays_on_counts_once(tmp_path):
    graph = pack(tmp_path, second=False)
    snaps = [
        ("2250.01.01", extract()),
        ("2252.01.01", extract(trees=["Supremacy"])),
        ("2260.01.01", extract(trees=["Supremacy"])),
    ]
    assert run(graph, "apply", snaps=snaps) == []


def test_a_remedy_undone_and_done_again_is_applied_twice(tmp_path):
    graph = pack(tmp_path, second=False)
    snaps = [
        ("2250.01.01", extract()),
        ("2252.01.01", extract(trees=["Supremacy"])),
        ("2253.01.01", extract()),
        ("2254.01.01", extract(trees=["Supremacy"])),
        ("2259.06.01", extract(trees=["Supremacy"])),
    ]
    assert kinds(run(graph, "apply", snaps=snaps)) == [("level", "create")]


# --- the drop ---------------------------------------------------------------------------------------------


HIGH = extract(fill=0.95)


def test_the_cause_in_two_snapshots_a_year_apart_drops_one_level(tmp_path):
    graph = pack(tmp_path)
    effects = run(graph, "apply", snaps=[("2250.01.01", HIGH), ("2251.01.01", HIGH)])
    assert kinds(effects) == [("drop", "understand")]
    assert effects[0]["announce"] is True and effects[0]["date"] == "2251.01.01"
    assert effects[0]["previous"] == "apply"


def test_359_days_are_not_a_year(tmp_path):
    graph = pack(tmp_path)
    assert run(graph, "apply", snaps=[("2250.01.01", HIGH), ("2250.12.30", HIGH)]) == []
    assert kinds(run(graph, "apply", snaps=[("2250.01.01", HIGH), ("2251.01.01", HIGH)])) == [
        ("drop", "understand")
    ]


def test_a_crisis_in_either_snapshot_cancels_the_pair(tmp_path):
    graph = pack(tmp_path)
    hard = extract(fill=0.95, energy=(-100, 500))
    assert run(graph, "apply", snaps=[("2250.01.01", hard), ("2251.01.01", HIGH)]) == []
    assert run(graph, "apply", snaps=[("2250.01.01", HIGH), ("2251.01.01", hard)]) == []


def test_a_clear_snapshot_between_does_not_hide_the_pair(tmp_path):
    graph = pack(tmp_path)
    snaps = [("2250.01.01", HIGH), ("2250.07.01", extract()), ("2251.01.01", HIGH)]
    assert kinds(run(graph, "apply", snaps=snaps)) == [("drop", "understand")]


def test_snapshots_before_the_last_change_do_not_count(tmp_path):
    graph = pack(tmp_path)
    snaps = [("2250.01.01", HIGH), ("2251.01.01", HIGH)]
    assert run(graph, "apply", snaps=snaps, state={"last": "2250.01.01"}) == []
    assert run(graph, "apply", snaps=snaps, state={"last": "2249.12.30"}) != []


def test_new_has_nothing_to_drop_and_a_cause_without_present_when_never_drops(tmp_path):
    snaps = [("2250.01.01", HIGH), ("2251.01.01", HIGH)]
    assert run(pack(tmp_path / "a"), "new", snaps=snaps) == []
    assert run(pack(tmp_path / "b", present=False), "apply", snaps=snaps) == []


def test_one_call_moves_one_level_however_many_snapshots_agree(tmp_path):
    graph = pack(tmp_path)
    snaps = [(f"{y}.01.01", HIGH) for y in range(2250, 2256)]
    assert kinds(run(graph, "evaluate", snaps=snaps)) == [("drop", "analyse")]


# --- recording --------------------------------------------------------------------------------------------


def test_record_writes_the_level_and_a_second_run_writes_nothing(tmp_path):
    graph = pack(tmp_path / "pack")
    base = tmp_path / "data"
    store.append(
        "level", concept=CONCEPT, level="understand", reason="seed", date="2250.01.01", base=base
    )
    snaps = [("2250.01.01", extract()), ("2252.01.01", extract(trees=["Supremacy"]))]
    first = record_evidence(
        graph, CONCEPT, snaps, raised="2250.01.01", campaign="vulkan", base=base
    )
    assert [e["kind"] for e in first["events"]] == ["level"]
    assert first["state"]["level"] == "apply"
    assert first["events"][0]["date"] == "2252.01.01" and first["events"][0]["campaign"] == "vulkan"
    second = record_evidence(graph, CONCEPT, snaps, raised="2250.01.01", base=base)
    assert second["events"] == [] and second["effects"] == []


def test_record_notes_ask_once_only_once(tmp_path):
    graph = pack(tmp_path / "pack")
    base = tmp_path / "data"
    store.append(
        "level", concept=CONCEPT, level="understand", reason="seed", date="2250.01.01", base=base
    )
    snaps = [("2250.01.01", extract()), ("2256.01.01", extract())]
    first = record_evidence(graph, CONCEPT, snaps, raised="2250.01.01", base=base)
    assert [e["kind"] for e in first["events"]] == ["note"] and first["events"][0]["ask_once"]
    again = record_evidence(graph, CONCEPT, snaps, raised="2250.01.01", base=base)
    assert again["events"] == []
    assert store.read_model(base)["concepts"][CONCEPT]["level"] == "understand"


def test_record_a_drop_counts_in_the_model(tmp_path):
    graph = pack(tmp_path / "pack")
    base = tmp_path / "data"
    store.append(
        "level", concept=CONCEPT, level="apply", reason="seed", date="2240.01.01", base=base
    )
    result = record_evidence(
        graph, CONCEPT, [("2250.01.01", HIGH), ("2251.01.01", HIGH)], base=base
    )
    assert result["state"]["level"] == "understand" and result["state"]["drops"] == 1
    assert result["state"]["last_change"]["date"] == "2251.01.01"
    assert (
        record_evidence(graph, CONCEPT, [("2250.01.01", HIGH), ("2251.01.01", HIGH)], base=base)[
            "events"
        ]
        == []
    )


# --- the real pack ------------------------------------------------------------------------------------------


def test_the_real_pack_covers_what_the_extract_can_show():
    """Coverage as logged in GOAL.md: most Remedies stay unseen by a Snapshot, and the Coach asks instead."""
    result = coverage(MechanicsGraph.load("4.5.2"))
    assert result["remedies"] == 65 and result["causes"] == 35
    assert len(result["applied_when"]) == 8 and len(result["present_when"]) == 4
    assert result["causes_with_apply"] == [
        "influence.diplomatic_upkeep",
        "influence.few_sources",
        "naval_capacity.low_base_sources",
        "naval_capacity.weak_multipliers",
        "pop_growth.slow_rate",
        "research.slow_research_speed",
        "unity.weak_multipliers",
    ]


def test_every_contains_label_is_a_display_name_of_the_game_files():
    from admiralty.game import GameEnvironment

    try:
        root = GameEnvironment.detect().install_dir / "localisation" / "english"
    except Exception:
        pytest.skip("no Stellaris install")
    if not root.is_dir():
        pytest.skip("no Stellaris install")
    text = "\n".join(path.read_text(encoding="utf-8-sig") for path in root.glob("*.yml"))
    graph = MechanicsGraph.load("4.5.2")
    labels = [m["contains"]["label"] for m in graph.metrics.values() if "contains" in m]
    assert labels
    for label in labels:
        assert f'"{label}"' in text, f"{label!r} is in no English localisation file"


def test_the_real_pack_on_the_vulkan_mid_save():
    from admiralty.extract.snapshot import Extractor

    document = Extractor().extract(str(reference_save("vulkan", "2259.12.25.sav")), "Plexxi")
    graph = MechanicsGraph.load("4.5.2")
    shown = {c: remedies_shown(graph, c, document) for c in coverage(graph)["causes_with_apply"]}
    # the mid save has the Supremacy tree and Fleet Logistics Corps, a Discovery tree not finished
    assert shown["naval_capacity.low_base_sources"] == ["naval_capacity.adopt_supremacy"]
    assert shown["naval_capacity.weak_multipliers"] == ["naval_capacity.fleet_logistics_corps"]
    assert shown["pop_growth.slow_rate"] == ["pop_growth.growth_techs"]
    assert shown["research.slow_research_speed"] == []
    assert crisis(document)["crisis"] is False
