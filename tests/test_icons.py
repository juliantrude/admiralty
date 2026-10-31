"""Game icons: every curated node names one that exists, and compose embeds them as PNGs."""

from __future__ import annotations

import base64

import pytest

from admiralty.game import GameEnvironment
from admiralty.graph.icons import embed_icons, icon_paths, load_icon
from admiralty.graph.mechanics import MechanicsGraph


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
            {"id": "alloys.more", "type": "goal", "source": "graph", "mark": "up"},
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
    doc = {"nodes": [{"id": "alloys.more", "type": "goal", "source": "graph", "mark": "up"}]}
    assert embed_icons(doc, None, "v4.5.2") == 0
    assert "icon" not in doc["nodes"][0]


def test_each_mark_draws_its_own_sign_over_the_icon(install):
    file = install / icon_paths("v4.5.2")["alloys.more"]
    plain = load_icon(file)
    marked = {mark: load_icon(file, mark=mark) for mark in ("up", "down", "flag")}
    assert len({plain, *marked.values()}) == 4


def test_every_goal_of_the_graph_carries_a_mark_of_its_own():
    graph = MechanicsGraph.load("v4.5.2")
    assert {g["mark"] for g in graph.goals.values()} <= {"up", "down", "flag"}


FLAG = {
    "icon": "pointy/flag_pointy_2.dds",
    "background": "backgrounds/00_solid.dds",
    "colors": ["intense_red", "grey", "black"],
}


def _flag_pixels(uri):
    import io

    from PIL import Image

    return Image.open(io.BytesIO(base64.b64decode(uri.removeprefix("data:image/png;base64,"))))


def test_a_flag_is_composed_from_background_swatches_and_symbol(install):
    from admiralty.graph.icons import flag_swatches, load_flag

    image = _flag_pixels(load_flag(install, FLAG)).convert("RGB")
    # a solid background is all slot 0: the corner shows that swatch, the symbol sits in the middle
    assert image.getpixel((2, 2)) == flag_swatches(install)["intense_red"]
    assert len(image.getcolors(maxcolors=10_000)) > 10  # the symbol's gold and shading


def test_the_swatches_of_other_slots_colour_the_other_background_channels(install):
    from admiralty.graph.icons import flag_swatches, load_flag

    swatches = flag_swatches(install)
    image = _flag_pixels(
        load_flag(install, {**FLAG, "background": "backgrounds/circle.dds"})
    ).convert("RGB")
    assert image.getpixel((2, 2)) == swatches["intense_red"]  # circle.dds: red outside
    assert image.getpixel((32, 64)) == swatches["grey"]  # green inside, below the symbol


def test_a_flag_with_a_missing_part_is_none(install):
    from admiralty.graph.icons import load_flag

    assert load_flag(install, {**FLAG, "icon": "pointy/nope.dds"}) is None
    assert load_flag(install, {**FLAG, "colors": ["nope", "grey", "black"]}) is None


def test_a_node_naming_an_empire_gets_its_flag(install):
    doc = {
        "nodes": [
            {"id": "model.x", "type": "cause", "source": "model", "empire": "Pallyrian Accord"},
            {"id": "model.y", "type": "cause", "source": "model", "empire": "Unknown"},
            {"id": "model.z", "type": "cause", "source": "model"},
        ]
    }
    assert embed_icons(doc, install, "v4.5.2", {"Pallyrian Accord": FLAG}) == 1
    assert doc["nodes"][0]["flag"].startswith("data:image/png;base64,")
    assert "flag" not in doc["nodes"][1] and "flag" not in doc["nodes"][2]
