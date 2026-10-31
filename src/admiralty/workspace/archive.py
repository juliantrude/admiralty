"""The Campaign archive: one Snapshot extract per in-game date, kept in the workspace.

    archive/2259.12.29.json.zst   the compact extract document, unchanged (`schema` included)
    saves/2259.12.29.sav          backup copy of the save it was made from

Keyed by the in-game date of the save header, not by the file name, so the archive does not
depend on how the game or the Player named the save. Debrief reads the archive, never the
saves, so a retrospective works after the originals are gone. Compression is the standard
library's `compression.zstd` (Python 3.14), so no dependency.

Two saves of one date (a manual save right after an autosave) resolve by modification time:
the newer wins. The archive file carries the modification time of the save it came from, so
that comparison needs no extra metadata and a second read of the same save writes nothing.
Pure file handling; knows nothing about the extractor.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from compression import zstd
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from admiralty.workspace.layout import ARCHIVE_DIR, SAVES_DIR

EXTRACT_SUFFIX = ".json.zst"
_DATE = re.compile(r"\d{4}\.\d{2}\.\d{2}")


class ArchiveCorrupt(ValueError):
    """An archived extract cannot be read back."""


@dataclass(frozen=True)
class ArchiveEntry:
    date: str
    path: Path
    campaign: str | None = None
    empire: str | None = None
    problem: str | None = None  # set when the file is unreadable; the entry is still listed


class Archive:
    def __init__(self, workspace: Path):
        self.extracts = workspace / ARCHIVE_DIR
        self.saves = workspace / SAVES_DIR

    def store(self, doc: dict[str, Any], source_mtime: float) -> bool:
        """Write `doc` under its header date. False when the archive already holds an extract
        of that date made from a save at least as new, so reading a save twice is free."""
        date = _check_date(doc["header"]["date"])
        target = self.extracts / f"{date}{EXTRACT_SUFFIX}"
        if _not_older(target, source_mtime):
            return False
        payload = zstd.compress(json.dumps(doc, ensure_ascii=False).encode("utf-8"))
        _write_atomic(target, payload, source_mtime)
        return True

    def backup(self, save: Path, date: str, source_mtime: float) -> bool:
        """Copy `save` to saves/<date>.sav unless the backup there is at least as new."""
        target = self.saves / f"{_check_date(date)}.sav"
        if _not_older(target, source_mtime):
            return False
        target.parent.mkdir(parents=True, exist_ok=True)
        handle, temp = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.")
        os.close(handle)
        try:
            shutil.copyfile(save, temp)
            os.utime(temp, (source_mtime, source_mtime))
            os.replace(temp, target)
        except BaseException:
            Path(temp).unlink(missing_ok=True)
            raise
        return True

    def current(self, date: str, source_mtime: float) -> bool:
        """True when the extract of `date` was made from a save at least as new as this one."""
        return _not_older(self.extracts / f"{_check_date(date)}{EXTRACT_SUFFIX}", source_mtime)

    def has(self, date: str) -> bool:
        return (self.extracts / f"{_check_date(date)}{EXTRACT_SUFFIX}").is_file()

    def dates(self) -> list[str]:
        """Archived in-game dates, oldest first; file names only, nothing is decompressed."""
        if not self.extracts.is_dir():
            return []
        found = (
            p.name.removesuffix(EXTRACT_SUFFIX) for p in self.extracts.glob(f"*{EXTRACT_SUFFIX}")
        )
        return sorted(d for d in found if _DATE.fullmatch(d))

    def load(self, date: str) -> dict[str, Any]:
        path = self.extracts / f"{_check_date(date)}{EXTRACT_SUFFIX}"
        if not path.is_file():
            raise FileNotFoundError(f"no archived extract for {date} in {self.extracts}")
        try:
            return json.loads(zstd.decompress(path.read_bytes()))
        except (zstd.ZstdError, ValueError, OSError) as error:
            raise ArchiveCorrupt(f"{path} cannot be read: {error}") from error

    def list(self) -> list[ArchiveEntry]:
        """Every archived date with a header summary; unreadable files are listed with their
        problem instead of failing the whole listing."""
        entries = []
        for date in self.dates():
            path = self.extracts / f"{date}{EXTRACT_SUFFIX}"
            try:
                header = self.load(date)["header"]
            except (ArchiveCorrupt, KeyError) as error:
                entries.append(ArchiveEntry(date, path, problem=str(error)))
                continue
            tracked = header.get("tracked_empire") or {}
            entries.append(ArchiveEntry(date, path, header.get("campaign"), tracked.get("name")))
        return entries


def _check_date(date: str) -> str:
    """The date becomes a file name, so anything but YYYY.MM.DD is refused."""
    if not _DATE.fullmatch(str(date)):
        raise ValueError(f"not an in-game date (YYYY.MM.DD): {date!r}")
    return date


def _not_older(target: Path, source_mtime: float) -> bool:
    return target.is_file() and target.stat().st_mtime >= source_mtime


def _write_atomic(target: Path, payload: bytes, mtime: float) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, temp = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.")
    try:
        with os.fdopen(handle, "wb") as out:
            out.write(payload)
        os.utime(temp, (mtime, mtime))
        os.replace(temp, target)
    except BaseException:
        Path(temp).unlink(missing_ok=True)
        raise
