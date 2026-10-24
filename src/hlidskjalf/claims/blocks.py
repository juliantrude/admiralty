"""Reads `.hlidskjalf/blocks.jsonl` (written by `claims/hook.py`) and groups it for review (M7).

One line of the log is one block of the Stop hook. `summarise` flattens the lines into their
Unverified Claims and groups those by kind (number/date/name) and reason code (`no_match`,
`near_match`, `derived_unexplained`, `name_no_match`), with a count and the answer sentence of
each claim. Blocks that were released after the second pass are listed separately, because a
released answer is where the check and the model disagreed twice. Nothing here decides whether a
group is an error or a false positive: that is the `review-blocks` skill's job.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from hlidskjalf.claims.hook import blocks_path

_MAX_EXAMPLES = 20


def read_blocks(workspace: Path) -> tuple[list[dict[str, Any]], int]:
    """The block lines of the workspace log and the number of lines that could not be read."""
    try:
        lines = blocks_path(workspace).read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return [], 0
    blocks: list[dict[str, Any]] = []
    unreadable = 0
    for line in lines:
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            unreadable += 1
            continue
        if isinstance(entry, dict):
            blocks.append(entry)
        else:
            unreadable += 1
    return blocks, unreadable


def summarise(workspace: Path) -> dict[str, Any]:
    """The log grouped by kind and reason code, plus the released blocks."""
    blocks, unreadable = read_blocks(workspace)
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    released: list[dict[str, Any]] = []
    for block in blocks:
        findings = [f for f in block.get("unverified") or [] if isinstance(f, dict)]
        where = {"session_id": block.get("session_id"), "prompt_id": block.get("prompt_id")}
        if block.get("released"):
            released.append(
                {
                    "ts": block.get("ts"),
                    **where,
                    "claims": len(findings),
                    "sentences": _sentences(findings),
                }
            )
        for finding in findings:
            key = (str(finding.get("kind")), str(finding.get("code")))
            group = groups.setdefault(
                key, {"kind": key[0], "code": key[1], "count": 0, "examples": []}
            )
            group["count"] += 1
            if len(group["examples"]) < _MAX_EXAMPLES:
                group["examples"].append(
                    {
                        "ts": block.get("ts"),
                        **where,
                        "text": finding.get("text"),
                        "sentence": finding.get("sentence"),
                        "nearest": finding.get("nearest"),
                        "nearest_source": finding.get("nearest_source"),
                        "released": bool(block.get("released")),
                    }
                )
    ordered = sorted(groups.values(), key=lambda g: (-g["count"], g["kind"], g["code"]))
    by_kind: Counter[str] = Counter()
    for group in ordered:
        by_kind[group["kind"]] += group["count"]
    return {
        "blocks": len(blocks),
        "unreadable_lines": unreadable,
        "claims": sum(group["count"] for group in ordered),
        "by_kind": dict(sorted(by_kind.items())),
        "groups": ordered,
        "released": released,
    }


def _sentences(findings: list[dict[str, Any]]) -> list[str]:
    seen: list[str] = []
    for finding in findings:
        sentence = finding.get("sentence")
        if isinstance(sentence, str) and sentence not in seen:
            seen.append(sentence)
    return seen[:_MAX_EXAMPLES]
