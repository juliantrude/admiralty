"""The Drill: one run of Coaching questions about one Snapshot (M9, `docs/plans/M9.md` 20d; `GLOSSARY.md` Drill).

    <workspace>/academy/
        drill.json      the open Drill: its topics, the current one, the Hint Ladder level of each
        drills.jsonl    closed Drills, one line each, appended on close (the dates the Coach raised each topic)
        evidence.jsonl  copy of the Player Model events this Campaign produced (`player/store.py` keeps the truth)
        .lock           flock target; the MCP server and the CLI may act on the Drill at the same time

The Coach is a language model and keeps no books. It reports the outcome of an attempt; this module moves the
Hint Ladder (`academy/ladder.py`), hands the outcome to the Mastery rules (`player/mastery.record`, the only way to
the Player Model), and keeps what the Evidence rules need: the in-game date the Coach raised each topic (`raised`),
and all such dates (`prompts`, see `evidence_inputs`) for `player/evidence.record_evidence`.

A topic is `{"concept", "crisis", "open_question", ...}` as the topic builder (`academy/topics.py`) hands it over; the fields beyond
those two flags are kept as they are. `crisis` doubles the Ladder step; the Drill itself keeps the Crisis the
Snapshot shows (`player/evidence.crisis`) so the Coach can name it in question mode.

Status of a topic: `current` (one at a time), `waiting`, `done` (`result` is `named`: cause and remedy named,
`explained`: the full explanation was given, `hatch`: the Escape Hatch), `skipped` ("next topic" before it was done),
`left` (the Drill closed first). Raised topics are those that were ever current.

Choices where the plan is silent, each pinned by a test:
- A topic is over when the Player named both the cause and the remedy, the Coach gave the full explanation or the
  Escape Hatch was pulled. The Drill does not move on by itself; `next_topic` does, and it works at any time.
- Naming the remedy first leaves the cause as the next question (the order is cause, then remedy).
- The Escape Hatch counts as Ladder level 4 and answers the current topic; a full Briefing the Player asked for passes
  `concepts` and records one hatch per concept in it.
- Closing needs the summary (the Player's plan in two or three sentences); it works with topics still waiting.
"""

from __future__ import annotations

import json
import os
from collections.abc import Collection, Iterable
from pathlib import Path
from typing import Any

from admiralty.academy import ladder
from admiralty.debrief.frame import day_number
from admiralty.player import evidence, mastery, store
from admiralty.player.mastery import Refused

ACADEMY_DIR = "academy"
DRILL_FILE = "drill.json"
ARCHIVE_FILE = "drills.jsonl"
EVIDENCE_FILE = "evidence.jsonl"

TOPIC_KEYS = ("concept", "crisis", "open_question")


class DrillError(ValueError):
    """The Drill is not in a state for this call (none open, one already open, nothing current)."""


def academy_dir(workspace: Path) -> Path:
    return Path(workspace) / ACADEMY_DIR


def open_drill(
    workspace: Path,
    *,
    date: str,
    topics: Iterable[dict[str, Any]],
    campaign: str | None = None,
    extract: dict[str, Any] | None = None,
    goals: Iterable[str] = (),
) -> dict[str, Any]:
    """Start a Drill on the Snapshot of `date`; the first topic is raised at once.

    `extract` is that Snapshot, used for the Crisis flag. `goals` are the Goals the Player named for this
    Drill (asked at the first Drill and at every Rendezvous), kept as given; the topics come from
    `academy/topics.build_topics`. Raises `DrillError` while another Drill is open and
    for a topic without a concept or a concept twice.
    """
    day_number(date)  # an in-game date, or FrameError
    prepared = _prepare(topics)
    directory = academy_dir(workspace)
    directory.mkdir(parents=True, exist_ok=True)
    with store.locked(directory):
        if (directory / DRILL_FILE).exists():
            raise DrillError("a Drill is already open; continue it or close it with a summary")
        drill = {
            "version": 1,
            "status": "open",
            "campaign": campaign,
            "date": date,
            "goals": list(dict.fromkeys(goals)),
            "crisis": evidence.crisis(extract) if extract is not None else _no_crisis(),
            "topics": prepared,
            "current": None,
        }
        _raise_next(drill)
        store.write_atomic(directory / DRILL_FILE, drill)
    return _view(drill)


def load(workspace: Path) -> dict[str, Any] | None:
    """The open Drill as stored, or None."""
    return _read(academy_dir(workspace))


def view(workspace: Path) -> dict[str, Any]:
    """Where the Drill stands: the current topic with its Ladder level, how many topics wait."""
    drill = load(workspace)
    if drill is None:
        raise DrillError("no Drill is open")
    return _view(drill)


def attempt(
    workspace: Path,
    outcome: str,
    *,
    domain_named: bool = True,
    supported: bool | None = None,
    text: str | None = None,
    situation: str | None = None,
) -> dict[str, Any]:
    """The Coach reports the outcome of the Player's answer to the current topic.

    The Ladder moves, the Mastery rules run (`player/mastery.record`; `supported` is the tool's check of a
    `support` answer against the Snapshot, never the model's say) and the topic is over when the rules above say
    so. `domain_named` is False only for a question that did not name the domain (Analyse). Raises `Refused`
    for an outcome the Ladder or the Mastery rules do not allow; nothing is written then.
    """
    directory = academy_dir(workspace)
    with store.locked(_existing(directory)):
        drill = _need(directory)
        topic = _current(drill)
        if topic["status"] == "done":
            raise DrillError("this topic is over; move on with `next topic`")
        moved = ladder.move(topic["ladder"], outcome, crisis=topic["crisis"], supported=supported)
        event = {
            "type": "attempt",
            "outcome": outcome,
            "ladder": topic["ladder"],
            "domain_named": domain_named,
            "supported": supported,
            "text": text,
            "situation": situation,
        }
        recorded = mastery.record(
            topic["concept"], event, campaign=drill["campaign"], date=drill["date"]
        )
        copy_events(directory, recorded["events"])
        topic["attempts"].append({"ladder": topic["ladder"], "outcome": outcome})
        topic["ladder"] = moved["level"]
        if moved["named"] and moved["named"] not in topic["named"]:
            topic["named"].append(moved["named"])
        if outcome == "escape_hatch":
            _finish(topic, "hatch")
        elif moved["explained"]:
            _finish(topic, "explained")
        elif all(name in topic["named"] for name in ladder.NAMED):
            _finish(topic, "named")
        store.write_atomic(directory / DRILL_FILE, drill)
        return {
            **_view(drill),
            "outcome": outcome,
            "ask_where": moved["ask_where"],
            "effects": recorded["effects"],
            "announce": [e for e in recorded["effects"] if e["effect"] == "level"],
        }


def escape(
    workspace: Path,
    situation: str,
    *,
    concepts: Collection[str] = (),
    known: Collection[str] | None = None,
) -> dict[str, Any]:
    """The Player asks to just be told: Ladder level 4, one `hatch` event with its Situation, the current topic over.

    `concepts` are further concepts the answer covered (a full Briefing the Player asked for counts for every
    concept in it); with `known` a concept outside it is refused. Without an open Drill only `concepts` can be
    recorded. Raises `Refused` without a Situation.
    """
    if not isinstance(situation, str) or not situation.strip():
        raise Refused("an Escape Hatch needs the Situation it was pulled in")
    directory = academy_dir(workspace)
    extra = list(dict.fromkeys(concepts))
    if known is not None:
        unknown = [c for c in extra if c not in known]
        if unknown:
            raise Refused(f"unknown concept(s) for the Escape Hatch: {', '.join(unknown)}")
    directory.mkdir(parents=True, exist_ok=True)
    with store.locked(directory):
        drill = _read(directory)
        topic = _current(drill) if drill is not None and drill["current"] is not None else None
        if topic is None and not extra:
            raise DrillError("no Drill is open and no concept was named")
        covered = list(dict.fromkeys([*([topic["concept"]] if topic else []), *extra]))
        event = {
            "type": "attempt",
            "outcome": "escape_hatch",
            "ladder": ladder.TOP,
            "situation": situation,
        }
        campaign, date = (drill["campaign"], drill["date"]) if drill else (None, None)
        written: list[dict[str, Any]] = []
        for concept in covered:
            written += mastery.record(concept, event, campaign=campaign, date=date)["events"]
        copy_events(directory, written)
        if topic is not None:
            topic["attempts"].append({"ladder": ladder.TOP, "outcome": "escape_hatch"})
            topic["ladder"] = ladder.TOP
            if topic["status"] != "done":
                _finish(topic, "hatch")
            store.write_atomic(directory / DRILL_FILE, drill)
        return {
            **(_view(drill) if drill else {}),
            "outcome": "escape_hatch",
            "concepts": covered,
            "events": len(written),
        }


def next_topic(workspace: Path) -> dict[str, Any]:
    """ "Next topic": the current one is skipped unless it is over, the next waiting one is raised.

    `finished` is True when none waits; the Coach closes the Drill with a summary then (or the Player plays on).
    """
    directory = academy_dir(workspace)
    with store.locked(_existing(directory)):
        drill = _need(directory)
        topic = _current(drill) if drill["current"] is not None else None
        if topic is not None and topic["status"] != "done":
            topic["status"] = "skipped"
        _raise_next(drill)
        store.write_atomic(directory / DRILL_FILE, drill)
        return _view(drill)


def close(workspace: Path, summary: str) -> dict[str, Any]:
    """End the Drill with the summary of what the Player means to do (two or three sentences).

    The Drill moves to `drills.jsonl`; topics not yet over are marked `left`. `ended` is `all_done` when every
    topic was over or skipped, else `player_stopped`.
    """
    if not isinstance(summary, str) or not summary.strip():
        raise Refused("closing a Drill needs the summary of what the Player means to do")
    directory = academy_dir(workspace)
    with store.locked(_existing(directory)):
        drill = _need(directory)
        statuses = [t["status"] for t in drill["topics"]]
        ended = "all_done" if all(s in ("done", "skipped") for s in statuses) else "player_stopped"
        for topic in drill["topics"]:
            if topic["status"] in ("current", "waiting"):
                topic["status"] = "left"
        drill = {
            **drill,
            "status": "closed",
            "ended": ended,
            "summary": summary.strip(),
            "current": None,
        }
        _append_line(directory / ARCHIVE_FILE, drill)
        (directory / DRILL_FILE).unlink()
    return {
        "status": "closed",
        "ended": ended,
        "summary": drill["summary"],
        "topics": [
            {"concept": t["concept"], "status": t["status"], "result": t.get("result")}
            for t in drill["topics"]
        ],
    }


def raised_dates(workspace: Path, concept: str) -> list[str]:
    """Every in-game date the Coach raised a topic on the concept, open and closed Drills, oldest first."""
    directory = academy_dir(workspace)
    drills = [*_archive(directory)]
    current = _read(directory)
    if current is not None:
        drills.append(current)
    dates = {
        t["raised"]
        for d in drills
        for t in d["topics"]
        if t["concept"] == concept and t.get("raised")
    }
    return sorted(dates, key=day_number)


def evidence_inputs(workspace: Path, concept: str) -> dict[str, Any]:
    """`{"raised": latest date or None, "prompts": all dates}` for `player/evidence.record_evidence`."""
    dates = raised_dates(workspace, concept)
    return {"raised": dates[-1] if dates else None, "prompts": dates}


def _no_crisis() -> dict[str, Any]:
    return {"crisis": False, "resources": []}


def _prepare(topics: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    prepared: list[dict[str, Any]] = []
    for topic in topics:
        concept = topic.get("concept")
        if not isinstance(concept, str) or not concept:
            raise DrillError("every topic needs a concept")
        if any(p["concept"] == concept for p in prepared):
            raise DrillError(f"the concept {concept} is in the Drill twice")
        prepared.append(
            {
                **{k: v for k, v in topic.items() if k not in TOPIC_KEYS},
                "concept": concept,
                "crisis": bool(topic.get("crisis")),
                "open_question": bool(topic.get("open_question")),
                "status": "waiting",
                "ladder": ladder.QUESTION,
                "named": [],
                "attempts": [],
                "raised": None,
                "result": None,
            }
        )
    return prepared


def _raise_next(drill: dict[str, Any]) -> None:
    """Make the next waiting topic current and note the date the Coach raised it; none left: `current` is None."""
    for index, topic in enumerate(drill["topics"]):
        if topic["status"] == "waiting":
            topic["status"] = "current"
            topic["raised"] = drill["date"]
            drill["current"] = index
            return
    drill["current"] = None


def _finish(topic: dict[str, Any], result: str) -> None:
    topic["status"] = "done"
    topic["result"] = result


def _current(drill: dict[str, Any]) -> dict[str, Any]:
    if drill["current"] is None:
        raise DrillError(
            "no topic is current; every topic has been taken, close the Drill with a summary"
        )
    return drill["topics"][drill["current"]]


def _view(drill: dict[str, Any]) -> dict[str, Any]:
    topic = _current(drill) if drill["current"] is not None else None
    shown = None
    if topic is not None:
        phase = next((n for n in ladder.NAMED if n not in topic["named"]), None)
        shown = {
            **{k: v for k, v in topic.items() if k != "attempts"},
            "attempts": len(topic["attempts"]),
            "ladder_name": ladder.NAMES[topic["ladder"]],
            "asks_for": phase if topic["status"] != "done" else None,
            "may_explain": topic["ladder"] == ladder.TOP and topic["status"] != "done",
        }
    return {
        "status": drill["status"],
        "date": drill["date"],
        "campaign": drill["campaign"],
        "goals": drill.get("goals", []),
        "crisis": drill["crisis"],
        "topic": shown,
        "waiting": sum(1 for t in drill["topics"] if t["status"] == "waiting"),
        "finished": topic is None
        or (
            topic["status"] == "done" and not any(t["status"] == "waiting" for t in drill["topics"])
        ),
    }


def _existing(directory: Path) -> Path:
    if not directory.is_dir():
        raise DrillError("no Drill is open")
    return directory


def _need(directory: Path) -> dict[str, Any]:
    drill = _read(directory)
    if drill is None:
        raise DrillError("no Drill is open")
    return drill


def _read(directory: Path) -> dict[str, Any] | None:
    try:
        drill = json.loads((directory / DRILL_FILE).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except ValueError as error:
        raise DrillError(f"{directory / DRILL_FILE} is damaged: {error}") from error
    return drill if isinstance(drill, dict) else None


def _archive(directory: Path) -> Iterable[dict[str, Any]]:
    try:
        lines = (directory / ARCHIVE_FILE).read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return
    for line in lines:
        try:
            found = json.loads(line)
        except ValueError:
            continue
        if isinstance(found, dict):
            yield found


def copy_events(directory: Path, events: Iterable[dict[str, Any]]) -> None:
    for event in events:
        _append_line(directory / EVIDENCE_FILE, event)


def _append_line(path: Path, document: dict[str, Any]) -> None:
    line = json.dumps(document, ensure_ascii=False, sort_keys=True) + "\n"
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        os.write(fd, line.encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)
