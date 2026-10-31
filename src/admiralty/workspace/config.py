"""campaign.yaml: the Campaign Setup a Campaign Workspace runs on.

Written by `admiralty setup write` (the admiralty:setup skill calls it; nobody writes YAML
by hand any more, but hand edits are fine and survive a rewrite):

    version: 1
    save_dir: ~/.local/share/Paradox Interactive/Stellaris/save games/mpkonfderationvonvulkan_-2027490598
    empire: Plexxi            # player name, empire name or country id of the Tracked Empire
    mode: consulting          # or coaching; never switches on its own
    knowledge: fair_play      # or god_mode
    backup_saves: true        # copy every save that is read into saves/
    save_service: true        # the Player wants `admiralty watch` to copy saves while the game runs
    save_reminder_minutes: 20 # no new save for this long while the game runs: a desktop reminder; 0 = off
    players:                  # everyone else who plays along; may be empty
      - {name: Friend1, relation: ally}   # ally or rival
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

CONFIG_FILE = "campaign.yaml"
CONFIG_VERSION = 1
DEFAULT_REMINDER_MINUTES = 20
STATE_DIR = ".admiralty"  # inside the Campaign Workspace: turn log, caches

MODES = ("consulting", "coaching")
KNOWLEDGE = ("fair_play", "god_mode")
RELATIONS = ("ally", "rival")


class SetupMissing(LookupError):
    """The workspace has no usable Campaign Setup yet."""


class SetupInvalid(SetupMissing):
    """campaign.yaml exists but holds a value the Campaign Setup does not allow."""


@dataclass(frozen=True)
class Player:
    """Another human player of the Campaign, as seen from the Tracked Empire."""

    name: str  # player name as in the save
    relation: str  # "ally" or "rival"


@dataclass(frozen=True)
class CampaignConfig:
    workspace: Path
    save_dir: Path
    empire: str | int
    mode: str = "consulting"
    knowledge: str = "fair_play"
    backup_saves: bool = True
    save_service: bool = False
    save_reminder_minutes: int = DEFAULT_REMINDER_MINUTES
    players: tuple[Player, ...] = ()
    raw: dict[str, Any] | None = None

    @property
    def god_mode(self) -> bool:
        return self.knowledge == "god_mode"

    @property
    def state_dir(self) -> Path:
        return self.workspace / STATE_DIR

    @classmethod
    def load(cls, workspace: Path) -> CampaignConfig:
        """Read campaign.yaml; ADMIRALTY_SAVE_DIR / ADMIRALTY_EMPIRE override it, which
        lets tests and first experiments run without a Campaign Setup."""
        workspace = workspace.resolve()
        data = read_raw(workspace)
        save_dir = os.environ.get("ADMIRALTY_SAVE_DIR") or data.get("save_dir")
        empire = os.environ.get("ADMIRALTY_EMPIRE") or data.get("empire")
        if not save_dir or empire in (None, ""):
            raise SetupMissing(
                f"No Campaign Setup in {workspace}: {CONFIG_FILE} needs save_dir and empire. "
                "Run the admiralty:setup skill."
            )
        return cls(
            workspace=workspace,
            save_dir=Path(os.path.expanduser(str(save_dir))),
            empire=empire,
            mode=_choice(data, "mode", MODES, "consulting"),
            knowledge=_choice(data, "knowledge", KNOWLEDGE, "fair_play"),
            backup_saves=_flag(data, "backup_saves", True),
            save_service=_flag(data, "save_service", False),
            save_reminder_minutes=_minutes(data, "save_reminder_minutes", DEFAULT_REMINDER_MINUTES),
            players=parse_players(data.get("players")),
            raw=data,
        )


def read_raw(workspace: Path) -> dict[str, Any]:
    """campaign.yaml as a dict ({} when missing); a file that is not a mapping is invalid."""
    path = workspace / CONFIG_FILE
    if not path.exists():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as error:
        raise SetupInvalid(f"{path} is not valid YAML: {error}") from error
    if not isinstance(data, dict):
        raise SetupInvalid(f"{path} must be a mapping of settings, not {type(data).__name__}")
    return data


def parse_players(value: Any) -> tuple[Player, ...]:
    if value in (None, ""):
        return ()
    if not isinstance(value, list):
        raise SetupInvalid("players must be a list of {name, relation} entries")
    players: list[Player] = []
    for entry in value:
        if not isinstance(entry, dict) or not entry.get("name"):
            raise SetupInvalid(f"every player needs a name, got {entry!r}")
        relation = entry.get("relation")
        if relation not in RELATIONS:
            raise SetupInvalid(
                f"relation of player {entry['name']!r} must be ally or rival, not {relation!r}"
            )
        if any(p.name == entry["name"] for p in players):
            raise SetupInvalid(f"player {entry['name']!r} is listed twice")
        players.append(Player(str(entry["name"]), relation))
    return tuple(players)


def write_config(workspace: Path, **fields: Any) -> CampaignConfig:
    """Merge `fields` into campaign.yaml and write it atomically (temp file, rename).

    Keys the Player added by hand are kept; a field set to None is removed. Every value is
    validated before anything is written, so a bad answer leaves the old file untouched.
    `players` may be given as Player objects or as {name, relation} dicts."""
    workspace = workspace.resolve()
    data = read_raw(workspace)
    for key, value in fields.items():
        if key == "players" and value is not None:
            value = [
                {"name": p.name, "relation": p.relation} if isinstance(p, Player) else dict(p)
                for p in value
            ]
        if value is None:
            data.pop(key, None)
        else:
            data[key] = str(value) if isinstance(value, Path) else value
    data["version"] = CONFIG_VERSION
    _check(data)
    workspace.mkdir(parents=True, exist_ok=True)
    text = yaml.safe_dump(_ordered(data), sort_keys=False, allow_unicode=True)
    handle, temp = tempfile.mkstemp(dir=workspace, prefix=f".{CONFIG_FILE}.")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as out:
            out.write(text)
        os.replace(temp, workspace / CONFIG_FILE)
    except BaseException:
        Path(temp).unlink(missing_ok=True)
        raise
    return CampaignConfig.load(workspace)


_KEY_ORDER = (
    "version",
    "save_dir",
    "campaign",
    "empire",
    "mode",
    "knowledge",
    "backup_saves",
    "save_service",
    "save_reminder_minutes",
    "players",
)


def _ordered(data: dict[str, Any]) -> dict[str, Any]:
    known = {k: data[k] for k in _KEY_ORDER if k in data}
    return known | {k: v for k, v in data.items() if k not in known}


def _check(data: dict[str, Any]) -> None:
    _choice(data, "mode", MODES, "consulting")
    _choice(data, "knowledge", KNOWLEDGE, "fair_play")
    _flag(data, "backup_saves", True)
    _flag(data, "save_service", False)
    _minutes(data, "save_reminder_minutes", DEFAULT_REMINDER_MINUTES)
    parse_players(data.get("players"))


def _choice(data: dict[str, Any], key: str, allowed: tuple[str, ...], default: str) -> str:
    value = data.get(key, default)
    if value not in allowed:
        raise SetupInvalid(f"{key} must be {' or '.join(allowed)}, not {value!r}")
    return value


def _flag(data: dict[str, Any], key: str, default: bool) -> bool:
    value = data.get(key, default)
    if not isinstance(value, bool):
        raise SetupInvalid(f"{key} must be true or false, not {value!r}")
    return value


def reminder_minutes(data: dict[str, Any]) -> int:
    """`save_reminder_minutes` of a raw campaign.yaml (default 20, 0 = off)."""
    return _minutes(data, "save_reminder_minutes", DEFAULT_REMINDER_MINUTES)


def _minutes(data: dict[str, Any], key: str, default: int) -> int:
    value = data.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise SetupInvalid(f"{key} must be a whole number of minutes (0 = off), not {value!r}")
    return value
