"""Golden values read off the game UI by the Player (docs/build-plan.md, Appendix A).

Read by Julian on 2026-10-24 with each save loaded and paused, as Plexxi ("Die Borg").
Values are written as the UI shows them: "5.5k" stays a string, because the UI cuts to
one decimal (5513 shows as 5.5k). Never fill a value from our own extractor output.
Keys: (campaign, save file) → values. Planets: (Display Name, system) → planet view.
Districts: type → (built, maximum); "district_limit" is the planet's overall maximum.
"""

from __future__ import annotations

from typing import Any

PENDING = None

VULKAN_EMPIRE = "Konföderation von Vulkan"

GOLDEN: dict[tuple[str, str], dict[str, Any]] = {
    ("vulkan", "2220.04.22.sav"): {
        "date": "2220.04.26",
        "naval_capacity": (50, 50),
        "unity_stockpile": "1.1k",
        "unity_income": 26,
        "next_tradition_cost": 2166,
        "monthly_net": {"energy": 54, "minerals": 107, "food": 24, "alloys": 31, "influence": 5},
        "planets": {
            ("Unimatrix 1", "Unimatrix 1"): {
                "pops": "5.5k",
                "district_limit": 17,
                "districts": {
                    "district_nexus": (3, 18),
                    "district_nexus_1": (5, 18),
                    "district_nexus_2": (5, 18),
                    "district_nexus_3": (1, 18),  # a second one was under construction
                },
                "open_jobs": 0,
                "unemployed": 273,
            },
            ("2", "Astarte"): {
                "designation": "Forge World",
                "district_limit": 10,
                "districts": {
                    "district_generator": (2, 3),
                    "district_mining": (0, 9),
                    "district_farming": (0, 13),
                    "district_nexus": (3, 13),
                },
                "open_jobs": 0,
                "unemployed": 102,
            },
        },
        "intel": {VULKAN_EMPIRE: 15},
    },
    ("vulkan", "2259.12.25.sav"): {
        "date": "2259.12.29",
        "naval_capacity": (195, 198),
        "unity_stockpile": "2.7k",
        "unity_income": 67,
        "next_tradition_cost": 5063,
        "monthly_net": {"energy": -46, "minerals": 105, "food": 4, "alloys": 88, "influence": 6},
        "planets": {
            ("Unimatrix 1", "Unimatrix 1"): {
                "pops": "7.9k",
                "district_limit": 17,
                "districts": {
                    "district_nexus": (3, 18),
                    "district_nexus_1": (7, 18),
                    "district_nexus_2": (5, 18),
                    "district_nexus_3": (2, 18),
                },
                "open_jobs": 0,
                "unemployed": 8,
            },
            ("2", "Astarte"): {
                "designation": "Forge World",
                "district_limit": 10,
                "districts": {
                    "district_generator": (3, 3),
                    "district_mining": (3, 9),
                    "district_farming": (0, 13),
                    "district_nexus": (3, 13),
                },
                "open_jobs": 0,
                "unemployed": 2,
            },
        },
        "intel": {VULKAN_EMPIRE: 50},
    },
    ("vulkan", "2298.03.11.sav"): {
        "date": "2298.03.16",
        "naval_capacity": (320, 318),
        "unity_stockpile": "8.7k",
        "unity_income": 62,
        "next_tradition_cost": 12742,
        "monthly_net": {"energy": -161, "minerals": 137, "food": -1, "alloys": 198, "influence": 6},
        "planets": {
            ("Unimatrix 1", "Unimatrix 1"): {
                "pops": "7.9k",
                "district_limit": 17,
                "districts": {
                    "district_nexus": (3, 18),
                    "district_nexus_1": (7, 18),
                    "district_nexus_2": (5, 18),
                    "district_nexus_3": (2, 18),
                },
                "open_jobs": 0,
                "unemployed": 20,
            },
            ("2", "Astarte"): {
                "designation": "Tech World",
                "district_limit": 13,
                "districts": {
                    "district_generator": (4, 5),
                    "district_mining": (3, 9),
                    "district_farming": (1, 13),
                    "district_nexus": (3, 13),
                },
                "open_jobs": 0,
                "unemployed": 812,
            },
        },
        "intel": {VULKAN_EMPIRE: 49},
    },
    # the prototype's campaign, where Helam and Kith'Valas live
    ("zygerrian", "2271.08.25.sav"): {
        "planets": {
            ("2", "Helam"): {
                "district_limit": 15,
                "districts": {
                    "district_generator": (3, 3),
                    "district_mining": (1, 5),
                    "district_farming": (1, 7),
                    "district_nexus": (2, 16),
                },
            },
            ("11", "Kith'Valas"): {
                "district_limit": 22,
                "districts": {
                    "district_generator": (4, 8),
                    "district_mining": (2, 6),
                    "district_farming": (5, 11),
                    "district_nexus": (11, 22),
                },
                "open_jobs": 0,
                "unemployed": "1.7k",
            },
        },
    },
}


def value(campaign: str, save: str, *path: Any) -> Any:
    node: Any = GOLDEN.get((campaign, save), {})
    for key in path:
        if not isinstance(node, dict):
            return PENDING
        node = node.get(key, PENDING)
    return node


def shown(number: float) -> str | int:
    """A number as the UI shows it: from 1000 on cut to one decimal with "k"."""
    if abs(number) >= 1000:
        tenths = int(abs(number) / 100)
        sign = "-" if number < 0 else ""
        return f"{sign}{tenths // 10}.{tenths % 10}k"
    return int(number)


def matches(actual: float, expected: str | int) -> bool:
    """Compare an extract value with a UI reading, in the UI's own format."""
    if isinstance(expected, str):
        return shown(actual) == expected
    return shown(actual) == expected or round(actual) == expected
