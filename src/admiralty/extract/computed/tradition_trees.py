"""Free Tradition tree slots and the Traditions left in a tree; the save stores neither.

Tree slots:
    free = max(0, @max_tradition_trees − number of Tradition trees the empire has unlocked)
@max_tradition_trees = 7 (common/scripted_variables/07_scripted_variables_machine_age.txt).
This is the game's own test for "Requires an empty Tradition Tree slot": the Ascension Perk
conditions in common/ascension_perks/00_ascension_paths.txt (fail_text
requires_free_tradition_tree) read `num_tradition_categories < @max_tradition_trees`. No game
file makes the limit grow or shrink, so the count is the cap minus `tradition_categories`.

Traditions left in a tree:
    left = number of the tree's `traditions` (common/tradition_categories/*.txt) the empire has
           not adopted
The adoption and finish bonuses of the tree (tr_*_adopt, tr_*_finish) are not in that list and
are not counted. A tree the empire has not unlocked gives the full tree size.
"""

from __future__ import annotations

from typing import Any

from admiralty.extract.computed.naval_capacity import _defines
from admiralty.extract.context import Context, as_list

DISCOVERY = "tradition_discovery"


def tradition_tree_slots(ctx: Context, country: dict[str, Any]) -> dict[str, Any]:
    maximum = ctx.game.scripted_variables.get("max_tradition_trees")
    if maximum is None:
        maximum = _defines(ctx).get("TRADITION_CATEGORIES_MAX", 7)
    adopted = len(as_list(country.get("tradition_categories")))
    return {"max": int(maximum), "adopted": adopted, "free": max(0, int(maximum) - adopted)}


def traditions_left(ctx: Context, country: dict[str, Any], category: str) -> dict[str, Any]:
    tree = ctx.game.category("tradition_categories").get(category)
    if tree is None:
        raise KeyError(f"tradition category {category!r} not in the game files")
    members = as_list(tree.get("traditions"))
    adopted = set(as_list(country.get("traditions")))
    taken = sum(1 for member in members if member in adopted)
    return {"total": len(members), "adopted": taken, "left": len(members) - taken}
