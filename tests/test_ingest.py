"""Ingest: raw copies from the save service become archive extracts on the next read."""

from __future__ import annotations

import os

from admiralty.mcp.service import CampaignService
from admiralty.workspace.archive import Archive
from admiralty.workspace.config import CampaignConfig
from admiralty.workspace.ingest import ingest, waiting


def doc(date):
    return {"schema": 1, "header": {"date": date, "campaign": "vulkan"}, "resources": {}}


def copy(workspace, name, mtime=100.0):
    path = workspace / "saves" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"raw")
    os.utime(path, (mtime, mtime))
    return path


def extractor(path):
    return doc(path.name[:10])


def test_waiting_lists_copies_by_date_and_ignores_other_files(tmp_path):
    copy(tmp_path, "2259.12.29.sav")
    copy(tmp_path, "2259.12.29.autosave.sav")
    copy(tmp_path, "2200.01.01.autosave.sav")
    copy(tmp_path, "notes.sav")
    (tmp_path / "saves" / ".2259.01.01.sav.abc123").write_bytes(b"temp")
    found = [(d, p.name, a) for d, p, a in waiting(Archive(tmp_path))]
    assert found == [
        ("2200.01.01", "2200.01.01.autosave.sav", True),
        ("2259.12.29", "2259.12.29.sav", False),
        ("2259.12.29", "2259.12.29.autosave.sav", True),
    ]


def test_autosave_copy_keeps_the_extract_only(tmp_path):
    archive = Archive(tmp_path)
    path = copy(tmp_path, "2259.04.01.autosave.sav", mtime=200.0)
    result = ingest(archive, extractor, keep_manual=True)
    assert result.extracted == ["2259.04.01"] and result.removed == [path.name]
    assert archive.has("2259.04.01") and not path.exists()
    assert archive.current("2259.04.01", 200.0)  # the extract carries the save's mtime


def test_manual_copy_stays_with_backup_on_and_goes_with_backup_off(tmp_path):
    archive = Archive(tmp_path)
    path = copy(tmp_path, "2259.04.01.sav")
    assert ingest(archive, extractor, keep_manual=True).removed == []
    assert path.exists() and archive.has("2259.04.01")
    again = ingest(archive, lambda p: 1 / 0, keep_manual=True)  # already extracted: not read again
    assert again.extracted == [] and again.problems == {}

    other = copy(tmp_path, "2259.07.01.sav")
    assert ingest(archive, extractor, keep_manual=False).removed == [path.name, other.name]
    assert not other.exists() and not path.exists() and archive.has("2259.07.01")


def test_an_older_copy_does_not_replace_a_newer_extract_but_is_cleaned_up(tmp_path):
    archive = Archive(tmp_path)
    archive.store(doc("2259.04.01") | {"tag": "newer"}, 300.0)
    path = copy(tmp_path, "2259.04.01.autosave.sav", mtime=200.0)
    result = ingest(archive, lambda p: 1 / 0, keep_manual=True)
    assert result.extracted == [] and result.removed == [path.name]
    assert archive.load("2259.04.01")["tag"] == "newer"


def test_a_copy_that_cannot_be_read_stays_and_does_not_stop_the_others(tmp_path):
    archive = Archive(tmp_path)
    bad = copy(tmp_path, "2259.01.01.autosave.sav")
    good = copy(tmp_path, "2259.04.01.autosave.sav")

    def flaky(path):
        if path == bad:
            raise ValueError("truncated")
        return extractor(path)

    result = ingest(archive, flaky, keep_manual=True)
    assert result.extracted == ["2259.04.01"] and not good.exists()
    assert bad.exists() and "truncated" in result.problems[bad.name]


def test_a_copy_whose_date_differs_from_its_name_is_refused(tmp_path):
    archive = Archive(tmp_path)
    path = copy(tmp_path, "2259.01.01.autosave.sav")
    result = ingest(archive, lambda p: doc("2300.01.01"), keep_manual=True)
    assert path.exists() and "2300.01.01" in result.problems[path.name]
    assert archive.dates() == []


# --- the service ----------------------------------------------------------------------------


def make_service(tmp_path, monkeypatch, backup=True):
    from admiralty.mcp import service as module

    saves = tmp_path / "game"
    saves.mkdir()
    (tmp_path / "campaign.yaml").write_text(
        f"save_dir: {saves}\nempire: Plexxi\nbackup_saves: {str(backup).lower()}\n"
    )
    for name in ("archive", "saves", ".admiralty"):
        (tmp_path / name).mkdir(exist_ok=True)
    calls = []

    class FakeSnapshot:
        def __init__(self, extractor, ctx, empire):
            self.date = ctx.name[:10]

        def document(self, planet_detail=False):
            calls.append(self.date)
            return doc(self.date)

    class FakeExtractor:
        def context(self, path):
            if path.name.startswith("broken"):
                raise ValueError("not a save")
            return path

    monkeypatch.setattr(module, "Snapshot", FakeSnapshot)
    service = CampaignService(CampaignConfig.load(tmp_path), FakeExtractor())
    return service, calls


def test_service_ingest_extracts_waiting_copies_once(tmp_path, monkeypatch):
    service, calls = make_service(tmp_path, monkeypatch)
    copy(tmp_path, "2259.01.01.autosave.sav")
    copy(tmp_path, "2259.04.01.autosave.sav")
    copy(tmp_path, "2259.07.01.autosave.sav")
    assert service.ingest() == ["2259.01.01", "2259.04.01", "2259.07.01"]
    assert service.archive.dates() == ["2259.01.01", "2259.04.01", "2259.07.01"]
    assert list((tmp_path / "saves").iterdir()) == []
    assert service.ingest() == []
    assert calls == ["2259.01.01", "2259.04.01", "2259.07.01"]


def test_service_tries_a_failed_copy_again_only_when_it_changed(tmp_path, monkeypatch):
    service, calls = make_service(tmp_path, monkeypatch)
    bad = copy(tmp_path, "broken.sav")  # not a copy name: never touched
    assert service.ingest() == [] and bad.exists()
    path = copy(tmp_path, "2259.01.01.autosave.sav")

    attempts = []
    real = service._extract_copy

    def failing(p):
        attempts.append(p.name)
        raise ValueError("half written")

    monkeypatch.setattr(service, "_extract_copy", failing)
    service.ingest()
    service.ingest()
    assert attempts == [path.name]  # not parsed again while unchanged
    assert "half written" in service._archive_warnings[path.name]

    monkeypatch.setattr(service, "_extract_copy", real)
    os.utime(path, (500.0, 500.0))  # the service wrote it again
    assert service.ingest() == ["2259.01.01"]
    assert path.name not in service._archive_warnings
