"""Benchmarks draft (M4): format and honesty rules, the review page, the committed file."""

from __future__ import annotations

import copy
import shutil

import pytest
import yaml
from conftest import MID, VULKAN, reference_save

from hlidskjalf.graph.benchmarks import (
    DECADES,
    BenchmarksInvalid,
    load_benchmarks,
    nearest_decade,
    read_benchmarks,
    render_review_page,
    resolve_source,
)
from hlidskjalf.graph.mechanics import KNOWLEDGE_ROOT, validate

METRICS = {
    "research.income": {"sum": ["a.x", "a.y"]},
    "share": {"ratio": {"numerator": "a.x", "denominator": "a.y"}},
    "a.x": {"path": "a.x"},
}
GOOD = {
    "version": "v4.5.2",
    "status": "draft",
    "decades": list(DECADES),
    "figures": {
        "research_income": {
            "label": "Research income",
            "unit": "research per month",
            "source": {"metric": "research.income"},
            "provenance": "test data",
            "assumptions": ["gross"],
            "values": dict.fromkeys(DECADES),
            "observed": [{"campaign": "demo", "date": "2259.12.29", "value": 230.4}],
        }
    },
}


def figure(document):
    return document["figures"]["research_income"]


def errors_of(tmp_path, change, registered=frozenset({"research.income"})):
    document = copy.deepcopy(GOOD)
    change(document)
    path = tmp_path / "benchmarks.yaml"
    path.write_text(yaml.safe_dump(document))
    return read_benchmarks(path, set(registered))[1]


def expect(errors, *fragments):
    assert any(all(f in e for f in fragments) for e in errors), errors


def test_good_document_is_clean(tmp_path):
    assert errors_of(tmp_path, lambda d: None) == []


def test_every_value_open_is_allowed_and_nothing_is_invented():
    benchmarks = load_benchmarks()
    assert benchmarks.status == "draft" and not benchmarks.usable
    for figure_id, entry in benchmarks.figures.items():
        for decade, value in entry["values"].items():
            assert value is None or value["basis"] == "derived", (figure_id, decade)


def test_a_draft_is_not_usable_and_a_reviewed_file_is(tmp_path):
    root = tmp_path / "4.5.2"
    root.mkdir()
    document = copy.deepcopy(GOOD)
    figure(document)["values"][2250] = {"value": 120, "basis": "reviewed"}
    document["status"] = "reviewed"
    (root / "benchmarks.yaml").write_text(yaml.safe_dump(document))
    benchmarks = load_benchmarks(root=tmp_path)
    assert benchmarks.usable and benchmarks.value("research_income", 2250) == 120
    assert benchmarks.value("research_income", 2260) is None


def test_reviewed_values_need_a_reviewed_file(tmp_path):
    def change(document):
        figure(document)["values"][2250] = {"value": 120, "basis": "reviewed"}

    expect(errors_of(tmp_path, change), "2250", "file status 'reviewed'")


def test_derived_values_need_their_formula(tmp_path):
    def change(document):
        figure(document)["values"][2250] = {"value": 120, "basis": "derived"}

    expect(errors_of(tmp_path, change), "2250", "formula")


def test_a_value_without_basis_or_number_is_refused(tmp_path):
    def change(document):
        figure(document)["values"][2250] = {"value": 120}
        figure(document)["values"][2260] = {"basis": "derived", "formula": "x"}

    errors = errors_of(tmp_path, change)
    expect(errors, "2250", "basis")
    expect(errors, "2260", "numeric")


def test_missing_decade_status_and_fields(tmp_path):
    def change(document):
        del figure(document)["values"][2290]
        del figure(document)["provenance"]
        document["status"] = "final"

    errors = errors_of(tmp_path, change)
    expect(errors, "values needs exactly the decades")
    expect(errors, "missing 'provenance'")
    expect(errors, "status must be")


def test_unknown_metric_and_bad_source(tmp_path):
    def unknown(document):
        figure(document)["source"] = {"metric": "research.incom"}

    def two(document):
        figure(document)["source"] = {"metric": "research.income", "path": "a.b"}

    expect(errors_of(tmp_path, unknown), "'research.incom' is not in metrics.yaml")
    expect(errors_of(tmp_path, two), "source must be exactly one of")


def test_bad_observed_entries(tmp_path):
    def change(document):
        figure(document)["observed"] = [
            {"campaign": "demo", "date": "2259", "value": 1},
            {"campaign": "demo", "date": "2259.12.29", "value": "high"},
        ]

    errors = errors_of(tmp_path, change)
    expect(errors, "observed[0]", "date")
    expect(errors, "observed[1]", "number")


def test_a_malformed_file_refuses_to_load(tmp_path):
    (tmp_path / "4.5.2").mkdir()
    (tmp_path / "4.5.2" / "benchmarks.yaml").write_text("status: draft\n")
    with pytest.raises(BenchmarksInvalid):
        load_benchmarks(root=tmp_path)


def test_nearest_decade():
    assert nearest_decade("2259.12.29") == 2260
    assert nearest_decade("2220.04.26") == 2220
    assert nearest_decade("2200.01.01") is None  # before 2205
    assert nearest_decade("2298.03.16") is None  # after 2295
    assert nearest_decade("2315.03.01") is None


def test_resolve_source():
    extract = {"a": {"x": 6, "y": 3}, "planets": [1, 2, 3]}
    assert resolve_source({"metric": "research.income"}, extract, METRICS) == 9
    assert resolve_source({"metric": "share"}, extract, METRICS) == 2
    assert resolve_source({"path": "a.y"}, extract, METRICS) == 3
    assert resolve_source({"count": "planets"}, extract, METRICS) == 3
    assert resolve_source({"path": "a.z"}, extract, METRICS) is None


def test_review_page_states_the_gaps_and_the_draft():
    from hlidskjalf.graph.benchmarks import Benchmarks

    page = render_review_page(Benchmarks("v4.5.2", "draft", GOOD["figures"]), {})
    assert "DRAFT" in page and "0 of 9 benchmark values are filled, 9 are open" in page
    assert "| 2260 | _open_ |  | demo 2259.12.29: 230.4 |" in page
    assert "Questions for the reviewers" in page


# --- the committed pack ---------------------------------------------------------------------------


def test_committed_page_matches_the_yaml():
    """docs/benchmarks-draft.md is generated: a stale page would show the reviewers old numbers."""
    benchmarks = load_benchmarks()
    page = (KNOWLEDGE_ROOT.parent / "docs" / "benchmarks-draft.md").read_text(encoding="utf-8")
    assert page == render_review_page(benchmarks, {})


def test_committed_figures_cover_the_plan_and_name_no_player():
    benchmarks = load_benchmarks()
    assert set(benchmarks.figures) >= {
        "research_income", "alloys_income", "energy_income", "minerals_income", "food_income",
        "unity_income", "influence_income", "naval_capacity", "pop_count", "planet_count",
    }  # fmt: skip
    text = (KNOWLEDGE_ROOT / "4.5.2" / "benchmarks.yaml").read_text(encoding="utf-8")
    for name in ("Plexxi", "Patrick"):
        assert name not in text
    for entry in benchmarks.figures.values():
        assert entry["provenance"] and entry["observed"]


def test_graph_validate_reports_benchmark_errors(tmp_path):
    shutil.copytree(
        KNOWLEDGE_ROOT / "4.5.2", tmp_path / "4.5.2", ignore=shutil.ignore_patterns("generated")
    )
    shutil.copytree(KNOWLEDGE_ROOT / "4.5.2" / "generated", tmp_path / "4.5.2" / "generated")
    assert [p for p in validate("v4.5.2", tmp_path) if p.severity == "error"] == []
    path = tmp_path / "4.5.2" / "benchmarks.yaml"
    document = yaml.safe_load(path.read_text())
    document["figures"]["research_income"]["source"] = {"metric": "nope.nothing"}
    path.write_text(yaml.safe_dump(document))
    problems = [str(p) for p in validate("v4.5.2", tmp_path) if p.severity == "error"]
    assert any("benchmarks.yaml" in p and "nope.nothing" in p for p in problems), problems


def test_observed_values_match_a_fresh_extract():
    """The recorded figures come from the extractor, not from hand: one reference save re-read."""
    from hlidskjalf.extract.snapshot import Extractor

    save = reference_save(VULKAN, MID)
    document = Extractor().extract(str(save), "Plexxi")
    registry = yaml.safe_load((KNOWLEDGE_ROOT / "4.5.2" / "graph" / "metrics.yaml").read_text())
    benchmarks = load_benchmarks()
    checked = 0
    for entry in benchmarks.figures.values():
        for seen in entry["observed"]:
            if (seen["campaign"], seen["date"]) == (VULKAN, document["header"]["date"]):
                expected = resolve_source(entry["source"], document, registry["metrics"])
                assert seen["value"] == pytest.approx(expected, abs=0.01)
                checked += 1
    assert checked == len(benchmarks.figures)
