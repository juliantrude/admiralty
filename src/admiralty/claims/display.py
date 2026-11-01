"""Hold an answer back until the Stop hook has judged it, so the Player sees only the last version.

Claude Code starts MessageDisplay (per batch of completed lines) and Stop at the same time, and only
MessageDisplay decides what reaches the screen. So every batch but the last is collected and replaced
by nothing, and the last batch waits for the verdict of Stop. Stop stays the only check.

Text before a tool call gets no Stop. If Stop does not show up within `WINDOW_S` the message counts
as such text and is shown: when in doubt, text appears rather than vanishes.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import time
import traceback
from pathlib import Path
from typing import Any, TextIO

from admiralty.claims.hook import find_workspace, log_error
from admiralty.workspace.config import STATE_DIR

WINDOW_S = 2.0
DEADLINE_S = 33.0  # just above the Stop hook's timeout, below the MessageDisplay one
TICK_S = 0.05
STALE_S = 3600
_DIR = "display"
_SHOW, _HIDE = "show", "hide"


def _folder(workspace: Path, session: Any) -> Path:
    folder = workspace / STATE_DIR / _DIR / str(session)
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _key(text: str) -> str:
    return hashlib.sha256(" ".join(text.split()).encode("utf-8")).hexdigest()[:16]


def stop_began(workspace: Path, session: Any, answer: str) -> None:
    folder, key = _folder(workspace, session), _key(answer)
    (folder / f"{key}.verdict").unlink(missing_ok=True)
    (folder / f"{key}.running").touch()


def stop_decided(workspace: Path, session: Any, answer: str, show: bool) -> None:
    folder, key = _folder(workspace, session), _key(answer)
    temporary = folder / f"{key}.tmp"
    temporary.write_text(_SHOW if show else _HIDE, encoding="utf-8")
    temporary.rename(folder / f"{key}.verdict")


def _await_verdict(folder: Path, key: str, window_s: float, deadline_s: float) -> bool:
    running, verdict = folder / f"{key}.running", folder / f"{key}.verdict"
    begin = time.monotonic()
    while True:
        elapsed = time.monotonic() - begin
        if verdict.exists():
            return verdict.read_text(encoding="utf-8") != _HIDE
        if elapsed >= (deadline_s if running.exists() else window_s):
            return True
        time.sleep(TICK_S)


def _clean_up(folder: Path, key: str) -> None:
    (folder / f"{key}.running").unlink(missing_ok=True)
    (folder / f"{key}.verdict").unlink(missing_ok=True)
    limit = time.time() - STALE_S
    for path in folder.iterdir():
        if path.stat().st_mtime < limit:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()


def hold(
    event: dict[str, Any],
    workspace: Path,
    window_s: float = WINDOW_S,
    deadline_s: float = DEADLINE_S,
) -> str:
    """The text Claude Code shall show for this batch."""
    folder = _folder(workspace, event.get("session_id"))
    message = folder / str(event["message_id"])
    message.mkdir(exist_ok=True)
    (message / f"{event['index']:06d}").write_text(event["delta"], encoding="utf-8")
    if not event["final"]:
        return ""

    # Batches run in parallel: earlier ones may still be on their way.
    begin = time.monotonic()
    while len(list(message.iterdir())) <= event["index"] and time.monotonic() - begin < window_s:
        time.sleep(TICK_S)
    text = "".join(path.read_text(encoding="utf-8") for path in sorted(message.iterdir()))
    shutil.rmtree(message)

    key = _key(text)
    show = _await_verdict(folder, key, window_s, deadline_s)
    _clean_up(folder, key)
    return text if show else ""


def display(stdin: TextIO, stdout: TextIO) -> int:
    """Run the hook. No output or a failure shows the batch as it is, so the Player keeps the text."""
    workspace: Path | None = None
    try:
        event = json.loads(stdin.read())
        cwd = event.get("cwd") if isinstance(event, dict) else None
        workspace = find_workspace(Path(cwd)) if isinstance(cwd, str) and cwd else None
        if workspace is None:
            return 0
        output = {"hookEventName": "MessageDisplay", "displayContent": hold(event, workspace)}
        stdout.write(json.dumps({"hookSpecificOutput": output}, ensure_ascii=True) + "\n")
    except Exception:  # noqa: BLE001 - the hook must never take the session down
        log_error(workspace, traceback.format_exc())
    return 0
