"""The PreToolUse hook that keeps the Coach's hands off the Player Model (M9, 20a).

Claude Code runs `admiralty hook pretooluse` before Write, Edit, MultiEdit, NotebookEdit and Bash
and writes the event as JSON to stdin. A call that touches the `player-model/` folder of the
data dir is denied: the Player Model changes through the Academy tools only (`player/store.py`).
Reading stays possible through the `player_model` tool; the folder is not hidden from the Player.

Protocol: allow = no output; deny = the `hookSpecificOutput` object with `permissionDecision`
`deny`. Every path exits 0: an exception lets the call through (same rule as the Stop hook).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, TextIO

from admiralty.player.store import MODEL_DIR, model_dir

WRITING_TOOLS = ("Write", "Edit", "MultiEdit", "NotebookEdit")
REASON = (
    "The Player Model changes only through the Academy tools; direct writes to player-model/ "
    "are refused. Report the outcome of the attempt with the tool instead."
)


def pretooluse(stdin: TextIO, stdout: TextIO) -> int:
    try:
        event = json.loads(stdin.read())
        if isinstance(event, dict) and touches_player_model(event):
            stdout.write(json.dumps(denial(), ensure_ascii=True) + "\n")
    except Exception:  # noqa: BLE001 - the hook must never take the session down
        pass
    return 0


def denial() -> dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": REASON,
        }
    }


def touches_player_model(event: dict[str, Any]) -> bool:
    tool, arguments = event.get("tool_name"), event.get("tool_input")
    if not isinstance(arguments, dict):
        return False
    cwd = event.get("cwd")
    base = Path(cwd) if isinstance(cwd, str) and cwd else Path.cwd()
    if tool in WRITING_TOOLS:
        paths = [arguments.get(key) for key in ("file_path", "notebook_path", "path")]
        return any(_inside(base, p) for p in paths if isinstance(p, str) and p)
    if tool == "Bash":
        command = arguments.get("command")
        return isinstance(command, str) and _mentions(command)
    return False


def _inside(base: Path, value: str) -> bool:
    path = Path(value).expanduser()
    path = (path if path.is_absolute() else base / path).resolve()
    folder = model_dir().resolve()
    return path == folder or folder in path.parents


# A Bash command is refused when it names the folder in any spelling: the resolved path, the
# default path with `~` or $HOME, or the folder name itself (cd into it, a glob, a variable).
_NAME = re.compile(rf"(?<![\w-]){re.escape(MODEL_DIR)}(?![\w-])")


def _mentions(command: str) -> bool:
    return bool(_NAME.search(command)) or str(model_dir().resolve()) in command
