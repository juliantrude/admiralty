"""The Hint Ladder: how much help the Coach may give next (M9, `docs/plans/M9.md`; grilling topic 1, R1 Q3, R4 Q4).

Four levels: 1 question, 2 hint, 3 partial answer, 4 full explanation. The Ladder follows the Player's answer in
the conversation, apart from the Mastery Level (`player/mastery.py`):

- the Player named the cause or the remedy (`cause`, `remedy`, a `support` answer the Snapshot backs): back to 1;
- a miss or a partial answer: one level up, two in a Crisis, never past 4;
- a `support` answer the Snapshot does not back: the Coach asks where the Player sees it, the level stays;
- the Escape Hatch: straight to 4.

`full_explanation` reports that the Coach gave the explanation; it is allowed only on level 4, so the answer stays
hidden until the Ladder has reached it. A pure module: the Drill (`academy/drill.py`) keeps the state.
"""

from __future__ import annotations

from typing import Any

from admiralty.player.mastery import OUTCOMES, Refused

QUESTION, HINT, PARTIAL_ANSWER, FULL_EXPLANATION = 1, 2, 3, 4
TOP = FULL_EXPLANATION
NAMES = {
    QUESTION: "question",
    HINT: "hint",
    PARTIAL_ANSWER: "partial answer",
    FULL_EXPLANATION: "full explanation",
}
NAMED = ("cause", "remedy")  # what a Drill topic wants the Player to name, in this order


def climb(level: int, *, crisis: bool = False) -> int:
    """One level up after a failed attempt, two in a Crisis, capped at the top."""
    return min(TOP, level + (2 if crisis else 1))


def move(
    level: int, outcome: str, *, crisis: bool = False, supported: bool | None = None
) -> dict[str, Any]:
    """The Ladder after one attempt at `level`.

    Returns `{"level", "named", "explained", "ask_where"}`: the new level, what the Player named (`cause`,
    `remedy`, or None), whether the Coach gave the full explanation (the topic is over) and whether the Coach
    asks where the Player sees the answer. Raises `Refused` for an outcome the Ladder does not allow.
    """
    if outcome not in OUTCOMES:
        raise Refused(f"unknown outcome {outcome!r}; known: {', '.join(OUTCOMES)}")
    if not QUESTION <= level <= TOP:
        raise Refused(f"the Hint Ladder level must be 1 to {TOP}, got {level!r}")
    result: dict[str, Any] = {
        "level": level,
        "named": None,
        "explained": False,
        "ask_where": False,
    }
    if outcome in NAMED:
        return {**result, "level": QUESTION, "named": outcome}
    if outcome == "support":
        if not isinstance(supported, bool):
            raise Refused(
                "a `support` answer needs the tool's check against the Snapshot (`supported`)"
            )
        if supported:
            return {**result, "level": QUESTION, "named": "cause"}
        return {**result, "ask_where": True}
    if outcome in ("miss", "partial"):
        return {**result, "level": climb(level, crisis=crisis)}
    if outcome == "full_explanation":
        if level != FULL_EXPLANATION:
            raise Refused(
                f"the full explanation comes on Ladder level {FULL_EXPLANATION}; this topic is on "
                f"{level} ({NAMES[level]})"
            )
        return {**result, "explained": True}
    return {**result, "level": TOP}  # escape_hatch
