"""The directory layout of a Campaign Workspace: create it, check it.

<workspace>/
    campaign.yaml   the Campaign Setup
    CLAUDE.md       generated; routes to the skill of the chosen mode
    archive/        one extract per in-game date (workspace/archive.py)
    saves/          backup copies of the saves that were read
    predictions/    reserved for Coaching mode (M9), created so the layout is stable
    .hlidskjalf/    machine state: turn log, Unverified Claim blocks
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from hlidskjalf.workspace.config import (
    CONFIG_FILE,
    STATE_DIR,
    CampaignConfig,
    SetupMissing,
)

ARCHIVE_DIR = "archive"
SAVES_DIR = "saves"
PREDICTIONS_DIR = "predictions"
DIRECTORIES = (ARCHIVE_DIR, SAVES_DIR, PREDICTIONS_DIR, STATE_DIR)


class NotAWorkspace(ValueError):
    """The directory holds other things and was never set up as a Campaign Workspace."""


def is_workspace(path: Path) -> bool:
    return (path / CONFIG_FILE).exists() or (path / STATE_DIR).is_dir()


def create_workspace(path: Path) -> Path:
    """Make `path` a Campaign Workspace. Idempotent for an existing workspace; refuses a
    directory that has other content, so a Player never turns Documents into a Campaign."""
    path = path.expanduser().resolve()
    if path.exists() and not path.is_dir():
        raise NotAWorkspace(f"{path} is a file, not a directory")
    if path.is_dir() and not is_workspace(path) and any(path.iterdir()):
        raise NotAWorkspace(
            f"{path} is not empty and is not a Campaign Workspace; choose a new or empty directory"
        )
    for name in DIRECTORIES:
        (path / name).mkdir(parents=True, exist_ok=True)
    return path


def validate_workspace(path: Path, players: Iterable[dict[str, Any]] | None = None) -> list[str]:
    """Plain-language problems of a workspace; an empty list means ready to use.

    File-level checks only. Whether the Tracked Empire and the players exist in the newest
    save needs the extractor, so the caller passes the save header's `players` (dicts with
    name, empire, country_id) when it has them."""
    path = path.expanduser().resolve()
    if not path.is_dir():
        return [f"{path} does not exist"]
    problems = [
        f"directory {name}/ is missing" for name in DIRECTORIES if not (path / name).is_dir()
    ]
    try:
        config = CampaignConfig.load(path)
    except SetupMissing as error:
        return [str(error), *problems]
    if not config.save_dir.is_dir():
        problems.append(f"save_dir {config.save_dir} does not exist")
    elif not any(config.save_dir.glob("*.sav")):
        problems.append(f"save_dir {config.save_dir} holds no saves")
    if players is not None:
        problems += _player_problems(config, list(players))
    return problems


def _player_problems(config: CampaignConfig, players: list[dict[str, Any]]) -> list[str]:
    names = {str(p["name"]) for p in players}
    empires = {str(p["empire"]) for p in players} | {str(p["country_id"]) for p in players}
    problems = []
    if str(config.empire) not in names | empires:
        problems.append(f"empire {config.empire!r} is not a player or empire in the newest save")
    for player in config.players:
        if player.name not in names:
            problems.append(f"player {player.name!r} is not in the newest save")
    return problems
