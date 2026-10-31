"""One current Briefing per workspace, the replaced versions in a history."""

import json

import pytest

from admiralty.workspace import briefings


def doc(date: str) -> dict:
    return {"date": date, "nodes": []}


def test_the_first_briefing_becomes_current_and_replaces_nothing(tmp_path):
    assert briefings.publish(tmp_path, {"empire": "E"}, doc("2294.01.01")) is None
    assert json.loads(briefings.current_graph(tmp_path).read_text())["date"] == "2294.01.01"
    assert json.loads(briefings.current_overlay(tmp_path).read_text()) == {"empire": "E"}
    assert briefings.history(tmp_path) == []


def test_an_update_moves_the_old_briefing_into_the_history(tmp_path):
    briefings.publish(tmp_path, {"v": 1}, doc("2294.01.01"))
    archived = briefings.publish(tmp_path, {"v": 2}, doc("2294.03.01"))
    assert archived == tmp_path / "briefings" / "history" / "001-2294.01.01"
    assert json.loads((archived / "overlay.json").read_text()) == {"v": 1}
    assert json.loads((archived / "solution-graph.json").read_text())["date"] == "2294.01.01"
    assert json.loads(briefings.current_overlay(tmp_path).read_text()) == {"v": 2}
    briefings.publish(tmp_path, {"v": 3}, doc("2294.03.01"))
    assert [p.name for p in briefings.history(tmp_path)] == ["001-2294.01.01", "002-2294.03.01"]
    assert {p.name for p in (tmp_path / "briefings").iterdir()} == {"history", "current"}


def test_the_history_sorts_by_number_not_by_text(tmp_path):
    for n in (2, 10, 9):
        (tmp_path / "briefings" / "history" / f"{n:03d}-2294.01.01").mkdir(parents=True)
    (tmp_path / "briefings" / "history" / "notes").mkdir()
    assert [p.name[:3] for p in briefings.history(tmp_path)] == ["002", "009", "010"]
    briefings.publish(tmp_path, {}, doc("2294.01.01"))
    archived = briefings.publish(tmp_path, {}, doc("2294.02.01"))
    assert archived.name == "011-2294.01.01"


def test_a_failed_write_leaves_the_old_briefing_in_place(tmp_path):
    briefings.publish(tmp_path, {"v": 1}, doc("2294.01.01"))
    with pytest.raises(TypeError):
        briefings.publish(tmp_path, {"v": 2}, {"date": object()})
    assert json.loads(briefings.current_overlay(tmp_path).read_text()) == {"v": 1}
    assert briefings.history(tmp_path) == []
    assert not (tmp_path / "briefings" / "current.new").exists()
