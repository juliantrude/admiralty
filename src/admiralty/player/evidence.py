"""What the Snapshots say about a concept: the rows of the Mastery table that mastery.py leaves out (M9, 20c).

`player/mastery.py` decides from what the Player said. This module decides from what the saves show:

    Apply    a Snapshot shows `applied_when` of a Remedy of the Cause, within five in-game years after
             the Coach raised the topic, and the Remedy was not already shown in the Snapshot the topic
             was raised on. No Snapshot shows it within the five years: no level change, and the effect
             `ask_once` tells the Coach to ask once what held the Player back.
    Create   a Remedy of the Cause was applied twice without prompting (a transition from not shown to
             shown between two Snapshots, no Drill topic on the Cause in the five years before it) and the
             Cause is not present in any Snapshot of the five years after the second one.
    Drop     the Cause is present (`present_when`) in two Snapshots at least 360 days apart, both after the
             last level change and neither in a Crisis: one level down, announced.

A Remedy is "shown" only where the pack says how (`applied_when`), a Cause "appears" only where it says
so (`present_when`); a Remedy or Cause without the field cannot lift or drop a concept, the Coach asks the
Player instead. Nothing is guessed. `expand_graph` was not used for the presence: it evaluates the same
comparisons through `graph.metrics.evaluate`, which is what this module calls, so the numbers agree.

Choices where the table is silent, each pinned by a test:
- Apply and `ask_once` need the Snapshot the topic was raised on (the newest one at or before `raised`);
  without it nothing is decided.
- Create needs the concept at Apply or higher; "applied twice" counts transitions, so a Remedy that
  stays on counts once.
- Drop never goes below New, and a Cause without `present_when` is never "present". Snapshots that
  are not after the last level change do not count, so one persistent Cause costs one level per year of
  fresh evidence, not one per call.
- A Crisis is a Snapshot where a resource with a stockpile has a negative net and the stockpile lasts
  under twelve months (the `reserve_months` of Debrief's `net_negative`, stockpile divided by the
  negative net). Admiralty's own rule, not a game value; the threshold is a placeholder tuned on the live
  trial (M9 decision 4). Energy, minerals, food, alloys and influence count; unity, trade and the research
  resources do not run out in a way that hurts.

Dates are Stellaris days: 12 months of 30 days, a year is 360 days (`debrief.frame.day_number`).
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from admiralty.debrief.frame import DAYS_PER_YEAR, day_number
from admiralty.graph.mechanics import MechanicsGraph
from admiralty.graph.metrics import dig, evaluate
from admiralty.player import store
from admiralty.player.store import LEVELS

WINDOW_YEARS = 5
DROP_DAYS = DAYS_PER_YEAR
CRISIS_MONTHS = 12
CRISIS_RESOURCES = ("energy", "minerals", "food", "alloys", "influence")

Snapshots = Sequence[tuple[str, dict[str, Any]]]  # (in-game date, extract), any order
Effect = dict[str, Any]


def crisis(extract: dict[str, Any]) -> dict[str, Any]:
    """`{"crisis": bool, "resources": [...]}`: every resource whose stockpile lasts under twelve months at its negative net."""
    found = []
    for name in CRISIS_RESOURCES:
        net, stock = (
            dig(extract, f"resources.{name}.net"),
            dig(extract, f"resources.{name}.stockpile"),
        )
        if not _number(net) or not _number(stock) or net >= 0:
            continue
        months = round(max(stock, 0) / -net, 1)
        if months < CRISIS_MONTHS:
            found.append(
                {"resource": name, "net": net, "stockpile": stock, "reserve_months": months}
            )
    return {"crisis": bool(found), "resources": found}


def remedies_shown(graph: MechanicsGraph, concept: str, extract: dict[str, Any]) -> list[str]:
    """The Remedies of the Cause whose `applied_when` holds in this Snapshot, in graph order."""
    shown = []
    for remedy in graph.node(concept).get("remedies", []):
        comparison = graph.node(remedy).get("applied_when")
        if comparison and evaluate(comparison, graph.metrics, extract).state == "present":
            shown.append(remedy)
    return shown


def cause_presence(graph: MechanicsGraph, concept: str, extract: dict[str, Any]) -> str:
    """`present`, `clear`, `unknown` (a metric has no value) or `unmeasured` (the pack gives no `present_when`)."""
    comparison = graph.node(concept).get("present_when")
    if not comparison:
        return "unmeasured"
    return evaluate(comparison, graph.metrics, extract).state


def evaluate_snapshots(
    graph: MechanicsGraph,
    concept: str,
    state: dict[str, Any],
    snapshots: Snapshots,
    *,
    raised: str | None = None,
    prompts: Sequence[str] = (),
) -> list[Effect]:
    """The effects the Snapshots have on one concept, in the vocabulary of `mastery.apply`.

    `state` is the concept's entry of the Player Model (`store.state_of`), `raised` the in-game date
    the Coach last raised the topic, `prompts` every date it did (a Drill topic on the Cause).
    """
    ordered = sorted(snapshots, key=lambda item: day_number(item[0]))
    effects: list[Effect] = []
    state = dict(state)
    for step in (_apply, _create, _drop):
        found = step(graph, concept, state, ordered, raised, prompts)
        for effect in found:
            if effect["effect"] in ("level", "drop"):
                state = {
                    **state,
                    "level": effect["level"],
                    "last_change": {"date": effect["date"]},
                }
        effects += found
    return effects


def _apply(graph, concept, state, ordered, raised, prompts) -> list[Effect]:
    if state["level"] != "understand" or raised is None:
        return []
    baseline = _baseline(ordered, raised)
    if baseline is None or remedies_shown(graph, concept, ordered[baseline][1]):
        return []
    deadline = day_number(raised) + WINDOW_YEARS * DAYS_PER_YEAR
    for date, extract in ordered[baseline + 1 :]:
        if day_number(date) > deadline:
            break
        shown = remedies_shown(graph, concept, extract)
        if shown:
            reason = (
                f"Snapshot {date} shows {', '.join(shown)} done, "
                f"within {WINDOW_YEARS} years after the Coach raised it on {raised}"
            )
            return [_level("understand", "apply", reason, date)]
    if day_number(ordered[-1][0]) > deadline:
        reason = f"no Snapshot within {WINDOW_YEARS} years after {raised} shows a Remedy done"
        return [{"effect": "ask_once", "raised": raised, "reason": reason}]
    return []


def _create(graph, concept, state, ordered, raised, prompts) -> list[Effect]:
    if _rank(state["level"]) < _rank("apply") or _rank(state["level"]) >= _rank("create"):
        return []
    if not graph.node(concept).get("present_when"):
        return []
    window = WINDOW_YEARS * DAYS_PER_YEAR
    prompted = sorted(day_number(p) for p in prompts)
    unprompted = []
    for (_, before), (date, after) in zip(ordered, ordered[1:], strict=False):
        done = set(remedies_shown(graph, concept, after)) - set(
            remedies_shown(graph, concept, before)
        )
        day = day_number(date)
        if done and not any(p <= day <= p + window for p in prompted):
            unprompted += [(day, date, remedy) for remedy in sorted(done)]
    if len(unprompted) < 2:
        return []
    day, date, _ = unprompted[1]
    if day_number(ordered[-1][0]) < day + window:
        return []
    for later_date, extract in ordered:
        if day < day_number(later_date) <= day + window and (
            cause_presence(graph, concept, extract) == "present"
        ):
            return []
    named = ", ".join(sorted({remedy for _, _, remedy in unprompted[:2]}))
    reason = (
        f"{named} applied twice without prompting (second time {date}), "
        f"and the Cause stayed away for {WINDOW_YEARS} years"
    )
    return [_level(state["level"], "create", reason, ordered[-1][0])]


def _drop(graph, concept, state, ordered, raised, prompts) -> list[Effect]:
    level = state["level"]
    if level == store.NEW or not graph.node(concept).get("present_when"):
        return []
    since = (state.get("last_change") or {}).get("date")
    floor = day_number(since) if since else -1
    seen = [
        (day_number(date), date)
        for date, extract in ordered
        if day_number(date) > floor
        and cause_presence(graph, concept, extract) == "present"
        and not crisis(extract)["crisis"]
    ]
    if not seen or seen[-1][0] - seen[0][0] < DROP_DAYS:
        return []
    first, last = seen[0][1], seen[-1][1]
    target = LEVELS[_rank(level) - 1]
    reason = f"the Cause is present in the Snapshots {first} and {last}, a year or more apart, outside a Crisis"
    return [{**_level(level, target, reason, last), "effect": "drop", "announce": True}]


def record_evidence(
    graph: MechanicsGraph,
    concept: str,
    snapshots: Snapshots,
    *,
    raised: str | None = None,
    prompts: Sequence[str] = (),
    campaign: str | None = None,
    base: Path | None = None,
) -> dict[str, Any]:
    """Decide from the Snapshots and write what follows through the store; running it twice on the same
    Snapshots writes nothing the second time. Returns `{"state", "effects", "events"}` like `mastery.record`."""
    state = store.state_of(store.read_model(base), concept)
    effects = evaluate_snapshots(graph, concept, state, snapshots, raised=raised, prompts=prompts)
    written: list[dict[str, Any]] = []
    context = {"concept": concept, "campaign": campaign, "base": base}
    for effect in effects:
        if effect["effect"] in ("level", "drop"):
            written.append(
                store.append(
                    "drop" if effect["effect"] == "drop" else "level",
                    level=effect["level"],
                    previous=effect["previous"],
                    reason=effect["reason"],
                    date=effect["date"],
                    **context,
                )
            )
        elif effect["effect"] == "ask_once" and not _asked(concept, effect["raised"], base):
            written.append(
                store.append(
                    "note",
                    ask_once=True,
                    raised=effect["raised"],
                    reason=effect["reason"],
                    date=_newest(snapshots),
                    **context,
                )
            )
    return {
        "state": store.state_of(store.read_model(base), concept),
        "effects": effects,
        "events": written,
    }


def coverage(graph: MechanicsGraph) -> dict[str, Any]:
    """How much of the pack the Snapshots can see: Remedies with `applied_when`, Causes with `present_when`
    and, per Cause, whether Apply is reachable at all."""
    remedies = [n for n in graph.nodes.values() if n["type"] == "remedy"]
    causes = [n for n in graph.nodes.values() if n["type"] == "cause"]
    applied = sorted(n["id"] for n in remedies if "applied_when" in n)
    present = sorted(n["id"] for n in causes if "present_when" in n)
    reachable = sorted(
        c["id"]
        for c in causes
        if any("applied_when" in graph.node(r) for r in c.get("remedies", []))
    )
    return {
        "remedies": len(remedies),
        "applied_when": applied,
        "causes": len(causes),
        "present_when": present,
        "causes_with_apply": reachable,
    }


def _newest(snapshots: Snapshots) -> str | None:
    return max((date for date, _ in snapshots), key=day_number, default=None)


def _asked(concept: str, raised: str, base: Path | None) -> bool:
    return any(
        e.get("kind") == "note"
        and e.get("concept") == concept
        and e.get("ask_once") is True
        and e.get("raised") == raised
        for e in store.events(base)
    )


def _baseline(ordered, raised: str) -> int | None:
    day = day_number(raised)
    before = [i for i, (date, _) in enumerate(ordered) if day_number(date) <= day]
    return before[-1] if before else None


def _level(previous: str, level: str, reason: str, date: str) -> Effect:
    return {"effect": "level", "previous": previous, "level": level, "reason": reason, "date": date}


def _rank(level: str) -> int:
    return LEVELS.index(level)


def _number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)
