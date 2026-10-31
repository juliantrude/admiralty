"""The save service: an artificial save folder where saves appear and are overwritten."""

from __future__ import annotations

import os
import time
import zipfile
from pathlib import Path

from admiralty.cli import main
from admiralty.workspace import registry
from admiralty.workspace.layout import create_workspace
from admiralty.workspace.watch import Watcher

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
