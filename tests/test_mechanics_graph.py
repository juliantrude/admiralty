"""Mechanics Graph schema and validator (M4): good and bad packs, the metrics registry, the CLI.

Packs are built in a temp folder with a tiny generated-facts file, so these tests need neither the
game install nor the 3.5 MB of real facts; only the registry-vs-extract test needs a reference save.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml
from conftest import MID, VULKAN, reference_save

from hlidskjalf.cli import main
from hlidskjalf.graph.mechanics import (
    KNOWLEDGE_ROOT,
    GraphInvalid,
    GraphMissing,
    MechanicsGraph,
    validate,
)

FACT = "naval_capacity.tradition.tr_supremacy_adopt.country_naval_cap_add"
JOB_FACT = "naval_capacity.job.soldier.country_naval_cap_add"

METRICS = {
    "version": "v4.5.2",
    "metrics": {
        "unity.stockpile": {"path": "resources.unity.stockpile", "unit": "unity"},
        "traditions.next_cost": {"path": "progression.next_tradition.cost", "unit": "unity"},
        "naval_capacity.fill": {
            "ratio": {"numerator": "naval_capacity.used", "denominator": "naval_capacity.max"},
            "unit": "fraction",
        },
    },
}

GRAPH = {
    "version": "v4.5.2",
    "domain": "naval_capacity",
    "goals": [
        {
            "id": "naval_capacity.more",
            "title": "More naval capacity",
            "symptom_metrics": ["naval_capacity.fill"],
            "causes": ["naval_capacity.few_sources"],
        }
    ],
    "nodes": [
        {
            "id": "naval_capacity.few_sources",
            "type": "cause",
            "title": "Few sources of naval capacity",
            "description": "Capacity is a flat base plus additive sources.",
            "remedies": ["naval_capacity.adopt_supremacy"],
            "facts": [FACT, "naval_capacity.job.*.country_naval_cap_add"],
        },
        {
            "id": "naval_capacity.adopt_supremacy",
            "type": "remedy",
            "title": "Adopt the Supremacy tradition tree",
            "judgement": "Worth it when capacity-bound and Unity is not earmarked.",
            "strength": "high",
            "speed": "medium",
            "cost": "high",
            "obstacles": ["naval_capacity.needs_unity"],
            "facts": [FACT],
            "rules": ["unity-vs-next-tradition"],
        },
        {
            "id": "naval_capacity.needs_unity",
            "type": "obstacle",
            "title": "Not enough Unity for the next Tradition",
            "description": "Unity is judged against the next Tradition cost.",
            "check": {
                "metric": "unity.stockpile",
                "op": "<",
                "compare_to": {"metric": "traditions.next_cost"},
            },
        },
    ],
}


def write_pack(tmp_path: Path, graph=GRAPH, metrics=METRICS, extra: dict | None = None) -> Path:
    """knowledge/4.5.2/{graph,generated,rules} in tmp_path; returns the knowledge root."""
    version = tmp_path / "4.5.2"
    for folder in ("graph", "generated", "rules"):
        (version / folder).mkdir(parents=True)
    (version / "generated" / "naval_capacity.yaml").write_text(
        yaml.safe_dump(
            {
                "game_version": "v4.5.2",
                "quantity": "naval_capacity",
                "facts": [{"id": FACT, "amount": 20}, {"id": JOB_FACT, "amount": 4}],
            }
        )
    )
    (version / "rules" / "unity.md").write_text(
        "---\nid: unity-vs-next-tradition\ndate: 2026-10-24\n---\nJudge Unity against the cost.\n"
    )
    if metrics is not None:
        (version / "graph" / "metrics.yaml").write_text(yaml.safe_dump(metrics))
    if graph is not None:
        (version / "graph" / "naval_capacity.yaml").write_text(yaml.safe_dump(graph))
    for name, document in (extra or {}).items():
        (version / "graph" / name).write_text(yaml.safe_dump(document))
    return tmp_path


def mutated(change) -> dict:
    graph = copy.deepcopy(GRAPH)
    change(graph)
    return graph


def node(graph: dict, suffix: str) -> dict:
    return next(n for n in graph["nodes"] if n["id"].endswith(suffix))


def problems_of(tmp_path: Path, graph: dict, severity: str = "error") -> list[str]:
    root = tmp_path / "pack"
    root = root if root.exists() else write_pack(root, graph=graph)
    return [str(p) for p in validate("v4.5.2", root) if p.severity == severity]


def expect(problems: list[str], *fragments: str) -> None:
    assert any(all(f in p for f in fragments) for p in problems), problems


# --- a good pack ------------------------------------------------------------------------------


def test_good_pack_is_clean_and_loads(tmp_path):
    root = write_pack(tmp_path)
    assert validate("v4.5.2", root) == []
    graph = MechanicsGraph.load("4.5.2", root)  # the version may be given without the 'v'
    assert graph.version == "v4.5.2"
    assert graph.goal("naval_capacity.more")["causes"] == ["naval_capacity.few_sources"]
    assert graph.node("naval_capacity.needs_unity")["type"] == "obstacle"
    assert graph.fact(FACT)["amount"] == 20
    # exact id plus a wildcard family, sorted and without duplicates
    assert [f["id"] for f in graph.node_facts("naval_capacity.few_sources")] == [JOB_FACT, FACT]


def test_judgement_only_obstacle_is_allowed(tmp_path):
    def change(graph):
        node(graph, "needs_unity")["check"] = {"judgement_only": True}

    assert problems_of(tmp_path, mutated(change)) == []


def test_pack_without_nodes_is_valid(tmp_path):
    graph = {"version": "v4.5.2", "domain": "naval_capacity", "goals": [], "nodes": []}
    assert problems_of(tmp_path, graph) == []


def test_missing_pack_is_reported(tmp_path):
    with pytest.raises(GraphMissing):
        validate("v9.9.9", tmp_path)


# --- bad packs: the failures the plan names ---------------------------------------------------


def test_dangling_link(tmp_path):
    def change(graph):
        node(graph, "few_sources")["remedies"].append("naval_capacity.not_there")

    expect(
        problems_of(tmp_path, mutated(change)),
        "naval_capacity.few_sources",
        "remedies: 'naval_capacity.not_there' does not exist",
    )


def test_dangling_goal_link(tmp_path):
    def change(graph):
        graph["goals"][0]["causes"] = ["naval_capacity.nowhere"]

    expect(problems_of(tmp_path, mutated(change)), "naval_capacity.more", "does not exist")


def test_link_to_the_wrong_type(tmp_path):
    def change(graph):
        node(graph, "few_sources")["remedies"] = ["naval_capacity.needs_unity"]

    expect(
        problems_of(tmp_path, mutated(change)),
        "'naval_capacity.needs_unity' is a obstacle, expected a remedy",
    )


def test_unknown_metric_in_a_check(tmp_path):
    def change(graph):
        node(graph, "needs_unity")["check"]["metric"] = "unity.stockpyle"

    expect(
        problems_of(tmp_path, mutated(change)), "metric 'unity.stockpyle' is not in metrics.yaml"
    )


def test_unknown_metric_in_compare_to_and_symptoms(tmp_path):
    def change(graph):
        node(graph, "needs_unity")["check"]["compare_to"] = {"metric": "traditions.next_price"}
        graph["goals"][0]["symptom_metrics"] = ["naval_capacity.filled"]

    problems = problems_of(tmp_path, mutated(change))
    expect(problems, "traditions.next_price")
    expect(problems, "naval_capacity.filled")


def test_dead_end_cause(tmp_path):
    def change(graph):
        node(graph, "few_sources").pop("remedies")

    expect(problems_of(tmp_path, mutated(change)), "dead-end Cause")


def test_remedy_without_ratings(tmp_path):
    def change(graph):
        del node(graph, "adopt_supremacy")["speed"]

    expect(problems_of(tmp_path, mutated(change)), "'speed' is a required property")


def test_remedy_rating_out_of_range(tmp_path):
    def change(graph):
        node(graph, "adopt_supremacy")["cost"] = "huge"

    expect(problems_of(tmp_path, mutated(change)), "cost", "'huge' is not one of")


def test_obstacle_without_check(tmp_path):
    def change(graph):
        del node(graph, "needs_unity")["check"]

    expect(problems_of(tmp_path, mutated(change)), "'check' is a required property")


def test_obstacle_with_incomplete_check(tmp_path):
    def change(graph):
        del node(graph, "needs_unity")["check"]["op"]

    assert problems_of(tmp_path, mutated(change))


def test_unknown_node_type_and_unknown_field(tmp_path):
    def change(graph):
        node(graph, "few_sources")["type"] = "symptom"
        node(graph, "adopt_supremacy")["colour"] = "red"

    problems = problems_of(tmp_path, mutated(change))
    expect(problems, "'symptom' is not one of")
    expect(problems, "colour")


def test_dangling_fact_and_empty_wildcard(tmp_path):
    def change(graph):
        node(graph, "few_sources")["facts"] = [FACT + "_typo", "naval_capacity.relic.*.x"]

    problems = problems_of(tmp_path, mutated(change))
    expect(problems, f"'{FACT}_typo' matches no generated fact")
    expect(problems, "'naval_capacity.relic.*.x' matches no generated fact")


def test_unknown_rule(tmp_path):
    def change(graph):
        node(graph, "adopt_supremacy")["rules"] = ["no-such-rule"]

    expect(problems_of(tmp_path, mutated(change)), "'no-such-rule' is not a Playbook Rule")


def test_duplicate_id_across_files(tmp_path):
    other = copy.deepcopy(GRAPH)
    other["domain"] = "energy"
    root = write_pack(tmp_path, extra={"energy.yaml": other})
    errors = [str(p) for p in validate("v4.5.2", root) if p.severity == "error"]
    expect(errors, "also defined in")
    expect(errors, "id must start with 'energy.'")


def test_domain_must_match_file_name_and_version(tmp_path):
    graph = mutated(lambda g: g.update(domain="energy", version="v4.4.0"))
    problems = problems_of(tmp_path, graph)
    expect(problems, "does not match the file name")
    expect(problems, "version is v4.4.0")


def test_break_point_needs_a_circle(tmp_path):
    def change(graph):
        node(graph, "adopt_supremacy")["break_point"] = True

    expect(problems_of(tmp_path, mutated(change)), "break_point")


def test_invalid_yaml_is_reported(tmp_path):
    root = write_pack(tmp_path)
    (root / "4.5.2" / "graph" / "broken.yaml").write_text("goals: [unclosed\n")
    expect([str(p) for p in validate("v4.5.2", root)], "broken.yaml", "not valid YAML")


def test_load_refuses_a_pack_with_errors(tmp_path):
    graph = mutated(lambda g: node(g, "few_sources").pop("remedies"))
    root = write_pack(tmp_path, graph=graph)
    with pytest.raises(GraphInvalid) as raised:
        MechanicsGraph.load("v4.5.2", root)
    assert any("dead-end" in str(p) for p in raised.value.problems)


# --- warnings: digits in prose, cycles --------------------------------------------------------


def test_figure_in_prose_is_only_a_warning(tmp_path):
    def change(graph):
        node(graph, "adopt_supremacy")["judgement"] = "Gives +20 capacity, worth it."
        node(graph, "few_sources")["description"] = "Identifiers like tr_supremacy_2 are fine."

    graph = mutated(change)
    assert problems_of(tmp_path, graph) == []
    warnings = problems_of(tmp_path, graph, "warning")
    assert len(warnings) == 1
    expect(warnings, "naval_capacity.adopt_supremacy", "judgement contains a figure")


def cycle_graph(circle: str | None, exit_link: bool) -> dict:
    """energy.a -> energy.b -> energy.a, optionally with a Remedy leaving the loop."""

    def cause(name: str, target: str) -> dict:
        entry = {
            "id": f"energy.{name}",
            "type": "cause",
            "title": name,
            "description": f"{name} feeds {target}",
            "causes": [f"energy.{target}"],
        }
        if circle:
            entry["circle"] = circle
        return entry

    nodes = [cause("a", "b"), cause("b", "a")]
    if exit_link:
        nodes[0]["remedies"] = ["energy.fix"]
        nodes.append(
            {
                "id": "energy.fix",
                "type": "remedy",
                "title": "Fix it",
                "judgement": "Do it.",
                "strength": "low",
                "speed": "low",
                "cost": "low",
            }
        )
    goals = [{"id": "energy.more", "title": "More", "causes": ["energy.a"]}]
    return {"version": "v4.5.2", "domain": "energy", "goals": goals, "nodes": nodes}


def validate_extra(tmp_path: Path, graph: dict):
    root = write_pack(tmp_path, graph=None, extra={"energy.yaml": graph})
    return [str(p) for p in validate("v4.5.2", root)]


def test_unnamed_cycle_with_exit_is_a_warning(tmp_path):
    problems = validate_extra(tmp_path, cycle_graph(None, exit_link=True))
    assert len(problems) == 1
    expect(problems, "warning", "cycle not marked with one `circle` name")


def test_named_cycle_with_exit_is_clean(tmp_path):
    assert validate_extra(tmp_path, cycle_graph("energy loop", exit_link=True)) == []


def test_cycle_without_exit_is_an_error(tmp_path):
    problems = validate_extra(tmp_path, cycle_graph("energy loop", exit_link=False))
    expect(problems, "error", "cycle without an exit")


# --- the metrics registry ---------------------------------------------------------------------


def test_metrics_registry_shape(tmp_path):
    bad = copy.deepcopy(METRICS)
    bad["metrics"]["unity.both"] = {"path": "a.b", "sum": ["a.b", "a.c"], "unit": "unity"}
    bad["metrics"]["unity.none"] = {"unit": "unity"}
    bad["metrics"]["Unity Bad"] = {"path": "a.b", "unit": "unity"}
    root = write_pack(tmp_path, metrics=bad)
    errors = [str(p) for p in validate("v4.5.2", root)]
    assert sum("metrics.yaml" in e for e in errors) >= 3


def test_real_pack_validates():
    """The committed pack: the registry now, the curated domains as they are added."""
    problems = [p for p in validate("v4.5.2") if p.severity == "error"]
    assert problems == []


def _dig(document: dict, path: str):
    value = document
    for part in path.split("."):
        assert isinstance(value, dict) and part in value, f"{path}: no '{part}' in the extract"
        value = value[part]
    return value


def test_every_registered_metric_path_exists_in_the_extract():
    """A renamed extract field must break the registry loudly, not silently disable an Obstacle."""
    from hlidskjalf.extract.snapshot import Extractor

    save = reference_save(VULKAN, MID)
    document = Extractor().extract(str(save), "Plexxi")
    registry = yaml.safe_load((KNOWLEDGE_ROOT / "4.5.2" / "graph" / "metrics.yaml").read_text())
    for name, metric in registry["metrics"].items():
        paths = (
            [metric["path"]]
            if "path" in metric
            else [metric["ratio"]["numerator"], metric["ratio"]["denominator"]]
            if "ratio" in metric
            else metric["sum"]
        )
        for path in paths:
            value = _dig(document, path)
            assert isinstance(value, int | float), f"{name}: {path} is {value!r}, not a number"


# --- CLI --------------------------------------------------------------------------------------


def test_cli_exit_codes(tmp_path, capsys):
    root = write_pack(tmp_path / "good")
    assert main(["graph", "validate", "--knowledge-root", str(root)]) == 0
    assert "0 error(s), 0 warning(s)" in capsys.readouterr().out

    broken = mutated(lambda g: node(g, "few_sources").pop("remedies"))
    root = write_pack(tmp_path / "bad", graph=broken)
    assert main(["graph", "validate", "--knowledge-root", str(root)]) == 1
    out = capsys.readouterr().out
    assert "error: naval_capacity.yaml naval_capacity.few_sources: dead-end Cause" in out
    assert "1 error(s)" in out


def test_cli_missing_pack(tmp_path, capsys):
    assert (
        main(["graph", "validate", "--version", "v9.9.9", "--knowledge-root", str(tmp_path)]) == 1
    )
    assert "no knowledge pack for v9.9.9" in capsys.readouterr().err
