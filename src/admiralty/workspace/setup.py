"""Campaign Setup, the part the admiralty:setup skill needs: find Campaigns, list who plays
in one, write campaign.yaml and the workspace CLAUDE.md.

The skill calls these through `admiralty setup ...` and never writes YAML or parses saves
itself, so a wrong answer is caught here (unknown empire, unknown ally) and not three
questions later.
"""

from __future__ import annotations

import shutil
import time
import zipfile
from pathlib import Path
from typing import Any

import rust_parser

from admiralty.extract.header import game_version
from admiralty.extract.snapshot import Extractor
from admiralty.workspace.archive import EXTRACT_SUFFIX
from admiralty.workspace.config import (
    CONFIG_FILE,
    KNOWLEDGE,
    MODES,
    CampaignConfig,
    Player,
    read_raw,
    write_config,
)
from admiralty.workspace.layout import ARCHIVE_DIR, create_workspace, validate_workspace

WORKSPACE_CLAUDE_MD = "CLAUDE.md"


class SetupRefused(ValueError):
    """An answer of the Campaign Setup cannot be used; the message says what to answer instead."""


# --- finding Campaigns and saves -------------------------------------------------------------


def _saves(folder: Path) -> list[Path]:
    return sorted(folder.glob("*.sav"), key=lambda p: (p.stat().st_mtime, p.name))


def read_meta(save: Path) -> dict[str, Any]:
    """The small `meta` file of a save (campaign name, date, version); no gamestate parsing."""
    with zipfile.ZipFile(save) as archive:
        return rust_parser.parse_save_from_string(archive.read("meta").decode("utf-8"))


def campaign_name(meta: dict[str, Any]) -> str:
    """Multiplayer saves carry the Campaign name behind an 'mp_' prefix."""
    return str(meta.get("name", "")).removeprefix("mp_")


def list_campaigns(save_root: Path) -> list[dict[str, Any]]:
    """One entry per subfolder of the Stellaris save folder that holds saves, newest first:
    folder, campaign name, number of saves, newest save with its in-game date and age. Only
    the meta of the newest save is read, so this takes milliseconds."""
    entries = []
    for folder in sorted(p for p in save_root.expanduser().glob("*") if p.is_dir()):
        saves = _saves(folder)
        if not saves:
            continue
        newest = saves[-1]
        try:
            meta = read_meta(newest)
        except OSError, zipfile.BadZipFile, KeyError, ValueError:
            meta = {}  # still listed: a half-written autosave must not hide the Campaign
        entries.append(
            {
                "folder": str(folder),
                "campaign": campaign_name(meta) or folder.name,
                "saves": len(saves),
                "newest_save": newest.name,
                "newest_date": meta.get("date"),
                "newest_age_hours": round((time.time() - newest.stat().st_mtime) / 3600, 1),
                "game_version": game_version(meta) if meta else None,
            }
        )
    return sorted(entries, key=lambda e: e["newest_age_hours"])


def newest_save(save_dir_or_save: Path) -> Path:
    path = save_dir_or_save.expanduser()
    if path.is_file():
        return path
    saves = _saves(path) if path.is_dir() else []
    if not saves:
        raise SetupRefused(f"no saves found in {path}")
    return saves[-1]


def describe_save(save_dir_or_save: Path, extractor: Extractor | None = None) -> dict[str, Any]:
    """Campaign, date, version and the human players of a save (the newest one of a folder),
    each with the Display Name of their empire, as Campaign Setup offers them."""
    save = newest_save(save_dir_or_save)
    ctx = (extractor or Extractor()).context(save)
    meta = ctx.save.meta
    return {
        "save_file": save.name,
        "campaign": campaign_name(meta),
        "date": ctx.g.get("date") or meta.get("date"),
        "game_version": game_version(meta),
        "players": [
            {"name": name, "empire": ctx.country_name(cid), "country_id": cid}
            for cid, name in ctx.player_by_country.items()
        ],
    }


# --- writing the Campaign Setup ------------------------------------------------------------


def _find_player(players: list[dict[str, Any]], wanted: str) -> dict[str, Any] | None:
    """A player by name, empire Display Name or country id (case-insensitive)."""
    key = str(wanted).casefold()
    for player in players:
        if key in (
            str(player["name"]).casefold(),
            str(player["empire"]).casefold(),
            str(player["country_id"]),
        ):
            return player
    return None


def _choices(players: list[dict[str, Any]]) -> str:
    return ", ".join(f"{p['name']} ({p['empire']})" for p in players)


def write_setup(
    workspace: Path,
    save_dir: Path,
    empire: str,
    *,
    mode: str = "consulting",
    knowledge: str = "fair_play",
    allies: tuple[str, ...] = (),
    rivals: tuple[str, ...] = (),
    backup_saves: bool = True,
    reset_archive: bool = False,
    extractor: Extractor | None = None,
) -> dict[str, Any]:
    """Create the workspace if needed, check every answer against the newest save, write
    campaign.yaml and CLAUDE.md. Idempotent; never touches saves/ and only moves archive/
    aside (never deletes it) when the Tracked Empire changes and `reset_archive` says so.

    Nothing is written when any answer is invalid."""
    workspace = workspace.expanduser().resolve()
    save_dir = save_dir.expanduser().resolve()
    if not save_dir.is_dir():
        raise SetupRefused(f"{save_dir} is not a folder; run `admiralty setup campaigns`")
    if mode not in MODES or knowledge not in KNOWLEDGE:
        raise SetupRefused(f"mode must be {' or '.join(MODES)}, knowledge {' or '.join(KNOWLEDGE)}")

    info = describe_save(save_dir, extractor)
    players = info["players"]
    tracked = _find_player(players, empire)
    if tracked is None:
        raise SetupRefused(
            f"No player or empire {empire!r} in {info['save_file']}. Choose one of: "
            f"{_choices(players)}"
        )
    others = []
    for names, relation in ((allies, "ally"), (rivals, "rival")):
        for name in names:
            found = _find_player(players, name)
            if found is None:
                raise SetupRefused(
                    f"No player {name!r} in {info['save_file']}. Choose from: {_choices(players)}"
                )
            if found["name"] == tracked["name"]:
                raise SetupRefused(f"{found['name']} is the Tracked Empire, not an {relation}")
            if any(p.name == found["name"] for p in others):
                raise SetupRefused(f"{found['name']} is listed as ally and rival; choose one")
            others.append(Player(found["name"], relation))

    previous = read_raw(workspace).get("empire") if workspace.is_dir() else None
    archive_dir = workspace / ARCHIVE_DIR
    moved = None
    before = _find_player(players, str(previous)) if previous is not None else tracked
    changed = before is None or before["name"] != tracked["name"]
    if changed and any(archive_dir.glob(f"*{EXTRACT_SUFFIX}")):
        if not reset_archive:
            raise SetupRefused(
                f"The archive holds extracts of {str(previous)!r}; another Tracked Empire would mix "
                "two empires in one history. Use a new workspace, or pass --reset-archive to "
                "move the archive aside (it is not deleted)."
            )
        moved = _move_archive_aside(archive_dir)

    create_workspace(workspace)
    config = write_config(
        workspace,
        save_dir=save_dir,
        campaign=info["campaign"],
        empire=tracked["name"],
        mode=mode,
        knowledge=knowledge,
        backup_saves=backup_saves,
        players=others or None,
    )
    (workspace / WORKSPACE_CLAUDE_MD).write_text(
        render_workspace_claude_md(config), encoding="utf-8"
    )
    return {
        "workspace": str(workspace),
        "campaign": info["campaign"],
        "tracked_empire": {"player": tracked["name"], "empire": tracked["empire"]},
        "mode": config.mode,
        "knowledge": config.knowledge,
        "players": [{"name": p.name, "relation": p.relation} for p in config.players],
        "backup_saves": config.backup_saves,
        "archive_moved_to": str(moved) if moved else None,
    }


def _move_archive_aside(archive_dir: Path) -> Path:
    number = 1
    while (target := archive_dir.with_name(f"{ARCHIVE_DIR}.{number}")).exists():
        number += 1
    shutil.move(archive_dir, target)
    archive_dir.mkdir()
    return target


def check_workspace(workspace: Path, extractor: Extractor | None = None) -> list[str]:
    """Problems of a workspace, including whether the Tracked Empire and the players exist in
    the newest save (the one check that needs the extractor)."""
    workspace = workspace.expanduser().resolve()
    problems = validate_workspace(workspace)
    if problems:
        return problems
    config = CampaignConfig.load(workspace)
    try:
        players = describe_save(config.save_dir, extractor)["players"]
    except SetupRefused as error:
        return [str(error)]
    return validate_workspace(workspace, players)


# --- workspace CLAUDE.md -----------------------------------------------------------------


def render_workspace_claude_md(config: CampaignConfig) -> str:
    """The short, generated CLAUDE.md of a Campaign Workspace: what this directory is, which
    skill answers in which mode, and the rules that keep numbers honest. English; the skills
    speak the Player's language at runtime."""
    campaign = (config.raw or {}).get("campaign") or config.workspace.name
    if config.mode == "coaching":
        questions = (
            "Questions about the current game: use the `admiralty:academy` skill (Coaching mode "
            "is built in milestone M9 and may not be installed yet; if it is missing, answer "
            "from tool results only and say that Coaching is not available)."
        )
    else:
        questions = "Questions about the current game: use the `admiralty:ops` skill."
    knowledge = (
        "God Mode: other empires' secrets (fleets, plans) may be used."
        if config.god_mode
        else "Fair Play: use only what the Tracked Empire could see itself."
    )
    others = "".join(f"\n  - {p.name} ({p.relation})" for p in config.players)
    return f"""<!-- Generated by `admiralty setup write`; rewritten on every run. Edit campaign.yaml, not this file. -->
# Campaign Workspace: {campaign}

Tracked Empire: {config.empire}. Mode: {config.mode}. Knowledge: {config.knowledge}. {knowledge}
{"Other players:" + others if others else "No other human players are tracked."}

## Which skill

- {questions}
- Retrospective questions ("how did we get here", epochs of the Campaign): use the
  `admiralty:debrief` skill. It reads the archive in `archive/`, not the saves.
- Mode never switches on its own; the Player changes it by running `admiralty:setup` again.
- If `{CONFIG_FILE}` is missing or `admiralty setup check` reports problems: run the
  `admiralty:setup` skill first.

## Rules

- Every number and every name comes from an `admiralty` tool result. Use Display Names as
  returned; never show a raw localisation key.
- When `campaign_status` says the save is stale, ask the Player to save again before
  answering about the current situation.
- Do not edit `archive/` or `saves/`.
"""
