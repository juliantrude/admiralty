"""The Player Model store (M9, 20a): events are the truth, the cache is rebuilt, appends are safe."""

from __future__ import annotations

import json
import multiprocessing
from pathlib import Path

import pytest

from admiralty.graph.mechanics import MechanicsGraph
from admiralty.player import store
from admiralty.player.concepts import concepts


def lvl(concept="energy.x", level="understand", **extra):
    return store.append("level", concept=concept, level=level, reason="named the cause", **extra)


def test_an_empty_store_reads_as_an_empty_model():
    assert store.read_model() == {"events": 0, "concepts": {}}
    assert store.events() == []
    assert store.level_of(store.read_model(), "energy.x") == "new"


def test_an_event_gets_a_sequence_number_and_lands_in_log_and_cache(data_dir):
    event = lvl(campaign="vulkan", date="2259.12.25")
    assert event["seq"] == 1 and event["ts"]
    assert store.events() == [event]
    model = store.read_model()
    assert model["concepts"]["energy.x"]["level"] == "understand"
    assert model["concepts"]["energy.x"]["last_change"]["date"] == "2259.12.25"
    assert (data_dir / "player-model" / "model.json").is_file()


def test_the_replay_counts_drops_and_hatch_uses():
    lvl(level="apply")
    store.append("drop", concept="energy.x", level="understand", reason="cause reappeared")
    store.append("hatch", concept="energy.x", situation="no idea at all", reason="Escape Hatch")
    entry = store.read_model()["concepts"]["energy.x"]
    assert (entry["level"], entry["drops"], entry["hatch_uses"]) == ("understand", 1, 1)


def test_a_note_is_logged_but_does_not_touch_the_model():
    store.append("note", concept="energy.x", reason="candidate answer", text="more farms")
    assert store.read_model() == {"events": 1, "concepts": {}}


def test_the_cache_equals_the_replay_of_the_events():
    lvl()
    lvl("food.y", "apply")
    cached = json.loads((store.model_dir() / "model.json").read_text(encoding="utf-8"))
    assert cached == store.replay(store.events())


def test_an_edited_cache_is_rebuilt_on_the_next_read():
    lvl()
    path = store.model_dir() / "model.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["concepts"]["energy.x"]["level"] = "create"
    path.write_text(json.dumps(document), encoding="utf-8")
    assert store.read_model()["concepts"]["energy.x"]["level"] == "understand"
    assert json.loads(path.read_text(encoding="utf-8"))["concepts"]["energy.x"]["level"] == (
        "understand"
    )


@pytest.mark.parametrize("damage", ["delete", "garbage"])
def test_a_missing_or_broken_cache_is_rebuilt(damage):
    lvl()
    path = store.model_dir() / "model.json"
    if damage == "delete":
        path.unlink()
    else:
        path.write_text("{broken", encoding="utf-8")
    assert store.read_model()["concepts"]["energy.x"]["level"] == "understand"
    assert json.loads(path.read_text(encoding="utf-8"))["events"] == 1


def test_a_damaged_log_line_is_skipped_and_numbering_goes_on():
    lvl()
    with (store.model_dir() / "events.jsonl").open("a", encoding="utf-8") as handle:
        handle.write("{broken\n")
    second = lvl("food.y")
    assert second["seq"] == 2
    assert set(store.read_model()["concepts"]) == {"energy.x", "food.y"}


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"kind": "bogus", "reason": "r"}, "unknown event kind"),
        ({"kind": "level", "concept": "a", "level": "understand", "reason": " "}, "reason"),
        ({"kind": "level", "level": "understand", "reason": "r"}, "needs a concept"),
        ({"kind": "level", "concept": "a", "level": "master", "reason": "r"}, "needs a level"),
        ({"kind": "hatch", "reason": "r"}, "needs a concept"),
        ({"kind": "note", "reason": "r", "seq": 7}, "set by the store"),
    ],
)
def test_an_invalid_event_is_refused_and_writes_nothing(kwargs, message):
    kind = kwargs.pop("kind")
    with pytest.raises(store.EventInvalid, match=message):
        store.append(kind, **kwargs)
    assert store.events() == []


def _append_many(base: str, worker: int) -> None:
    for i in range(15):
        store.append(
            "level",
            concept=f"c.{worker}",
            level="understand",
            reason=f"w{worker} #{i}",
            base=Path(base),
        )


def test_concurrent_appends_lose_nothing_and_number_every_event_once(tmp_path):
    context = multiprocessing.get_context("fork")
    workers = [context.Process(target=_append_many, args=(str(tmp_path), n)) for n in range(4)]
    for process in workers:
        process.start()
    for process in workers:
        process.join(60)
        assert process.exitcode == 0
    history = store.events(tmp_path)
    assert sorted(e["seq"] for e in history) == list(range(1, 61))
    assert store.read_model(tmp_path)["events"] == 60
    assert store.read_model(tmp_path) == store.replay(history)


def test_no_temp_file_stays_behind():
    lvl()
    assert sorted(p.name for p in store.model_dir().iterdir()) == [
        ".lock",
        "events.jsonl",
        "model.json",
    ]


# --- concepts ---------------------------------------------------------------------------------


def test_the_concepts_are_the_causes_of_the_graph():
    graph = MechanicsGraph.load()
    found = concepts(graph)
    causes = {i for i, n in graph.nodes.items() if n["type"] == "cause"}
    assert set(found) == causes and causes
    sample = found["alloys.few_metallurgists"]
    assert sample.domain == "alloys" and sample.version == graph.version
    assert sample.remedies == ("alloys.staff_metallurgists", "alloys.build_foundry_zones")
    assert sample.facts


def test_the_signature_ignores_titles_and_order_but_not_links():
    graph = MechanicsGraph.load()
    base = concepts(graph)["alloys.few_metallurgists"]
    retitled = type(base)(**{**base.__dict__, "title": "Other words"})
    reordered = type(base)(**{**base.__dict__, "remedies": tuple(reversed(base.remedies))})
    relinked = type(base)(**{**base.__dict__, "remedies": base.remedies[:1]})
    assert retitled.signature == reordered.signature == base.signature
    assert relinked.signature != base.signature
