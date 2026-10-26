"""Playbook Rules: the Player's approved judgement, one Markdown file per rule.

`knowledge/<version>/rules/<id>.md` holds YAML front matter (id, date, status, applies_to, reason)
and a Markdown body that Ops may quote in a Briefing (the Unverified Claim check exempts
numbers inside quoted rules, so the body is the quotable text). Format and rationale:
docs/plans/M4.md "Playbook Rules".

Only `status: approved` rules live in `knowledge/`. A proposed rule belongs in
docs/proposals/playbook.md until the Player approves it, so `read_rules` reports a proposed file
as an error instead of loading it. The graph validator calls `read_rules` and adds the
cross-checks that need the graph (`applies_to` patterns must match node or Goal ids).
"""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

DEFAULT_VERSION = "v4.5.2"
_ID = re.compile(r"[a-z][a-z0-9]*(-[a-z0-9]+)*")
_REQUIRED = ("id", "date", "status", "applies_to", "reason")


class RulesInvalid(ValueError):
    """A rule file is malformed; `errors` lists every problem, as `file: message`."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(f"{len(errors)} error(s) in the Playbook, first: {errors[0]}")


@dataclass(frozen=True)
class Rule:
    id: str
    date: datetime.date
    reason: str
    applies_to: tuple[str, ...]  # node / Goal ids, `*` allowed as in fact patterns
    body: str  # the quotable Markdown text
    file: str


def read_rules(directory: Path) -> tuple[dict[str, Rule], list[str]]:
    """Rules by id from one rules folder, plus every problem found (never raises)."""
    rules: dict[str, Rule] = {}
    errors: list[str] = []
    for path in sorted(directory.glob("*.md")) if directory.is_dir() else ():
        rule, problems = _parse(path)
        errors += [f"{path.name}: {message}" for message in problems]
        if rule is None:
            continue
        if rule.id in rules:
            errors.append(f"{path.name}: id '{rule.id}' is already used by {rules[rule.id].file}")
        else:
            rules[rule.id] = rule
    return rules, errors


def load_rules(version: str = DEFAULT_VERSION, root: Path | None = None) -> dict[str, Rule]:
    """The approved Playbook Rules of a game version, by id, in file order."""
    # imported here: mechanics imports this module to validate the rules its nodes cite
    from admiralty.graph.mechanics import KNOWLEDGE_ROOT, GraphMissing

    base = (root or KNOWLEDGE_ROOT) / version.removeprefix("v")
    if not base.is_dir():
        raise GraphMissing(f"no knowledge pack for {version} in {base.parent}")
    rules, errors = read_rules(base / "rules")
    if errors:
        raise RulesInvalid(errors)
    return rules


def _parse(path: Path) -> tuple[Rule | None, list[str]]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n") or "\n---" not in text[4:]:
        return None, ["no YAML front matter between '---' lines"]
    end = text.index("\n---", 4)
    try:
        front = yaml.safe_load(text[4:end])
    except yaml.YAMLError as error:
        return None, [f"front matter is not valid YAML: {error}"]
    if not isinstance(front, dict):
        return None, ["front matter is not a mapping"]
    missing = [key for key in _REQUIRED if key not in front]
    if missing:
        return None, [f"front matter lacks {', '.join(missing)}"]

    problems: list[str] = []
    rule_id, date, reason, applies = (front[k] for k in ("id", "date", "reason", "applies_to"))
    if not isinstance(rule_id, str) or not _ID.fullmatch(rule_id):
        problems.append(f"id {rule_id!r} is not lower-case words joined by '-'")
    elif path.stem != rule_id:
        problems.append(f"id '{rule_id}' does not match the file name")
    if not isinstance(date, datetime.date) or isinstance(date, datetime.datetime):
        problems.append(f"date {date!r} is not an ISO date (YYYY-MM-DD)")
    if front["status"] != "approved":
        problems.append(
            f"status is {front['status']!r}; only approved rules belong in knowledge/ "
            "(proposals go to docs/proposals/playbook.md)"
        )
    if not isinstance(reason, str) or not reason.strip():
        problems.append("reason is empty")
    if not (
        isinstance(applies, list) and applies and all(isinstance(a, str) and a for a in applies)
    ):
        problems.append("applies_to is not a non-empty list of node ids")
    body = text[end + 4 :].strip()
    if not body:
        problems.append("the rule has no body text")
    if problems:
        return None, problems
    return Rule(rule_id, date, reason.strip(), tuple(applies), body, path.name), []
