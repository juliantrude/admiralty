"""The headless-Chromium driver and the pins check, proven on a stub page (the real page comes in M6 step 3)."""

from __future__ import annotations

import json
import re

import engine_driver as driver
import pytest

PINNED_TAGS = """<script src="https://cdn.jsdelivr.net/npm/cytoscape@3.34.4/dist/cytoscape.min.js" integrity="sha384-lyd1lDWZ623YSUJ/wMQH50y+T81dWKJk7ZoFdYWXQS83b0+QpW0pgdfXEnQnXL/X" crossorigin="anonymous"></script>
<script src="https://cdn.jsdelivr.net/npm/elkjs@0.12.0/lib/elk.bundled.js" integrity="sha384-ww57TDqx4cGknIavPm0QKO+aygLUR1BLSn2Vhbnt1XdYKWcwLyWTFKX7aZMaKIi2" crossorigin="anonymous"></script>
<script src="https://cdn.jsdelivr.net/npm/cytoscape-elk@2.3.0/dist/cytoscape-elk.js" integrity="sha384-VCqo69qSTjiAwEkpykDLjsy96VKDH33my5mKmDfk3HhB85Iy4QwZ9R0IXqYuxV1A" crossorigin="anonymous"></script>"""

STUB = (
    """<!doctype html><html><head><meta charset="utf-8">
"""
    + "{tags}"
    + """
</head><body><pre id="engine-state"></pre><script>
const cy = cytoscape({
  headless: true,
  elements: [
    { data: { id: "a", width: 40, height: 20 } },
    { data: { id: "b", width: 40, height: 20 } },
    { data: { id: "ab", source: "a", target: "b" } },
  ],
});
cy.layout({ name: "elk", elk: { algorithm: "layered", "elk.direction": "RIGHT" }, stop: () => {
  const x = id => Math.round(cy.getElementById(id).position("x"));
  document.getElementById("engine-state").textContent =
    JSON.stringify({ versions: { cytoscape: cytoscape.version, hasElk: typeof ELK }, a: x("a"), b: x("b") });
} }).run();
</script></body></html>"""
)

needs_browser = pytest.mark.skipif(
    driver.skip_reason() is not None, reason=driver.skip_reason() or ""
)


def stub_page() -> str:
    return STUB.replace("{tags}", PINNED_TAGS)


def test_pinned_tags_pass_the_pins_check():
    assert driver.script_pin_problems(PINNED_TAGS) == []


def test_pins_json_matches_the_tags_and_the_versions_doc():
    pins = json.loads(driver.PINS.read_text(encoding="utf-8"))["libraries"]
    doc = (driver.ROOT / "engine" / "VERSIONS.md").read_text(encoding="utf-8")
    assert [pin["url"] for pin in pins] == re.findall(r'src="([^"]+)"', PINNED_TAGS)
    for pin in pins:
        assert pin["integrity"].startswith("sha384-")
        assert pin["version"] in doc
        assert pin["integrity"].removeprefix("sha384-") in doc


@pytest.mark.parametrize(
    "tag, problem",
    [
        (
            '<script src="https://cdn.jsdelivr.net/npm/cytoscape@latest/dist/c.js" integrity="sha384-AAAA" crossorigin="anonymous"></script>',
            "exact version",
        ),
        (
            '<script src="https://cdn.jsdelivr.net/npm/cytoscape@^3.34.4/dist/c.js" integrity="sha384-AAAA" crossorigin="anonymous"></script>',
            "exact version",
        ),
        (
            '<script src="https://cdn.jsdelivr.net/npm/cytoscape@~3.34.4/dist/c.js" integrity="sha384-AAAA" crossorigin="anonymous"></script>',
            "exact version",
        ),
        (
            '<script src="https://cdn.jsdelivr.net/npm/cytoscape/dist/c.js" integrity="sha384-AAAA" crossorigin="anonymous"></script>',
            "exact version",
        ),
        (
            '<script src="https://cdn.jsdelivr.net/npm/cytoscape@3.34.4/dist/c.js" crossorigin="anonymous"></script>',
            "integrity",
        ),
        (
            '<script src="https://cdn.jsdelivr.net/npm/cytoscape@3.34.4/dist/c.js" integrity="sha384-AAAA"></script>',
            "crossorigin",
        ),
    ],
)
def test_pins_check_rejects_a_loose_script_tag(tag, problem):
    problems = driver.script_pin_problems(tag)
    assert len(problems) == 1 and problem in problems[0]


def test_pins_check_rejects_a_page_without_external_scripts():
    assert driver.script_pin_problems("<html></html>") == ["no <script src> found"]


def test_offline_copy_points_at_the_cache_and_drops_integrity():
    rewritten = driver.offline_copy(stub_page())
    assert "cdn.jsdelivr.net" not in rewritten and "integrity" not in rewritten
    assert rewritten.count("file://") == 3


def test_offline_copy_refuses_an_unpinned_script():
    with pytest.raises(driver.EngineDriverError):
        driver.offline_copy('<script src="https://example.com/x.js"></script>')


@needs_browser
def test_headless_chromium_runs_the_libraries_and_the_state_reads_back():
    state = driver.render(stub_page())
    assert state["versions"] == {"cytoscape": "3.34.4", "hasElk": "function"}
    assert state["a"] < state["b"]


@needs_browser
def test_a_page_without_state_is_an_error():
    with pytest.raises(driver.EngineDriverError, match="engine-state"):
        driver.render(PINNED_TAGS + "<body>nothing</body>")
