"""The Rendezvous: the in-game date the Coach and the Player agree on at the end of a Drill (M9, `docs/plans/M9.md` 20g;
`GLOSSARY.md` Rendezvous; grilling topic 1, R5 Q4).

    <workspace>/academy/rendezvous.json    {"date", "save_name", "set_on", "moves": [...]}, or absent

The Player plays until the date, saves by hand under the agreed name, and the next Drill starts like a Debrief in
Coaching. The Coach proposes ("Play until January 2290, save by hand as Academy 2290-01"); the Player may move it.

`propose`: at most five in-game years after today, and late enough that every open Prediction can be checked (the
latest check date of an open foretold Prediction); otherwise `DEFAULT_YEARS` ahead. The date is the first day of a
month where that keeps the rules, as in the example. `move` takes any date after today within five years and reports
the open Predictions whose check date then lies after the Rendezvous (`unchecked`); the Player's say wins.

`position(newest)` answers for the newest save: `before` (the Player is still playing; days left), `at` (the save lies
at the date or at most `TOLERANCE_DAYS` after it: the Rendezvous was kept), `after` (later than that: missed, the
newest save is used and the missed date is named). The archive keys saves by in-game date, not by file name, so the
date is what identifies the save; the name is the instruction to the Player.

Choices where the plan is silent, each pinned by a test:
- Two years ahead and thirty days of tolerance are placeholders, tuned on Julian's trial.
- Moving keeps every earlier date in `moves`, so the Debrief can say that the Rendezvous was moved.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from admiralty.academy.drill import academy_dir
from admiralty.debrief.frame import DAYS_PER_YEAR, date_of, day_number
from admiralty.player import store
from admiralty.player.mastery import Refused

RENDEZVOUS_FILE = "rendezvous.json"
MAX_YEARS = 5
DEFAULT_YEARS = 2
TOLERANCE_DAYS = 30


def propose(
    today: str, predictions: Iterable[dict[str, Any]] = (), *, years: float = DEFAULT_YEARS
) -> dict[str, Any]:
    """The date and save name the Coach proposes at the end of a Drill on the Snapshot of `today`."""
    if not 0 < years <= MAX_YEARS:
        raise Refused(f"a Rendezvous lies at most {MAX_YEARS} years ahead, not {years}")
    start = day_number(today)
    cap = start + MAX_YEARS * DAYS_PER_YEAR
    open_checks = {
        p["id"]: day_number(p["check_date"])
        for p in predictions
        if p.get("state") == "open" and p.get("basis") == "foretold"
    }
    wanted = max([start + round(years * DAYS_PER_YEAR), *open_checks.values()])
    aligned = _month_start_on_or_after(wanted)
    day = aligned if aligned <= cap else min(wanted, cap)
    return {
        "date": date_of(day),
        "save_name": save_name(date_of(day)),
        "checks": sorted(i for i, d in open_checks.items() if d <= day),
    }


def save_name(date: str) -> str:
    """The name the Player saves under, `Academy 2290-01`: year and month keep two Rendezvous apart."""
    day_number(date)
    return f"Academy {date[:4]}-{date[5:7]}"


def set_rendezvous(
    workspace: Path,
    date: str,
    *,
    today: str,
    predictions: Iterable[dict[str, Any]] = (),
    save_name_: str | None = None,
) -> dict[str, Any]:
    """Agree on `date` (the Coach's proposal or the Player's own) or move an agreed one; atomic, under the Academy lock.

    Raises `Refused` for a date that is not after `today` or more than five years ahead. `unchecked` lists the open
    foretold Predictions whose check date lies after the new date.
    """
    start, day = day_number(today), day_number(date)
    if day <= start:
        raise Refused(f"the Rendezvous {date} must lie after {today}")
    if day > start + MAX_YEARS * DAYS_PER_YEAR:
        raise Refused(f"the Rendezvous {date} lies more than {MAX_YEARS} years after {today}")
    name = (
        save_name_.strip()
        if isinstance(save_name_, str) and save_name_.strip()
        else save_name(date)
    )
    directory = academy_dir(workspace)
    directory.mkdir(parents=True, exist_ok=True)
    with store.locked(directory):
        earlier = _read(directory)
        moves = list(earlier["moves"]) if earlier else []
        if earlier and earlier["date"] != date:
            moves.append(
                {"date": earlier["date"], "save_name": earlier["save_name"], "moved_on": today}
            )
        document = {"date": date, "save_name": name, "set_on": today, "moves": moves}
        store.write_atomic(directory / RENDEZVOUS_FILE, document)
    unchecked = sorted(
        p["id"]
        for p in predictions
        if p.get("state") == "open"
        and p.get("basis") == "foretold"
        and day_number(p["check_date"]) > day
    )
    return {**document, "unchecked": unchecked}


def load(workspace: Path) -> dict[str, Any] | None:
    """The agreed Rendezvous, or None."""
    return _read(academy_dir(workspace))


def position(workspace: Path, newest: str) -> dict[str, Any]:
    """Where the newest save (in-game date) lies relative to the agreed Rendezvous: `none`, `before`, `at`, `after`."""
    agreed = load(workspace)
    if agreed is None:
        return {"position": "none"}
    distance = day_number(newest) - day_number(agreed["date"])
    base = {"date": agreed["date"], "save_name": agreed["save_name"], "newest": newest}
    if distance < 0:
        return {**base, "position": "before", "days_left": -distance}
    if distance <= TOLERANCE_DAYS:
        return {**base, "position": "at"}
    return {**base, "position": "after", "days_late": distance, "missed": True}


def _month_start_on_or_after(day: int) -> int:
    start = day - day % 30
    return start if start == day else start + 30


def _read(directory: Path) -> dict[str, Any] | None:
    try:
        found = json.loads((directory / RENDEZVOUS_FILE).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except ValueError as error:
        raise Refused(f"{directory / RENDEZVOUS_FILE} is damaged: {error}") from error
    return found if isinstance(found, dict) else None
