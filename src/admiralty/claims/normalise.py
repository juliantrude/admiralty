"""Normalisation for the Unverified Claim check (M7, `docs/plans/M7.md`).

Pure functions, no I/O. A number as the answer writes it becomes one or two `Reading`s: the value
and the stated precision (`step`, the unit of the last written digit: 0.01 for `2794.45`, 1 for
`2794`, 100 for `7.4k`). A claim matches a data value when the value rounds to the claim at that
precision (`Reading.covers`). The token is read on its own, with no guess about the language of the
sentence around it (the answer may mix both separator styles):

- one separator, exactly three digits after it, a group of one to three digits before that does not
  start with `0`: thousands (`2,794` is 2794) *and* decimal (`2.794`), both readings kept, because
  `2.794` is as likely a decimal as a thousands group and a false block is the worse error;
- one separator otherwise: the decimal mark;
- two kinds of separator: the one that appears last is the decimal mark, the other groups thousands;
- the same separator several times: thousands (`1.234.567`), else the token is not one number
  (`1,2,3` is three numbers; `4.5.2` is a version and no number at all).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal

_MAGNITUDE = {"k": Decimal(1000), "K": Decimal(1000), "M": Decimal(1_000_000)}
_HALF = Decimal("0.5")
_DIGITS = re.compile(r"\d+")


@dataclass(frozen=True)
class Reading:
    """One reading of a written number: its value and the step of its last written digit."""

    value: Decimal
    step: Decimal

    @property
    def low(self) -> Decimal:
        """Smallest data value that rounds to this reading (inclusive)."""
        return self.value - self.step * _HALF

    @property
    def high(self) -> Decimal:
        """Smallest data value above it that no longer does (exclusive)."""
        return self.value + self.step * _HALF

    def covers(self, data: int | float | Decimal) -> bool:
        """True when `data` rounds (half up) to this reading at its stated precision."""
        number = to_decimal(data)
        return number is not None and self.low <= number < self.high

    def scaled(self, factor: Decimal) -> Reading:
        return Reading(self.value * factor, self.step * factor)


def to_decimal(value: int | float | Decimal) -> Decimal | None:
    """A data value as Decimal; None for booleans, NaN and infinities."""
    if isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        number = value
    elif isinstance(value, int):
        number = Decimal(value)
    else:
        number = Decimal(repr(float(value)))
    return number if number.is_finite() else None


def _reading(text: str) -> Reading:
    """`text` is digits with at most one `.`: its value and one step of its last digit."""
    decimals = len(text.split(".")[1]) if "." in text else 0
    return Reading(Decimal(text), Decimal(1).scaleb(-decimals))


def _is_thousands(token: str, separator: str) -> bool:
    groups = token.split(separator)
    head, rest = groups[0], groups[1:]
    return 1 <= len(head) <= 3 and head[0] != "0" and all(len(group) == 3 for group in rest)


def _readings(token: str) -> tuple[Reading, ...] | None:
    """Readings of a token of digits, `.` and `,` that is one number; None when it is not."""
    kinds = {char for char in token if char in ".,"}
    if not kinds:
        return (_reading(token),)
    if len(kinds) == 1:
        separator = next(iter(kinds))
        if token.count(separator) == 1:
            head, tail = token.split(separator)
            decimal = _reading(f"{head}.{tail}")
            if len(tail) == 3 and _is_thousands(token, separator):
                return (_reading(head + tail), decimal)
            return (decimal,)
        return (
            (_reading(token.replace(separator, "")),) if _is_thousands(token, separator) else None
        )
    last = max(token.rfind("."), token.rfind(","))
    mark, other = token[last], "," if token[last] == "." else "."
    head, tail = token[:last], token[last + 1 :]
    if mark in head or not _is_thousands(head, other):
        return None
    return (_reading(f"{head.replace(other, '')}.{tail}"),)


def read_tokens(token: str) -> list[tuple[int, int, tuple[Reading, ...]]]:
    """The numbers in one token of digits and separators, as (start, end, readings) in the token.

    One number gives one entry; a token that is several numbers written with separators
    (`1,2,3`) gives one entry per digit run; a version or date shaped token (`4.5.2`) gives none.
    """
    readings = _readings(token)
    if readings is not None:
        return [(0, len(token), readings)]
    if set(token) - set("0123456789") == {"."} and token.count(".") >= 2:
        return []
    return [(m.start(), m.end(), (_reading(m.group()),)) for m in _DIGITS.finditer(token)]


def apply_suffix(readings: tuple[Reading, ...], suffix: str) -> tuple[Reading, ...]:
    """`7.4` with suffix `k` is 7400 at a step of 100; `M` is millions. Other suffixes change nothing."""
    factor = _MAGNITUDE.get(suffix)
    return tuple(r.scaled(factor) for r in readings) if factor else readings


_QUOTE_CHARS = '"„“”«»'


def normalise_name(text: str) -> str:
    """Case-folded name without markup, outer quotes and a trailing colon, spaces collapsed."""
    text = unicodedata.normalize("NFKC", text).replace("`", "").replace("*", "")
    text = " ".join(text.split()).strip(_QUOTE_CHARS + " ")
    return text.removesuffix(":").strip().casefold()


def name_forms(text: str) -> frozenset[str]:
    """The strings a name may match: itself, and with a singular/plural `s` toggled."""
    name = normalise_name(text)
    forms = {name, name + "s"}
    if len(name) > 3 and name.endswith("s"):
        forms.add(name[:-1])
    return frozenset(forms)
