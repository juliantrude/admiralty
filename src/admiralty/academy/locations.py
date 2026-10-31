"""Where a figure lives in the game's interface (M9, `docs/plans/M9.md` 20f).

`knowledge/<version>/ui_locations.yaml` gives, per domain and per key figure (a metric of the Mechanics
Graph), a path in the interface such as "Top bar, the Energy figure ...". The Coach says it when the Player
asks "where do I see this" and when a Hint Ladder step points at a figure. Each entry cites the game files it
was drafted from (`sources`: file in the install plus a string that occurs in it); the table is drafted from
those files only, no wiki text.

`where(domain, figure)`: the figure's entry when there is one, else the domain's entry (`scope`
"domain"), else `LocationUnknown`; a figure alone (no domain) falls back to the domain named by the part
of its name before the first dot, when that is a domain.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

import yaml

from admiralty.graph.mechanics import DEFAULT_VERSION, KNOWLEDGE_ROOT


class LocationUnknown(KeyError):
    """Neither the figure nor its domain has an entry."""


@dataclass(frozen=True)
class Location:
    path: str
    scope: str  # "figure" | "domain"
    key: str  # the figure or domain the entry belongs to
    sources: tuple[dict[str, str], ...]


def table_path(version: str = DEFAULT_VERSION, root: Path | None = None) -> Path:
    return (root or KNOWLEDGE_ROOT) / version.removeprefix("v") / "ui_locations.yaml"


@cache
def _read(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def read_table(version: str = DEFAULT_VERSION, root: Path | None = None) -> dict[str, Any]:
    path = table_path(version, root)
    return _read(path) if path.exists() else {}


def where(
    domain: str | None = None,
    figure: str | None = None,
    *,
    version: str = DEFAULT_VERSION,
    root: Path | None = None,
) -> Location:
    table = read_table(version, root)
    figures, domains = table.get("figures", {}), table.get("domains", {})
    if figure in figures:
        return _location(figures[figure], "figure", figure)
    domain = domain or (figure.split(".", 1)[0] if figure and "." in figure else None)
    if domain in domains:
        return _location(domains[domain], "domain", domain)
    raise LocationUnknown(figure or domain or "")


def _location(entry: dict[str, Any], scope: str, key: str) -> Location:
    return Location(entry["path"], scope, key, tuple(entry["sources"]))
