"""Unity cost of the next Tradition, which the save does not store.

Formula, from common/defines/00_defines.txt (NGameplay / NEconomy):
    base   = TRADITION_COST_AMOUNTS (300 Unity) + (TRADITION_COST_TRADITION × N) ^ TRADITION_COST_TRADITION_EXP
    size   = 1 + EMPIRE_SIZE_TRADITION_COST_PENALTY × max(0, empire_size − EMPIRE_SIZE_BASE)
                 × (1 + Σ tradition_cost_empire_size_mult)
    cost   = base × size × (1 + Σ tradition_cost_mult) × galaxy setting 'traditions'
N counts every entry of the empire's tradition list: tree adoptions (tr_*_adopt) and
tree completions (tr_*_finish) included. Settled by golden values on 2026-10-24: this
reproduces 2166, 5063 and 12742 (UI) as 2166, 5063 and 12744 for the vulkan saves.
tradition_cost_mult and tradition_cost_empire_size_mult come from civics, ascension perks
and static modifiers (see computed/modifiers.py). empire_size is stored in the save.
Pinned by golden tests: the Player reads the next Tradition's cost off the Traditions screen.
"""

from __future__ import annotations

from typing import Any

from admiralty.extract.computed.modifiers import Ledger
from admiralty.extract.computed.naval_capacity import _defines
from admiralty.extract.context import Context, as_list, block, rounded


def adopted_count(traditions: list[str]) -> int:
    """Every entry counts, adoptions and completions included (see module docstring)."""
    return len(traditions)


def next_tradition_cost(ctx: Context, country: dict[str, Any], ledger: Ledger) -> dict[str, Any]:
    defines = _defines(ctx)
    base_amount = as_list(defines.get("TRADITION_COST_AMOUNTS", [300]))[0]
    per_tradition = defines.get("TRADITION_COST_TRADITION", 8)
    exponent = defines.get("TRADITION_COST_TRADITION_EXP", 1.8)
    penalty = defines.get("EMPIRE_SIZE_TRADITION_COST_PENALTY", 0.002)
    size_base = defines.get("EMPIRE_SIZE_BASE", 100)

    count = adopted_count(as_list(country.get("traditions")))
    empire_size = country.get("empire_size", 0)
    size_mult = ledger.total("tradition_cost_empire_size_mult")
    cost_mult = ledger.total("tradition_cost_mult")
    galaxy = float(block(ctx.g.get("galaxy")).get("traditions", 1))

    base = base_amount + (per_tradition * count) ** exponent
    size_factor = 1 + penalty * max(0, empire_size - size_base) * (1 + size_mult)
    cost = base * size_factor * (1 + cost_mult) * galaxy
    stockpile = block(block(country["modules"].get("standard_economy_module")).get("resources"))
    unity = stockpile.get("unity", 0)
    return {
        "cost": round(cost),
        "unity_stockpile": rounded(unity),
        "affordable": unity >= cost,
        "breakdown": {
            "traditions_counted": count,
            "base": rounded(base),
            "empire_size": empire_size,
            "empire_size_factor": rounded(size_factor, 3),
            "tradition_cost_mult": rounded(cost_mult, 3),
            "tradition_cost_empire_size_mult": rounded(size_mult, 3),
            "galaxy_setting_mult": galaxy,
        },
    }
