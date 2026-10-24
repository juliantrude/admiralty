"""Campaign archive: extracts by in-game date, save backups, and the service hook."""

from __future__ import annotations

import os

import pytest
from conftest import SAVES_DIR, VULKAN, reference_save

from hlidskjalf.extract.diff import diff_extracts
from hlidskjalf.mcp.service import CampaignService
from hlidskjalf.workspace.archive import EXTRACT_SUFFIX, Archive, ArchiveCorrupt
from hlidskjalf.workspace.config import CampaignConfig
from hlidskjalf.workspace.turnlog import TURN_LOG


def doc(date="2259.12.29", **extra):
    header = {
        "date": date,
        "campaign": "vulkan",
        "tracked_empire": {"country_id": 0, "name": "Vulkan", "player": "Anna"},
    }
    return {"schema": 1, "header": header, "resources": {}, **extra}


# --- Archive on synthetic documents ------------------------------------------------------


def test_store_list_load_round_trip(tmp_path):
    archive = Archive(tmp_path)
    assert archive.list() == [] and archive.dates() == []
    assert archive.store(doc("2259.12.29", note="ünï"), 100.0) is True
    assert archive.store(doc("2200.01.04"), 100.0) is True
    assert archive.dates() == ["2200.01.04", "2259.12.29"]
    assert archive.has("2259.12.29") and not archive.has("2300.01.01")
    assert archive.load("2259.12.29")["note"] == "ünï"
    entry = archive.list()[1]
    assert (entry.date, entry.campaign, entry.empire, entry.problem) == (
        "2259.12.29", "vulkan", "Vulkan", None,
    )  # fmt: skip


def test_same_date_keeps_the_newer_save(tmp_path):
    archive = Archive(tmp_path)
    assert archive.store(doc(tag="first"), 100.0)
    assert not archive.store(doc(tag="older"), 90.0)
    assert not archive.store(doc(tag="same"), 100.0)  # reading a save twice writes nothing
    assert archive.load("2259.12.29")["tag"] == "first"
    assert archive.store(doc(tag="newer"), 200.0)
    assert archive.load("2259.12.29")["tag"] == "newer"
    assert len(list((tmp_path / "archive").iterdir())) == 1  # no temp files left behind


def test_corrupt_file_is_reported_not_fatal(tmp_path):
    archive = Archive(tmp_path)
    archive.store(doc("2259.12.29"), 1.0)
    (tmp_path / "archive" / f"2270.01.01{EXTRACT_SUFFIX}").write_bytes(b"not zstd")
    entries = {e.date: e for e in archive.list()}
    assert entries["2259.12.29"].problem is None
    assert "cannot be read" in entries["2270.01.01"].problem
    with pytest.raises(ArchiveCorrupt):
        archive.load("2270.01.01")
    with pytest.raises(FileNotFoundError):
        archive.load("2300.01.01")


def test_dates_become_file_names_only_when_well_formed(tmp_path):
    archive = Archive(tmp_path)
    with pytest.raises(ValueError, match="in-game date"):
        archive.load("../../etc/passwd")
    with pytest.raises(ValueError, match="in-game date"):
        archive.store(doc("2259-12-29"), 1.0)


def test_backup_copies_keeps_mtime_and_prefers_newer(tmp_path):
    save = tmp_path / "autosave_x.sav"
    save.write_bytes(b"one")
    archive = Archive(tmp_path / "ws")
    assert archive.backup(save, "2259.12.29", 100.0)
    backup = tmp_path / "ws" / "saves" / "2259.12.29.sav"
    assert backup.read_bytes() == b"one" and backup.stat().st_mtime == 100.0
    assert save.exists()  # a copy, never a move
    assert not archive.backup(save, "2259.12.29", 100.0)
    save.write_bytes(b"two")
    assert archive.backup(save, "2259.12.29", 200.0)
    assert backup.read_bytes() == b"two"


# --- the service hook ----------------------------------------------------------------------


def workspace_for(tmp_path, save_dir, backup=True):
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "campaign.yaml").write_text(
        f"save_dir: {save_dir}\nempire: Plexxi\nbackup_saves: {str(backup).lower()}\n"
    )
    return ws


@pytest.mark.saves
def test_two_saves_read_leave_two_archived_extracts_and_survive_the_originals(tmp_path):
    reference_save(VULKAN, "2220.04.22.sav")
    reference_save(VULKAN, "2259.12.25.sav")
    source = tmp_path / "game"
    source.mkdir()
    for name in ("2220.04.22.sav", "2259.12.25.sav"):
        os.symlink(SAVES_DIR / VULKAN / name, source / name)
    ws = workspace_for(tmp_path, source)
    service = CampaignService(CampaignConfig.load(ws))

    first = service.empire_overview("2220.04.22")
    service.empire_overview("2220.04.22")  # a cache hit archives nothing new
    service.planet("2", save="2259.12.25")  # detail read still archives the compact extract
    assert first["date"] == "2220.04.26"

    archive = Archive(ws)
    assert archive.dates() == ["2220.04.26", "2259.12.29"]
    assert sorted(p.name for p in (ws / "saves").iterdir()) == [
        "2220.04.26.sav", "2259.12.29.sav",
    ]  # fmt: skip
    assert "planets" in archive.load("2259.12.29")
    assert "jobs" not in archive.load("2259.12.29")["planets"][0]  # compact, no planet detail

    # Muninn-style read: the originals are gone, the archive alone answers.
    for link in source.iterdir():
        link.unlink()
    older, newer = archive.load("2220.04.26"), archive.load("2259.12.29")
    diff = diff_extracts(older, newer)
    assert (diff["from"], diff["to"]) == ("2220.04.26", "2259.12.29")


@pytest.mark.saves
def test_backup_can_be_switched_off_and_failures_become_warnings(tmp_path, monkeypatch):
    reference_save(VULKAN, "2259.12.25.sav")
    source = tmp_path / "game"
    source.mkdir()
    os.symlink(SAVES_DIR / VULKAN / "2259.12.25.sav", source / "2259.12.25.sav")
    ws = workspace_for(tmp_path, source, backup=False)
    service = CampaignService(CampaignConfig.load(ws))
    status = service.campaign_status()
    assert Archive(ws).has("2259.12.29")
    assert not (ws / "saves").exists() or not any((ws / "saves").iterdir())
    assert not any("archive" in w for w in status["warnings"])

    # A broken archive must not break the tool; it shows up as a warning and in the turn log.
    def fail(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(Archive, "store", fail)
    broken = CampaignService(CampaignConfig.load(ws))
    assert broken.empire_overview()["date"] == "2259.12.29"
    assert any("disk full" in w for w in broken.campaign_status()["warnings"])
    log = (ws / ".hlidskjalf" / TURN_LOG).read_text()
    assert '"tool": "archive"' in log and "disk full" in log
