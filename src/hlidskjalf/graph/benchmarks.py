"""Benchmarks: provisional per-decade values for the main figures, drafts until experts review them.

`knowledge/<version>/benchmarks.yaml` holds one entry per figure (research, alloys, ...). Format
and rationale: docs/plans/M4.md "Benchmarks (draft)". Three kinds of number, in order of honesty:

- `observed`: what one reference Campaign's empire had in an archived extract. A fact about one
  empire, not a benchmark; it only tells the reviewers what a real game looked like.
- `values[decade]` with `basis: derived`: computed from game files, the formula in `formula`.
- `values[decade]` with `basis: reviewed`: an experienced player's figure; only allowed once the
  file's `status` is `reviewed`.
- `null`: nobody has a source yet. Nothing is invented.

A Briefing may only use benchmarks of a `reviewed` file (`usable`); a draft is for the review page
(`render_review_page`, written to docs/benchmarks-draft.md by tools/gen_benchmarks.py).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULT_VERSION = "v4.5.2"
STATUSES = ("draft", "reviewed")
BASES = ("derived", "reviewed")
DECADES = tuple(range(2210, 2300, 10))
_DATE = re.compile(r"\d{4}\.\d{2}\.\d{2}")
_FIGURE_FIELDS = ("label", "unit", "source", "provenance", "assumptions", "values", "observed")
_SOURCE_KINDS = ("metric", "path", "count")


class BenchmarksInvalid(ValueError):
    """The benchmarks file is malformed; `errors` lists every problem."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(f"{len(errors)} error(s) in benchmarks.yaml, first: {errors[0]}")


@dataclass(frozen=True)
class Benchmarks:
    version: str
    status: str
    figures: dict[str, dict[str, Any]]

    @property
    def usable(self) -> bool:
        """Only reviewed benchmarks may back a statement in a Briefing."""
        return self.status == "reviewed"

    def value(self, figure: str, decade: int) -> float | None:
        entry = self.figures[figure]["values"].get(decade)
        return None if entry is None else entry["value"]


def benchmarks_path(version: str = DEFAULT_VERSION, root: Path | None = None) -> Path:
    from hlidskjalf.graph.mechanics import KNOWLEDGE_ROOT

    return (root or KNOWLEDGE_ROOT) / version.removeprefix("v") / "benchmarks.yaml"


def load_benchmarks(version: str = DEFAULT_VERSION, root: Path | None = None) -> Benchmarks:
    """The benchmarks of a game version, refusing a malformed file."""
    document, errors = read_benchmarks(benchmarks_path(version, root), _registry(version, root))
    if errors:
        raise BenchmarksInvalid(errors)
    return Benchmarks(version, document["status"], document["figures"])


def read_benchmarks(
    path: Path, registered_metrics: set[str] | None = None
) -> tuple[dict[str, Any], list[str]]:
    """The raw document plus every problem found (never raises).

    `registered_metrics` is the metrics registry's names; None skips the metric check.
    """
    try:
        document = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.CSafeLoader)
    except (OSError, yaml.YAMLError) as error:
        return {}, [f"cannot read {path.name}: {error}"]
    return document, _check(document, registered_metrics)


def resolve_source(source: dict[str, Any], extract: dict[str, Any], metrics: dict[str, Any]):
    """The figure's value in one Snapshot extract; None when the extract lacks the field."""
    if "metric" in source:
        return _resolve_metric(metrics[source["metric"]], extract)
    if "path" in source:
        return _dig(extract, source["path"])
    value = _dig(extract, source["count"])
    return len(value) if isinstance(value, list | dict) else None


def nearest_decade(date: str) -> int | None:
    """The benchmark decade a save date belongs to (within five years), else None."""
    year = int(date[:4])
    decade = round(year / 10) * 10
    return decade if decade in DECADES and abs(year - decade) <= 5 else None


def render_review_page(benchmarks: Benchmarks, metrics: dict[str, Any]) -> str:
    """The Markdown page experienced players review: one table per figure, gaps stated."""
    lines = [
        "# Benchmarks (DRAFT)",
        "",
        f"> **Draft for review, game version {benchmarks.version}.** Status: `{benchmarks.status}`."
        " No Briefing uses these numbers until the status is `reviewed`."
        " Generated from `knowledge/"
        f"{benchmarks.version.removeprefix('v')}/benchmarks.yaml` by `tools/gen_benchmarks.py`;"
        " edit the YAML, not this page.",
        "",
        "How to read it: *Benchmark* is the proposed value for a decent empire at that decade"
        " (empty = nobody has a source yet). *Observed* is what one reference Campaign's empire"
        " had in a save near that decade: a fact about one empire, not a recommendation.",
        "",
    ]
    total = sum(len(f["values"]) for f in benchmarks.figures.values())
    filled = sum(1 for f in benchmarks.figures.values() for v in f["values"].values() if v)
    lines += [
        f"**{filled} of {total} benchmark values are filled, {total - filled} are open.**",
        "",
    ]
    for figure_id, figure in benchmarks.figures.items():
        lines += [f"## {figure['label']}", "", f"`{figure_id}`, unit: {figure['unit']}", ""]
        lines += [f"Provenance: {figure['provenance']}", ""]
        if figure["assumptions"]:
            lines += ["Assumptions:", ""] + [f"- {text}" for text in figure["assumptions"]] + [""]
        by_decade: dict[int, list[str]] = {}
        for seen in figure["observed"]:
            decade = nearest_decade(seen["date"])
            if decade is not None:
                by_decade.setdefault(decade, []).append(
                    f"{seen['campaign']} {seen['date']}: {_number(seen['value'])}"
                )
        lines += ["| Decade | Benchmark | Basis | Observed |", "|---|---|---|---|"]
        for decade in DECADES:
            entry = figure["values"].get(decade)
            value = _number(entry["value"]) if entry else "_open_"
            basis = (entry.get("formula") or entry["basis"]) if entry else ""
            lines.append(
                f"| {decade} | {value} | {basis} | {'<br>'.join(by_decade.get(decade, [])) or '-'} |"
            )
        outside = [s for s in figure["observed"] if nearest_decade(s["date"]) is None]
        if outside:
            lines += ["", "Observed outside the decades: " + "; ".join(
                f"{s['campaign']} {s['date']}: {_number(s['value'])}" for s in outside
            )]  # fmt: skip
        lines += [""]
    lines += [
        "## Questions for the reviewers",
        "",
        "- Which values per decade would you expect from a competent, not optimised, empire?"
        " Any figure you fill in needs a short reason (your own games, a guide, a calculation).",
        "- Are these the right figures? Is gross income or net the number you watch, per resource?",
        "- Do the observed values of the reference Campaigns look typical for their decade?",
        "- Pop counts may be scaled by 100 in the save (the Player's UI read decides, see"
        " docs/awaiting-julian.md); compare shares and growth, not the raw numbers, until then.",
        "",
    ]
    return "\n".join(lines)


# --- checks ------------------------------------------------------------------------------------


def _check(document: Any, registered: set[str] | None) -> list[str]:
    if not isinstance(document, dict):
        return ["the file is not a mapping"]
    errors: list[str] = []
    if document.get("status") not in STATUSES:
        errors.append(f"status must be one of {', '.join(STATUSES)}")
    if document.get("decades") != list(DECADES):
        errors.append(f"decades must be {list(DECADES)}")
    figures = document.get("figures")
    if not isinstance(figures, dict) or not figures:
        return errors + ["figures: needs at least one figure"]
    for figure_id, figure in figures.items():
        if not isinstance(figure, dict):
            errors.append(f"{figure_id}: not a mapping")
            continue
        errors += _figure_errors(figure_id, figure, document.get("status"), registered)
    return errors


def _figure_errors(figure_id: str, figure: dict, status: Any, registered: set[str] | None):
    errors = [f"{figure_id}: missing '{key}'" for key in _FIGURE_FIELDS if key not in figure]
    for key in ("label", "unit", "provenance"):
        if key in figure and not (isinstance(figure[key], str) and figure[key].strip()):
            errors.append(f"{figure_id}: '{key}' must be non-empty text")
    if not isinstance(figure.get("assumptions", []), list):
        errors.append(f"{figure_id}: 'assumptions' must be a list")
    errors += _source_errors(figure_id, figure.get("source"), registered)
    errors += _values_errors(figure_id, figure.get("values"), status)
    errors += _observed_errors(figure_id, figure.get("observed"))
    return errors


def _source_errors(figure_id: str, source: Any, registered: set[str] | None) -> list[str]:
    if source is None:
        return []  # reported as missing
    if not isinstance(source, dict) or len(source) != 1 or next(iter(source)) not in _SOURCE_KINDS:
        return [f"{figure_id}: source must be exactly one of {', '.join(_SOURCE_KINDS)}"]
    (kind, target), = source.items()  # fmt: skip
    if kind == "metric" and registered is not None and target not in registered:
        return [f"{figure_id}: metric '{target}' is not in metrics.yaml"]
    return []


def _values_errors(figure_id: str, values: Any, status: Any) -> list[str]:
    if values is None:
        return []
    if not isinstance(values, dict) or sorted(values) != list(DECADES):
        return [f"{figure_id}: values needs exactly the decades {DECADES[0]}..{DECADES[-1]}"]
    errors = []
    for decade, entry in values.items():
        where = f"{figure_id} {decade}"
        if entry is None:
            continue
        if not isinstance(entry, dict) or not isinstance(entry.get("value"), int | float):
            errors.append(f"{where}: needs null or a mapping with a numeric 'value'")
        elif entry.get("basis") not in BASES:
            errors.append(f"{where}: basis must be one of {', '.join(BASES)}")
        elif entry["basis"] == "derived" and not entry.get("formula"):
            errors.append(f"{where}: a derived value needs its 'formula'")
        elif entry["basis"] == "reviewed" and status != "reviewed":
            errors.append(f"{where}: basis 'reviewed' needs the file status 'reviewed'")
    return errors


def _observed_errors(figure_id: str, observed: Any) -> list[str]:
    if observed is None:
        return []
    if not isinstance(observed, list):
        return [f"{figure_id}: observed must be a list"]
    errors = []
    for index, seen in enumerate(observed):
        where = f"{figure_id} observed[{index}]"
        if not isinstance(seen, dict):
            errors.append(f"{where}: not a mapping")
        elif not (seen.get("campaign") and _DATE.fullmatch(str(seen.get("date", "")))):
            errors.append(f"{where}: needs a campaign and a date like 2259.12.29")
        elif not isinstance(seen.get("value"), int | float):
            errors.append(f"{where}: value must be a number")
    return errors


# --- resolving a source ------------------------------------------------------------------------


def _registry(version: str, root: Path | None) -> set[str] | None:
    from hlidskjalf.graph.mechanics import KNOWLEDGE_ROOT, METRICS_FILE

    path = (root or KNOWLEDGE_ROOT) / version.removeprefix("v") / "graph" / METRICS_FILE
    if not path.is_file():
        return None
    return set((yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("metrics", {}))


def _dig(document: dict[str, Any], path: str):
    value: Any = document
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def _resolve_metric(spec: dict[str, Any], extract: dict[str, Any]):
    if "path" in spec:
        return _dig(extract, spec["path"])
    if "sum" in spec:
        parts = [_dig(extract, path) for path in spec["sum"]]
        return None if None in parts else sum(parts)
    ratio = spec["ratio"]
    top, bottom = _dig(extract, ratio["numerator"]), _dig(extract, ratio["denominator"])
    return None if top is None or not bottom else top / bottom


def _number(value: float) -> str:
    if isinstance(value, float) and value != int(value):
        return f"{value:,.1f}"
    return f"{int(value):,}"
