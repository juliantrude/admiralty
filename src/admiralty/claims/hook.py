"""The Stop hook of the Unverified Claim check (M7, `docs/plans/M7.md`).

Claude Code runs `admiralty hook stop` when the model is about to end its turn and writes a JSON
object to stdin. The fields used (probed on Claude Code, see the plan's open risks): `cwd`,
`session_id`, `prompt_id`, `transcript_path`, `stop_hook_active` (true while the model answers
after an earlier block of this hook) and `last_assistant_message`, the final answer.

Protocol: allow = no output; block = `{"decision": "block", "reason": ...}` on stdout. Every path
exits 0: a broken check must not silence the Coach, so an exception is logged to
`.admiralty/hook-errors.log` and the answer goes through.
"""

from __future__ import annotations

import hashlib
import json
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TextIO

from admiralty.claims.check import Unverified, Verdict, check_answer
from admiralty.claims.evidence import build_evidence, read_transcript, read_turn_log
from admiralty.workspace.config import STATE_DIR

CONFIG_FILE = "campaign.yaml"
BLOCKS_LOG = "blocks.jsonl"
ERRORS_LOG = "hook-errors.log"
MAX_BLOCKS = 2  # per answer; then the answer is released with a notice
_MAX_LISTED = 8
_MAX_SENTENCE = 240

RELEASE_NOTICE = (
    "Admiralty could not verify every figure or name in this answer against the tool results; "
    "treat the unchecked ones with care."
)
_INSTRUCTION = (
    "Rewrite the answer using only figures and names from the tool results, or call a tool to "
    "get them. For a total, show the addends in the same item or quote the tool's figure. "
    "Do not mention this check to the Player."
)


def find_workspace(start: Path) -> Path | None:
    """The first directory from `start` upwards holding `campaign.yaml` and `.admiralty/`."""
    for directory in (start, *start.parents):
        if (directory / CONFIG_FILE).is_file() and (directory / STATE_DIR).is_dir():
            return directory
    return None


def blocks_path(workspace: Path) -> Path:
    return workspace / STATE_DIR / BLOCKS_LOG


def stop(stdin: TextIO, stdout: TextIO) -> int:
    """Run the hook: read the event from `stdin`, print the decision (if any) to `stdout`."""
    workspace: Path | None = None
    try:
        event = json.loads(stdin.read())
        if not isinstance(event, dict):
            return 0
        cwd = event.get("cwd")
        workspace = find_workspace(Path(cwd)) if isinstance(cwd, str) and cwd else None
        if workspace is None:
            return 0
        output = decide(event, workspace)
        if output is not None:
            stdout.write(json.dumps(output, ensure_ascii=True) + "\n")
    except Exception:  # noqa: BLE001 - the hook must never take the session down
        _log_error(workspace, traceback.format_exc())
    return 0


def decide(event: dict[str, Any], workspace: Path) -> dict[str, Any] | None:
    """The hook output for this event: None to allow, else the block or the release notice."""
    transcript = _path(event.get("transcript_path"))
    started, player_texts = read_transcript(transcript) if transcript else (None, [])
    answer = event.get("last_assistant_message")
    if not isinstance(answer, str) or not answer.strip():
        answer = last_assistant_text(transcript) if transcript else ""
    if not answer.strip():
        return None

    evidence = build_evidence(read_turn_log(workspace, started), player_texts)
    verdict = check_answer(answer, evidence)
    if verdict.ok:
        return None

    session, prompt = event.get("session_id"), event.get("prompt_id")
    active = bool(event.get("stop_hook_active"))
    earlier = _blocks_for(workspace, session, prompt) if active else 0
    released = active and earlier >= MAX_BLOCKS
    _append_block(workspace, session, prompt, answer, verdict, active, released)
    if released:
        return {"systemMessage": RELEASE_NOTICE}
    return {"decision": "block", "reason": block_reason(verdict)}


def block_reason(verdict: Verdict) -> str:
    lines = [
        f"{len(verdict.unverified)} unverified claim(s) in your answer. "
        "These were not found in any tool result of this session:"
    ]
    for finding in verdict.unverified[:_MAX_LISTED]:
        lines.append("- " + _describe(finding))
    if len(verdict.unverified) > _MAX_LISTED:
        lines.append(f"- ... and {len(verdict.unverified) - _MAX_LISTED} more")
    lines.append(_INSTRUCTION)
    return "\n".join(lines)


def _describe(finding: Unverified) -> str:
    claim = finding.claim
    sentence = " ".join(claim.sentence.split())
    if len(sentence) > _MAX_SENTENCE:
        sentence = sentence[:_MAX_SENTENCE] + "..."
    text = f'{claim.kind} "{claim.text}" in: "{sentence}"'
    if finding.code == "derived_unexplained":
        text += " (a total none of the figures shown with it explains)"
    if finding.nearest is not None:
        source = f" ({finding.nearest_source})" if finding.nearest_source else ""
        text += f"; nearest value in the tool results: {finding.nearest}{source}"
    return text


def last_assistant_text(transcript: Path) -> str:
    """The text of the last assistant message of a Claude Code transcript that has any."""
    try:
        lines = transcript.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    for line in reversed(lines):
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        message = entry.get("message") if isinstance(entry, dict) else None
        if not isinstance(message, dict) or message.get("role") != "assistant":
            continue
        content = message.get("content")
        if isinstance(content, str):
            parts = [content]
        elif isinstance(content, list):
            parts = [
                block.get("text", "")
                for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            ]
        else:
            continue
        text = "\n".join(p for p in parts if p).strip()
        if text:
            return text
    return ""


def _path(value: Any) -> Path | None:
    return Path(value) if isinstance(value, str) and value else None


def _blocks_for(workspace: Path, session: Any, prompt: Any) -> int:
    """Blocks already issued for this answer: same session and prompt, not released."""
    try:
        lines = blocks_path(workspace).read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return 0
    count = 0
    for line in lines:
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if (
            isinstance(entry, dict)
            and entry.get("session_id") == session
            and entry.get("prompt_id") == prompt
            and not entry.get("released")
        ):
            count += 1
    return count


def _append_block(
    workspace: Path,
    session: Any,
    prompt: Any,
    answer: str,
    verdict: Verdict,
    active: bool,
    released: bool,
) -> None:
    entry = {
        "ts": datetime.now(UTC).isoformat(timespec="seconds"),
        "session_id": session,
        "prompt_id": prompt,
        "answer_hash": hashlib.sha256(answer.encode("utf-8")).hexdigest()[:16],
        "stop_hook_active": active,
        "released": released,
        "claims_checked": verdict.claims,
        "unverified": [u.to_dict() for u in verdict.unverified],
    }
    with blocks_path(workspace).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _log_error(workspace: Path | None, trace: str) -> None:
    if workspace is None:
        return
    try:
        stamp = datetime.now(UTC).isoformat(timespec="seconds")
        with (workspace / STATE_DIR / ERRORS_LOG).open("a", encoding="utf-8") as handle:
            handle.write(f"{stamp}\n{trace}\n")
    except OSError:
        pass
