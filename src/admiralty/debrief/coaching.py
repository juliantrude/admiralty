"""The `coaching` part of a retrospective (M9, `docs/plans/M9.md` 20j): what the Academy knows about the frame.

A Coaching Campaign's Debrief is a Rendezvous: the Player has made decisions, the Coach has made Predictions and
the Player Model has moved. This module only reads; nothing here writes a Prediction or a level.

    predictions   foretold Predictions that matter to the frame: made in it, due in it (check date between the first
                  and the last date), or decided in it. Each keeps its state (`open` with `due` true means the
                  check date has come and nobody decided yet), who decided (`snapshot` or `player`) and the note.
    hindsight     expectations given after the decision, labelled and `weight` "less": they were never foretold,
                  so they never count as a hit or a miss of the Player's judgement.
    player_model  the events of the Player Model dated inside the frame, for this Campaign (events without a
                  Campaign belong to none and stay out), with the title of the concept where the Mechanics Graph
                  has it. Level and drop events say where the concept moved; an Escape Hatch use says in which
                  Situation; notes are left out (candidate answers, patch resets: bookkeeping, not progress).

Choices where the plan is silent, each pinned by a test:
- A foretold Prediction whose check date lies after the frame is left out unless it was made in the frame: the
  Debrief looks back, a later check belongs to a later Debrief. The made-in-frame ones are listed with `due` false
  so the Player sees what is still open.
- The Player's own sentence is quoted as given; the module adds no figure.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from admiralty.academy import predictions
from admiralty.debrief.frame import Frame, day_number
from admiralty.graph.mechanics import MechanicsGraph
from admiralty.player import store

HINDSIGHT_WEIGHT = "less"
PROGRESS_KINDS = ("level", "drop", "hatch")


def coaching_material(
    workspace: Path, frame: Frame, campaign: str, graph: MechanicsGraph | None = None
) -> dict[str, Any]:
    """Predictions, hindsight expectations and Player Model changes of `frame` for `campaign`."""
    start, end = day_number(frame.start), day_number(frame.end)

    def inside(date: str | None) -> bool:
        return date is not None and start <= day_number(date) <= end

    foretold: list[dict[str, Any]] = []
    hindsight: list[dict[str, Any]] = []
    for prediction in predictions.listing(workspace):
        if prediction.get("campaign") not in (None, campaign):
            continue
        made_in, due_in = inside(prediction["made"]), inside(prediction["check_date"])
        decided_in = inside(prediction["decided"])
        if prediction["basis"] == "hindsight":
            if made_in or due_in or decided_in:
                hindsight.append({**_view(prediction), "weight": HINDSIGHT_WEIGHT})
            continue
        passed = day_number(prediction["check_date"]) <= end
        if made_in or decided_in or (passed and prediction["state"] == "open") or due_in:
            foretold.append({**_view(prediction), "due": passed})
    return {
        "predictions": foretold,
        "hindsight": hindsight,
        "player_model": _model_changes(inside, campaign, graph),
    }


def _view(prediction: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "id", "kind", "subject", "sentence", "basis", "made", "check_date", "state", "decided_by",
        "decided", "note", "concepts",
    )  # fmt: skip
    return {key: prediction[key] for key in keys}


def _model_changes(
    inside: Any, campaign: str, graph: MechanicsGraph | None
) -> list[dict[str, Any]]:
    changes = []
    for event in store.events():
        if event.get("kind") not in PROGRESS_KINDS or event.get("campaign") != campaign:
            continue
        if not inside(event.get("date")):
            continue
        concept = event["concept"]
        known = graph is not None and concept in graph.nodes
        change = {
            "seq": event["seq"],
            "date": event["date"],
            "kind": event["kind"],
            "concept": concept,
            "title": graph.node(concept)["title"] if known else None,
            "reason": event["reason"],
        }
        for key in ("level", "previous", "situation"):
            if key in event:
                change[key] = event[key]
        changes.append(change)
    return changes
