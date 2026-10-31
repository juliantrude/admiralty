"""W, A, S, D move the view of the graph page (docs/proposals/ops.md entry 13)."""

from __future__ import annotations

import engine_driver as driver
import pytest
from test_engine_page import chain_graph, needs_browser

KEY_EVENT = (
    "document.dispatchEvent(new KeyboardEvent('{kind}', {{key: '{key}', bubbles: true{extra}}}));"
)


def view_after(after_ready: str | None) -> dict:
    return driver.render_engine(chain_graph(), after_ready=after_ready)["view"]


def moved(keys: str, ms: int = 500) -> tuple[float, float]:
    start = view_after(None)
    end = view_after(f'AdmiraltyEngine.pan("{keys}", {ms})')
    assert end["zoom"] == start["zoom"]
    return end["pan"]["x"] - start["pan"]["x"], end["pan"]["y"] - start["pan"]["y"]


@needs_browser
@pytest.mark.parametrize(
    ("keys", "expected"),
    [("w", (0, 350)), ("s", (0, -350)), ("a", (350, 0)), ("d", (-350, 0)), ("ws", (0, 0))],
)
def test_each_key_moves_the_view_in_its_direction(keys, expected):
    assert moved(keys) == pytest.approx(expected, abs=1)


@needs_browser
def test_two_keys_move_diagonally_at_the_same_speed():
    dx, dy = moved("wd")
    assert (dx, dy) == pytest.approx((-350 / 2**0.5, 350 / 2**0.5), abs=1)


@needs_browser
def test_moving_the_view_leaves_the_nodes_where_they_are():
    start = driver.render_engine(chain_graph())
    end = driver.render_engine(chain_graph(), after_ready='AdmiraltyEngine.pan("wa", 800)')
    assert end["nodes"] == start["nodes"]


@needs_browser
def test_a_held_key_moves_the_view_until_it_is_released():
    press = KEY_EVENT.format(kind="keydown", key="W", extra="")
    release = KEY_EVENT.format(kind="keyup", key="W", extra="")
    held = view_after(f"{press} setTimeout(() => {{ {release} }}, 300);")
    assert held["pan"]["y"] > view_after(None)["pan"]["y"]


@needs_browser
@pytest.mark.parametrize("extra", [", ctrlKey: true", ", metaKey: true", ", altKey: true"])
def test_chords_with_w_do_not_move_the_view(extra):
    press = KEY_EVENT.format(kind="keydown", key="w", extra=extra)
    release = KEY_EVENT.format(kind="keyup", key="w", extra="")
    chord = view_after(f"{press} setTimeout(() => {{ {release} }}, 300);")
    assert chord == view_after(None)


@needs_browser
def test_typing_in_a_field_does_not_move_the_view():
    press = (
        "const f = document.createElement('input'); document.body.append(f);"
        "f.dispatchEvent(new KeyboardEvent('keydown', {key: 'w', bubbles: true}));"
        "setTimeout(() => f.dispatchEvent(new KeyboardEvent('keyup', {key: 'w', bubbles: true})), 300);"
    )
    assert view_after(press) == view_after(None)
