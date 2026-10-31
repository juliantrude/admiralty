"""The headless-Chromium driver and the pins check, proven on a stub page (the real page comes in M6 step 3)."""

from __future__ import annotations

import base64
import hashlib
import json
import re
import sys

import engine_driver as driver
import pytest

LIBRARY_TAGS = """<script src="vendor/cytoscape.min.js"></script>
<script src="vendor/elk.bundled.js"></script>
<script src="vendor/cytoscape-elk.js"></script>"""

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
    return STUB.replace("{tags}", LIBRARY_TAGS)


def pins() -> list[dict]:
    return json.loads(driver.PINS.read_text(encoding="utf-8"))["libraries"]


def sri(data: bytes) -> str:
    return "sha384-" + base64.b64encode(hashlib.sha384(data).digest()).decode("ascii")


def test_every_pin_is_an_exact_version_and_names_its_file_and_licence():
    for pin in pins():
        assert re.fullmatch(r"\d+\.\d+\.\d+", pin["version"]), pin["name"]
        assert f"@{pin['version']}/" in pin["url"], pin["name"]
        assert pin["integrity"].startswith("sha384-")
        assert (driver.VENDOR / pin["license_file"]).stat().st_size > 500, pin["name"]
        assert pin["license"]


def test_the_vendored_files_match_their_pins_and_nothing_else_is_there():
    expected = {pin["file"] for pin in pins()} | {pin["license_file"] for pin in pins()}
    assert {path.name for path in driver.VENDOR.iterdir()} == expected
    for pin in pins():
        assert sri((driver.VENDOR / pin["file"]).read_bytes()) == pin["integrity"], pin["name"]


def test_pins_json_matches_the_versions_doc():
    doc = (driver.ROOT / "engine" / "VERSIONS.md").read_text(encoding="utf-8")
    for pin in pins():
        assert pin["version"] in doc
        assert pin["integrity"].removeprefix("sha384-") in doc
        assert pin["license"] in doc


def test_the_fetch_tool_refuses_a_file_that_does_not_match_its_pin(tmp_path, monkeypatch):
    sys.path.insert(0, str(driver.ROOT / "tools"))
    import fetch_engine_libs

    monkeypatch.setattr(fetch_engine_libs, "_download", lambda url: b"tampered")
    with pytest.raises(ValueError, match="does not match the pin"):
        fetch_engine_libs.fetch(pins()[0], tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_external_loads_finds_scripts_stylesheets_imports_and_urls_but_not_inline_data():
    assert driver.external_loads(LIBRARY_TAGS) != []
    assert driver.external_loads('<link rel="stylesheet" href="https://x.test/a.css">') != []
    assert driver.external_loads("<style>@import 'a.css'; b { background: url(a.png) }</style>")
    assert (
        driver.external_loads('<style>@font-face { src: url("data:font/woff2;base64,AA") }</style>')
        == []
    )
    assert driver.external_loads("<script>const a = 1;</script>") == []


@needs_browser
def test_headless_chromium_runs_the_libraries_and_the_state_reads_back():
    state = driver.render(stub_page())
    assert state["versions"] == {"cytoscape": "3.34.4", "hasElk": "function"}
    assert state["a"] < state["b"]


@needs_browser
def test_a_page_without_state_is_an_error():
    with pytest.raises(driver.EngineDriverError, match="engine-state"):
        driver.render(LIBRARY_TAGS + "<body>nothing</body>")


@needs_browser
def test_the_driver_cuts_the_network():
    probe = (
        '<pre id="engine-state"></pre><script>fetch("https://cdn.jsdelivr.net/")'
        '.then(() => "reached", () => "blocked").then(r => '
        'document.getElementById("engine-state").textContent = JSON.stringify({r}));</script>'
    )
    assert driver.render(probe)["r"] == "blocked"
