"""The concepts of the Player Model: the Causes of the loaded Mechanics Graph (M9, decision 1).

A concept is a Cause node. The Mastery Levels are defined by "found the cause", "a Snapshot shows
the Remedy done" and "the cause reappears", so the Cause is the unit; its Remedies are the evidence
of Apply and its Obstacles belong to the Remedies. Goals, Remedies and Obstacles have no level.

`signature` is what the patch rule compares between two versions of the graph: the Cause's
formula (the generated facts it links to) and its links. A changed title, description or number
leaves the signature as it is.
"""

from __future__ import annotations

from dataclasses import dataclass

from admiralty.graph.mechanics import MechanicsGraph


@dataclass(frozen=True)
class Concept:
    id: str
    title: str
    version: str
    domain: str
    facts: tuple[str, ...]
    causes: tuple[str, ...]
    remedies: tuple[str, ...]
    obstacles: tuple[str, ...]

    @property
    def signature(self) -> tuple[tuple[str, ...], ...]:
        return (
            tuple(sorted(self.facts)),
            tuple(sorted(self.causes)),
            tuple(sorted(self.remedies)),
            tuple(sorted(self.obstacles)),
        )


def concepts(graph: MechanicsGraph) -> dict[str, Concept]:
    """Every Cause of the graph by id, in graph order."""
    return {
        node_id: Concept(
            id=node_id,
            title=node["title"],
            version=graph.version,
            domain=node_id.split(".", 1)[0],
            facts=tuple(node.get("facts", [])),
            causes=tuple(node.get("causes", [])),
            remedies=tuple(node.get("remedies", [])),
            obstacles=tuple(node.get("obstacles", [])),
        )
        for node_id, node in graph.nodes.items()
        if node["type"] == "cause"
    }
