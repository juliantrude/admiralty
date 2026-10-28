"""Free Ascension Perk slots, which the save does not store (it lists only the perks taken).

Formula:
    unlocked = min(Σ ascension_perks_add, ASCENSION_PERKS_SLOTS)
    free     = max(0, unlocked − perks taken)
Sources of ascension_perks_add (common/traditions: the `modifier` of every tr_*_finish and of
some adoption bonuses; common/technology/00_soc_tech.txt:5960, tech_ascension_theory); they
come from the Ledger in computed/modifiers.py. There is no base slot: no game file adds one,
and on all 15 reference saves (vulkan, zygerrian) the unlocked count never falls below the
perks taken. The slot text in localisation/english/utopia_l_english.yml
(ADOPT_TRADITION_TREE_TO_UNLOCK_ASCENSION_PERK_SLOT) names the same two sources: "Finish a
Tradition group ... or research the Ascension Theory technology".
ASCENSION_PERKS_SLOTS = 8 is the cap (common/defines/00_defines.txt, NGameplay).
A perk's own prerequisite (technology, ethic) is not part of the number.
"""

from __future__ import annotations

from typing import Any

from admiralty.extract.computed.modifiers import Ledger
from admiralty.extract.computed.naval_capacity import _defines
from admiralty.extract.context import Context, as_list


def ascension_slots(ctx: Context, country: dict[str, Any], ledger: Ledger) -> dict[str, Any]:
    cap = int(_defines(ctx).get("ASCENSION_PERKS_SLOTS", 8))
    unlocked = min(int(ledger.total("ascension_perks_add")), cap)
    taken = len(as_list(country.get("ascension_perks")))
    return {"unlocked": unlocked, "cap": cap, "taken": taken, "free": max(0, unlocked - taken)}
