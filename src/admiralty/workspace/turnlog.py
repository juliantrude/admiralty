"""The workspace turn log (`.admiralty/turn-log.jsonl`): one JSON line per tool call, written by
the MCP server. A line's number (counting from 1) is its id; `expand_graph` hands it out as
`expansion_id` so the CLI can read the expansion from here instead of the model copying it."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from admiralty.workspace.config import STATE_DIR

TURN_LOG = "turn-log.jsonl"


def turn_log_path(workspace: Path) -> Path:
    return workspace / STATE_DIR / TURN_LOG


def count_lines(path: Path) -> int:
    """Lines already in the log (0 when there is none)."""
    try:
        return path.read_bytes().count(b"\n")
    except FileNotFoundError:
        return 0


def read_entry(workspace: Path, line: int) -> dict[str, Any]:
    """The entry with this id; LookupError when the log or the line does not exist."""
    path = turn_log_path(workspace)
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        raise LookupError(f"no turn log at {path}") from None
    if not 1 <= line <= len(lines):
        raise LookupError(f"turn log {path} has {len(lines)} entries, none with id {line}")
    return json.loads(lines[line - 1])


def append_entry(workspace: Path, tool: str, args: dict[str, Any], result: Any) -> int:
    """Append one entry from outside the MCP server (the `admiralty setup` CLI) and return its id.
    The entry has the shape the server writes, so the Unverified Claim check counts it as
    evidence."""
    path = turn_log_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = count_lines(path) + 1
    entry = {
        "ts": datetime.now(UTC).isoformat(timespec="seconds"),
        "tool": tool,
        "args": args,
        "result": result,
    }
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return line
