"""Playbook Rules: the three approved seed rules, the loader, and their links into the graph."""

from __future__ import annotations

import datetime
import fnmatch
import shutil
import textwrap
from pathlib import Path

import pytest

from hlidskjalf.graph.mechanics import KNOWLEDGE_ROOT, MechanicsGraph, validate
from hlidskjalf.graph.playbook import RulesInvalid, load_rules, read_rules

SEEDS = ["unity-vs-next-tradition", "influence-at-cap-is-waste", "unemployed-before-colonies"]


def _write(directory: Path, name: str, text: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(textwrap.dedent(text).lstrip(), encoding="utf-8")


GOOD = """
    ---
    id: some-rule
    date: 2026-10-24
    status: approved
    applies_to: [unity.more]
    reason: Because.
    ---
    Do the thing.
    """


def test_the_three_seed_rules_load_and_nothing_else():
    rules = load_rules("v4.5.2")
    assert sorted(rules) == sorted(SEEDS)
    for rule in rules.values():
        assert isinstance(rule.date, datetime.date)
        assert rule.reason and rule.body and rule.applies_to


def test_the_pack_validates_with_the_rules_in_it():
    assert validate("v4.5.2") == []


def test_the_unity_rule_is_cited_by_the_remedies_that_spend_unity():
    graph = MechanicsGraph.load("v4.5.2")
    citing = {
        n for n, node in graph.nodes.items() if "unity-vs-next-tradition" in node.get("rules", [])
    }
    assert {
        "naval_capacity.adopt_supremacy",
        "influence.run_will_to_power",
        "influence.take_colonial_viceroys",
        "influence.adopt_diplomacy_tradition",
        "unity.raise_income",
    } <= citing


def test_the_unemployed_rule_is_cited_by_every_no_spare_pops_obstacle():
    graph = MechanicsGraph.load("v4.5.2")
    obstacles = [n for n in graph.nodes if n.endswith(".no_spare_pops")]
    assert len(obstacles) >= 9
    for node_id in obstacles + ["pop_growth.grow_pops"]:
        assert "unemployed-before-colonies" in graph.node(node_id)["rules"], node_id


def test_the_influence_rule_is_cited_by_a_remedy_that_spends_influence():
    graph = MechanicsGraph.load("v4.5.2")
    assert "influence-at-cap-is-waste" in graph.node("influence.stagger_projects")["rules"]


def test_every_cited_rule_applies_to_the_node_that_cites_it():
    graph = MechanicsGraph.load("v4.5.2")
    rules = load_rules("v4.5.2")
    for node_id, node in graph.nodes.items():
        for rule_id in node.get("rules", []):
            patterns = rules[rule_id].applies_to
            assert any(fnmatch.fnmatchcase(node_id, p) for p in patterns), (node_id, rule_id)


def test_rule_bodies_state_no_figures():
    # the Unverified Claim check exempts numbers in quoted rules, so keep the quotable text free
    # of figures that could go stale
    for rule in load_rules("v4.5.2").values():
        assert not any(ch.isdigit() for ch in rule.body), rule.id


@pytest.mark.parametrize(
    ("text", "fragment"),
    [
        ("no front matter at all", "front matter"),
        (GOOD.replace("id: some-rule", "id: Some_Rule"), "id"),
        (GOOD.replace("2026-10-24", "yesterday"), "date"),
        (GOOD.replace("approved", "proposed"), "docs/proposals/playbook.md"),
        (GOOD.replace("    reason: Because.\n", ""), "lacks reason"),
        (GOOD.replace("applies_to: [unity.more]", "applies_to: []"), "applies_to"),
        (GOOD.replace("Do the thing.", ""), "no body"),
    ],
)
def test_malformed_rule_files_are_reported(tmp_path, text, fragment):
    _write(tmp_path, "some-rule.md", text)
    rules, errors = read_rules(tmp_path)
    assert rules == {}
    assert len(errors) == 1 and fragment in errors[0], errors


def test_the_id_must_match_the_file_name_and_be_unique(tmp_path):
    _write(tmp_path, "other-name.md", GOOD)
    assert "file name" in read_rules(tmp_path)[1][0]
    (tmp_path / "other-name.md").unlink()
    _write(tmp_path, "some-rule.md", GOOD)
    assert read_rules(tmp_path)[1] == []


def test_a_bad_rules_folder_refuses_to_load(tmp_path):
    _write(tmp_path / "4.5.2" / "rules", "some-rule.md", GOOD.replace("approved", "proposed"))
    with pytest.raises(RulesInvalid):
        load_rules("v4.5.2", root=tmp_path)

    # in a temp copy of the real pack
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        shutil.copytree(KNOWLEDGE_ROOT / "4.5.2" / "graph", root / "4.5.2" / "graph")
        shutil.copytree(KNOWLEDGE_ROOT / "4.5.2" / "generated", root / "4.5.2" / "generated")
        _write(
            root / "4.5.2" / "rules",
            "some-rule.md",
            GOOD.replace("[unity.more]", "[nothing.here]"),
        )
        problems = [str(p) for p in validate("v4.5.2", root=root)]
    assert any("applies_to: 'nothing.here' matches no node" in p for p in problems), problems
    assert any("is not a Playbook Rule" in p for p in problems)
