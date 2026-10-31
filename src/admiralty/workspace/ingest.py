"""Ingest: turn the raw copies the save service left in `saves/` into archive extracts.

The watcher (workspace/watch.py) only copies. The next read of the Campaign calls `ingest`,
which extracts every copy whose in-game date has no extract made from a save at least as new:

    saves/2259.12.29.autosave.sav   deleted after its extract is stored (the extract is kept)
    saves/2259.12.29.sav            deleted after extraction when `backup_saves` is off

A copy that cannot be extracted (half written, wrong game version, no such empire) stays where
it is and is reported, so the next read tries again and nothing is lost. The extractor is passed
in, so this module stays pure file handling like the archive.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from admiralty.workspace.archive import Archive
from admiralty.workspace.watch import AUTOSAVE_MARK

_COPY = re.compile(rf"(\d{{4}}\.\d{{2}}\.\d{{2}})({re.escape(AUTOSAVE_MARK)})?\.sav")


@dataclass
class IngestResult:
    extracted: list[str] = field(default_factory=list)  # in-game dates stored in the archive
    removed: list[str] = field(default_factory=list)  # file names of copies deleted afterwards
    problems: dict[str, str] = field(default_factory=dict)  # file name -> why it stays


def waiting(archive: Archive) -> list[tuple[str, Path, bool]]:
    """(date, path, is_autosave) of every raw copy in saves/, oldest in-game date first."""
    if not archive.saves.is_dir():
        return []
    found = []
    for path in archive.saves.iterdir():
        match = _COPY.fullmatch(path.name)
        if match and path.is_file():
            found.append((match.group(1), path, match.group(2) is not None))
    return sorted(found, key=lambda item: (item[0], item[2]))  # manual before autosave


def ingest(
    archive: Archive,
    extract: Callable[[Path], dict[str, Any]],
    keep_manual: bool,
    skip: Callable[[Path, float], bool] = lambda path, mtime: False,
) -> IngestResult:
    """`skip(path, mtime)` lets the caller leave out a copy that failed before and has not changed."""
    result = IngestResult()
    for date, path, autosave in waiting(archive):
        try:
            mtime = path.stat().st_mtime
            if skip(path, mtime):
                continue
            if not archive.current(date, mtime):
                doc = extract(path)
                if doc["header"]["date"] != date:
                    raise ValueError(f"the save says {doc['header']['date']}, not {date}")
                archive.store(doc, mtime)
                result.extracted.append(date)
            if autosave or not keep_manual:
                path.unlink()
                result.removed.append(path.name)
        except Exception as error:  # noqa: BLE001 - one bad copy must not stop the others
            result.problems[path.name] = f"Could not ingest {path.name}: {error}"
    return result
