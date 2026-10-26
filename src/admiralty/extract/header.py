"""Header of a Snapshot extract: version, date, players, version gate and mod check."""

from __future__ import annotations

import re
from typing import Any

from admiralty.extract.context import Context
from admiralty.game import GameEnvironment

# The game version the shipped knowledge pack (Mechanics Graph, Playbook) is built for.
KNOWLEDGE_PACK_VERSION = "4.5.2"


def game_version(meta: dict[str, Any]) -> str:
    """'Cygnus v4.5.2' → '4.5.2'."""
    match = re.search(r"v?(\d+\.\d+(?:\.\d+)?)", str(meta.get("version", "")))
    return match.group(1) if match else str(meta.get("version", ""))


def build_header(ctx: Context, env: GameEnvironment, tracked: int) -> dict[str, Any]:
    meta = ctx.save.meta
    version = game_version(meta)
    warnings: list[str] = []
    if version != KNOWLEDGE_PACK_VERSION:
        warnings.append(
            f"Save is from game version {version}, but the knowledge pack is for "
            f"{KNOWLEDGE_PACK_VERSION}. Mechanics and numbers may differ."
        )
    mods = []
    for mod in env.enabled_mods:
        mods.append({"name": mod.name, "cosmetic": mod.is_cosmetic})
        if not mod.is_cosmetic:
            changed = ", ".join(sorted(mod.content_folders - mod.COSMETIC_FOLDERS))
            warnings.append(
                f"Mod '{mod.name}' changes game content ({changed}); values may not match vanilla."
            )
    saved_mods = sorted(set(meta.get("mods") or []) - {m.name for m in env.enabled_mods})
    for name in saved_mods:
        warnings.append(f"The save was played with mod '{name}', which is not enabled now.")

    players = [
        {"name": name, "country_id": cid, "empire": ctx.country_name(cid)}
        for cid, name in ctx.player_by_country.items()
    ]
    return {
        "save_file": ctx.save.path.name,
        "campaign": _campaign_name(meta),
        "game_version": version,
        "date": ctx.g.get("date") or meta.get("date"),
        "players": players,
        "tracked_empire": {
            "country_id": tracked,
            "name": ctx.country_name(tracked),
            "player": ctx.player_by_country.get(tracked),
        },
        "mods": mods,
        "warnings": warnings,
    }


def _campaign_name(meta: dict[str, Any]) -> str:
    name = str(meta.get("name", ""))
    return name.removeprefix("mp_")


def resolve_tracked_empire(ctx: Context, empire: str | int | None) -> int:
    """Find the Tracked Empire by player name, empire Display Name or country id.
    Without a choice, single-player saves pick the only player."""
    if isinstance(empire, int) or (isinstance(empire, str) and empire.isdigit()):
        cid = int(empire)
        if cid in ctx.countries:
            return cid
        raise LookupError(f"no country with id {cid}")
    if empire is None:
        players = list(ctx.player_by_country)
        if len(players) == 1:
            return players[0]
        names = ", ".join(ctx.player_by_country.values())
        raise LookupError(f"several players in this save ({names}); choose a Tracked Empire")
    wanted = empire.casefold()
    for cid, player in ctx.player_by_country.items():
        if player.casefold() == wanted:
            return cid
    for cid in ctx.countries:
        if "name" in ctx.countries[cid] and ctx.country_name(cid).casefold() == wanted:
            return cid
    raise LookupError(f"no player or empire named {empire!r}")
