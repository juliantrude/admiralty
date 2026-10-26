"""Refresh the observed values in knowledge/<version>/benchmarks.yaml and write the review page.

    uv run python tools/gen_benchmarks.py [--saves DIR] [--empire NAME] [--page-only]

Reads every Campaign folder under DIR (default tests/fixtures/saves, git-ignored), extracts the
Player's empire from each save and records the figures as `observed` entries. Benchmark `values`,
`status` and any figure you added by hand are kept; only `observed` is rewritten, and only for the
figures defined here. With `--page-only` (or no saves on this machine) the YAML is left alone and
only docs/benchmarks-draft.md is regenerated from it.

The saves hold friends' player names; the YAML records only the Campaign folder name, the in-game
date and numbers.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from admiralty.extract.snapshot import Extractor
from admiralty.graph.benchmarks import (
    DECADES,
    DEFAULT_VERSION,
    benchmarks_path,
    load_benchmarks,
    render_review_page,
    resolve_source,
)
from admiralty.graph.mechanics import KNOWLEDGE_ROOT, METRICS_FILE

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "docs" / "benchmarks-draft.md"
HEADER = """\
# Benchmarks for the Consulting mode (docs/plans/M4.md, "Benchmarks (draft)").
# status: draft means no Briefing may use a value; experienced players review and set it to reviewed.
# values: per decade null (no source yet), or {value, basis: derived|reviewed, formula}.
# observed: refreshed from the reference Campaigns by tools/gen_benchmarks.py (one empire each).
"""
# id -> (label, unit, source, assumptions)
FIGURES = {
    "research_income": (
        "Research income",
        "research per month, physics + society + engineering",
        {"metric": "research.income"},
        ["Gross monthly income summed over the three research fields."],
    ),
    "alloys_income": (
        "Alloys income",
        "alloys per month",
        {"metric": "alloys.income"},
        ["Gross monthly income; upkeep and fleet building are not netted out."],
    ),
    "energy_income": (
        "Energy income",
        "energy per month",
        {"metric": "energy.income"},
        ["Gross monthly income; the reviewers may prefer net."],
    ),
    "minerals_income": (
        "Minerals income",
        "minerals per month",
        {"metric": "minerals.income"},
        ["Gross monthly income."],
    ),
    "food_income": (
        "Food income",
        "food per month",
        {"metric": "food.income"},
        ["Gross monthly income; food-hungry species change the useful value a lot."],
    ),
    "unity_income": (
        "Unity income",
        "unity per month",
        {"metric": "unity.income"},
        ["Gross monthly income, Tradition cost not netted out."],
    ),
    "influence_income": (
        "Influence income",
        "influence per month",
        {"metric": "influence.income"},
        ["Gross monthly income; colonies and upkeep eat most of it, so net is the usual watch."],
    ),
    "naval_capacity": (
        "Naval capacity (maximum)",
        "naval capacity",
        {"metric": "naval_capacity.max"},
        ["The extract's maximum, a computed value pinned by pending golden tests."],
    ),
    "military_power": (
        "Fleet power",
        "the game's military power score",
        {"path": "empire.military_power"},
        ["The in-game military power number, not a count of ships."],
    ),
    "pop_count": (
        "Pop count",
        "pops (extract scale)",
        {"metric": "pops.total"},
        ["The extract may carry pops times 100 (open question for the Player's UI read)."],
    ),
    "planet_count": (
        "Planet count",
        "planets",
        {"count": "planets"},
        ["Planets the empire owns, as listed in the extract."],
    ),
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--saves", type=Path, default=ROOT / "tests" / "fixtures" / "saves")
    parser.add_argument("--empire", default="Plexxi", help="player name tracked in every save")
    parser.add_argument("--page-only", action="store_true")
    args = parser.parse_args(argv)

    path = benchmarks_path(DEFAULT_VERSION)
    if not args.page_only:
        saves = sorted(args.saves.glob("*/*.sav")) if args.saves.is_dir() else []
        if not saves:
            print(f"no saves under {args.saves}: keeping the observed values", file=sys.stderr)
        else:
            _refresh(path, _observations(saves, args.empire))
    benchmarks = load_benchmarks(DEFAULT_VERSION)
    PAGE.write_text(render_review_page(benchmarks, {}), encoding="utf-8")
    print(f"{path} and {PAGE} written ({benchmarks.status})")
    return 0


def _observations(saves: list[Path], empire: str) -> dict[str, list[dict]]:
    """Per figure the observed entries, one per (campaign, in-game date), later file wins."""
    registry = yaml.safe_load((KNOWLEDGE_ROOT / "4.5.2" / "graph" / METRICS_FILE).read_text())
    metrics = registry["metrics"]
    extractor = Extractor()
    seen: dict[tuple[str, str], dict] = {}
    for save in saves:
        document = extractor.extract(str(save), empire)
        date = document["header"]["date"]
        row = {}
        for figure_id, (_, _, source, _) in FIGURES.items():
            value = resolve_source(source, document, metrics)
            if value is not None:
                row[figure_id] = round(value, 2) if isinstance(value, float) else value
        seen[(save.parent.name, date)] = row  # sorted input: the later file name replaces
    observed: dict[str, list[dict]] = {figure_id: [] for figure_id in FIGURES}
    for (campaign, date), row in sorted(seen.items()):
        for figure_id, value in row.items():
            observed[figure_id].append({"campaign": campaign, "date": date, "value": value})
    return observed


def _refresh(path: Path, observed: dict[str, list[dict]]) -> None:
    existing = yaml.safe_load(path.read_text(encoding="utf-8")) if path.is_file() else {}
    figures = dict(existing.get("figures", {}))
    for figure_id, (label, unit, source, assumptions) in FIGURES.items():
        old = figures.get(figure_id, {})
        figures[figure_id] = {
            "label": old.get("label", label),
            "unit": old.get("unit", unit),
            "source": old.get("source", source),
            "provenance": old.get("provenance", _provenance(source)),
            "assumptions": old.get("assumptions", assumptions),
            "values": old.get("values", dict.fromkeys(DECADES)),
            "observed": observed[figure_id],
        }
    document = {
        "version": DEFAULT_VERSION,
        "status": existing.get("status", "draft"),
        "decades": list(DECADES),
        "figures": figures,
    }
    body = yaml.safe_dump(document, sort_keys=False, allow_unicode=True, width=100)
    path.write_text(HEADER + body, encoding="utf-8")


def _provenance(source: dict) -> str:
    target = next(iter(source.values()))
    kind = next(iter(source))
    field = f"metric '{target}' (metrics.yaml)" if kind == "metric" else f"extract field '{target}'"
    return (
        f"Observed: {field} in the archived extracts of the reference Campaigns. "
        "Benchmark values: open, no game-file formula covers a whole empire and nobody has "
        "contributed a figure yet."
    )


if __name__ == "__main__":
    sys.exit(main())
