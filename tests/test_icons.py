"""Game icons: every curated node names one that exists, and compose embeds them as PNGs."""

from __future__ import annotations

import base64

import pytest

from hlidskjalf.game import GameEnvironment
from hlidskjalf.graph.icons import embed_icons, icon_paths
from hlidskjalf.graph.mechanics import MechanicsGraph


@pytest.fixture(scope="module")
def install():
    try:
        return GameEnvironment.detect().install_dir
    except FileNotFoundError:
        pytest.skip("Stellaris is not installed here; icons come from the Player's install")


def test_every_goal_and_node_of_the_graph_has_an_icon():
    graph = MechanicsGraph.load("v4.5.2")
    assert set(graph.nodes) | set(graph.goals) <= set(icon_paths("v4.5.2"))


def test_every_icon_file_exists_in_the_install(install):
    missing = [p for p in set(icon_paths("v4.5.2").values()) if not (install / p).exists()]
    assert missing == []


def test_icons_are_embedded_as_png_for_graph_nodes_only(install):
    doc = {
        "nodes": [
            {"id": "alloys.more", "type": "goal", "source": "graph"},
            {"id": "alloys.few_metallurgists", "type": "cause", "source": "graph"},
            {"id": "model.idea", "type": "remedy", "source": "model"},
        ]
    }
    assert embed_icons(doc, install, "v4.5.2") == 2
    for node in doc["nodes"][:2]:
        data = node["icon"].removeprefix("data:image/png;base64,")
        assert base64.b64decode(data).startswith(b"\x89PNG")
    assert "icon" not in doc["nodes"][2]


def test_without_an_install_nothing_is_embedded():
    doc = {"nodes": [{"id": "alloys.more", "type": "goal", "source": "graph"}]}
    assert embed_icons(doc, None, "v4.5.2") == 0
    assert "icon" not in doc["nodes"][0]
