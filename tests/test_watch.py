"""The save service: an artificial save folder where saves appear and are overwritten."""

from __future__ import annotations

import os
import time
import zipfile
from pathlib import Path

from admiralty.cli import main
from admiralty.workspace import registry
from admiralty.workspace.layout import create_workspace
from admiralty.workspace.watch import DesktopNotifier, Watcher, game_is_running

NOW = 2_000_000_000.0


def make_save(
    folder: Path, name: str, date: str, age: float = 60.0, body: str = "x", now: float = NOW
) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("meta", f'version="Cetus v4.5.2"\nname="mp_vulkan"\ndate="{date}"\n')
        archive.writestr("gamestate", body)
    stamp = now - age
    os.utime(path, (stamp, stamp))
    return path


def watcher(tmp_path: Path) -> Watcher:
    return Watcher(tmp_path / "saves", tmp_path / "data", clock=lambda: NOW)


def test_first_run_records_and_a_new_save_is_copied_to_the_inbox(tmp_path):
    folder = tmp_path / "saves" / "vulkan_1"
    make_save(folder, "old.sav", "2250.01.01")
    first = watcher(tmp_path)
    assert first.poll() == []  # the first run only records what lies there

    make_save(folder, "new.sav", "2259.12.29")
    copies = watcher(tmp_path).poll()  # a restart catches up on what changed
    assert [(c.date, c.autosave) for c in copies] == [("2259.12.29", False)]
    assert copies[0].target == tmp_path / "data" / "inbox" / "vulkan_1" / "2259.12.29.sav"
    assert copies[0].target.read_bytes() == (folder / "new.sav").read_bytes()
    assert copies[0].target.stat().st_mtime == (folder / "new.sav").stat().st_mtime
    assert watcher(tmp_path).poll() == []  # nothing new, nothing copied twice


def test_autosaves_are_marked_and_overwrites_are_copied_again(tmp_path):
    folder = tmp_path / "saves" / "vulkan_1"
    make_save(folder, "autosave_1.sav", "2259.01.01", age=600)
    w = watcher(tmp_path)
    w.poll()
    make_save(folder, "autosave_1.sav", "2259.04.01", age=60, body="a longer gamestate")
    [copy] = w.poll()
    assert copy.autosave and copy.target.name == "2259.04.01.autosave.sav"
    make_save(folder, "autosave_1.sav", "2259.07.01", age=30, body="again, longer still")
    [copy] = w.poll()
    assert copy.target.name == "2259.07.01.autosave.sav"
    assert sorted(p.name for p in copy.target.parent.iterdir()) == [
        "2259.04.01.autosave.sav",
        "2259.07.01.autosave.sav",
    ]


def test_a_save_still_being_written_waits(tmp_path):
    folder = tmp_path / "saves" / "vulkan_1"
    folder.mkdir(parents=True)
    w = watcher(tmp_path)
    w.poll()
    make_save(folder, "busy.sav", "2259.12.29", age=1)
    assert w.poll() == []  # modified one second ago
    (folder / "half.sav").write_bytes(b"PK\x03\x04 not finished")
    os.utime(folder / "half.sav", (NOW - 60, NOW - 60))
    assert w.poll() == []  # settled but unreadable
    w.clock = lambda: NOW + 10
    assert [c.date for c in w.poll()] == ["2259.12.29"]


def test_a_registered_workspace_receives_the_copies_and_adopts_the_inbox(tmp_path):
    folder = tmp_path / "saves" / "vulkan_1"
    base = tmp_path / "data"
    w = watcher(tmp_path)
    w.poll()
    make_save(folder, "a.sav", "2259.12.01")
    assert [c.target.parent.parent.name for c in w.poll()] == ["inbox"]

    workspace = create_workspace(tmp_path / "ws")
    moved = registry.register(base, folder, workspace)
    assert [p.name for p in moved] == ["2259.12.01.sav"]
    assert not (base / "inbox" / "vulkan_1").exists()
    assert registry.workspace_of(base, folder) == workspace.resolve()

    make_save(folder, "b.sav", "2259.12.02")
    [copy] = w.poll()
    assert copy.target == workspace.resolve() / "saves" / "2259.12.02.sav"


def test_watch_once_prints_the_copies(tmp_path, capsys):
    folder = tmp_path / "saves" / "vulkan_1"
    args = ["watch", "--once", "--save-root", str(tmp_path / "saves")]
    args += ["--data-dir", str(tmp_path / "data")]
    assert main(args) == 0  # baseline of an empty folder
    make_save(folder, "a.sav", "2259.12.01", now=time.time())  # the command uses the real clock
    assert main(args) == 0
    assert "vulkan_1/a.sav ->" in capsys.readouterr().out


# --- the reminder: the game runs and no new save came -------------------------------------


class Desk:
    """Stands in for the desktop: records what was shown and what was withdrawn."""

    def __init__(self):
        self.shown: list[tuple[str, str]] = []
        self.withdrawn: list[object] = []

    def send(self, title, body):
        self.shown.append((title, body))
        return len(self.shown)

    def withdraw(self, handle):
        self.withdrawn.append(handle)


class Stage:
    """A save folder with a workspace, a movable clock and a game that can be started."""

    def __init__(self, tmp_path: Path, minutes: int | None = 20):
        self.now = NOW
        self.running = True
        self.desk = Desk()
        self.folder = tmp_path / "saves" / "vulkan_1"
        self.workspace = create_workspace(tmp_path / "ws")
        if minutes is not None:
            (self.workspace / "campaign.yaml").write_text(f"save_reminder_minutes: {minutes}\n")
        registry.register(tmp_path / "data", self.folder.parent / "vulkan_1", self.workspace)
        make_save(self.folder, "autosave_1.sav", "2259.01.01", age=3600)
        self.watcher = Watcher(
            tmp_path / "saves",
            tmp_path / "data",
            clock=lambda: self.now,
            game_running=lambda: self.running,
            notifier=self.desk,
        )

    def look(self, minutes_later: float = 0.0):
        self.now += minutes_later * 60
        return self.watcher.poll()

    def save(self, date: str, name: str = "autosave_1.sav"):
        make_save(self.folder, name, date, age=60, body=date * 5, now=self.now)


def test_no_new_save_for_the_wait_sends_one_reminder(tmp_path):
    stage = Stage(tmp_path)
    stage.look()  # the game is seen starting
    stage.look(19)
    assert stage.desk.shown == []
    stage.look(2)
    assert len(stage.desk.shown) == 1
    assert "vulkan_1" in stage.desk.shown[0][1]
    stage.look(10)
    assert len(stage.desk.shown) == 1  # one reminder, not a stream


def test_the_next_save_withdraws_it_and_the_wait_starts_again(tmp_path):
    stage = Stage(tmp_path)
    stage.look()
    stage.look(21)
    stage.save("2259.04.01")
    stage.look(1)
    assert stage.desk.withdrawn == [1]
    stage.look(15)
    assert len(stage.desk.shown) == 1
    stage.look(10)
    assert len(stage.desk.shown) == 2  # silent again for 20 minutes after that save


def test_the_wait_counts_from_the_start_of_the_game_not_from_an_old_save(tmp_path):
    stage = Stage(tmp_path)  # the newest save is an hour old
    stage.running = False
    stage.look()
    stage.running = True
    stage.look(5)  # the game is seen starting here
    assert stage.desk.shown == []
    stage.look(15)
    assert stage.desk.shown == []
    stage.look(6)
    assert len(stage.desk.shown) == 1


def test_no_game_no_reminder_and_the_end_of_the_game_withdraws(tmp_path):
    stage = Stage(tmp_path)
    stage.running = False
    stage.look(60)
    assert stage.desk.shown == []
    stage.running = True
    stage.look()
    stage.look(25)
    assert len(stage.desk.shown) == 1
    stage.running = False
    stage.look(1)
    assert stage.desk.withdrawn == [1]


def test_zero_minutes_is_off_and_the_default_is_twenty(tmp_path):
    off = Stage(tmp_path / "a", minutes=0)
    off.look()
    off.look(120)
    assert off.desk.shown == []
    default = Stage(tmp_path / "b", minutes=None)
    default.look()
    default.look(21)
    assert len(default.desk.shown) == 1


def test_a_campaign_without_a_workspace_is_never_reminded(tmp_path):
    desk = Desk()
    now = [NOW]
    folder = tmp_path / "saves" / "vulkan_1"
    make_save(folder, "a.sav", "2259.01.01", age=3600)
    w = Watcher(
        tmp_path / "saves",
        tmp_path / "data",
        clock=lambda: now[0],
        game_running=lambda: True,
        notifier=desk,
    )
    w.poll()
    now[0] += 7200
    w.poll()
    assert desk.shown == []


def test_the_campaign_with_the_newest_save_is_the_one_played(tmp_path):
    stage = Stage(tmp_path)
    other = tmp_path / "saves" / "other_2"
    stage.look()
    stage.now += 30 * 60
    make_save(other, "a.sav", "2300.01.01", age=60, now=stage.now)
    stage.look()
    assert stage.desk.shown == []  # `other` is played; it has no workspace
    assert stage.desk.withdrawn == []


def test_the_desktop_notifier_survives_missing_tools(monkeypatch):
    def missing(*args, **kwargs):
        raise FileNotFoundError("notify-send")

    monkeypatch.setattr("admiralty.workspace.watch.subprocess.run", missing)
    desk = DesktopNotifier()
    assert desk.send("title", "body") is None
    desk.withdraw(7)  # no desktop: no error


def test_game_is_running_reads_proc(tmp_path, monkeypatch):
    assert isinstance(game_is_running(), bool)
    monkeypatch.setattr("admiralty.workspace.watch.Path", lambda _: tmp_path)
    (tmp_path / "123").mkdir()
    (tmp_path / "123" / "comm").write_text("bash\n")
    assert game_is_running() is False
    (tmp_path / "456").mkdir()
    (tmp_path / "456" / "comm").write_text("stellaris\n")
    assert game_is_running() is True
