"""Golden values read off the game UI by the Player (docs/build-plan.md, Appendix A).

Every None is a value nobody has read yet; its test skips as pending. Fill a value in
only from the game UI with the save loaded, never from our own extractor output.
Keys: (campaign, save file) → values. The Tracked Empire is the Player's (Plexxi).
"""

from __future__ import annotations

from typing import Any

PENDING = None

GOLDEN: dict[tuple[str, str], dict[str, Any]] = {
    # early game, Konföderation von Vulkan campaign
    ("vulkan", "2220.04.22.sav"): {
        "date": PENDING,  # top bar, e.g. "2220.04.22"
        "empire_name": PENDING,
        "naval_capacity_used": PENDING,  # Fleet Manager "used / max"
        "naval_capacity_max": PENDING,
        "unity_stockpile": PENDING,  # Traditions screen
        "unity_income": PENDING,
        "next_tradition_cost": PENDING,
        "monthly_net": {  # top bar tooltips
            "energy": PENDING,
            "minerals": PENDING,
            "food": PENDING,
            "alloys": PENDING,
            "influence": PENDING,
        },
        "planets": {
            # planet Display Name → values from the planet view
            # "2": {"system": "Astarte", "districts": {"district_generator": (built, max)},
            #       "open_jobs": n, "unemployed": n, "designation": "Forge World"},
        },
        "renamed_planet": PENDING,  # a planet the Player renamed, as the UI shows it
        "rival": PENDING,  # {"name": ..., "intel_level": "Low"/"Medium"/...}
        "pop_scale": PENDING,  # pops on the capital as the planet view shows them
    },
    ("vulkan", "2259.12.25.sav"): {},
    ("vulkan", "2298.03.11.sav"): {},
    # the prototype's campaign, where Helam and Kith'Valas live
    ("zygerrian", "2271.08.25.sav"): {
        "planets": {
            # "2": {"system": "Helam", "districts": {"district_generator": (3, PENDING)}},
            # "11": {"system": "Kith'Valas"},
        },
    },
}


def value(campaign: str, save: str, *path: str) -> Any:
    node: Any = GOLDEN.get((campaign, save), {})
    for key in path:
        if not isinstance(node, dict):
            return PENDING
        node = node.get(key, PENDING)
    return node
