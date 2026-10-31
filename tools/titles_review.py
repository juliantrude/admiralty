"""Write the review page for the title rewrite: old and new titles side by side, per domain.

Julian reads all Goals and Remedies, one domain completely (energy) and a fixed sample of ten Causes and
Obstacles from the other domains (docs/plans/grilling.md topic 2). The old titles are the snapshot in
docs/plans/titles-before.json, taken before the rewrite; the new ones are read from the Mechanics Graph.
The page is one static file with no script and no game graphics.

    uv run python tools/titles_review.py            # write docs/plans/titles-review.html
    uv run python tools/titles_review.py --check    # exit 1 if the committed page is stale
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from admiralty.graph.mechanics import MechanicsGraph  # noqa: E402

BEFORE = ROOT / "docs" / "plans" / "titles-before.json"
PAGE = ROOT / "docs" / "plans" / "titles-review.html"
FULL_DOMAIN = "energy"
SAMPLE_SIZE = 10
SAMPLE_SEED = 20261031
KINDS = (("goal", "Goals"), ("cause", "Causes"), ("remedy", "Remedies"), ("obstacle", "Obstacles"))

STYLE = """
body{font:15px/1.45 system-ui,sans-serif;max-width:60rem;margin:2rem auto;padding:0 1rem;color:#222}
h1,h2,h3{line-height:1.2} h2{margin-top:2.2rem;border-bottom:1px solid #ccc}
table{border-collapse:collapse;width:100%;margin:.5rem 0 1.2rem}
td,th{border:1px solid #ddd;padding:.3rem .5rem;vertical-align:top;text-align:left}
th{background:#f3f3f3} .id{color:#777;font-size:.8em;white-space:nowrap}
.same td.new{color:#777} .old{color:#9a2a2a} .may{color:#555;font-style:italic;display:block}
"""


def _domain(node_id: str) -> str:
    return node_id.split(".")[0]


def _entries(graph: MechanicsGraph) -> dict[str, dict]:
    out = {}
    for goal_id, goal in graph.goals.items():
        out[goal_id] = {"type": "goal", "title": goal["title"]}
    for node_id, node in graph.nodes.items():
        out[node_id] = {
            "type": node["type"],
            "title": node["title"],
            "uncertain_title": node.get("uncertain_title"),
        }
    return out


def _sample(entries: dict[str, dict]) -> set[str]:
    pool = sorted(
        i
        for i, e in entries.items()
        if e["type"] in ("cause", "obstacle") and _domain(i) != FULL_DOMAIN
    )
    return set(random.Random(SAMPLE_SEED).sample(pool, SAMPLE_SIZE))


def _row(node_id: str, old: dict, new: dict) -> str:
    changed = old["title"] != new["title"] or old.get("uncertain_title") != new.get(
        "uncertain_title"
    )
    old_cell = escape(old["title"])
    new_cell = escape(new["title"])
    if new.get("uncertain_title"):
        old_cell += f'<span class="may">{escape(old.get("uncertain_title") or "")}</span>'
        new_cell += f'<span class="may">{escape(new["uncertain_title"])}</span>'
    cls = "" if changed else ' class="same"'
    return (
        f'<tr{cls}><td class="id">{escape(node_id)}</td><td class="old">{old_cell}</td>'
        f'<td class="new">{new_cell}{"" if changed else " (unchanged)"}</td></tr>'
    )


def _table(ids: list[str], before: dict, entries: dict) -> str:
    rows = "\n".join(_row(i, before[i], entries[i]) for i in ids)
    return f"<table><tr><th>Node</th><th>Before</th><th>Now</th></tr>\n{rows}\n</table>"


def build() -> str:
    graph = MechanicsGraph.load()
    entries = _entries(graph)
    before = json.loads(BEFORE.read_text(encoding="utf-8"))
    missing = sorted(set(entries) - set(before))
    if missing:
        raise SystemExit(f"nodes without an old title in {BEFORE.name}: {', '.join(missing)}")
    sample = _sample(entries)
    changed = sum(1 for i, e in entries.items() if e["title"] != before[i]["title"])
    parts = [
        "<!doctype html><html lang=en><meta charset=utf-8><title>Admiralty: title review</title>",
        f"<style>{STYLE}</style>",
        "<h1>Title review</h1>",
        f"<p>{changed} of {len(entries)} titles changed. Rules: docs/plans/titles.md. "
        "Please read: <b>every Goal and every Remedy</b>, <b>all of the energy domain</b>, and "
        f"<b>the {SAMPLE_SIZE} Causes and Obstacles of the sample</b>. More than two bad ones in the "
        "sample: read everything (the per-domain lists are below).</p>",
    ]
    for kind, label in (("goal", "Goals"), ("remedy", "Remedies")):
        ids = [i for i, e in entries.items() if e["type"] == kind]
        parts += [f"<h2>All {label}</h2>", _table(ids, before, entries)]
    energy = [
        i
        for i in entries
        if _domain(i) == FULL_DOMAIN and entries[i]["type"] in ("cause", "obstacle")
    ]
    parts += [f"<h2>Domain read in full: {FULL_DOMAIN}</h2>", _table(energy, before, entries)]
    parts += [f"<h2>Sample of {SAMPLE_SIZE}</h2>", _table(sorted(sample), before, entries)]
    parts.append("<h2>Everything, by domain</h2>")
    for domain in sorted({_domain(i) for i in entries}):
        parts.append(f"<h3>{escape(domain)}</h3>")
        for kind, label in KINDS:
            ids = [i for i, e in entries.items() if _domain(i) == domain and e["type"] == kind]
            if ids:
                parts += [f"<h4>{label}</h4>", _table(ids, before, entries)]
    return "\n".join(parts) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--check", action="store_true", help="exit 1 if the committed page is stale"
    )
    args = parser.parse_args()
    page = build()
    if args.check:
        stale = not PAGE.exists() or PAGE.read_text(encoding="utf-8") != page
        if stale:
            print(f"{PAGE} is stale; run tools/titles_review.py", file=sys.stderr)
        return int(stale)
    PAGE.write_text(page, encoding="utf-8")
    print(f"wrote {PAGE} ({len(page)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
