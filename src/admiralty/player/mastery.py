"""The fixed rules of the Mastery Levels (M9, `docs/plans/M9.md` "The fixed rules"; grilling topic 1).

`apply(state, event) -> (state, effects)` is pure: it knows the table and nothing else. `state` is one
concept's entry of the Player Model (`store.state_of`), an `event` is what the Coach reports, an effect
is what the caller has to do about it. `record` is the one place that reads the model, applies and writes
the result through `player/store.py`. The model reports the outcome of an attempt; it never sets a level.

Events (`type`):
    attempt   `outcome` (cause remedy support miss partial full_explanation escape_hatch), `ladder`
              (Hint Ladder level 1 question, 2 hint, 3 partial answer, 4 full explanation),
              `domain_named` (the Coach named the domain before the Player answered); `support` also
              `supported` (the tool's check of the answer against the Snapshot, decided by code) and
              `text`; `escape_hatch` also `situation`.
    evaluate  `basis` (choice: chose between Remedies, needs `detail` with the reasons; prediction: a
              Prediction on the concept came true, `detail` names it)
    patch     the concept's formula or links changed between two versions of the Mechanics Graph

Rows of the table that need a Snapshot (Apply, the five-year window, Create, the drop) are not here;
`player/evidence.py` decides those from two Snapshots (increment 20c).

Choices where the table is silent, each pinned by a test:
- `remedy` helps the Hint Ladder only; "found the cause" is the evidence of Understand, so no level moves.
- `partial`, `full_explanation` and `miss` change no level, also not downwards; only the Escape Hatch
  leaves a trace in the model (`hatch_uses`).
- Analyse needs the cause named on Ladder level 1 with the domain not named. Reached without Apply once
  before (`peak`), the same answer gives Understand.
- Evaluate may follow any lower level: the observable fact is the choice or the Prediction itself.
- Evaluate and Create concepts are skipped by the Drill, so an attempt on them is refused, except
  `escape_hatch` (always honoured). At Analyse only an answer to a question that did not name the domain
  is accepted.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from admiralty.graph.mechanics import MechanicsGraph
from admiralty.player import store
from admiralty.player.concepts import concepts
from admiralty.player.store import LEVELS

OUTCOMES = ("cause", "remedy", "support", "miss", "partial", "full_explanation", "escape_hatch")
LADDER = (1, 2, 3, 4)
EVALUATE_BASES = ("choice", "prediction")

State = dict[str, Any]
Effect = dict[str, Any]


class Refused(ValueError):
    """The state does not allow this event; nothing is written."""


def rank(level: str) -> int:
    return LEVELS.index(level)


def apply(state: State, event: dict[str, Any]) -> tuple[State, list[Effect]]:
    """One event on one concept: the new state and the effects, or `Refused`."""
    kind = event.get("type")
    if kind == "attempt":
        return _attempt(state, event)
    if kind == "evaluate":
        return _evaluate(state, event)
    if kind == "patch":
        return _patch(state, event)
    raise Refused(f"unknown event type {kind!r}; known: attempt, evaluate, patch")


def _attempt(state: State, event: dict[str, Any]) -> tuple[State, list[Effect]]:
    outcome, ladder = event.get("outcome"), event.get("ladder")
    if outcome not in OUTCOMES:
        raise Refused(f"unknown outcome {outcome!r}; known: {', '.join(OUTCOMES)}")
    if ladder not in LADDER:
        raise Refused(f"the Hint Ladder level must be one of {LADDER}, got {ladder!r}")
    level = state["level"]
    domain_named = bool(event.get("domain_named"))

    if outcome == "escape_hatch":
        situation = event.get("situation")
        if not isinstance(situation, str) or not situation.strip():
            raise Refused("an Escape Hatch needs the Situation it was pulled in")
        reason = f"Escape Hatch at Ladder level {ladder}: {situation.strip()}"
        new = {**state, "hatch_uses": state["hatch_uses"] + 1}
        return new, [{"effect": "hatch", "situation": situation.strip(), "reason": reason}]

    if rank(level) >= rank("evaluate"):
        raise Refused(f"the concept is at {level}; the Drill skips it, so no attempt is recorded")
    if level == "analyse" and domain_named:
        raise Refused("at Analyse only a question that does not name the domain is asked")

    effects: list[Effect] = []
    if outcome == "support":
        supported = event.get("supported")
        if not isinstance(supported, bool):
            raise Refused(
                "a `support` answer needs the tool's check against the Snapshot (`supported`)"
            )
        if not supported:
            return state, [
                {"effect": "ask_where", "reason": "answer not supported by the Snapshot"}
            ]
        text = str(event.get("text") or "").strip()
        effects.append(
            {"effect": "candidate", "text": text, "reason": "answer supported by the Snapshot"}
        )
        outcome = "cause"

    if outcome != "cause" or ladder > 2:
        return state, effects

    target = level
    if not domain_named and ladder == 1 and rank(level) < rank("analyse"):
        target = "analyse" if rank(state["peak"]) >= rank("apply") else "understand"
        why = "named the cause before the Coach named the domain"
    elif level == "new":
        target = "understand"
        why = f"named the cause on Ladder level {ladder}"
    if rank(target) > rank(level):
        effects.append(_level(level, target, why))
        state = {**state, "level": target, "peak": _peak(state, target)}
    return state, effects


def _evaluate(state: State, event: dict[str, Any]) -> tuple[State, list[Effect]]:
    basis, detail = event.get("basis"), str(event.get("detail") or "").strip()
    if basis not in EVALUATE_BASES:
        raise Refused(f"unknown basis {basis!r}; known: {', '.join(EVALUATE_BASES)}")
    if not detail:
        raise Refused("Evaluate needs the reasons of the choice or the Prediction that came true")
    level = state["level"]
    if rank(level) >= rank("evaluate"):
        raise Refused(f"the concept is already at {level}")
    why = (
        f"chose between Remedies with reasons: {detail}"
        if basis == "choice"
        else (f"a Prediction on the concept came true: {detail}")
    )
    new = {**state, "level": "evaluate", "peak": _peak(state, "evaluate")}
    return new, [_level(level, "evaluate", why)]


def _patch(state: State, event: dict[str, Any]) -> tuple[State, list[Effect]]:
    if not event.get("changed"):
        return state, []
    level = state["level"]
    if rank(level) <= rank("understand"):
        return state, []
    why = f"the formula or links changed between {event.get('from')} and {event.get('to')}"
    return {**state, "level": "understand"}, [
        {**_level(level, "understand", why), "announce": True}
    ]


def _level(previous: str, level: str, reason: str) -> Effect:
    return {"effect": "level", "previous": previous, "level": level, "reason": reason}


def _peak(state: State, level: str) -> str:
    return level if rank(level) > rank(state["peak"]) else state["peak"]


def changed_concepts(old: MechanicsGraph, new: MechanicsGraph) -> list[str]:
    """Concepts in both versions whose formula (`facts`) or links differ; a changed number, title or
    description leaves the signature as it was. A concept that is gone or new in `new` keeps its level."""
    before, after = concepts(old), concepts(new)
    return sorted(
        c for c in before.keys() & after.keys() if before[c].signature != after[c].signature
    )


def record(
    concept: str,
    event: dict[str, Any],
    *,
    campaign: str | None = None,
    date: str | None = None,
    base: Path | None = None,
) -> dict[str, Any]:
    """Apply an event to the stored concept and write what follows through the store.

    Returns `{"state", "effects", "events"}`; a refused event raises `Refused` and writes nothing.
    """
    state = store.state_of(store.read_model(base), concept)
    new, effects = apply(state, event)
    written: list[dict[str, Any]] = []
    context = {"concept": concept, "campaign": campaign, "date": date, "base": base}
    for effect in effects:
        if effect["effect"] == "level":
            written.append(
                store.append(
                    "level",
                    level=effect["level"],
                    previous=effect["previous"],
                    reason=effect["reason"],
                    **context,
                )
            )
        elif effect["effect"] == "hatch":
            written.append(
                store.append(
                    "hatch", situation=effect["situation"], reason=effect["reason"], **context
                )
            )
        elif effect["effect"] == "candidate":
            written.append(
                store.append(
                    "note", candidate=True, text=effect["text"], reason=effect["reason"], **context
                )
            )
    return {"state": new, "effects": effects, "events": written}


def record_patch(
    old: MechanicsGraph,
    new: MechanicsGraph,
    *,
    date: str | None = None,
    base: Path | None = None,
) -> dict[str, dict[str, Any]]:
    """The patch rule over the whole model: each concept the player has a level for, whose formula
    or links changed between the two versions, falls back to Understand. Returns the result of
    `record` per concept that moved."""
    model = store.read_model(base)
    event = {"type": "patch", "changed": True, "from": old.version, "to": new.version}
    moved: dict[str, dict[str, Any]] = {}
    for concept in changed_concepts(old, new):
        if concept not in model["concepts"]:
            continue
        result = record(concept, event, date=date, base=base)
        if result["events"]:
            moved[concept] = result
    return moved
