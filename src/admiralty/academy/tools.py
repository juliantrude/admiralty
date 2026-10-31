"""The Academy tools (M9, `docs/plans/M9.md` 20h): what the Coach calls, in the MCP server and under `admiralty academy`.

One class, `AcademyTools`, sits on a `CampaignService` (`service.academy`). Each method is one tool, takes plain
arguments and returns a JSON dict; the server and the CLI log the result in the turn log, so the Unverified Claim
check sees it. The tools only exist in a Coaching Campaign: a Consulting one gets `NotCoaching`, an error answer.

    academy_open        the first call of a Coaching turn: ingest, newest save, the checks that follow from a new
                        Snapshot (Player Model evidence, decisions announced or made), the Rendezvous position,
                        and the Drill: continued when one is open, else opened from the Goals the Player names
    academy_attempt     the Coach reports the outcome of the Player's answer to the current topic
    academy_next        the next topic ("next topic" skips the current one)
    academy_escape      the Escape Hatch, with its Situation
    academy_close       end the Drill with the summary; proposes the Rendezvous
    prediction_add      store a Prediction; prediction_check: due ones are decided, the Player's verdict is stored
    rendezvous_set      agree on the date (the proposal or the Player's own) or move it
    player_model        read only: what the Coach knows about the Player

What the model sees is cut here, not in the modules below: the current topic carries no `concept` key and no
`answer` until the Hint Ladder is on its top level (or the topic is over), because the key names the Cause and the
answer is the Cause with its Remedies. A topic never carries its title. The pointers carry the visible figures and,
where the table of `ui_locations.yaml` has one, where in the game to look.

Choices where the plan is silent, each pinned by a test:
- `support` is checked as `{path, op, value}` against the Snapshot the Drill runs on: the figure the Player's own
  answer rests on. A path the Tracked Empire cannot see under Fair Play is refused; a path without a number is not
  backed (`ask_where`), never an error.
- `escape_hatch` through `academy_attempt` is the same as `academy_escape` (the Situation is required).
- Continuing a Drill reports a newer save (`newer_save`) and changes nothing else; a Drill is bound to its Snapshot.
- Evidence (Apply, Create, drop) is decided when a Drill is opened, from every archived Snapshot, for the concepts the
  Player Model knows and the Coach ever raised here; it is idempotent.
- `rendezvous_set` takes the date; the proposal is what `academy_close` returns.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from admiralty.academy import drill, ladder, locations, predictions, rendezvous, topics
from admiralty.debrief.frame import load_campaign
from admiralty.graph.expand import catalogue
from admiralty.graph.mechanics import MechanicsGraph
from admiralty.graph.metrics import dig
from admiralty.player import concepts as concept_list
from admiralty.player import evidence, store
from admiralty.player.mastery import Refused

if TYPE_CHECKING:
    from admiralty.mcp.service import CampaignService

COACHING = "coaching"
RECENT_EVENTS = 20


class NotCoaching(ValueError):
    """The Academy tools were called in a Consulting Campaign."""


class AcademyTools:
    def __init__(self, service: CampaignService):
        self.service = service

    # --- the Drill ------------------------------------------------------------------------

    def academy_open(self, goals: list[str] | None = None) -> dict[str, Any]:
        self._coaching()
        svc = self.service
        status = svc.campaign_status()
        ref = svc.newest()
        doc = svc.document(ref)
        graph = svc.graph(doc["header"]["game_version"])
        date = doc["header"]["date"]
        workspace = svc.config.workspace
        result: dict[str, Any] = {
            "save_file": status["save_file"],
            "in_game_date": date,
            "saved_minutes_ago": status["saved_minutes_ago"],
            "warnings": status["warnings"],
            "mode": svc.config.mode,
            "knowledge": svc.config.knowledge,
            "rendezvous": rendezvous.position(workspace, date),
        }
        if status.get("save_is_stale"):
            result["save_is_stale"] = True
        open_drill = drill.load(workspace)
        if open_drill is not None:
            if open_drill["date"] != date:
                result["newer_save"] = {"in_game_date": date, "drill_date": open_drill["date"]}
            return {**result, "continued": True, **self._present(drill.view(workspace), graph)}

        loaded = load_campaign(svc.archive).documents
        result["changes"] = self._update_evidence(graph, loaded, doc["header"]["campaign"])
        result.update(self._decisions(date, doc, loaded))
        if not goals:
            return {
                **result,
                "drill": None,
                "needs_goals": True,
                "goals": [
                    {k: g[k] for k in ("id", "domain", "title")} for g in catalogue(graph, doc)
                ],
            }
        built = topics.build_topics(
            graph, doc, goals, model=store.read_model(), god_mode=svc.config.god_mode
        )
        if not built["topics"]:
            return {
                **result,
                "drill": None,
                "nothing_to_ask": True,
                "skipped": built["skipped"],
                "unknown_goals": built["unknown_goals"],
            }
        opened = drill.open_drill(
            workspace,
            date=date,
            topics=built["topics"],
            campaign=doc["header"]["campaign"],
            extract=doc,
            goals=built["goals"],
        )
        return {
            **result,
            "continued": False,
            "count": built["count"],
            "skipped": built["skipped"],
            "unknown_goals": built["unknown_goals"],
            **self._present(opened, graph),
        }

    def academy_attempt(
        self,
        outcome: str,
        text: str | None = None,
        domain_named: bool = True,
        support: dict[str, Any] | None = None,
        situation: str | None = None,
    ) -> dict[str, Any]:
        self._coaching()
        if outcome == "escape_hatch":
            return self.academy_escape(situation or "")
        workspace = self.service.config.workspace
        current = self._open_drill()
        extract = self._drill_extract(current)
        supported = None
        checked = None
        if outcome == "support":
            checked = check_support(support, extract, self.service.config.god_mode)
            supported = checked["supported"]
        result = drill.attempt(
            workspace,
            outcome,
            domain_named=domain_named,
            supported=supported,
            text=text,
            situation=situation,
        )
        graph = self._graph(extract)
        if checked is not None:
            result["support_check"] = checked
        result["announce"] = [self._titled(graph, result, e) for e in result["announce"]]
        return self._present(result, graph)

    def academy_next(self) -> dict[str, Any]:
        self._coaching()
        result = drill.next_topic(self.service.config.workspace)
        return self._present(result, self._graph(self._drill_extract(self._open_drill())))

    def academy_escape(self, situation: str, concepts: list[str] | None = None) -> dict[str, Any]:
        self._coaching()
        workspace = self.service.config.workspace
        current = drill.load(workspace)
        extract = (
            self._drill_extract(current)
            if current
            else self.service.document(self.service.newest())
        )
        graph = self._graph(extract)
        result = drill.escape(
            workspace, situation, concepts=concepts or (), known=concept_list.concepts(graph)
        )
        return self._present(result, graph)

    def academy_close(self, summary: str) -> dict[str, Any]:
        self._coaching()
        svc = self.service
        workspace = svc.config.workspace
        current = self._open_drill()
        graph = self._graph(self._drill_extract(current))
        closed = drill.close(workspace, summary)
        for entry in closed["topics"]:
            if entry["status"] == "done":
                entry["title"] = graph.node(entry["concept"])["title"]
            else:
                del entry["concept"]  # a topic that was not finished keeps its answer hidden
        today = svc.document(svc.newest())["header"]["date"]
        proposal = rendezvous.propose(today, predictions.listing(workspace))
        return {
            **closed,
            "proposal": proposal,
            "agreed": rendezvous.load(workspace),
        }

    # --- Predictions and the Rendezvous ------------------------------------------------------

    def prediction_add(
        self,
        kind: str,
        sentence: str,
        check_date: str | None = None,
        basis: str = "foretold",
        subject: str | None = None,
        concepts: list[str] | None = None,
        expect: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._coaching()
        svc = self.service
        doc = svc.document(svc.newest())
        graph = self._graph(doc)
        return predictions.add(
            svc.config.workspace,
            kind=kind,
            sentence=sentence,
            made=doc["header"]["date"],
            check_date=check_date,
            basis=basis,
            subject=subject,
            concepts=concepts or (),
            known=concept_list.concepts(graph),
            expect=expect,
            extract=doc,
            campaign=doc["header"]["campaign"],
        )

    def prediction_check(
        self, id: str | None = None, verdict: str | None = None, note: str | None = None
    ) -> dict[str, Any]:
        self._coaching()
        svc = self.service
        workspace = svc.config.workspace
        doc = svc.document(svc.newest())
        today = doc["header"]["date"]
        if id or verdict:
            if not (id and verdict):
                raise Refused("a verdict needs the Prediction `id` and the `verdict`")
            return {"decided_by_player": predictions.decide(
                workspace, id, verdict, date=today, note=note
            )}  # fmt: skip
        loaded = load_campaign(svc.archive).documents
        checked = predictions.check_due(
            workspace, list(loaded.items()), campaign=doc["header"]["campaign"]
        )
        return {
            "date": today,
            **checked,
            "open": [
                {k: p[k] for k in ("id", "kind", "sentence", "basis", "check_date")}
                for p in predictions.listing(workspace, state="open")
            ],
        }

    def rendezvous_set(self, date: str, save_name: str | None = None) -> dict[str, Any]:
        self._coaching()
        svc = self.service
        workspace = svc.config.workspace
        today = svc.document(svc.newest())["header"]["date"]
        return rendezvous.set_rendezvous(
            workspace,
            date,
            today=today,
            predictions=predictions.listing(workspace),
            save_name_=save_name,
        )

    # --- the Player Model ----------------------------------------------------------------------

    def player_model(self) -> dict[str, Any]:
        """What the Coach knows about the Player, read only. Level changes, drops and Escape Hatch uses with the
        reason each was written for."""
        self._coaching()
        svc = self.service
        graph = self._graph(svc.document(svc.newest()))
        model = store.read_model()
        entries = []
        for concept, state in sorted(model["concepts"].items()):
            known = concept in graph.nodes
            entries.append(
                {
                    "concept": concept,
                    "title": graph.node(concept)["title"] if known else None,
                    **state,
                    **({} if known else {"in_this_version": False}),
                }
            )
        counts = {level: 0 for level in store.LEVELS}
        for entry in entries:
            counts[entry["level"]] = counts.get(entry["level"], 0) + 1
        events = store.events()
        return {
            "concepts": entries,
            "counts": counts,
            "events": len(events),
            "recent": events[-RECENT_EVENTS:],
        }

    # --- helpers ---------------------------------------------------------------------------------

    def _coaching(self) -> None:
        if self.service.config.mode != COACHING:
            raise NotCoaching(
                "The Academy works in a Coaching Campaign; this one is a Consulting Campaign. "
                "Ask the Player to set up a Coaching Campaign (admiralty:setup) to use it."
            )

    def _graph(self, extract: dict[str, Any]) -> MechanicsGraph:
        return self.service.graph(extract["header"]["game_version"])

    def _open_drill(self) -> dict[str, Any]:
        current = drill.load(self.service.config.workspace)
        if current is None:
            raise drill.DrillError("no Drill is open")
        return current

    def _drill_extract(self, current: dict[str, Any] | None) -> dict[str, Any]:
        """The Snapshot the Drill runs on, from the archive; the newest save when it is not archived."""
        svc = self.service
        if current is not None and svc.archive.has(current["date"]):
            return svc.archive.load(current["date"])
        return svc.document(svc.newest())

    def _update_evidence(
        self, graph: MechanicsGraph, loaded: dict[str, dict[str, Any]], campaign: str
    ) -> list[dict[str, Any]]:
        """Run the Snapshot rules (Apply, Create, drop) for every concept the Player Model knows or the Coach raised
        here. Returns what the Coach says openly (level changes, drops) and what it asks once."""
        workspace = self.service.config.workspace
        wanted = [
            *store.read_model()["concepts"],
            *drill.raised_concepts(workspace),
        ]
        snapshots = list(loaded.items())
        changes: list[dict[str, Any]] = []
        for concept in dict.fromkeys(wanted):
            if concept not in graph.nodes or not snapshots:
                continue
            result = evidence.record_evidence(
                graph,
                concept,
                snapshots,
                campaign=campaign,
                **drill.evidence_inputs(workspace, concept),
            )
            if result["events"]:
                academy = drill.academy_dir(workspace)
                academy.mkdir(parents=True, exist_ok=True)
                drill.copy_events(academy, result["events"])
            title = graph.node(concept)["title"]
            for effect in result["effects"]:
                if effect["effect"] in ("level", "drop", "ask_once"):
                    changes.append({"concept": concept, "title": title, **effect})
        return changes

    def _decisions(
        self, date: str, doc: dict[str, Any], loaded: dict[str, dict[str, Any]]
    ) -> dict[str, Any]:
        """Decisions the newest Snapshot announces and the ones it shows against the Snapshot before it."""
        workspace = self.service.config.workspace
        existing = predictions.listing(workspace)
        found: dict[str, Any] = {"announced": predictions.detect_before(doc, existing)}
        earlier = [d for d in loaded if d < date]
        if earlier:
            found["happened"] = predictions.detect_after(loaded[max(earlier)], doc, existing)
        found["open_predictions"] = [
            {k: p[k] for k in ("id", "kind", "sentence", "check_date")}
            for p in existing
            if p["state"] == "open" and p["basis"] == "foretold"
        ]
        return found

    @staticmethod
    def _titled(
        graph: MechanicsGraph, result: dict[str, Any], effect: dict[str, Any]
    ) -> dict[str, Any]:
        """A level change after an attempt is announced with the Cause's title: the Player has just named it."""
        topic = result["topic"]
        if topic is None or topic["concept"] not in graph.nodes:
            return effect
        return {**effect, "about": graph.node(topic["concept"])["title"]}

    def _present(self, view: dict[str, Any], graph: MechanicsGraph) -> dict[str, Any]:
        """The view of the Drill as the model gets it: no key and no answer before the Ladder reaches it."""
        topic = view.get("topic")
        if topic is None:
            return view
        shown = {k: v for k, v in topic.items() if k not in ("weight", "raised")}
        concept = shown.pop("concept")
        if topic["ladder"] == ladder.TOP or topic["status"] == "done":
            shown["concept"] = concept
            shown["answer"] = _answer(graph, concept)
        shown["pointers"] = [
            _with_location(graph, shown["domain"], pointer) for pointer in shown.get("pointers", [])
        ]
        return {**view, "topic": shown}


def check_support(
    support: dict[str, Any] | None, extract: dict[str, Any], god_mode: bool
) -> dict[str, Any]:
    """Check the figure a `support` answer rests on against the Snapshot: `{path, op, value}`.

    Returns `{"supported", "path", "found"}`. Raises `Refused` for a malformed `support`, an unknown operator or a
    path the Tracked Empire cannot see (Fair Play); a path without a number is simply not backed.
    """
    if not isinstance(support, dict) or set(support) != {"path", "op", "value"}:
        raise Refused(
            "a `support` answer names the figure of the Snapshot it rests on: {path, op, value}"
        )
    path, op, value = support["path"], support["op"], support["value"]
    if op not in predictions.OPERATORS:
        raise Refused(f"unknown operator {op!r}; known: {', '.join(predictions.OPERATORS)}")
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise Refused("`support.value` is a number")
    if not god_mode and topics.is_hidden(str(path)):
        raise Refused(f"{path} is not visible to the Tracked Empire; the answer cannot rest on it")
    found = dig(extract, str(path))
    if not isinstance(found, int | float) or isinstance(found, bool):
        return {"supported": False, "path": path, "found": None}
    return {
        "supported": bool(predictions.OPERATORS[op](found, value)),
        "path": path,
        "found": found,
    }


def _answer(graph: MechanicsGraph, concept: str) -> dict[str, Any]:
    """The Cause with its Remedies: what the Coach may explain once the Ladder is on its top level."""
    node = graph.node(concept)
    return {
        "title": node["title"],
        "description": node["description"],
        "remedies": [
            {"id": r, "title": graph.node(r)["title"], "judgement": graph.node(r).get("judgement")}
            for r in node.get("remedies", [])
        ],
    }


def _with_location(graph: MechanicsGraph, domain: str, pointer: dict[str, Any]) -> dict[str, Any]:
    try:
        found = locations.where(domain, pointer["metric"], version=graph.version)
    except locations.LocationUnknown:
        return pointer
    return {**pointer, "where": found.path}
