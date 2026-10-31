"""Finds the checkable claims in a final answer (M7, `docs/plans/M7.md`).

`extract_claims(answer)` returns every number, in-game date and marked name the answer states,
each with the sentence it stands in. It decides only *what is a claim*; whether a claim is backed
by the turn's tool results is `claims/check.py`.

Numbers: see `normalise.py` for the spelling rules. Not claims (never extracted): list numbering
and heading numbers, numbers in code spans (file names, ids, commands; a code span that is only a
number stays a claim), numbers in fenced code blocks, link targets and URLs, version numbers
(`4.5.2`), bare years 2200 to 2500, and digits glued to letters (`mk2`, `10th`, `2x`). In-game dates
(`2259.12.25`) are `date` claims, matched as a whole string.

Names: only spans the answer marks as a thing. `**bold**`, `` `code` ``, quoted text (`"..."`,
`„..."`, `“..."`, `«...»`) and the cells of a table column headed Name. Not extracted: bold that is a
whole line (headings, labels), a label ending in a colon (`**Gesperrt:**`), a bold figure
with its unit (`**-130.92 Energy Credits**`), a bold sentence (ends in `.`/`!`/`?` or has more than
six words), a single lowercase word, a quote longer than eight words (running prose), a code span
that is a command, path, file name or snake_case/kebab-case identifier. Capitalised words in running text are
never names: in German every noun is capitalised.

Claims carry what the check needs without re-reading the text: `unit` (list item, table row or
paragraph, the scope in which a derived sum must show its addends), `quoted` (a blockquote line,
where the consult skill quotes Playbook Rules) and `within_name` (a number that is part of a marked
name such as `**Hangar 3**`, allowed when the name itself matches).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from itertools import pairwise

from admiralty.claims.normalise import Reading, apply_suffix, normalise_name, read_tokens


@dataclass(frozen=True)
class Claim:
    kind: str  # "number" | "date" | "name"
    text: str  # as written (names: without markup)
    sentence: str
    line: int  # 1-based line of the answer
    unit: int  # list item, table row or paragraph, in answer order
    quoted: bool = False
    readings: tuple[Reading, ...] = ()  # numbers: unsigned, at the written precision
    percent: bool = False
    sign: str = ""  # "+", "-" or ""
    via: str = ""  # names: "bold" | "code" | "quote" | "table"
    key: str = ""  # names: normalised; dates: the date string
    within_name: str | None = None  # numbers: key of the marked name they are part of


_NUMBER = re.compile(
    r"(?<![\w.,])(?P<token>\d(?:[\d.,]*\d)?)(?:\s?(?P<suffix>%|[kKM](?!\w)))?(?!\w)"
)
_DATE = re.compile(r"(?<![\w.])\d{4}\.\d{1,2}\.\d{1,2}(?!\w)")
_SIGN_BEFORE = re.compile(r"(?:^|[\s(\[{/:;=~≈*\"„“«'])[+\-−–]$")
_LIST_NUMBER = re.compile(r"^\s*(?:[-*+•]\s+)?(\d{1,3}[.)])(?=\s)")
_HEADING_NUMBER = re.compile(r"^\s*#{1,6}\s+(\d{1,3}[.)]?)(?=\s)")
_LIST_START = re.compile(r"^\s*(?:[-*+•]|\d{1,3}[.)])\s+")
_BLOCKQUOTE = re.compile(r"^\s*(?:>\s?)+")
_HEADING = re.compile(r"^\s*#{1,6}\s+")
_FENCE = re.compile(r"^\s*(```|~~~)")
_CODE = re.compile(r"`([^`\n]+)`")
_LINK_TARGET = re.compile(r"\]\(([^)\s]*)\)|<https?://[^>\s]+>|https?://[^\s)>\]]+")
_BOLD_MARK = re.compile(r"\*\*")
_BOLD_UNDERSCORE = re.compile(r"__(?=\S)(.+?)(?<=\S)__")
_QUOTED = re.compile(r'"([^"\n]+?)"|„([^“”"\n]+?)[“”"]|“([^”\n]+?)”|«\s?([^»\n]+?)\s?»')
_PURE_NUMBER = re.compile(r"[+\-−–]?\d(?:[\d.,]*\d)?\s?(?:%|[kKM])?")
_LOWERCASE_WORD = re.compile(r"[a-zäöüß]+")
_WHOLE_LINE_BOLD = re.compile(r"(?:\*\*[^*]+\*\*|__[^_]+__)[:.]?")
_BULLET = re.compile(r"^\s*(?:[-*+•]|\d+[.)])\s+|^\s*#{1,6}\s+")
_QUANTITY = re.compile(r"[+\-−–]?\d[\d.,]*\s?(?:%|[kKM])?(?:\s.*)?")
_SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+(?=\S)")
_TABLE_SEPARATOR = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(?:\|\s*:?-{2,}:?\s*)*\|?\s*$")
_NAME_HEADERS = {"name", "names", "namen"}
_COMMANDS = {"uv", "admiralty", "git", "claude", "python", "pytest", "cd", "ls"}
_FILE_EXTENSION = re.compile(
    r"\.(?:yaml|yml|json|jsonl|md|py|html|js|css|log|sav|toml|txt|zst)$", re.IGNORECASE
)
_MAX_NAME_WORDS = 8
# Display Names in the reference data have at most 5 words; a longer bold span is a sentence.
_MAX_BOLD_NAME_WORDS = 6
# snake_case or kebab-case: lowercase words joined by _ or -, as tool and command names are.
_IDENTIFIER = re.compile(r"[a-z][a-z0-9]*(?:[_-][a-z0-9]+)+")
_YEARS = range(2200, 2501)


@dataclass(frozen=True)
class _Span:
    start: int
    end: int
    via: str
    text: str  # inner text without markup


def extract_claims(answer: str) -> list[Claim]:
    """Every number, in-game date and marked name the answer states, in answer order."""
    lines = answer.splitlines()
    units = _units(lines)
    tables = _tables(lines)
    claims: list[Claim] = []
    fenced = False
    for index, line in enumerate(lines):
        if _FENCE.match(line):
            fenced = not fenced
            continue
        if fenced or not line.strip():
            continue
        claims += _line_claims(
            line, index + 1, units[index], tables.get(index), quoted=bool(_BLOCKQUOTE.match(line))
        )
    return claims


def _units(lines: list[str]) -> list[int]:
    """Unit number per line: a list item, table row, heading or paragraph shares one number."""
    units: list[int] = []
    current = -1
    previous_quoted = False
    starts_new = True  # the previous line was blank, a heading or a table row
    for line in lines:
        blank = not line.strip()
        quoted = bool(_BLOCKQUOTE.match(line))
        row = line.strip().startswith("|") or bool(_HEADING.match(line))
        if blank or row or starts_new or quoted != previous_quoted or _LIST_START.match(line):
            current += 1
        units.append(current)
        previous_quoted = quoted
        starts_new = blank or row
    return units


def _split_cells(line: str) -> list[tuple[int, int]]:
    """(start, end) of each cell of a table row, the outer pipes dropped."""
    bounds = [m.start() for m in re.finditer(r"(?<!\\)\|", line)]
    if not bounds:
        return []
    edges = [-1, *bounds] if line.strip()[0] != "|" else bounds
    if line.rstrip()[-1] != "|":
        edges.append(len(line))
    return [(a + 1, b) for a, b in pairwise(edges)]


def _tables(lines: list[str]) -> dict[int, list[tuple[int, int]]]:
    """For each row (index) of a table with a Name column: the (start, end) of its name cell."""
    found: dict[int, list[tuple[int, int]]] = {}
    for index in range(len(lines) - 1):
        header, rule = lines[index], lines[index + 1]
        if "|" not in header or not _TABLE_SEPARATOR.match(rule) or "-" not in rule:
            continue
        columns = [
            column
            for column, (a, b) in enumerate(_split_cells(header))
            if normalise_name(header[a:b]) in _NAME_HEADERS
        ]
        if not columns:
            continue
        for row in range(index + 2, len(lines)):
            if "|" not in lines[row] or not lines[row].strip():
                break
            cells = _split_cells(lines[row])
            found[row] = [cells[column] for column in columns if column < len(cells)]
    return found


def _line_claims(
    line: str,
    number: int,
    unit: int,
    name_cells: list[tuple[int, int]] | None,
    *,
    quoted: bool,
) -> list[Claim]:
    prefix = _BLOCKQUOTE.match(line)
    body_start = prefix.end() if prefix else 0
    masked = list(line)

    def blank(start: int, end: int) -> None:
        masked[start:end] = " " * (end - start)

    blank(0, body_start)
    for pattern in (_LIST_NUMBER, _HEADING_NUMBER):
        found = pattern.match(line, body_start)
        if found:
            blank(*found.span(1))
    for found in _LINK_TARGET.finditer(line):
        blank(*found.span())

    spans = _spans(line, body_start, blank, name_cells)
    sentences = _sentence_bounds(line, body_start, name_cells)

    def sentence_at(position: int) -> str:
        for start, end in sentences:
            if start <= position < end:
                return " ".join(line[start:end].split())
        return " ".join(line[body_start:].split())

    names = [s for s in spans if _is_name(s, line, body_start)]
    claims: list[Claim] = []
    seen: set[str] = set()
    for span in names:
        key = normalise_name(span.text)
        if key not in seen:
            seen.add(key)
            claims.append(
                Claim(
                    "name",
                    span.text,
                    sentence_at(span.start),
                    number,
                    unit,
                    quoted,
                    via=span.via,
                    key=key,
                )
            )

    for found in _DATE.finditer("".join(masked)):
        claims.append(
            Claim(
                "date",
                found.group(),
                sentence_at(found.start()),
                number,
                unit,
                quoted,
                key=found.group(),
            )
        )
        blank(*found.span())

    text = "".join(masked)
    for found in _NUMBER.finditer(text):
        claims += _number_claims(found, text, sentence_at, number, unit, quoted, names)
    return claims


def _number_claims(
    found: re.Match[str],
    text: str,
    sentence_at: Callable[[int], str],
    number: int,
    unit: int,
    quoted: bool,
    names: list[_Span],
) -> list[Claim]:
    token = found.group("token")
    suffix = found.group("suffix") or ""
    entries = read_tokens(token)
    single = len(entries) == 1 and entries[0][:2] == (0, len(token))
    if not single:
        suffix = ""  # a suffix after `1,2,3` belongs to nothing we can name
    claims = []
    for start, end, readings in entries:
        begin = found.start("token") + start
        stop = found.start("token") + end
        if not suffix and _is_year(text[begin:stop]):
            continue
        sign = ""
        if single and _SIGN_BEFORE.search(text[max(0, begin - 2) : begin]):
            sign = "+" if text[begin - 1] == "+" else "-"
        within = next(
            (normalise_name(s.text) for s in names if s.start <= begin and stop <= s.end), None
        )
        claims.append(
            Claim(
                "number",
                text[begin - 1 if sign else begin : found.end() if suffix else stop].strip(),
                sentence_at(begin),
                number,
                unit,
                quoted,
                readings=apply_suffix(readings, suffix),
                percent=suffix == "%",
                sign=sign,
                within_name=within,
            )
        )
    return claims


def _is_year(token: str) -> bool:
    return token.isdigit() and int(token) in _YEARS


def _inner(line: str, found: re.Match[str]) -> str:
    """The text of the first group that took part in the match, taken from the original line
    (the match ran on a copy with other spans blanked)."""
    index = next(i for i, group in enumerate(found.groups(), 1) if group is not None)
    return line[found.start(index) : found.end(index)].strip()


def _spans(
    line: str, body_start: int, blank: Callable[[int, int], None], name_cells
) -> list[_Span]:
    """Marked spans: code, bold, quotes and Name-column cells. Code spans that are not a bare
    number are blanked so their digits are no number claims."""
    spans: list[_Span] = []
    work = list(line)

    def hide(start: int, end: int) -> None:
        work[start:end] = "\0" * (end - start)

    for found in _CODE.finditer(line):
        if found.start() < body_start:
            continue
        inner = found.group(1).strip()
        if not _PURE_NUMBER.fullmatch(inner):
            blank(found.start(), found.end())
            spans.append(_Span(found.start(), found.end(), "code", inner))
        hide(found.start(), found.end())
    for start, end, inner in _bold_spans("".join(work), line):
        if start >= body_start:
            spans.append(_Span(start, end, "bold", inner))
            hide(start, end)
    for found in _BOLD_UNDERSCORE.finditer("".join(work)):
        if found.start() >= body_start:
            spans.append(_Span(found.start(), found.end(), "bold", _inner(line, found)))
            hide(found.start(), found.end())
    for found in _QUOTED.finditer("".join(work)):
        if found.start() >= body_start:
            spans.append(_Span(found.start(), found.end(), "quote", _inner(line, found)))
    for start, end in name_cells or []:
        inner = line[start:end].strip()
        if inner and inner not in {"-", "—", "–"}:
            spans.append(_Span(start, end, "table", re.sub(r"[*`]", "", inner)))
    return sorted(spans, key=lambda s: (s.start, s.end))


def _bold_spans(work: str, line: str) -> list[tuple[int, int, str]]:
    """(start, end, inner text) of every `**bold**` span, nested ones included.

    A `**` opens a span when a non-space follows it and closes one when a non-space precedes it
    (`**Frage: **Borg** mit?**` is the outer span around the inner `**Borg**`). A closer takes the
    innermost open span; a `**` that closes nothing and an opener never closed are plain text.
    The inner text of an outer span has the markup of its inner spans removed."""
    spans: list[tuple[int, int, str]] = []
    open_at: list[int] = []
    for found in _BOLD_MARK.finditer(work):
        before = work[found.start() - 1 : found.start()]
        after = work[found.end() : found.end() + 1]
        can_close = bool(before) and not before.isspace() and bool(open_at)
        can_open = bool(after) and not after.isspace()
        if can_close and open_at[-1] + 2 < found.start():
            start = open_at.pop()
            inner = line[start + 2 : found.start()].replace("**", "").strip()
            spans.append((start, found.end(), inner))
        elif can_open:
            open_at.append(found.start())
    return sorted(spans)


def _is_name(span: _Span, line: str, body_start: int) -> bool:
    text = span.text.strip().rstrip(":").strip()
    if not text or _PURE_NUMBER.fullmatch(text):
        return False
    if span.via == "bold":
        body = _HEADING.sub("", line[body_start:]).strip()
        if _WHOLE_LINE_BOLD.fullmatch(body):
            return False
        if span.text.rstrip().endswith(":"):
            return False  # a label ("**Diplomatie:** ..."), not a thing
        if body.endswith(":") and not _BULLET.sub("", line[body_start : span.start]).strip():
            return False  # the bold lead of a line that introduces a list, a label as well
        if _QUANTITY.fullmatch(text):
            return False  # bold figure with its unit; the number itself is checked as a number
        if text.endswith((".", "!", "?")) or len(text.split()) > _MAX_BOLD_NAME_WORDS:
            return False  # a bold sentence is emphasis ("**Energie ist das Dauerproblem.**")
    if span.via == "quote" and len(text.split()) > _MAX_NAME_WORDS:
        return False
    if _LOWERCASE_WORD.fullmatch(text):
        return False
    if span.via == "code":
        first = text.split()[0]
        if first in _COMMANDS or "/" in text or _FILE_EXTENSION.search(text):
            return False
        if _IDENTIFIER.fullmatch(text):
            return False  # a tool or command name (`campaign_status`, `check-epochs`)
    return True


def _sentence_bounds(line, body_start, name_cells) -> list[tuple[int, int]]:
    if name_cells is not None or line.strip().startswith("|"):
        return [(0, len(line))]
    bounds, start = [], body_start
    for found in _SENTENCE_BREAK.finditer(line, body_start):
        bounds.append((start, found.start()))
        start = found.end()
    bounds.append((start, len(line)))
    return bounds
