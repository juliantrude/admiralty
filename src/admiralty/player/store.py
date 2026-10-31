"""The Player Model as an event store, and the only code that writes it (M9, `docs/plans/M9.md`).

    <data dir>/player-model/
        events.jsonl    append-only, one line per change: what, which concept, which Campaign,
                        in-game date, why. The truth.
        model.json      cache: the replay of events.jsonl. Rebuilt whenever it differs from the replay.
        .lock           flock target; the MCP server and the CLI may append at the same time.

The Coach is a language model and keeps no books: it reaches this store through the Academy tools
only, and the PreToolUse hook (`player/guard.py`) refuses Write, Edit and Bash on the folder.

Event kinds (the rules that produce them live in `player/mastery.py`):
    level   the concept moved to `level` (`previous` is where it was)
    drop    like `level`, downwards by the drop rule; counted in `drops`
    hatch   the Player pulled the Escape Hatch on the concept; `situation` says in which situation
    note    anything else worth keeping (a candidate answer, a patch reset); no effect on the model
"""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from admiralty.workspace.registry import data_dir

MODEL_DIR = "player-model"
EVENTS_FILE = "events.jsonl"
MODEL_FILE = "model.json"
LOCK_FILE = ".lock"

LEVELS = ("new", "understand", "apply", "analyse", "evaluate", "create")
KINDS = ("level", "drop", "hatch", "note")
NEW = LEVELS[0]


class EventInvalid(ValueError):
    """An event the store refuses to write."""


def model_dir(base: Path | None = None) -> Path:
    return (base if base is not None else data_dir()) / MODEL_DIR


def append(
    kind: str,
    *,
    reason: str,
    concept: str | None = None,
    campaign: str | None = None,
    date: str | None = None,
    base: Path | None = None,
    **fields: Any,
) -> dict[str, Any]:
    """Write one event and refresh the cache; returns the event as stored (with `seq` and `ts`).

    `level` and `drop` need a concept and a known `level`; `hatch` needs a concept. `reason` is
    required for every kind: no change without a stated cause.
    """
    event: dict[str, Any] = {
        "kind": kind,
        "concept": concept,
        "campaign": campaign,
        "date": date,
        "reason": reason,
        **fields,
    }
    _check(event)
    directory = model_dir(base)
    directory.mkdir(parents=True, exist_ok=True)
    with locked(directory):
        events = list(_read_events(directory))
        event = {"seq": len(events) + 1, "ts": _now(), **event}
        line = json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n"
        fd = os.open(directory / EVENTS_FILE, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        try:
            os.write(fd, line.encode("utf-8"))
            os.fsync(fd)
        finally:
            os.close(fd)
        write_atomic(directory / MODEL_FILE, replay([*events, event]))
    return event


def events(base: Path | None = None) -> list[dict[str, Any]]:
    """Every event in order. A damaged line is skipped, not fatal: the log stays readable."""
    return list(_read_events(model_dir(base)))


def read_model(base: Path | None = None) -> dict[str, Any]:
    """The Player Model, verified against the events on every read: a cache that is missing,
    unreadable or different from the replay is rebuilt from `events.jsonl`."""
    directory = model_dir(base)
    expected = replay(_read_events(directory))
    try:
        cached = json.loads((directory / MODEL_FILE).read_text(encoding="utf-8"))
    except OSError, ValueError:
        cached = None
    if cached != expected and (directory / EVENTS_FILE).exists():
        directory.mkdir(parents=True, exist_ok=True)
        with locked(directory):
            expected = replay(_read_events(directory))
            write_atomic(directory / MODEL_FILE, expected)
    return expected


def level_of(model: dict[str, Any], concept: str) -> str:
    return model["concepts"].get(concept, {}).get("level", NEW)


def state_of(model: dict[str, Any], concept: str) -> dict[str, Any]:
    """The model's entry for a concept; one never seen is New with nothing behind it."""
    fresh = {"level": NEW, "peak": NEW, "last_change": None, "drops": 0, "hatch_uses": 0}
    return {**fresh, **model["concepts"].get(concept, {})}


def replay(history: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Fold events into the model: per concept its level, the last change, drops and hatch uses."""
    concepts: dict[str, dict[str, Any]] = {}
    count = 0
    for event in history:
        count += 1
        kind, concept = event.get("kind"), event.get("concept")
        if kind not in ("level", "drop", "hatch") or not isinstance(concept, str):
            continue
        entry = concepts.setdefault(
            concept, {"level": NEW, "peak": NEW, "last_change": None, "drops": 0, "hatch_uses": 0}
        )
        if kind in ("level", "drop") and event.get("level") in LEVELS:
            entry["level"] = event["level"]
            if LEVELS.index(entry["level"]) > LEVELS.index(entry["peak"]):
                entry["peak"] = entry["level"]
            entry["last_change"] = {
                "seq": event.get("seq"),
                "date": event.get("date"),
                "campaign": event.get("campaign"),
                "reason": event.get("reason"),
            }
            if kind == "drop":
                entry["drops"] += 1
        elif kind == "hatch":
            entry["hatch_uses"] += 1
    return {"events": count, "concepts": dict(sorted(concepts.items()))}


def _check(event: dict[str, Any]) -> None:
    kind, concept = event["kind"], event["concept"]
    if kind not in KINDS:
        raise EventInvalid(f"unknown event kind {kind!r}; known: {', '.join(KINDS)}")
    if not isinstance(event["reason"], str) or not event["reason"].strip():
        raise EventInvalid("an event needs a reason")
    if kind in ("level", "drop", "hatch") and not (isinstance(concept, str) and concept):
        raise EventInvalid(f"a {kind} event needs a concept")
    if kind in ("level", "drop") and event.get("level") not in LEVELS:
        raise EventInvalid(f"a {kind} event needs a level out of {', '.join(LEVELS)}")
    for key in ("seq", "ts"):
        if key in event:
            raise EventInvalid(f"{key!r} is set by the store")


def _read_events(directory: Path) -> Iterator[dict[str, Any]]:
    try:
        lines = (directory / EVENTS_FILE).read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return
    for line in lines:
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict):
            yield event


@contextmanager
def locked(directory: Path) -> Iterator[None]:
    with (directory / LOCK_FILE).open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def write_atomic(path: Path, document: dict[str, Any]) -> None:
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(document, handle, ensure_ascii=False, indent=1, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    except BaseException:
        Path(temp).unlink(missing_ok=True)
        raise


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")
