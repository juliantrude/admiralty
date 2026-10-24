"""Where the game and the Player's game data live on this machine."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

_STEAM_LIBRARIES = (
    Path.home() / ".local/share/Steam",
    Path.home() / ".steam/steam",
    Path.home() / ".var/app/com.valvesoftware.Steam/.local/share/Steam",
)
STELLARIS_APP_ID = "281990"


def _find_install_dir() -> Path:
    if env := os.environ.get("HLIDSKJALF_GAME_DIR"):
        return Path(env)
    for library in _STEAM_LIBRARIES:
        candidate = library / "steamapps/common/Stellaris"
        if (candidate / "localisation").is_dir():
            return candidate
    raise FileNotFoundError(
        "Stellaris installation not found. Set HLIDSKJALF_GAME_DIR to the game folder."
    )


def _find_user_dir() -> Path:
    if env := os.environ.get("HLIDSKJALF_USER_DIR"):
        return Path(env)
    return Path.home() / ".local/share/Paradox Interactive/Stellaris"


@dataclass(frozen=True)
class Mod:
    name: str
    path: Path
    supported_version: str | None

    # Folders a mod can ship without changing the game checksum or its rules.
    COSMETIC_FOLDERS = frozenset(
        {
            "gfx",
            "interface",
            "localisation",
            "localisation_synced",
            "fonts",
            "sound",
            "music",
            "flags",
            "unchecked_defines",
        }
    )

    @property
    def content_folders(self) -> set[str]:
        if not self.path.is_dir():
            return set()
        return {p.name for p in self.path.iterdir() if p.is_dir()}

    @property
    def is_cosmetic(self) -> bool:
        return self.content_folders <= self.COSMETIC_FOLDERS


def _descriptor_field(text: str, field: str) -> str | None:
    match = re.search(rf'^{field}\s*=\s*"([^"]*)"', text, re.MULTILINE)
    return match.group(1) if match else None


@dataclass(frozen=True)
class GameEnvironment:
    install_dir: Path
    user_dir: Path

    @classmethod
    def detect(cls) -> GameEnvironment:
        return cls(install_dir=_find_install_dir(), user_dir=_find_user_dir())

    @cached_property
    def language(self) -> str:
        settings = self.user_dir / "settings.txt"
        if settings.exists():
            match = re.search(r'^language="(l_\w+)"', settings.read_text(), re.MULTILINE)
            if match:
                return match.group(1)
        return "l_english"

    @cached_property
    def enabled_mods(self) -> list[Mod]:
        dlc_load = self.user_dir / "dlc_load.json"
        if not dlc_load.exists():
            return []
        mods = []
        for rel in json.loads(dlc_load.read_text()).get("enabled_mods", []):
            descriptor = self.user_dir / rel
            if not descriptor.exists():
                continue
            text = descriptor.read_text(encoding="utf-8", errors="replace")
            path = _descriptor_field(text, "path")
            mods.append(
                Mod(
                    name=_descriptor_field(text, "name") or rel,
                    path=Path(path) if path else descriptor.with_suffix(""),
                    supported_version=_descriptor_field(text, "supported_version"),
                )
            )
        return mods

    def localisation_files(self) -> list[Path]:
        """Game localisation for the game language, then mod localisation (mods override)."""
        language = self.language
        roots = [self.install_dir / "localisation"]
        roots += [mod.path / "localisation" for mod in self.enabled_mods]
        files: list[Path] = []
        for root in roots:
            if root.is_dir():
                files += sorted(root.rglob(f"*_{language}.yml"))
        return files
