"""Golden-test harness.

Reference saves contain friends' player names, so they live in the git-ignored
folder tests/fixtures/saves/ (override with ADMIRALTY_SAVES). Tests that need
them skip with a clear message when they are missing.

Layout: one subfolder per Campaign, e.g. tests/fixtures/saves/vulkan/2259.12.25.sav
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

SAVES_DIR = Path(os.environ.get("ADMIRALTY_SAVES", Path(__file__).parent / "fixtures" / "saves"))

# Time budgets from the build plan assume a CPU at full clock. On a throttled machine
# (powersave governor, battery) set ADMIRALTY_PERF_SLACK=1.5 or so.
PERF_SLACK = float(os.environ.get("ADMIRALTY_PERF_SLACK", "1.0"))


@pytest.fixture(autouse=True)
def no_browser(monkeypatch):
    """`briefing compose` opens the current Briefing in the browser; no test does that unless it
    says so (`monkeypatch.delenv("ADMIRALTY_NO_BROWSER")`)."""
    monkeypatch.setenv("ADMIRALTY_NO_BROWSER", "1")


@pytest.fixture(autouse=True)
def data_dir(monkeypatch, tmp_path_factory):
    """The save service keeps its registry, state and inbox under the Player's data folder; no
    test touches the real one."""
    path = tmp_path_factory.mktemp("admiralty-data")
    monkeypatch.setenv("ADMIRALTY_DATA_DIR", str(path))
    return path


def budget(seconds: float) -> float:
    return seconds * PERF_SLACK


# The 4.5.2 reference Campaign "Konföderation von Vulkan" (2200–2298).
VULKAN = "vulkan"
EARLY, MID, LATE = "2220.04.22.sav", "2259.12.25.sav", "2298.03.11.sav"


def reference_save(campaign: str, name: str) -> Path:
    path = SAVES_DIR / campaign / name
    if not path.exists():
        pytest.skip(
            f"reference save missing: {path}. Copy the Campaign's saves into "
            f"{SAVES_DIR / campaign}/ (they stay out of git) or set ADMIRALTY_SAVES."
        )
    return path


@pytest.fixture
def late_save() -> Path:
    return reference_save(VULKAN, LATE)


@pytest.fixture
def mid_save() -> Path:
    return reference_save(VULKAN, MID)


@pytest.fixture
def early_save() -> Path:
    return reference_save(VULKAN, EARLY)
