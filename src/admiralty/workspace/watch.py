"""The save service: watch the Stellaris save folder and keep a raw copy of every save.

The game overwrites its autosaves in turn, so a save that nobody reads in time is gone for
Debrief. `Watcher.poll` looks at every Campaign folder under "save games" and copies each new
or changed save, sorted by its in-game date:

    <workspace>/saves/2259.12.29.sav            a manual save
    <workspace>/saves/2259.12.29.autosave.sav   a file called autosave_*.sav
    <data dir>/inbox/<folder>/...               the same, for a Campaign without a workspace

Nothing is parsed beyond the small `meta` file of the zip, so the service adds no knowledge and
the game is not slowed down. The workspace extracts the waiting copies on its next read
(workspace/ingest.py). A save counts once it was not modified for `SETTLE_SECONDS` and its meta
can be read; the first run only records what lies in the folder, later runs catch up on what
changed while the service was down.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from admiralty.workspace import registry
from admiralty.workspace.layout import SAVES_DIR
from admiralty.workspace.setup import read_meta

POLL_SECONDS = 30
SETTLE_SECONDS = 3
AUTOSAVE_PREFIX = "autosave_"
AUTOSAVE_MARK = ".autosave"
STATE_FILE = "watch-state.json"


@dataclass(frozen=True)
class Copy:
    source: Path
    target: Path
    date: str
    autosave: bool


def is_autosave(save: Path) -> bool:
    return save.name.startswith(AUTOSAVE_PREFIX)


def copy_name(date: str, autosave: bool) -> str:
    return f"{date}{AUTOSAVE_MARK if autosave else ''}.sav"


def is_autosave_copy(copy: Path) -> bool:
    return copy.name.endswith(f"{AUTOSAVE_MARK}.sav")


class Watcher:
    def __init__(
        self,
        save_root: Path,
        base: Path | None = None,
        clock: Callable[[], float] = time.time,
    ):
        self.save_root = save_root.expanduser()
        self.base = base if base is not None else registry.data_dir()
        self.clock = clock
        self._state_path = self.base / STATE_FILE
        self._first_run = not self._state_path.exists()
        self._seen: dict[str, list[int]] = self._load_state()

    def _load_state(self) -> dict[str, list[int]]:
        try:
            data = json.loads(self._state_path.read_text(encoding="utf-8"))
        except FileNotFoundError, ValueError:
            return {}
        return data if isinstance(data, dict) else {}

    def _save_state(self) -> None:
        registry._write(self._state_path, self._seen)

    def poll(self) -> list[Copy]:
        """One look at the save folder; returns the copies made."""
        copies: list[Copy] = []
        folders = sorted(p for p in self.save_root.glob("*") if p.is_dir())
        for folder in folders:
            for save in sorted(folder.glob("*.sav")):
                copy = self._look_at(folder, save)
                if copy:
                    copies.append(copy)
        self._save_state()
        self._first_run = False
        return copies

    def _look_at(self, folder: Path, save: Path) -> Copy | None:
        try:
            stat = save.stat()
        except OSError:
            return None  # replaced while we looked
        key = f"{folder.name}/{save.name}"
        signature = [stat.st_mtime_ns, stat.st_size]
        if self._seen.get(key) == signature:
            return None
        if self._first_run:
            self._seen[key] = signature
            return None
        if self.clock() - stat.st_mtime < SETTLE_SECONDS:
            return None  # the game is still writing it
        try:
            date = str(read_meta(save)["date"])
            target = self._destination(folder) / copy_name(date, is_autosave(save))
            _copy_if_newer(save, target, stat.st_mtime)
        except OSError, zipfile.BadZipFile, KeyError, ValueError:
            return None  # half written or vanished: look again at the next poll
        self._seen[key] = signature
        return Copy(save, target, date, is_autosave(save))

    def _destination(self, folder: Path) -> Path:
        workspace = registry.workspace_of(self.base, folder)
        if workspace and workspace.is_dir():
            return workspace / SAVES_DIR
        return registry.inbox_of(self.base, folder)


def _copy_if_newer(source: Path, target: Path, mtime: float) -> None:
    if target.is_file() and target.stat().st_mtime >= mtime:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, temp = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.")
    os.close(handle)
    try:
        shutil.copyfile(source, temp)
        os.utime(temp, (mtime, mtime))
        os.replace(temp, target)
    except BaseException:
        Path(temp).unlink(missing_ok=True)
        raise


def run(
    watcher: Watcher, interval: float = POLL_SECONDS, report: Callable[[Copy], None] | None = None
):
    """Poll until interrupted."""
    while True:
        for copy in watcher.poll():
            if report:
                report(copy)
        time.sleep(interval)
