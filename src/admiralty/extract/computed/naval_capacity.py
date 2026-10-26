"""Maximum naval capacity, which the save does not store (only the used part).

Formula (common/defines/00_defines.txt, NCountry):
    max = (NAVAL_CAPACITY_BASE + Σ country_naval_cap_add) × (1 + Σ country_naval_cap_mult)
          × galaxy setting naval_capacity_mult, capped at NAVAL_CAPACITY_MAX
Sources of country_naval_cap_add / _mult: technologies (common/technology), traditions
(common/traditions, Supremacy), ascension perks, civics and origins, edicts, policies,
starbase modules and buildings (Anchorage: common/starbase_modules), soldier-type jobs
(common/pop_jobs, country_modifier per job) and timed country modifiers
(common/static_modifiers). See computed/modifiers.py for how they are collected.
Pinned by golden tests: the Player reads "naval capacity used / max" off the Fleet Manager.
"""

from __future__ import annotations

from typing import Any

from admiralty.extract.computed.modifiers import Ledger
from admiralty.extract.context import Context, block, rounded


def naval_capacity(ctx: Context, country: dict[str, Any], ledger: Ledger) -> dict[str, Any]:
    defines = _defines(ctx)
    base = defines.get("NAVAL_CAPACITY_BASE", 0)
    cap = defines.get("NAVAL_CAPACITY_MAX", 9999)
    galaxy_mult = float(block(ctx.g.get("galaxy")).get("naval_capacity_mult", 1))

    def compute(certain_only: bool) -> float:
        add = ledger.total("country_naval_cap_add", certain_only)
        mult = ledger.total("country_naval_cap_mult", certain_only)
        return min((base + add) * (1 + mult) * galaxy_mult, cap)

    maximum = compute(certain_only=True)
    grouped: dict[tuple[str, str], float] = {}
    for key in ("country_naval_cap_add", "country_naval_cap_mult"):
        for c in ledger.contributions(key):
            if not c.certain:
                grouped[(c.source, key)] = grouped.get((c.source, key), 0) + c.amount
    uncertain = [
        {"source": source, "modifier": key, "amount": rounded(amount)}
        for (source, key), amount in grouped.items()
    ]
    result = {
        "used": country.get("used_naval_capacity", 0),
        "max": int(maximum),
        "breakdown": {
            "base": base,
            "add": _grouped(ledger, "country_naval_cap_add"),
            "mult": _grouped(ledger, "country_naval_cap_mult"),
            "galaxy_setting_mult": galaxy_mult,
        },
    }
    if uncertain:
        result["uncertain"] = uncertain
        result["max_if_all_uncertain_apply"] = int(compute(certain_only=False))
    return result


def _grouped(ledger: Ledger, key: str) -> list[dict[str, Any]]:
    """Certain contributions summed per source, e.g. four Anchorages as one line."""
    totals: dict[str, list[float]] = {}
    for c in ledger.contributions(key):
        if c.certain:
            totals.setdefault(c.source, []).append(c.amount)
    return [
        {"source": source, "amount": rounded(sum(amounts)), "count": len(amounts)}
        if len(amounts) > 1
        else {"source": source, "amount": rounded(amounts[0])}
        for source, amounts in totals.items()
    ]


def _defines(ctx: Context) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for group in ctx.game.defines().values():
        merged.update(group)
    return merged
