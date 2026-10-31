"""Which save folder belongs to which Campaign Workspace, kept for the save service.

`~/.local/share/admiralty/workspaces.json` maps the resolved save folder of a Campaign to its
workspace. `admiralty setup write` adds the entry; the watcher reads it to decide whether a
copied save goes into the workspace or waits in the inbox. Pure file handling.

    ~/.local/share/admiralty/
        workspaces.json     {"<save folder>": "<workspace>"}
        watch-state.json    what the watcher has seen (workspace/watch.py)
        inbox/<folder>/     saves of a Campaign that has no workspace yet
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path

REGISTRY_FILE = "workspaces.json"
INBOX_DIR = "inbox"


def data_dir() -> Path:
    """The Player's Admiralty folder; ADMIRALTY_DATA_DIR moves it (tests, experiments)."""
    if env := os.environ.get("ADMIRALTY_DATA_DIR"):
        return Path(env).expanduser()
    return Path.home() / ".local/share/admiralty"


def load(base: Path) -> dict[str, str]:
    path = base / REGISTRY_FILE
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError, ValueError:
        return {}
    return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}


def workspace_of(base: Path, save_folder: Path) -> Path | None:
    entry = load(base).get(str(save_folder.expanduser().resolve()))
    return Path(entry) if entry else None


def inbox_of(base: Path, save_folder: Path) -> Path:
    return base / INBOX_DIR / save_folder.name


def register(base: Path, save_folder: Path, workspace: Path) -> list[Path]:
    """Record that `save_folder` belongs to `workspace` and move the inbox of that folder into
    the workspace's saves/. Returns the moved files."""
    from admiralty.workspace.layout import SAVES_DIR

    save_folder = save_folder.expanduser().resolve()
    workspace = workspace.expanduser().resolve()
    entries = load(base)
    entries[str(save_folder)] = str(workspace)
    _write(base / REGISTRY_FILE, entries)

    moved = []
    inbox = inbox_of(base, save_folder)
    if inbox.is_dir():
        target = workspace / SAVES_DIR
        target.mkdir(parents=True, exist_ok=True)
        for copy in sorted(inbox.glob("*.sav")):
            destination = target / copy.name
            if destination.exists() and destination.stat().st_mtime >= copy.stat().st_mtime:
                copy.unlink()
                continue
            shutil.move(copy, destination)
            moved.append(destination)
        try:
            inbox.rmdir()
        except OSError:
            pass  # something else is in there; leave it
    return moved


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as out:
            json.dump(data, out, indent=1, ensure_ascii=False)
        os.replace(temp, path)
    except BaseException:
        Path(temp).unlink(missing_ok=True)
        raise
