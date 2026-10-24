"""Golden-test harness.

Reference saves contain friends' player names, so they live in the git-ignored
folder tests/fixtures/saves/ (override with HLIDSKJALF_SAVES). Tests that need
them skip with a clear message when they are missing.

Layout: one subfolder per Campaign, e.g. tests/fixtures/saves/vulkan/2259.12.25.sav
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

SAVES_DIR = Path(os.environ.get("HLIDSKJALF_SAVES", Path(__file__).parent / "fixtures" / "saves"))

# The 4.5.2 reference Campaign "Konföderation von Vulkan" (2200–2298).
VULKAN = "vulkan"
EARLY, MID, LATE = "2220.04.22.sav", "2259.12.25.sav", "2298.03.11.sav"


def reference_save(campaign: str, name: str) -> Path:
    path = SAVES_DIR / campaign / name
    if not path.exists():
        pytest.skip(
            f"reference save missing: {path}. Copy the Campaign's saves into "
            f"{SAVES_DIR / campaign}/ (they stay out of git) or set HLIDSKJALF_SAVES."
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
