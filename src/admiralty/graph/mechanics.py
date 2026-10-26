"""The curated Mechanics Graph: load it, validate it, look nodes and facts up.

Three layers (docs/plans/M4.md): generated facts <- curated graph <- Playbook Rules. This module
is the middle one. `knowledge/<version>/graph/<domain>.yaml` holds Goals and Nodes (Causes,
Remedies, Obstacles); `metrics.yaml` next to them registers the Snapshot values an Obstacle may
check. Every number a node states lives in a generated fact it links to, so the validator
resolves each fact reference and flags digits in prose.

`validate` never raises on a bad pack, it returns every problem it finds (JSON Schema errors
first, then the cross-file checks). `MechanicsGraph.load` refuses a pack with errors, so a loaded
graph is always consistent. Warnings (digits in prose, unnamed cycles) do not fail.
"""

from __future__ import annotations

import fnmatch
import json
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from functools import cache
from importlib import resources
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

from admiralty.graph.benchmarks import read_benchmarks
from admiralty.graph.playbook import Rule, read_rules

KNOWLEDGE_ROOT = Path(__file__).resolve().parents[3] / "knowledge"
METRICS_FILE = "metrics.yaml"
DEFAULT_VERSION = "v4.5.2"

# which node type each link list may point at
_LINK_TYPES = {"causes": "cause", "remedies": "remedy", "obstacles": "obstacle"}
# a digit run that is not part of an identifier: "+20", "7.4k", "tier 3" (not "tr_supremacy_2")
_FIGURE = re.compile(r"(?<![\w])\d")
_PROSE_FIELDS = ("description", "judgement")


class GraphMissing(FileNotFoundError):
    """There is no knowledge pack (graph folder) for the requested game version."""


class GraphInvalid(ValueError):
    """The pack has errors; `problems` lists all of them."""

    def __init__(self, problems: list[Problem]):
        self.problems = problems
        errors = [p for p in problems if p.severity == "error"]
        super().__init__(f"{len(errors)} error(s) in the Mechanics Graph, first: {errors[0]}")


@dataclass(frozen=True)
class Problem:
    severity: str  # "error" | "warning"
    where: str  # file name, optionally followed by the node id
    message: str

    def __str__(self) -> str:
        return f"{self.severity}: {self.where}: {self.message}"


@dataclass
class MechanicsGraph:
    """A validated pack: Goals and Nodes by id, plus the generated facts they link to."""

    version: str
    goals: dict[str, dict[str, Any]]
    nodes: dict[str, dict[str, Any]]
    metrics: dict[str, dict[str, Any]]
    warnings: list[Problem] = field(default_factory=list)
    _generated: Path | None = None
    _facts: dict[str, dict[str, Any]] | None = None

    @classmethod
    def load(cls, version: str = DEFAULT_VERSION, root: Path | None = None) -> MechanicsGraph:
        pack = _read(version, root)
        problems = _check(pack)
        if any(p.severity == "error" for p in problems):
            raise GraphInvalid(problems)
        return cls(
            version=_tag(version),
            goals={g["id"]: g for _, doc in pack.graphs for g in doc["goals"]},
            nodes={n["id"]: n for _, doc in pack.graphs for n in doc["nodes"]},
            metrics=pack.metrics["metrics"] if pack.metrics else {},
            warnings=problems,
            _generated=pack.directory / "generated",
        )

    def goal(self, goal_id: str) -> dict[str, Any]:
        return self.goals[goal_id]

    def node(self, node_id: str) -> dict[str, Any]:
        return self.nodes[node_id]

    def reachable(self, goal_id: str) -> list[str]:
        """Node ids a Goal expands to, depth-first in file order, each once.

        This is the graph's shape alone, blind to the Snapshot: M5's `expand_graph` adds the
        Obstacle checks, the depth limit and the Vicious Circles. Visiting each node once is what
        makes the walk terminate on the legal cycles.
        """
        order: list[str] = []
        seen: set[str] = set()

        def visit(node_id: str) -> None:
            if node_id in seen:
                return
            seen.add(node_id)
            order.append(node_id)
            node = self.nodes[node_id]
            for kind in _LINK_TYPES:
                for target in node.get(kind, []):
                    visit(target)

        for cause in self.goals[goal_id]["causes"]:
            visit(cause)
        return order

    @property
    def facts(self) -> dict[str, dict[str, Any]]:
        """All generated facts by id; read on first use (the files are several MB)."""
        if self._facts is None:
            self._facts = _facts(self._generated) if self._generated else {}
        return self._facts

    def fact(self, fact_id: str) -> dict[str, Any]:
        return self.facts[fact_id]

    @property
    def rules(self) -> dict[str, Rule]:
        """The approved Playbook Rules of this pack by id (the loader already checked them)."""
        return read_rules(self._generated.parent / "rules")[0] if self._generated else {}

    def node_facts(self, node_id: str) -> list[dict[str, Any]]:
        """The generated facts a node links to, wildcards expanded, sorted by id."""
        found: dict[str, dict[str, Any]] = {}
        for pattern in self.nodes[node_id].get("facts", []):
            for fact_id in _matching(self.facts, pattern):
                found[fact_id] = self.facts[fact_id]
        return [found[k] for k in sorted(found)]


def validate(version: str = DEFAULT_VERSION, root: Path | None = None) -> list[Problem]:
    """Every problem of the pack, errors and warnings; empty when the pack is clean."""
    return _check(_read(version, root))


# --- reading ---------------------------------------------------------------------------------


@dataclass
class _Pack:
    version: str
    directory: Path
    graphs: list[tuple[str, dict[str, Any]]]  # (file name, document)
    metrics: dict[str, Any] | None
    problems: list[Problem]  # parse errors found while reading


def _tag(version: str) -> str:
    return version if version.startswith("v") else f"v{version}"


def _read(version: str, root: Path | None) -> _Pack:
    directory = (root or KNOWLEDGE_ROOT) / _tag(version).removeprefix("v")
    graph_dir = directory / "graph"
    if not graph_dir.is_dir():
        raise GraphMissing(f"no knowledge pack for {_tag(version)}: {graph_dir} does not exist")
    problems: list[Problem] = []
    graphs: list[tuple[str, dict[str, Any]]] = []
    metrics = None
    for path in sorted(graph_dir.glob("*.yaml")):
        try:
            document = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.CSafeLoader)
        except yaml.YAMLError as error:
            problems.append(Problem("error", path.name, f"not valid YAML: {error}"))
            continue
        if path.name == METRICS_FILE:
            metrics = document
        else:
            graphs.append((path.name, document))
    return _Pack(_tag(version), directory, graphs, metrics, problems)


@cache
def _schema(name: str) -> Draft202012Validator:
    text = (resources.files("admiralty.graph") / name).read_text(encoding="utf-8")
    schema = json.loads(text)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


@cache
def _facts(generated: Path) -> dict[str, dict[str, Any]]:
    facts: dict[str, dict[str, Any]] = {}
    for path in sorted(generated.glob("*.yaml")):
        document = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.CSafeLoader)
        for fact in document["facts"]:
            facts[fact["id"]] = fact
    return facts


def _fact_ids(generated: Path) -> frozenset[str]:
    return frozenset(_facts(generated))


def _matching(ids, pattern: str) -> list[str]:
    if "*" not in pattern:
        return [pattern] if pattern in ids else []
    return sorted(i for i in ids if fnmatch.fnmatchcase(i, pattern))


# --- checking --------------------------------------------------------------------------------


def _check(pack: _Pack) -> list[Problem]:
    problems = list(pack.problems)
    if pack.metrics is not None:
        problems += _schema_errors("metrics.schema.json", METRICS_FILE, pack.metrics)
        if isinstance(pack.metrics, dict) and pack.metrics.get("version") not in (
            None,
            pack.version,
        ):
            problems.append(Problem("error", METRICS_FILE, f"version is not {pack.version}"))
    for name, document in pack.graphs:
        problems += _schema_errors("mechanics.schema.json", name, document)
        if isinstance(document, dict):
            problems += _file_level(pack, name, document)
    if any(p.severity == "error" for p in problems):
        # the cross-file checks assume documents of the right shape
        return problems

    nodes, goals = _index(pack, problems)
    metrics = set((pack.metrics or {}).get("metrics", {}))
    facts = _fact_ids(pack.directory / "generated")
    rules, rule_errors = read_rules(pack.directory / "rules")
    for message in rule_errors:
        file, _, text = message.partition(": ")
        problems.append(Problem("error", f"rules/{file}", text))
    for rule in rules.values():
        for pattern in rule.applies_to:
            if pattern != "*" and not (_matching(nodes, pattern) or _matching(goals, pattern)):
                problems.append(
                    Problem(
                        "error",
                        f"rules/{rule.file}",
                        f"applies_to: '{pattern}' matches no node or Goal",
                    )
                )
    benchmarks = pack.directory / "benchmarks.yaml"
    if benchmarks.is_file():
        _, benchmark_errors = read_benchmarks(benchmarks, metrics)
        problems += [Problem("error", "benchmarks.yaml", m) for m in benchmark_errors]
    file_of = {n["id"]: name for name, doc in pack.graphs for n in doc["nodes"]}
    file_of |= {g["id"]: name for name, doc in pack.graphs for g in doc["goals"]}

    for goal in goals.values():
        where = f"{file_of[goal['id']]} {goal['id']}"
        problems += _links(where, goal, nodes, ("causes",))
        for metric in goal.get("symptom_metrics", []):
            problems += _metric(where, metric, metrics)
    for node in nodes.values():
        where = f"{file_of[node['id']]} {node['id']}"
        problems += _node_problems(where, node, nodes, metrics, facts, rules)
    problems += _cycles(nodes, file_of)
    return problems


def _schema_errors(schema: str, name: str, document: Any) -> list[Problem]:
    errors = sorted(_schema(schema).iter_errors(document), key=lambda e: list(map(str, e.path)))
    return [
        Problem("error", name, f"{_location(error.absolute_path)}{error.message}")
        for error in errors
    ]


def _location(path) -> str:
    return "/".join(str(part) for part in path) + ": " if path else ""


def _file_level(pack: _Pack, name: str, document: dict[str, Any]) -> list[Problem]:
    problems = []
    if document.get("version") not in (None, pack.version):
        problems.append(
            Problem("error", name, f"version is {document['version']}, not {pack.version}")
        )
    domain = document.get("domain")
    if isinstance(domain, str) and Path(name).stem != domain:
        problems.append(Problem("error", name, f"domain '{domain}' does not match the file name"))
    return problems


def _index(pack: _Pack, problems: list[Problem]):
    """Nodes and goals by id; duplicate ids and ids outside their file's domain are errors."""
    nodes: dict[str, dict[str, Any]] = {}
    goals: dict[str, dict[str, Any]] = {}
    seen: dict[str, str] = {}
    for name, document in pack.graphs:
        entries = [*document["goals"], *document["nodes"]]
        for entry in entries:
            identity = entry["id"]
            if identity in seen:
                problems.append(
                    Problem("error", name, f"{identity}: also defined in {seen[identity]}")
                )
                continue
            seen[identity] = name
            if not identity.startswith(f"{document['domain']}."):
                problems.append(
                    Problem(
                        "error", name, f"{identity}: id must start with '{document['domain']}.'"
                    )
                )
        for goal in document["goals"]:
            goals.setdefault(goal["id"], goal)
        for node in document["nodes"]:
            nodes.setdefault(node["id"], node)
    return nodes, goals


def _links(where: str, entry: dict[str, Any], nodes, kinds) -> list[Problem]:
    problems = []
    for kind in kinds:
        for target in entry.get(kind, []):
            if target not in nodes:
                problems.append(Problem("error", where, f"{kind}: '{target}' does not exist"))
            elif nodes[target]["type"] != _LINK_TYPES[kind]:
                problems.append(
                    Problem(
                        "error",
                        where,
                        f"{kind}: '{target}' is a {nodes[target]['type']}, expected a "
                        f"{_LINK_TYPES[kind]}",
                    )
                )
    return problems


def _metric(where: str, metric: str, registered: set[str]) -> list[Problem]:
    if metric in registered:
        return []
    return [Problem("error", where, f"metric '{metric}' is not in {METRICS_FILE}")]


def _comparison_metrics(comparison: dict[str, Any]) -> Iterator[str]:
    if "metric" in comparison:
        yield comparison["metric"]
    target = comparison.get("compare_to")
    if isinstance(target, dict):
        yield target["metric"]


def _node_problems(where, node, nodes, metrics, facts, rules) -> list[Problem]:
    problems = _links(where, node, nodes, ("causes", "remedies", "obstacles"))
    if node["type"] == "cause" and not node.get("causes") and not node.get("remedies"):
        problems.append(Problem("error", where, "dead-end Cause: no deeper causes and no remedies"))
    if node.get("break_point") and "circle" not in node:
        problems.append(Problem("error", where, "break_point is only meaningful with a circle"))
    for comparison in (node.get("check"), node.get("pending_when")):
        for metric in _comparison_metrics(comparison or {}):
            problems += _metric(where, metric, metrics)
    for pattern in node.get("facts", []):
        if not _matching(facts, pattern):
            problems.append(
                Problem("error", where, f"facts: '{pattern}' matches no generated fact")
            )
    for rule in node.get("rules", []):
        if rule not in rules:
            problems.append(Problem("error", where, f"rules: '{rule}' is not a Playbook Rule"))
    for name in _PROSE_FIELDS:
        if _FIGURE.search(node.get(name, "")):
            problems.append(
                Problem(
                    "warning",
                    where,
                    f"{name} contains a figure; numbers belong in linked facts, not in prose",
                )
            )
    return problems


def _edges(node: dict[str, Any], nodes: dict[str, dict[str, Any]]) -> list[str]:
    """Links that lead to an existing node (dangling ones are reported elsewhere)."""
    return [t for kind in _LINK_TYPES for t in node.get(kind, []) if t in nodes]


def _cycles(nodes: dict[str, dict[str, Any]], file_of: dict[str, str]) -> list[Problem]:
    """Cycles are legal (energy -> jobs -> pops -> food -> energy). An unnamed one is a warning,
    a cycle without any link leading out of it an error: nobody could ever act on it."""
    problems = []
    for component in _components(nodes):
        members = set(component)
        if len(members) == 1 and component[0] not in _edges(nodes[component[0]], nodes):
            continue
        where = file_of[component[0]]
        names = {nodes[m].get("circle") for m in members}
        label = " -> ".join(component)
        if not any(t not in members for m in members for t in _edges(nodes[m], nodes)):
            problems.append(Problem("error", where, f"cycle without an exit: {label}"))
        elif len(names) != 1 or None in names:
            problems.append(
                Problem("warning", where, f"cycle not marked with one `circle` name: {label}")
            )
    return problems


def _components(nodes: dict[str, dict[str, Any]]) -> list[list[str]]:
    """Strongly connected components (Tarjan), each in a stable order; recursion depth is the
    longest link chain, a few dozen nodes."""
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    result: list[list[str]] = []

    def visit(name: str) -> None:
        index[name] = low[name] = len(index)
        stack.append(name)
        on_stack.add(name)
        for target in _edges(nodes[name], nodes):
            if target not in index:
                visit(target)
                low[name] = min(low[name], low[target])
            elif target in on_stack:
                low[name] = min(low[name], index[target])
        if low[name] == index[name]:
            component = []
            while True:
                member = stack.pop()
                on_stack.discard(member)
                component.append(member)
                if member == name:
                    break
            result.append(sorted(component))

    for name in sorted(nodes):
        if name not in index:
            visit(name)
    return result
