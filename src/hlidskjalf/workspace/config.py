"""campaign.yaml: the Campaign Setup a Campaign Workspace runs on.

Written by the hlidskjalf:setup skill (M3). Until then it can be written by hand:

    save_dir: ~/.local/share/Paradox Interactive/Stellaris/save games/mpkonfderationvonvulkan_-2027490598
    empire: Plexxi            # player name, empire name or country id of the Tracked Empire
    mode: consulting          # or coaching
    knowledge: fair_play      # or god_mode
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

CONFIG_FILE = "campaign.yaml"
STATE_DIR = ".hlidskjalf"  # inside the Campaign Workspace: turn log, caches


class SetupMissing(LookupError):
    """The workspace has no usable Campaign Setup yet."""


@dataclass(frozen=True)
class CampaignConfig:
    workspace: Path
    save_dir: Path
    empire: str | int
    mode: str = "consulting"
    knowledge: str = "fair_play"
    raw: dict[str, Any] | None = None

    @property
    def god_mode(self) -> bool:
        return self.knowledge == "god_mode"

    @property
    def state_dir(self) -> Path:
        return self.workspace / STATE_DIR

    @classmethod
    def load(cls, workspace: Path) -> CampaignConfig:
        """Read campaign.yaml; HLIDSKJALF_SAVE_DIR / HLIDSKJALF_EMPIRE override it, which
        lets tests and first experiments run without a Campaign Setup."""
        workspace = workspace.resolve()
        data: dict[str, Any] = {}
        path = workspace / CONFIG_FILE
        if path.exists():
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        save_dir = os.environ.get("HLIDSKJALF_SAVE_DIR") or data.get("save_dir")
        empire = os.environ.get("HLIDSKJALF_EMPIRE") or data.get("empire")
        if not save_dir or empire in (None, ""):
            raise SetupMissing(
                f"No Campaign Setup in {workspace}: {CONFIG_FILE} needs save_dir and empire. "
                "Run the hlidskjalf:setup skill."
            )
        knowledge = data.get("knowledge", "fair_play")
        if knowledge not in ("fair_play", "god_mode"):
            raise SetupMissing(f"knowledge must be fair_play or god_mode, not {knowledge!r}")
        return cls(
            workspace=workspace,
            save_dir=Path(os.path.expanduser(str(save_dir))),
            empire=empire,
            mode=data.get("mode", "consulting"),
            knowledge=knowledge,
            raw=data,
        )
