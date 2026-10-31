"""The time frame of a retrospective, resolved against the archived dates.

The archive holds one extract per in-game date it was ever fed (`workspace/archive.py`), nothing in
between. A frame therefore starts and ends on archived dates only; the result states them so the
Player can correct what "the last session" resolved to.

    request                  frame
    default / "last"         second newest archived date to the newest (the archive has no notion
                             of a Play Session: one entry per save read)
    since=D                  newest archived date at or before D (the first one when D lies before
                             all of them) to the newest
    since="all"              first to last archived date
    until=E                  the end moves to the newest archived date at or before E; `last` then
                             means the date before that end

Stellaris counts 12 months of 30 days, so a year is 360 days (`years_between`).
"""

from __future__ import annotations

import re
from bisect import bisect_right
from dataclasses import dataclass
from typing import Any

from admiralty.workspace.archive import Archive

_DATE = re.compile(r"(\d{4})\.(\d{2})\.(\d{2})")
DAYS_PER_YEAR = 360
LAST = "last"
ALL = "all"


class FrameError(ValueError):
    """The request cannot be resolved against the archive; the message is shown to the Player."""


@dataclass(frozen=True)
class Frame:
    request: str  # what was asked, for the result: "last", "all", "since 2250.01.01", ...
    start: str
    end: str
    dates: list[str]  # every usable archived date from start to end, oldest first


@dataclass
class Loaded:
    """The usable archived extracts of one Campaign and what was left out."""

    documents: dict[str, dict[str, Any]]  # by header date, oldest first
    problems: list[str]

    @property
    def dates(self) -> list[str]:
        return list(self.documents)


def day_number(date: str) -> int:
    found = _DATE.fullmatch(str(date))
    if not found:
        raise FrameError(f"not an in-game date (YYYY.MM.DD): {date!r}")
    year, month, day = (int(part) for part in found.groups())
    return year * DAYS_PER_YEAR + (month - 1) * 30 + (day - 1)


def date_of(day: int) -> str:
    """The in-game date of a day number (the inverse of `day_number`)."""
    year, rest = divmod(day, DAYS_PER_YEAR)
    month, offset = divmod(rest, 30)
    return f"{year:04d}.{month + 1:02d}.{offset + 1:02d}"


def years_between(start: str, end: str) -> float:
    """Span in in-game years, two decimals (12 months of 30 days)."""
    return round((day_number(end) - day_number(start)) / DAYS_PER_YEAR, 2)


def load_campaign(archive: Archive) -> Loaded:
    """Read every archived extract. Unreadable files and extracts of another Campaign or Tracked
    Empire than the newest one's are left out and listed in `problems`, never fatal."""
    problems: list[str] = []
    documents: dict[str, dict[str, Any]] = {}
    for entry in archive.list():
        if entry.problem:
            problems.append(f"{entry.date}: {entry.problem}")
            continue
        try:
            documents[entry.date] = archive.load(entry.date)
        except Exception as error:  # a file may turn bad between listing and loading
            problems.append(f"{entry.date}: {error}")
    if documents:
        newest = documents[max(documents)]["header"]
        key = (newest["campaign"], newest["tracked_empire"]["country_id"])
        for date in list(documents):
            header = documents[date]["header"]
            if (header["campaign"], header["tracked_empire"]["country_id"]) != key:
                del documents[date]
                problems.append(
                    f"{date}: skipped, it belongs to another Campaign or Tracked Empire than "
                    f"{newest['campaign']!r} / {newest['tracked_empire']['name']!r}"
                )
    return Loaded(dict(sorted(documents.items())), problems)


def resolve_frame(dates: list[str], since: str | None = None, until: str | None = None) -> Frame:
    """The frame for a request over the usable archived `dates` (sorted, oldest first)."""
    if len(dates) < 2:
        raise FrameError(_too_few(dates))
    since = (since or LAST).strip()
    if until is not None:
        day_number(until)
    end_index = len(dates) - 1 if until is None else _at_or_before(dates, until, "until", "before")
    if since == LAST:
        start_index, label = end_index - 1, LAST
    elif since == ALL:
        start_index, label = 0, ALL
    else:
        day_number(since)
        start_index, label = max(bisect_right(dates, since) - 1, 0), f"since {since}"
    if until is not None:
        label += f" until {until}"
    if start_index >= end_index:
        raise FrameError(
            f"the request ({label}) resolves to {dates[start_index]} to {dates[end_index]}: a "
            f"retrospective needs two archived dates. Archived: {', '.join(dates)}"
        )
    return Frame(label, dates[start_index], dates[end_index], dates[start_index : end_index + 1])


def _at_or_before(dates: list[str], date: str, name: str, what: str) -> int:
    index = bisect_right(dates, date) - 1
    if index < 0:
        raise FrameError(
            f"{name}={date} lies {what} the first archived date {dates[0]}: nothing is archived "
            "up to it"
        )
    return index


def _too_few(dates: list[str]) -> str:
    held = f"only {dates[0]}" if dates else "none"
    return (
        f"a retrospective needs two archived dates; the archive holds {held}. Debrief reads what "
        "the Ops and Academy tools archived on every save they read: read another save, then ask again"
    )
