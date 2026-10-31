"""The Briefings of a Campaign Workspace: one current Briefing, older versions in a history.

    briefings/current/overlay.json          the overlay of the current Briefing
    briefings/current/solution-graph.json   its Solution Graph
    briefings/history/001-2294.01.01/       the Briefing it replaced (same two files)

The Player wants one Briefing, not a pile (docs/proposals/ops.md entry 11). Feedback, new Goals
and a new save update it: Ops starts from the current overlay, keeps what still holds and
composes again; `publish` then moves the old version into the history and puts the new one in
its place. The history is numbered in the order the versions were replaced and named after the
in-game date of the save each was composed from. Pure file handling; knows nothing about the
graph.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

BRIEFINGS_DIR = "briefings"
CURRENT = "current"
HISTORY = "history"
OVERLAY_FILE = "overlay.json"
GRAPH_FILE = "solution-graph.json"
_VERSION = re.compile(r"(\d+)-.+")


def current_dir(workspace: Path) -> Path:
    return workspace / BRIEFINGS_DIR / CURRENT


def current_graph(workspace: Path) -> Path:
    return current_dir(workspace) / GRAPH_FILE


def current_overlay(workspace: Path) -> Path:
    return current_dir(workspace) / OVERLAY_FILE


def history(workspace: Path) -> list[Path]:
    """The replaced versions, oldest first."""
    root = workspace / BRIEFINGS_DIR / HISTORY
    if not root.is_dir():
        return []
    return sorted(
        (p for p in root.iterdir() if p.is_dir() and _VERSION.fullmatch(p.name)),
        key=lambda p: int(_VERSION.fullmatch(p.name).group(1)),
    )


def publish(workspace: Path, overlay: dict[str, Any], doc: dict[str, Any]) -> Path | None:
    """Make `doc` and its `overlay` the current Briefing. A Briefing that was current moves into
    the history first; its path is returned (None when there was none). Both new files are
    written before anything is moved, so a failure leaves the old Briefing in place."""
    current = current_dir(workspace)
    staging = current.with_name(CURRENT + ".new")
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    try:
        _write_json(staging / OVERLAY_FILE, overlay)
        _write_json(staging / GRAPH_FILE, doc)
        archived = _archive_current(workspace)
        staging.rename(current)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return archived


def _archive_current(workspace: Path) -> Path | None:
    current = current_dir(workspace)
    if not current.is_dir():
        return None
    versions = history(workspace)
    number = int(_VERSION.fullmatch(versions[-1].name).group(1)) + 1 if versions else 1
    target = workspace / BRIEFINGS_DIR / HISTORY / f"{number:03d}-{_date_of(current)}"
    target.parent.mkdir(parents=True, exist_ok=True)
    current.rename(target)
    return target


def _date_of(directory: Path) -> str:
    try:
        return json.loads((directory / GRAPH_FILE).read_text(encoding="utf-8"))["date"]
    except OSError, ValueError, KeyError:
        return "undated"


def _write_json(path: Path, content: dict[str, Any]) -> None:
    path.write_text(json.dumps(content, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
