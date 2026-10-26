"""What the Unverified Claim check may rely on (M7, `docs/plans/M7.md`).

Evidence = the tool results of the session (turn log entries from `since` on) plus what the
Player wrote in the same session. `build_evidence` indexes it once:

- numbers: every JSON number and every number inside a string (evidence texts, rule bodies),
  by absolute value in a sorted list so a claim is looked up at its own precision with `bisect`;
  the length of a list of records counts as a number too (`planets`, `districts`, `nodes`: a
  count the answer states is a count of what the tool listed);
- dates: in-game dates found in any string;
- names: every string value, case-folded (ids and Display Names alike; dictionary keys are
  field names and never count), searched as a whole word, so a name inside a longer text string
  of the evidence matches too;
- rules: the Playbook Rule texts in the results (`playbook_rules`), which exempt blockquotes.

Errors (`{"error": ...}`) are not evidence. The Player's messages come from the Claude Code
transcript: user text only, without tool results, meta messages and system reminders.
"""

from __future__ import annotations

import json
import re
from bisect import bisect_left
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from admiralty.claims.extract import extract_claims
from admiralty.claims.normalise import Reading, name_forms, normalise_name, to_decimal
from admiralty.workspace.turnlog import turn_log_path

_MAX_PATH = 80
_SYSTEM_REMINDER = re.compile(r"<system-reminder>.*?</system-reminder>", re.DOTALL)
_RELATIVE_NEAR = Decimal("0.1")


@dataclass(frozen=True)
class Datum:
    value: Decimal  # absolute
    source: str


@dataclass
class Evidence:
    values: list[Decimal] = field(default_factory=list)  # sorted, absolute
    sources: list[str] = field(default_factory=list)  # parallel to `values`
    dates: set[str] = field(default_factory=set)
    text: str = ""  # every string, normalised, one per line
    rules: list[str] = field(default_factory=list)
    entries: int = 0  # tool results indexed

    def find(self, reading: Reading, *, percent: bool = False) -> str | None:
        """Source of a data value the reading covers; the percent sign also allows a ratio
        (`15%` against 0.15). None when nothing rounds to the reading."""
        for candidate in (reading, reading.scaled(Decimal("0.01")) if percent else None):
            if candidate is None:
                continue
            index = bisect_left(self.values, candidate.low)
            if index < len(self.values) and self.values[index] < candidate.high:
                return self.sources[index]
        return None

    def nearest(self, reading: Reading, *, percent: bool = False) -> Datum | None:
        """The data value closest to the reading if it lies within 10 % of it, else None."""
        best: tuple[Decimal, Datum] | None = None
        for scale in (Decimal(1), Decimal("0.01")) if percent else (Decimal(1),):
            target = reading.value * scale
            index = bisect_left(self.values, target)
            for position in (index - 1, index):
                if not 0 <= position < len(self.values):
                    continue
                gap = abs(self.values[position] - target)
                if gap <= target * _RELATIVE_NEAR and (best is None or gap < best[0]):
                    best = (gap, Datum(self.values[position], self.sources[position]))
        return best[1] if best else None

    def has_name(self, key: str) -> bool:
        return any(
            re.search(rf"(?<!\w){re.escape(form)}(?!\w)", self.text) for form in name_forms(key)
        )


def build_evidence(entries: Iterable[dict[str, Any]], player_texts: Iterable[str] = ()) -> Evidence:
    """Index the turn log entries (`tool`, `result`) and the Player's messages."""
    data: list[Datum] = []
    strings: list[str] = []
    evidence = Evidence()
    for number, entry in enumerate(entries, 1):
        result = entry.get("result")
        if not isinstance(result, (dict, list)) or (isinstance(result, dict) and "error" in result):
            continue
        evidence.entries += 1
        label = f"{entry.get('tool', '?')}#{number}"
        for path, value in _walk(result, label):
            _add_value(value, path, data, strings, evidence.dates)
        if isinstance(result, dict):
            for rule_id, rule in (result.get("playbook_rules") or {}).items():
                strings.append(normalise_name(rule_id))  # a rule id is a name the answer may cite
                evidence.rules += [v for v in rule.values() if isinstance(v, str)]
    for text in player_texts:
        _add_value(text, "player", data, strings, evidence.dates)
    data.sort(key=lambda d: d.value)
    evidence.values = [d.value for d in data]
    evidence.sources = [d.source for d in data]
    evidence.text = "\n".join(strings)
    return evidence


def _walk(node: Any, path: str) -> Iterator[tuple[str, Any]]:
    """(path, leaf) for every leaf; a list of records also yields its length as a number."""
    if isinstance(node, dict):
        for key, child in node.items():
            yield from _walk(child, f"{path}.{key}"[-_MAX_PATH:])
    elif isinstance(node, list):
        if node and all(isinstance(child, dict) for child in node):
            yield path, len(node)
        for child in node:
            yield from _walk(child, path)
    else:
        yield path, node


def _add_value(
    value: Any, path: str, data: list[Datum], strings: list[str], dates: set[str]
) -> None:
    if isinstance(value, str):
        name = normalise_name(value)
        if name:
            strings.append(name)
        if any(char.isdigit() for char in value):
            for claim in extract_claims(value):
                if claim.kind == "date":
                    dates.add(claim.key)
                for reading in claim.readings:
                    data.append(Datum(abs(reading.value), path))
        return
    number = to_decimal(value) if isinstance(value, (int, float)) else None
    if number is not None:
        data.append(Datum(abs(number), path))


# --- reading the session ----------------------------------------------------------------------


def read_turn_log(workspace: Path, since: datetime | None = None) -> list[dict[str, Any]]:
    """The turn log entries of the workspace, from `since` on. Broken lines are skipped."""
    try:
        lines = turn_log_path(workspace).read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []
    since = _aware(since) if since else None
    entries = []
    for line in lines:
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if isinstance(entry, dict) and (since is None or _after(entry.get("ts"), since)):
            entries.append(entry)
    return entries


def _after(stamp: Any, since: datetime) -> bool:
    moment = _parse_time(stamp)
    return moment is None or moment >= since


def _aware(moment: datetime) -> datetime:
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def _parse_time(stamp: Any) -> datetime | None:
    if not isinstance(stamp, str):
        return None
    try:
        return _aware(datetime.fromisoformat(stamp.replace("Z", "+00:00")))
    except ValueError:
        return None


def read_transcript(path: Path) -> tuple[datetime | None, list[str]]:
    """(time of the first entry, the Player's own messages) of a Claude Code transcript.

    Player messages are `user` entries whose content is text; tool results, meta messages (skill
    text, hook output) and `<system-reminder>` blocks are left out. Unreadable lines are skipped.
    """
    first: datetime | None = None
    texts: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None, []
    for line in lines:
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if not isinstance(entry, dict):
            continue
        first = first or _parse_time(entry.get("timestamp"))
        if entry.get("type") != "user" or entry.get("isMeta"):
            continue
        message = entry.get("message")
        content = message.get("content") if isinstance(message, dict) else None
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
        texts += [t for t in (_SYSTEM_REMINDER.sub("", p).strip() for p in parts) if t]
    return first, texts
