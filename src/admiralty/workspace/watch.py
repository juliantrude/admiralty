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

The reminder (grilling topic 8, R4): while Stellaris runs and the Campaign played, the one with
the newest save, got no new save for `save_reminder_minutes` of its workspace (default 20, 0 =
off; a folder without a workspace is never reminded), the watcher sends one desktop
notification. The next save, another Campaign taking over, or the end of the game withdraws it.
The wait counts from the newest save or from the moment the watcher saw the game start,
whichever is later. Autosaves count as saves; the date in the game is not needed. Game check and
notifier are parameters, so tests need no desktop.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from admiralty.workspace import registry
from admiralty.workspace.config import (
    SetupInvalid,
    read_raw,
    reminder_minutes,
)
from admiralty.workspace.layout import SAVES_DIR
from admiralty.workspace.setup import read_meta

POLL_SECONDS = 30
SETTLE_SECONDS = 3
AUTOSAVE_PREFIX = "autosave_"
AUTOSAVE_MARK = ".autosave"
STATE_FILE = "watch-state.json"
GAME_PROCESS = "stellaris"  # /proc/<pid>/comm of the game on Linux
REMINDER_TITLE = "Stellaris: no new save"


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


class Notifier(Protocol):
    def send(self, title: str, body: str) -> object | None:
        """Show a notification; the handle goes back to `withdraw`."""

    def withdraw(self, handle: object | None) -> None: ...


def game_is_running() -> bool:
    """Whether a Stellaris process exists (Linux: a /proc entry whose comm is `stellaris`)."""
    for comm in Path("/proc").glob("[0-9]*/comm"):
        try:
            if comm.read_text(encoding="utf-8").strip() == GAME_PROCESS:
                return True
        except OSError:
            continue  # the process ended while we looked
    return False


class DesktopNotifier:
    """notify-send to show, the freedesktop CloseNotification call (gdbus) to withdraw."""

    def send(self, title: str, body: str) -> int | None:
        try:
            done = subprocess.run(
                ["notify-send", "--app-name=Admiralty", "--print-id", title, body],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return int(done.stdout.strip()) if done.returncode == 0 else None
        except OSError, ValueError, subprocess.SubprocessError:
            return None  # no desktop to tell: the reminder is an extra

    def withdraw(self, handle: object | None) -> None:
        if not isinstance(handle, int):
            return
        call = [
            "gdbus", "call", "--session",
            "--dest", "org.freedesktop.Notifications",
            "--object-path", "/org/freedesktop/Notifications",
            "--method", "org.freedesktop.Notifications.CloseNotification", str(handle),
        ]  # fmt: skip
        try:
            subprocess.run(call, capture_output=True, timeout=10)
        except OSError, subprocess.SubprocessError:
            pass


@dataclass
class _Reminder:
    folder: Path
    newest: float  # mtime of the newest save when the reminder was sent
    handle: object | None


class Watcher:
    def __init__(
        self,
        save_root: Path,
        base: Path | None = None,
        clock: Callable[[], float] = time.time,
        game_running: Callable[[], bool] | None = None,
        notifier: Notifier | None = None,
    ):
        self.save_root = save_root.expanduser()
        self.base = base if base is not None else registry.data_dir()
        self.clock = clock
        self.game_running = game_running
        self.notifier = notifier
        self._newest: dict[Path, float] = {}  # newest save mtime per Campaign folder, this poll
        self._running_since: float | None = None
        self._reminder: _Reminder | None = None
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
        self._newest = {}
        folders = sorted(p for p in self.save_root.glob("*") if p.is_dir())
        for folder in folders:
            for save in sorted(folder.glob("*.sav")):
                copy = self._look_at(folder, save)
                if copy:
                    copies.append(copy)
        self._save_state()
        self._first_run = False
        self._remind()
        return copies

    def _look_at(self, folder: Path, save: Path) -> Copy | None:
        try:
            stat = save.stat()
        except OSError:
            return None  # replaced while we looked
        self._newest[folder] = max(self._newest.get(folder, 0.0), stat.st_mtime)
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

    def _remind(self) -> None:
        if self.game_running is None or self.notifier is None:
            return
        if not self.game_running():
            self._running_since = None
            self._withdraw()
            return
        now = self.clock()
        if self._running_since is None:
            self._running_since = now
        if not self._newest:
            return
        folder = max(self._newest, key=lambda f: self._newest[f])  # the Campaign played
        newest = self._newest[folder]
        if self._reminder and (self._reminder.folder != folder or newest > self._reminder.newest):
            self._withdraw()  # a save came, or another Campaign took over
        minutes = self._reminder_minutes(folder)
        if self._reminder or minutes <= 0:
            return
        quiet = now - max(newest, self._running_since)
        if quiet >= minutes * 60:
            body = f"No new save in {folder.name} for {int(quiet // 60)} minutes."
            handle = self.notifier.send(REMINDER_TITLE, body)
            self._reminder = _Reminder(folder, newest, handle)

    def _withdraw(self) -> None:
        if self._reminder and self.notifier:
            self.notifier.withdraw(self._reminder.handle)
        self._reminder = None

    def _reminder_minutes(self, folder: Path) -> int:
        workspace = registry.workspace_of(self.base, folder)
        if not workspace or not workspace.is_dir():
            return 0
        try:
            return reminder_minutes(read_raw(workspace))
        except SetupInvalid:
            return 0  # a broken campaign.yaml is not a reason to nag

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
