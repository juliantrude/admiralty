"""Where in the game (M9, 20f): the table is complete for the domains, rests on the metrics and cites game files."""

from __future__ import annotations

import copy

import pytest
import yaml

from admiralty.academy import locations
from admiralty.academy.locations import LocationUnknown, where
from admiralty.game import GameEnvironment
from admiralty.graph.mechanics import MechanicsGraph


@pytest.fixture(scope="module")
def table():
    return locations.read_table()


@pytest.fixture(scope="module")
def graph():
    return MechanicsGraph.load()


def graph_domains(graph):
    return {node_id.split(".", 1)[0] for node_id in graph.nodes}


def test_every_domain_of_the_graph_has_an_entry_and_no_other_does(table, graph):
    assert set(table["domains"]) == graph_domains(graph)


def test_every_figure_is_a_metric_of_the_graph(table, graph):
    assert set(table["figures"]) <= set(graph.metrics)


def test_every_entry_has_a_path_and_game_file_sources(table):
    for section in ("domains", "figures"):
        for key, entry in table[section].items():
            assert entry["path"].strip(), key
            assert entry["sources"], f"{key} cites no source"
            for source in entry["sources"]:
                assert set(source) == {"file", "find"}, key
                assert source["file"].startswith(("interface/", "localisation/")), key


def test_no_entry_is_a_localisation_key_or_a_wiki_text(table):
    for section in ("domains", "figures"):
        for key, entry in table[section].items():
            assert "http" not in entry["path"], key
            assert not any(word.isupper() and "_" in word for word in entry["path"].split()), key


def test_the_table_has_no_yaml_aliases():
    text = locations.table_path().read_text(encoding="utf-8")
    assert "&id" not in text and "*id" not in text


def test_every_cited_string_occurs_in_the_cited_game_file(table):
    try:
        install = GameEnvironment.detect().install_dir
    except FileNotFoundError:
        pytest.skip("Stellaris is not installed here; the sources are game files")
    for section in ("domains", "figures"):
        for key, entry in table[section].items():
            for source in entry["sources"]:
                path = install / source["file"]
                assert path.is_file(), f"{key}: {source['file']} is not in the install"
                assert source["find"] in path.read_text(encoding="utf-8", errors="ignore"), (
                    f"{key}: {source['find']!r} not in {source['file']}"
                )


def test_a_known_figure_gets_its_own_entry():
    found = where("energy", "energy.net")
    assert found.scope == "figure"
    assert found.key == "energy.net"
    assert "Top bar" in found.path and "Energy" in found.path


def test_an_unknown_figure_falls_back_to_the_domain():
    found = where("energy", "energy.something_new")
    assert found.scope == "domain"
    assert found.key == "energy"
    assert found.path == where("energy").path


def test_a_figure_alone_falls_back_to_the_domain_in_its_name():
    assert where(figure="naval_capacity.brand_new").key == "naval_capacity"


def test_a_figure_of_another_domain_keeps_its_own_entry():
    assert where("jobs", "pops.unemployed").key == "pops.unemployed"


def test_neither_figure_nor_domain_is_an_error_and_never_a_guess():
    with pytest.raises(LocationUnknown):
        where("nonsense", "nonsense.figure")
    with pytest.raises(LocationUnknown):
        where(figure="unlocks.decree_missing")
    with pytest.raises(LocationUnknown):
        where()


def test_a_pack_without_a_table_knows_nothing(tmp_path):
    with pytest.raises(LocationUnknown):
        where("energy", root=tmp_path)


def test_the_lookup_reads_the_table_of_the_given_root(tmp_path):
    folder = tmp_path / "4.5.2"
    folder.mkdir()
    doc = {
        "domains": {
            "energy": {"path": "Somewhere", "sources": [{"file": "interface/x", "find": "y"}]}
        },
        "figures": {},
    }
    (folder / "ui_locations.yaml").write_text(yaml.safe_dump(copy.deepcopy(doc)), encoding="utf-8")
    assert where("energy", "energy.net", root=tmp_path).path == "Somewhere"
