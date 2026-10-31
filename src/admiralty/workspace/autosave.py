"""The Player's autosave interval, read from the game's `settings.txt`, and what to tell them
about it.

The game overwrites autosaves in turn, so a rare autosave leaves the save service (`watch`)
little to copy. Admiralty only reads the setting and recommends; it never changes game settings.

`autosave=<n>` indexes the options of the settings screen in the order of their localisation
keys (`localisation/english/main_2_l_english.yml`, `AUTOSAVE_NEVER` ... `AUTOSAVE_YEARLY`;
`interface/settings_view.gui`, `autosave_spinner`): 0 Never, 1 Daily, 2 Monthly, 3 Quarterly,
4 Semiannually, 5 Annually. Checked against the real game: `autosave=4` in the Player's
settings.txt and autosave files of the Mireesh Campaign dated 2293.07.01, 2294.01.01, 2294.07.01.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

# (name as the game shows it, months between two autosaves; None = never)
AUTOSAVE_OPTIONS: tuple[tuple[str, float | None], ...] = (
    ("Never", None),
    ("Daily", 1 / 30),
    ("Monthly", 1),
    ("Quarterly", 3),
    ("Semiannually", 6),
    ("Annually", 12),
)
RECOMMENDED = "Quarterly"
_RECOMMENDED_MONTHS = 3


def read_autosave(user_dir: Path) -> dict[str, Any]:
    """`setting` (the game's name of the option, None when settings.txt or the line is missing
    or the value is unknown), `months`, and `recommend` (True when the interval is rarer than
    quarterly or autosave is off). Never raises on a missing or odd settings file."""
    path = user_dir.expanduser() / "settings.txt"
    value = None
    if path.is_file():
        match = re.search(
            r"^autosave=(\d+)\s*$", path.read_text(encoding="utf-8", errors="replace"), re.M
        )
        value = int(match.group(1)) if match else None
    if value is None or value >= len(AUTOSAVE_OPTIONS):
        return {"setting": None, "months": None, "recommend": False}
    name, months = AUTOSAVE_OPTIONS[value]
    return {
        "setting": name,
        "months": months,
        "recommend": months is None or months > _RECOMMENDED_MONTHS,
    }


def autosave_hint(user_dir: Path) -> dict[str, Any]:
    """The reading of `read_autosave` plus `recommended` (the interval to suggest, only when the
    current one is rarer) and `hint`, one English sentence for the skill to pass on."""
    found = read_autosave(user_dir)
    if found["setting"] is None:
        hint = "The autosave interval could not be read from the game's settings.txt."
    elif found["recommend"]:
        hint = (
            f"Autosave is {found['setting']}. Setting it to {RECOMMENDED} in the game's settings "
            "gives Debrief more points in time to look back on; Admiralty does not change it."
        )
    else:
        hint = f"Autosave is {found['setting']}, often enough for Debrief."
    return found | {"recommended": RECOMMENDED if found["recommend"] else None, "hint": hint}
