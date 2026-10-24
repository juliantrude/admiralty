"""The Unverified Claim check (M7, `docs/plans/M7.md`): every claim of an answer against the
evidence of `claims/evidence.py`. A plain rule set, no model, no network: the same answer and the
same evidence give the same verdict.

- A **number** is backed when some data value rounds to it at its own stated precision (an
  ambiguous `2.794` is backed by either reading; `15%` by 15 or 0.15; the sign is ignored).
- A number that is part of a marked name (`**Hangar 3**`) is backed with the name; if the name is
  not found, the name is the finding and the number is not reported a second time.
- A number in a **quoted Playbook Rule** (blockquote) is exempt when the results hold rule texts.
- A number is **derived** and backed when it is the sum or difference of 2 to 4 other numbers of
  the same unit (list item, table row, paragraph) that are backed themselves, or, as a percentage,
  the quotient of two of them, compared with interval arithmetic over the rounding of every operand.
  So the model may compute, but must show its addends. Products and other formulas are not allowed.
- A **date** is backed when the exact string occurs in the evidence; a **name** when it matches a
  string of the evidence (case-folded, singular/plural `s`, as a whole word).

Reason codes of an Unverified Claim: `no_match`; `near_match` (a data value within 10 % exists, so
the model probably rounded or misread it); `derived_unexplained` (the unit shows two or more backed
numbers, yet none of the sums, differences or ratios gives this total); `name_no_match`.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from itertools import combinations, product
from typing import Any

from hlidskjalf.claims.evidence import Evidence
from hlidskjalf.claims.extract import Claim, extract_claims
from hlidskjalf.claims.normalise import Reading

_MAX_OPERANDS = 8
_ADDENDS = (2, 3, 4)


@dataclass(frozen=True)
class Unverified:
    claim: Claim
    code: str  # no_match | near_match | derived_unexplained | name_no_match
    nearest: Decimal | None = None
    nearest_source: str | None = None

    def to_dict(self) -> dict[str, Any]:
        claim = self.claim
        return {
            "kind": claim.kind,
            "text": claim.text,
            "code": self.code,
            "sentence": claim.sentence,
            "line": claim.line,
            "values": [str(r.value) for r in claim.readings],
            "precision": [str(r.step) for r in claim.readings],
            "nearest": None if self.nearest is None else str(self.nearest),
            "nearest_source": self.nearest_source,
        }


@dataclass(frozen=True)
class Verdict:
    claims: int  # claims looked at, exempt ones included
    unverified: tuple[Unverified, ...]

    @property
    def ok(self) -> bool:
        return not self.unverified

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "claims": self.claims,
            "unverified": [u.to_dict() for u in self.unverified],
        }


def check_answer(answer: str, evidence: Evidence) -> Verdict:
    claims = extract_claims(answer)
    name_found = {c.key: evidence.has_name(c.key) for c in claims if c.kind == "name"}
    backed: dict[int, Reading] = {}  # number claims found in the data, by index, with the reading
    for index, claim in enumerate(claims):
        if claim.kind == "number" and claim.within_name is None:
            reading = _find(claim, evidence)
            if reading is not None:
                backed[index] = reading

    findings: list[Unverified] = []
    for index, claim in enumerate(claims):
        if claim.kind == "name":
            if not name_found[claim.key]:
                findings.append(Unverified(claim, "name_no_match"))
        elif claim.kind == "date":
            if claim.key not in evidence.dates and not claim.quoted:
                findings.append(Unverified(claim, "no_match"))
        elif claim.within_name is not None or index in backed:
            continue  # a number in a marked name stands or falls with the name
        elif claim.quoted and evidence.rules:
            continue
        else:
            finding = _number_finding(index, claims, backed, evidence)
            if finding is not None:
                findings.append(finding)
    return Verdict(len(claims), tuple(findings))


def _find(claim: Claim, evidence: Evidence) -> Reading | None:
    for reading in claim.readings:
        if evidence.find(reading, percent=claim.percent) is not None:
            return reading
    return None


def _number_finding(
    index: int, claims: list[Claim], backed: dict[int, Reading], evidence: Evidence
) -> Unverified | None:
    claim = claims[index]
    operands = [
        reading
        for other, reading in backed.items()
        if claims[other].unit == claim.unit and not claims[other].quoted
    ][:_MAX_OPERANDS]
    if any(_derived(reading, operands, claim.percent) for reading in claim.readings):
        return None
    best = None
    for reading in claim.readings:
        near = evidence.nearest(reading, percent=claim.percent)
        if near is not None and (best is None or near.value < best.value):
            best = near
    if len(operands) >= 2:
        return Unverified(claim, "derived_unexplained", best and best.value, best and best.source)
    if best is not None:
        return Unverified(claim, "near_match", best.value, best.source)
    return Unverified(claim, "no_match")


def _derived(total: Reading, operands: list[Reading], percent: bool) -> bool:
    """True when `total` is a sum or difference of 2 to 4 operands, or (percent) a quotient of two."""
    for size in _ADDENDS:
        for chosen in combinations(operands, size):
            for signs in product((1, -1), repeat=size):
                low = sum((r.low if s > 0 else -r.high) for r, s in zip(chosen, signs, strict=True))
                high = sum(
                    (r.high if s > 0 else -r.low) for r, s in zip(chosen, signs, strict=True)
                )
                if low < total.high and high > total.low:
                    return True
    if percent:
        for top, bottom in product(operands, repeat=2):
            if top is not bottom and bottom.low > 0:
                low = top.low / bottom.high * 100
                high = top.high / bottom.low * 100
                if low < total.high and high > total.low:
                    return True
    return False
