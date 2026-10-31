"""The topic list of a Drill (M9, 20e): order, skips, the Player's Goals, Fair Play and the hidden answer.

Synthetic packs and extracts; the real pack is read for the lint and a smoke run on the vulkan mid save.
"""

from __future__ import annotations

import copy
import json

import pytest
from conftest import MID, VULKAN, reference_save
from test_mechanics_graph import GRAPH, METRICS, node, write_pack

from admiralty.academy import drill
from admiralty.academy.topics import TopicError, build_topics, is_hidden, metric_paths
from admiralty.graph.mechanics import MechanicsGraph

NAVAL = "naval_capacity.few_sources"
ENERGY = "energy.low_income"
HIDDEN_VALUE = 987654


def energy_graph(*, strength="low"):
    return {
        "version": "v4.5.2",
        "domain": "energy",
        "goals": [
            {
                "id": "energy.more",
                "title": "More energy income",
                "mark": "up",
                "symptom_metrics": ["energy.net"],
                "causes": [ENERGY],
            }
        ],
        "nodes": [
            {
                "id": ENERGY,
                "type": "cause",
                "title": "Too few power plants",
                "description": "Generators make the energy; there are not enough of them.",
                "remedies": ["energy.build_plants"],
            },
            {
                "id": "energy.build_plants",
                "type": "remedy",
                "title": "Build power plants",
                "judgement": "Cheap and quick.",
                "strength": strength,
                "speed": "high",
                "cost": "low",
            },
        ],
    }


def pack(tmp_path, *, strength="low", rivals=False):
    tmp_path = tmp_path / f"pack{sum(1 for _ in tmp_path.glob('pack*'))}"
    graph = copy.deepcopy(GRAPH)
    metrics = copy.deepcopy(METRICS)
    metrics["metrics"]["energy.net"] = {"path": "resources.energy.net", "unit": "energy/month"}
    metrics["metrics"]["energy.stockpile"] = {
        "path": "resources.energy.stockpile",
        "unit": "energy",
    }
    for entry in graph["nodes"]:
        entry.pop(
            "facts", None
        )  # the synthetic facts have no Display Name, `expand_graph` needs one
    cause = node(graph, "few_sources")
    cause["present_when"] = {"metric": "naval_capacity.fill", "op": ">=", "compare_to": 0.9}
    if rivals:
        metrics["metrics"]["rivals.power"] = {
            "path": "known_empires.full.military_power",
            "unit": "power",
        }
        metrics["metrics"]["rivals.seen"] = {
            "path": "known_empires.visible.military_power",
            "unit": "power",
        }
        cause["present_when"] = {"metric": "rivals.power", "op": ">", "compare_to": 0}
        graph["goals"][0]["symptom_metrics"].append("rivals.seen")
    return MechanicsGraph.load(
        "4.5.2",
        write_pack(
            tmp_path,
            graph=graph,
            metrics=metrics,
            extra={"energy.yaml": energy_graph(strength=strength)},
        ),
    )


def extract(*, fill=0.95, unity=100, cost=50, energy=(5, 400), date="2259.12.25", **more):
    document = {
        "header": {"date": date},
        "naval_capacity": {"used": fill * 100, "max": 100},
        "progression": {"next_tradition": {"cost": cost}},
        "resources": {
            "unity": {"stockpile": unity},
            "energy": {"net": energy[0], "stockpile": energy[1]},
        },
    }
    document.update(more)
    return document


def model(**levels):
    return {"concepts": {c: {"level": level} for c, level in levels.items()}}


def concepts(result):
    return [t["concept"] for t in result["topics"]]


def build(tmp_path, goals=("naval_capacity.more",), document=None, **options):
    options.setdefault("model", model())
    return build_topics(pack(tmp_path), document or extract(), goals, **options)


# --- order ------------------------------------------------------------------------------------------


def test_a_crisis_comes_first_even_when_the_player_did_not_name_its_goal(tmp_path):
    result = build(tmp_path, document=extract(energy=(-10, 20)))
    assert concepts(result) == [ENERGY, NAVAL]
    first, second = result["topics"]
    assert first["crisis"] and not second["crisis"]
    assert result["crisis"]["crisis"] and result["goals"] == ["energy.more", "naval_capacity.more"]


def test_a_stockpile_that_lasts_is_no_crisis(tmp_path):
    result = build(tmp_path, document=extract(energy=(-10, 5000)))
    assert concepts(result) == [NAVAL]
    assert not result["topics"][0]["crisis"]


def test_the_better_key_action_comes_first_and_an_obstructed_cause_last(tmp_path):
    goals = ("naval_capacity.more", "energy.more")
    # Unity covers the next tradition: both causes have an actionable Remedy, the better one first.
    mild = build_topics(pack(tmp_path, strength="low"), extract(), goals, model=model())
    assert concepts(mild) == [NAVAL, ENERGY]
    assert [t["weight"] for t in mild["topics"]] == [1, 2]
    # The energy Remedy is as strong and quicker now, so it ranks first.
    strong = build_topics(pack(tmp_path, strength="high"), extract(), goals, model=model())
    assert concepts(strong) == [ENERGY, NAVAL]
    assert [t["weight"] for t in strong["topics"]] == [1, 2]
    # Unity short of the cost: the naval Remedy is obstructed, the cause has no weight and comes last.
    blocked = build_topics(pack(tmp_path), extract(unity=1), goals, model=model())
    assert concepts(blocked) == [ENERGY, NAVAL]
    assert [t["weight"] for t in blocked["topics"]] == [1, None]


def test_the_order_is_the_same_every_time(tmp_path):
    graph = pack(tmp_path)
    goals = ("naval_capacity.more", "energy.more")
    runs = [build_topics(graph, extract(), goals, model=model()) for _ in range(3)]
    assert runs[0] == runs[1] == runs[2]
    assert build_topics(graph, extract(), goals[::-1], model=model())["topics"] == runs[0]["topics"]


# --- what is left out -------------------------------------------------------------------------------


@pytest.mark.parametrize("level", ["evaluate", "create"])
def test_a_concept_at_evaluate_or_above_is_skipped(tmp_path, level):
    result = build(tmp_path, model=model(**{NAVAL: level}))
    assert result["topics"] == [] and result["count"] == 0
    assert result["skipped"] == {"mastered": 1, "not_present": 0}


@pytest.mark.parametrize("level", ["new", "understand", "apply"])
def test_a_lower_level_stays_and_asks_the_usual_question(tmp_path, level):
    (topic,) = build(tmp_path, model=model(**{NAVAL: level}))["topics"]
    assert topic["level"] == level and topic["open_question"] is False


def test_a_concept_at_analyse_asks_an_open_question_only(tmp_path):
    (topic,) = build(tmp_path, model=model(**{NAVAL: "analyse"}))["topics"]
    assert topic["open_question"] is True


def test_a_cause_the_snapshot_does_not_show_is_not_a_topic(tmp_path):
    result = build(tmp_path, document=extract(fill=0.5))
    assert result["topics"] == [] and result["skipped"]["not_present"] == 1


def test_a_cause_without_a_presence_check_stays(tmp_path):
    (topic,) = build_topics(pack(tmp_path), extract(), ["energy.more"], model=model())["topics"]
    assert topic["concept"] == ENERGY


def test_a_cause_with_an_unknown_presence_stays(tmp_path):
    document = extract()
    del document["naval_capacity"]
    assert concepts(build(tmp_path, document=document)) == [NAVAL]


def test_unknown_goals_are_reported_and_no_known_goal_is_refused(tmp_path):
    result = build(tmp_path, goals=("naval_capacity.more", "nonsense.more"))
    assert result["unknown_goals"] == ["nonsense.more"] and concepts(result) == [NAVAL]
    with pytest.raises(TopicError, match="Goal"):
        build(tmp_path, goals=("nonsense.more",))
    with pytest.raises(TopicError):
        build(tmp_path, goals=())


def test_the_player_model_is_read_when_none_is_given(tmp_path):
    from admiralty.player import store

    store.append("level", concept=NAVAL, level="evaluate", previous="new", reason="test")
    result = build_topics(pack(tmp_path), extract(), ["naval_capacity.more"])
    assert result["topics"] == [] and result["skipped"]["mastered"] == 1


# --- the answer stays hidden ------------------------------------------------------------------------


def test_a_topic_names_neither_the_cause_nor_its_remedies(tmp_path):
    graph = pack(tmp_path)
    result = build_topics(graph, extract(), ["naval_capacity.more", "energy.more"], model=model())
    text = json.dumps(result["topics"]).lower()
    topic_ids = {t["concept"] for t in result["topics"]}
    for node_id, entry in graph.nodes.items():
        if (
            node_id not in topic_ids
        ):  # the concept id is the key and stays; 20h keeps it from the model
            assert node_id.lower() not in text, node_id
        assert entry["title"].lower() not in text, node_id
        assert entry.get("description", "x").strip().lower() not in text, node_id
    for topic in result["topics"]:
        assert not (set(topic) & {"title", "description", "remedies", "causes", "obstacles"})


def test_pointers_carry_the_presence_figure_and_the_goal_symptoms(tmp_path):
    (topic,) = build(tmp_path)["topics"]
    assert topic["pointers"] == [
        {"metric": "naval_capacity.fill", "value": 0.95, "unit": "fraction", "why": "presence"}
    ]
    (energy,) = build_topics(pack(tmp_path), extract(), ["energy.more"], model=model())["topics"]
    assert energy["pointers"] == [
        {"metric": "energy.net", "value": 5, "unit": "energy/month", "why": "symptom"}
    ]


# --- Fair Play --------------------------------------------------------------------------------------


def rival_extract():
    return extract(
        known_empires={
            "full": {"military_power": HIDDEN_VALUE},
            "visible": {"military_power": 321},
        }
    )


def test_a_path_is_hidden_when_it_reads_other_empires_without_their_visible_part():
    assert is_hidden("known_empires.full.military_power")
    assert is_hidden("known_empires.military_power")
    assert not is_hidden("known_empires.visible.military_power")
    assert not is_hidden("resources.energy.net")
    assert not is_hidden("empire.known_empires")


def test_metric_paths_cover_every_kind_of_metric():
    assert list(metric_paths({"path": "a.b"})) == ["a.b"]
    assert list(metric_paths({"sum": ["a.b", "c.d"]})) == ["a.b", "c.d"]
    assert list(metric_paths({"contains": {"path": "x.y", "label": "L"}})) == ["x.y"]
    assert list(metric_paths({"ratio": {"numerator": "n.n", "denominator": "d.d"}})) == [
        "n.n",
        "d.d",
    ]


def test_under_fair_play_a_topic_chosen_by_hidden_knowledge_says_so_and_carries_no_hidden_fact(
    tmp_path,
):
    graph = pack(tmp_path, rivals=True)
    result = build_topics(graph, rival_extract(), ["naval_capacity.more"], model=model())
    (topic,) = result["topics"]
    assert topic["hidden_knowledge"] is True
    assert [p["metric"] for p in topic["pointers"]] == [
        "naval_capacity.fill",
        "rivals.seen",
    ]
    assert str(HIDDEN_VALUE) not in json.dumps(result)
    assert "rivals.power" not in json.dumps(result)


def test_under_god_mode_the_pointers_may_carry_everything(tmp_path):
    graph = pack(tmp_path, rivals=True)
    result = build_topics(
        graph, rival_extract(), ["naval_capacity.more"], model=model(), god_mode=True
    )
    (topic,) = result["topics"]
    assert topic["hidden_knowledge"] is True
    assert {p["metric"]: p["value"] for p in topic["pointers"]} == {
        "rivals.power": HIDDEN_VALUE,
        "rivals.seen": 321,
        "naval_capacity.fill": 0.95,
    }


def test_a_topic_chosen_by_own_data_is_not_flagged(tmp_path):
    (topic,) = build(tmp_path)["topics"]
    assert topic["hidden_knowledge"] is False


def test_no_metric_of_the_real_pack_reads_hidden_data():
    graph = MechanicsGraph.load()
    hidden = [
        name
        for name, spec in graph.metrics.items()
        if any(is_hidden(path) for path in metric_paths(spec))
    ]
    assert hidden == []


# --- the Drill takes the list -----------------------------------------------------------------------


def test_the_drill_takes_the_list_keeps_its_extra_fields_and_stores_the_goals(tmp_path):
    graph = pack(tmp_path)
    goals = ["naval_capacity.more", "energy.more"]
    result = build_topics(graph, extract(), goals, model=model())
    workspace = tmp_path / "workspace"
    opened = drill.open_drill(
        workspace,
        date="2259.12.25",
        topics=result["topics"],
        goals=goals,
        campaign="test",
        extract=extract(),
    )
    assert opened["goals"] == goals
    assert opened["waiting"] == result["count"] - 1
    shown = opened["topic"]
    assert shown["concept"] == result["topics"][0]["concept"]
    assert shown["pointers"] == result["topics"][0]["pointers"]
    assert shown["goals"] == result["topics"][0]["goals"]
    assert drill.load(workspace)["goals"] == goals


def test_a_drill_without_goals_stores_none(tmp_path):
    opened = drill.open_drill(tmp_path / "w", date="2259.12.25", topics=[{"concept": NAVAL}])
    assert opened["goals"] == []


# --- the real pack ----------------------------------------------------------------------------------


def test_the_real_pack_on_the_vulkan_mid_save(tmp_path):
    from admiralty.extract.snapshot import Extractor

    document = Extractor().extract(str(reference_save(VULKAN, MID)), "Plexxi")
    graph = MechanicsGraph.load(document["header"]["game_version"])
    goals = sorted(graph.goals)
    result = build_topics(graph, document, goals, model=model())
    assert result["count"] > 5 and result["unknown_goals"] == []
    assert len(set(concepts(result))) == result["count"]
    assert not any(t["hidden_knowledge"] for t in result["topics"])
    flags = [t["crisis"] for t in result["topics"]]
    assert flags == sorted(flags, reverse=True)  # every Crisis topic before every other
    opened = drill.open_drill(
        tmp_path / "workspace",
        date=document["header"]["date"],
        topics=result["topics"],
        goals=goals,
        extract=document,
    )
    assert opened["waiting"] == result["count"] - 1
    print(
        f"vulkan {document['header']['date']}: {result['count']} topics, "
        f"{sum(flags)} in a Crisis, skipped {result['skipped']}"
    )
