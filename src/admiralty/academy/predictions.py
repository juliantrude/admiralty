"""Predictions: what the Player expects a major decision to achieve (M9, `docs/plans/M9.md` 20g; `GLOSSARY.md` Prediction).

    <workspace>/predictions/p001.json, p002.json, ...   one file per Prediction (the directory exists since M2)

A Prediction is one sentence, given before the decision, and a check date the Coach proposes, at most five in-game
years after it was made. The decisions are a fixed list (`KINDS`): declare a war, take an Ascension Perk, adopt a
Tradition tree, build a megastructure, found or join a federation, redesignate a world. The Coach is a language
model; this module keeps the books (the state, the date rules, the Evaluate feed), the model words the sentence.

Detection, from the Snapshots (grilling topic 1, R3 Q3):
    `detect_before(extract)`   one Snapshot announces a decision: Unity covers the next Tradition and a Tradition
                               tree slot is free (`progression.next_tradition.affordable`,
                               `progression.tradition_tree_slots.free`; adopting a tree is a Tradition of its own
                               and costs what `extract/computed/tradition_cost.py` computes for the next one), or
                               an Ascension Perk slot is free (`progression.ascension_slots.free`). Nothing else is
                               announced by a save; a war is not.
    `detect_after(old, new)`   two Snapshots show a decision that was made in between: a Tradition tree or Ascension
                               Perk in `new` and not in `old`, a war the Tracked Empire attacked in
                               (`military.wars`, `side` attacker, not in `old`), a planet whose designation changed.
                               A war that began and ended between the two is not seen.
    Megastructures and federations are on the list but the extract does not carry them, so they are named in
    `NOT_DETECTABLE` and never found; the Player can still state a Prediction about them.

An expectation given after the decision is stored apart (`basis` `hindsight`), never feeds Evaluate and weighs less in
Debrief; one given before is `foretold`. A detected decision whose kind has an open foretold Prediction is reported as
a match of that Prediction, not as a new hindsight candidate.

The check (`check_due`): the Snapshot of the check date is the first one at or after it. A Prediction that carries an
`expect` (a dotted path into the extract, an operator, a number, the same shape the Mechanics Graph uses) is decided
by this module from that Snapshot: `confirmed` or `refuted`, `unclear` where the path has no value. One without
`expect` stays `open` and is listed under `needs_verdict`; the Player's verdict (`decide`) is stored as
`decided_by` `player`.

Choices where the plan is silent, each pinned by a test:
- Only a foretold Prediction decided by a Snapshot (`decided_by` `snapshot`) and `confirmed` lifts the concepts it
  names to Evaluate (`mastery.record`, basis `prediction`); a Player verdict and a hindsight expectation do not,
  because the observable fact of the table is a Prediction that came true in the data.
- A concept already at Evaluate or above is left alone (the rule refuses it; the result says `skipped`).
- The proposed check date is two years after the decision (placeholder, tuned on Julian's trial); the Coach may ask
  for another horizon, the five-year cap holds for every date.
"""

from __future__ import annotations

import json
import operator
import re
from collections.abc import Collection, Iterable, Sequence
from pathlib import Path
from typing import Any

from admiralty.academy import drill
from admiralty.debrief.frame import DAYS_PER_YEAR, date_of, day_number
from admiralty.graph.metrics import dig
from admiralty.player import mastery, store
from admiralty.player.mastery import Refused
from admiralty.workspace.layout import PREDICTIONS_DIR

KINDS = {
    "war": "declare a war",
    "ascension_perk": "take an Ascension Perk",
    "tradition_tree": "adopt a Tradition tree",
    "megastructure": "build a megastructure",
    "federation": "found or join a federation",
    "world_designation": "redesignate a world",
}
NOT_DETECTABLE = ("megastructure", "federation")
STATES = ("open", "confirmed", "refuted", "unclear")
VERDICTS = ("confirmed", "refuted", "unclear")
BASES = ("foretold", "hindsight")
MAX_YEARS = 5
DEFAULT_YEARS = 2
OPERATORS = {
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
    "==": operator.eq,
    "!=": operator.ne,
}
_FILE = re.compile(r"p(\d{3,})\.json")


class PredictionError(ValueError):
    """A Prediction that does not exist, or one that is not in a state for this call."""


def predictions_dir(workspace: Path) -> Path:
    return Path(workspace) / PREDICTIONS_DIR


# --- detection ----------------------------------------------------------------------------


def detect_before(
    extract: dict[str, Any], existing: Iterable[dict[str, Any]] = ()
) -> list[dict[str, Any]]:
    """Decisions this one Snapshot announces: candidates for a foretold Prediction.

    A kind that already has an open foretold Prediction is not offered again.
    """
    taken = _open_foretold_kinds(existing)
    found: list[dict[str, Any]] = []
    tree = dig(extract, "progression.tradition_tree_slots.free")
    next_tradition = dig(extract, "progression.next_tradition") or {}
    if (
        isinstance(tree, int)
        and tree > 0
        and next_tradition.get("affordable") is True
        and "tradition_tree" not in taken
    ):
        found.append(
            _candidate(
                "tradition_tree",
                None,
                "before",
                {
                    "cost": next_tradition.get("cost"),
                    "unity_stockpile": next_tradition.get("unity_stockpile"),
                    "free_tree_slots": tree,
                },
            )
        )
    perks = dig(extract, "progression.ascension_slots.free")
    if isinstance(perks, int) and perks > 0 and "ascension_perk" not in taken:
        found.append(_candidate("ascension_perk", None, "before", {"free_slots": perks}))
    return found


def detect_after(
    old: dict[str, Any], new: dict[str, Any], existing: Iterable[dict[str, Any]] = ()
) -> dict[str, Any]:
    """Decisions the comparison of two Snapshots shows.

    `hindsight` are candidates for a hindsight expectation (already predicted decisions left out, as are
    decisions with a stored Prediction of the same kind and subject), `matches` pair a decision with the open
    foretold Prediction of its kind, `not_detectable` names the kinds the extract cannot show.
    """
    existing = list(existing)
    seen = [
        c
        for c in (*_trees(old, new), *_perks(old, new), *_wars(old, new), *_designations(old, new))
    ]
    waiting = {p["kind"]: p for p in existing if _is_open_foretold(p)}
    stored = {(p["kind"], p.get("subject")) for p in existing}
    matches, hindsight = [], []
    for candidate in seen:
        if candidate["kind"] in waiting:
            matches.append({"prediction": waiting[candidate["kind"]]["id"], "decision": candidate})
        elif (candidate["kind"], candidate["subject"]) not in stored:
            hindsight.append(candidate)
    return {
        "hindsight": hindsight,
        "matches": matches,
        "not_detectable": list(NOT_DETECTABLE),
    }


def _candidate(kind: str, subject: str | None, phase: str, facts: dict[str, Any]) -> dict[str, Any]:
    return {"kind": kind, "subject": subject, "phase": phase, "facts": facts}


def _trees(old: dict[str, Any], new: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        _candidate("tradition_tree", name, "after", {})
        for name in _added(old, new, "progression.tradition_trees")
    ]


def _perks(old: dict[str, Any], new: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        _candidate("ascension_perk", name, "after", {})
        for name in _added(old, new, "progression.ascension_perks")
    ]


def _wars(old: dict[str, Any], new: dict[str, Any]) -> list[dict[str, Any]]:
    before = {(w.get("name"), w.get("start_date")) for w in dig(old, "military.wars") or []}
    return [
        _candidate(
            "war",
            war.get("name"),
            "after",
            {"start_date": war.get("start_date"), "war_goal": war.get("our_war_goal")},
        )
        for war in dig(new, "military.wars") or []
        if war.get("side") == "attacker" and (war.get("name"), war.get("start_date")) not in before
    ]


def _designations(old: dict[str, Any], new: dict[str, Any]) -> list[dict[str, Any]]:
    before = {p.get("id"): p.get("designation") for p in old.get("planets") or []}
    return [
        _candidate(
            "world_designation",
            planet.get("name"),
            "after",
            {
                "from": before[planet["id"]],
                "to": planet.get("designation"),
                "system": planet.get("system"),
            },
        )
        for planet in new.get("planets") or []
        if planet.get("id") in before and before[planet["id"]] != planet.get("designation")
    ]


def _added(old: dict[str, Any], new: dict[str, Any], path: str) -> list[str]:
    before = set(dig(old, path) or [])
    return [name for name in dig(new, path) or [] if name not in before]


# --- the books ----------------------------------------------------------------------------


def propose_check_date(made: str, *, years: float = DEFAULT_YEARS) -> str:
    """The check date the Coach proposes: `years` after `made` (two by default), at most five."""
    if not 0 < years <= MAX_YEARS:
        raise Refused(f"a check date lies at most {MAX_YEARS} years ahead, not {years}")
    return date_of(day_number(made) + round(years * DAYS_PER_YEAR))


def add(
    workspace: Path,
    *,
    kind: str,
    sentence: str,
    made: str,
    check_date: str | None = None,
    basis: str = "foretold",
    subject: str | None = None,
    concepts: Collection[str] = (),
    known: Collection[str] | None = None,
    expect: dict[str, Any] | None = None,
    extract: dict[str, Any] | None = None,
    campaign: str | None = None,
) -> dict[str, Any]:
    """Store a Prediction: the Player's one sentence about a decision, made on the Snapshot of in-game date `made`.

    `check_date` defaults to the proposal (`propose_check_date`); a date after the decision's own date and within
    five years is required. `concepts` (Causes of the Mechanics Graph, checked against `known` when given) are what
    a confirmed Prediction lifts to Evaluate. `expect` makes the check measurable; with `extract` its path must
    have a value in that Snapshot. Raises `Refused` for anything outside the rules; nothing is written then.
    """
    if kind not in KINDS:
        raise Refused(f"unknown decision {kind!r}; the list is: {', '.join(KINDS)}")
    if basis not in BASES:
        raise Refused(f"unknown basis {basis!r}; known: {', '.join(BASES)}")
    if not isinstance(sentence, str) or not sentence.strip():
        raise Refused("a Prediction is one sentence")
    if sentence.strip().count("\n"):
        raise Refused("a Prediction is one sentence, not a text of several lines")
    check = check_date or propose_check_date(made)
    days = day_number(check) - day_number(made)
    if days <= 0:
        raise Refused(f"the check date {check} must lie after {made}")
    if days > MAX_YEARS * DAYS_PER_YEAR:
        raise Refused(f"the check date {check} lies more than {MAX_YEARS} years after {made}")
    chosen = list(dict.fromkeys(concepts))
    if known is not None:
        unknown = [c for c in chosen if c not in known]
        if unknown:
            raise Refused(f"unknown concept(s): {', '.join(unknown)}")
    if expect is not None:
        _check_expect(expect, extract)
    directory = predictions_dir(workspace)
    directory.mkdir(parents=True, exist_ok=True)
    with store.locked(directory):
        number = 1 + max(
            (int(m.group(1)) for m in map(_FILE.fullmatch, _names(directory)) if m), default=0
        )
        prediction = {
            "id": f"p{number:03d}",
            "kind": kind,
            "subject": subject,
            "sentence": sentence.strip(),
            "basis": basis,
            "made": made,
            "check_date": check,
            "state": "open",
            "concepts": chosen,
            "expect": expect,
            "campaign": campaign,
            "decided_by": None,
            "decided": None,
            "note": None,
        }
        store.write_atomic(directory / f"{prediction['id']}.json", prediction)
    return prediction


def load(workspace: Path, prediction_id: str) -> dict[str, Any]:
    try:
        found = json.loads(
            (predictions_dir(workspace) / f"{prediction_id}.json").read_text(encoding="utf-8")
        )
    except FileNotFoundError as error:
        raise PredictionError(f"no Prediction {prediction_id}") from error
    except ValueError as error:
        raise PredictionError(f"Prediction {prediction_id} is damaged: {error}") from error
    return found


def listing(workspace: Path, *, state: str | None = None) -> list[dict[str, Any]]:
    """Every Prediction, oldest first; `state` keeps one state only."""
    directory = predictions_dir(workspace)
    if not directory.is_dir():
        return []
    found = []
    for name in _names(directory):
        match = _FILE.fullmatch(name)
        if not match:
            continue
        try:
            found.append(load(workspace, name[: -len(".json")]))
        except PredictionError:
            continue
    return [p for p in found if state is None or p["state"] == state]


def decide(
    workspace: Path,
    prediction_id: str,
    verdict: str,
    *,
    date: str,
    note: str | None = None,
) -> dict[str, Any]:
    """The Player's verdict on an open Prediction (`confirmed`, `refuted`, `unclear`); it never lifts a level."""
    if verdict not in VERDICTS:
        raise Refused(f"unknown verdict {verdict!r}; known: {', '.join(VERDICTS)}")
    day_number(date)
    directory = predictions_dir(workspace)
    with store.locked(_existing(directory)):
        prediction = load(workspace, prediction_id)
        if prediction["state"] != "open":
            raise PredictionError(f"Prediction {prediction_id} is already {prediction['state']}")
        prediction = _settled(prediction, verdict, "player", date, note)
        store.write_atomic(directory / f"{prediction_id}.json", prediction)
    return prediction


def check_due(
    workspace: Path,
    snapshots: Sequence[tuple[str, dict[str, Any]]],
    *,
    campaign: str | None = None,
) -> dict[str, Any]:
    """Check every open foretold Prediction whose date has come against the Snapshot of its check date.

    `snapshots` are `(in-game date, extract)` pairs, any order. Returns `decided` (state set from the data, with the
    Evaluate effects), `needs_verdict` (due, no measurable `expect`: the Player judges), `waiting` (no Snapshot at
    or after the check date yet) and `hindsight` (open hindsight expectations, never checked toward Evaluate).
    """
    ordered = sorted(snapshots, key=lambda item: day_number(item[0]))
    result: dict[str, Any] = {"decided": [], "needs_verdict": [], "waiting": [], "hindsight": []}
    directory = predictions_dir(workspace)
    if not directory.is_dir():
        return result
    with store.locked(directory):
        for prediction in listing(workspace, state="open"):
            if prediction["basis"] != "foretold":
                result["hindsight"].append(prediction["id"])
                continue
            due = next(
                (
                    item
                    for item in ordered
                    if day_number(item[0]) >= day_number(prediction["check_date"])
                ),
                None,
            )
            if due is None:
                result["waiting"].append(prediction["id"])
            elif prediction["expect"] is None:
                result["needs_verdict"].append(
                    {"id": prediction["id"], "sentence": prediction["sentence"], "snapshot": due[0]}
                )
            else:
                result["decided"].append(
                    _decide_from(workspace, directory, prediction, due, campaign)
                )
    return result


def _decide_from(
    workspace: Path,
    directory: Path,
    prediction: dict[str, Any],
    snapshot: tuple[str, dict[str, Any]],
    campaign: str | None,
) -> dict[str, Any]:
    date, extract = snapshot
    expect = prediction["expect"]
    value = dig(extract, expect["path"])
    if not isinstance(value, int | float) or isinstance(value, bool):
        verdict, note = "unclear", f"{expect['path']} has no value in the Snapshot of {date}"
    else:
        holds = OPERATORS[expect["op"]](value, expect["value"])
        verdict = "confirmed" if holds else "refuted"
        note = f"{expect['path']} was {value} on {date}, expected {expect['op']} {expect['value']}"
    settled = _settled(prediction, verdict, "snapshot", date, note)
    store.write_atomic(directory / f"{prediction['id']}.json", settled)
    effects = _evaluate(workspace, settled, campaign) if verdict == "confirmed" else []
    return {"id": settled["id"], "state": verdict, "note": note, "effects": effects}


def _evaluate(
    workspace: Path, prediction: dict[str, Any], campaign: str | None
) -> list[dict[str, Any]]:
    """Feed a confirmed foretold Prediction to the Evaluate rule, one concept at a time."""
    effects: list[dict[str, Any]] = []
    event = {"type": "evaluate", "basis": "prediction", "detail": prediction["sentence"]}
    for concept in prediction["concepts"]:
        try:
            recorded = mastery.record(
                concept,
                event,
                campaign=campaign or prediction.get("campaign"),
                date=prediction["decided"],
            )
        except Refused as refusal:
            effects.append({"effect": "skipped", "concept": concept, "reason": str(refusal)})
            continue
        academy = drill.academy_dir(workspace)
        academy.mkdir(parents=True, exist_ok=True)
        drill.copy_events(academy, recorded["events"])
        effects += [{**e, "concept": concept} for e in recorded["effects"]]
    return effects


def _settled(
    prediction: dict[str, Any], verdict: str, by: str, date: str, note: str | None
) -> dict[str, Any]:
    return {**prediction, "state": verdict, "decided_by": by, "decided": date, "note": note}


def _check_expect(expect: dict[str, Any], extract: dict[str, Any] | None) -> None:
    if not isinstance(expect, dict) or set(expect) != {"path", "op", "value"}:
        raise Refused("`expect` is {path, op, value}")
    if expect["op"] not in OPERATORS:
        raise Refused(f"unknown operator {expect['op']!r}; known: {', '.join(OPERATORS)}")
    value = expect["value"]
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise Refused("`expect.value` is a number")
    if extract is not None:
        found = dig(extract, expect["path"])
        if not isinstance(found, int | float) or isinstance(found, bool):
            raise Refused(f"`expect.path` {expect['path']!r} has no number in the Snapshot")


def _is_open_foretold(prediction: dict[str, Any]) -> bool:
    return prediction.get("state") == "open" and prediction.get("basis") == "foretold"


def _open_foretold_kinds(existing: Iterable[dict[str, Any]]) -> set[str]:
    return {p["kind"] for p in existing if _is_open_foretold(p)}


def _names(directory: Path) -> list[str]:
    names = [p.name for p in directory.iterdir() if _FILE.fullmatch(p.name)]
    return sorted(names, key=lambda name: int(_FILE.fullmatch(name).group(1)))  # type: ignore[union-attr]


def _existing(directory: Path) -> Path:
    if not directory.is_dir():
        raise PredictionError("no Predictions yet")
    return directory
