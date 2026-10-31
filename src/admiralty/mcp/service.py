"""The Campaign service behind the MCP tools: finds the newest save, caches what was
parsed, answers each tool with a slice of the Snapshot extract and logs every result to
the workspace turn log (read by the Unverified Claim check, M7)."""

from __future__ import annotations

import json
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from admiralty.debrief.frame import load_campaign, resolve_frame
from admiralty.debrief.result import build_result, goal_symptoms
from admiralty.extract import empire as data
from admiralty.extract.diff import diff_extracts
from admiralty.extract.snapshot import Extractor, Snapshot
from admiralty.graph.expand import catalogue, expand_graph
from admiralty.graph.mechanics import GraphInvalid, GraphMissing, MechanicsGraph
from admiralty.workspace.archive import Archive
from admiralty.workspace.config import CampaignConfig
from admiralty.workspace.turnlog import count_lines, turn_log_path

STALE_AFTER_SECONDS = 10 * 60  # a save older than this in real time: ask for a new one


@dataclass(frozen=True)
class SaveRef:
    path: Path
    mtime: float

    @property
    def age_seconds(self) -> float:
        return max(0.0, time.time() - self.mtime)


class CampaignService:
    def __init__(self, config: CampaignConfig, extractor: Extractor | None = None):
        self.config = config
        self.extractor = extractor or Extractor()
        # A parsed save takes several hundred MB, so only the latest one stays in memory;
        # finished extracts are small and kept per file and modification time.
        self._snapshot: tuple[SaveRef, Snapshot] | None = None
        self._documents: OrderedDict[tuple[str, float, bool], dict] = OrderedDict()
        self._lock = threading.RLock()  # the warm-up thread and tool calls share the caches
        self.archive = Archive(config.workspace)
        self._archive_warnings: dict[str, str] = {}  # save file name -> why it was not archived
        self._graphs: dict[str, MechanicsGraph] = {}  # by game version, loaded on first use
        self._log_lock = threading.Lock()

    def warm_up(self) -> None:
        """Load localisation, game files and the newest save ahead of the first question."""
        try:
            self.document(self.newest())
        except OSError, LookupError, ValueError:
            pass  # the first tool call reports the problem

    # --- saves --------------------------------------------------------------------------

    def saves(self) -> list[SaveRef]:
        refs = [SaveRef(p, p.stat().st_mtime) for p in self.config.save_dir.glob("*.sav")]
        return sorted(refs, key=lambda r: (r.mtime, r.path.name))

    def newest(self) -> SaveRef:
        refs = self.saves()
        if not refs:
            raise FileNotFoundError(f"no saves in {self.config.save_dir}")
        return refs[-1]

    def find(self, name: str | None) -> SaveRef:
        """A save by file name or in-game date prefix ('2259.12.25'); newest when None."""
        if not name:
            return self.newest()
        for ref in reversed(self.saves()):
            if ref.path.name == name or ref.path.stem.startswith(name):
                return ref
        raise FileNotFoundError(f"no save matching {name!r} in {self.config.save_dir}")

    def snapshot(self, ref: SaveRef) -> Snapshot:
        with self._lock:
            return self._snapshot_locked(ref)

    def _snapshot_locked(self, ref: SaveRef) -> Snapshot:
        if self._snapshot and self._snapshot[0] == ref:
            return self._snapshot[1]
        self._snapshot = None  # free the previous gamestate before parsing the next
        ctx = self.extractor.context(ref.path)
        snapshot = Snapshot(self.extractor, ctx, self.config.empire)
        self._snapshot = (ref, snapshot)
        return snapshot

    def document(self, ref: SaveRef, planet_detail: bool = False) -> dict[str, Any]:
        key = (str(ref.path), ref.mtime, planet_detail)
        with self._lock:
            if key not in self._documents:
                if planet_detail:
                    self.document(ref)  # every save that is read is archived, compact form
                self._documents[key] = self.snapshot(ref).document(planet_detail)
                if not planet_detail:
                    self._archive(ref, self._documents[key])
                while len(self._documents) > 32:
                    self._documents.popitem(last=False)
            return self._documents[key]

    def _archive(self, ref: SaveRef, doc: dict[str, Any]) -> None:
        """Keep the extract (always) and a copy of the save (unless backup_saves is off) in
        the workspace. Never fails the tool call: a problem goes to the turn log and to the
        warnings of campaign_status, since a missing archive only hurts Debrief later."""
        date = doc["header"]["date"]
        try:
            self.archive.store(doc, ref.mtime)
            if self.config.backup_saves:
                self.archive.backup(ref.path, date, ref.mtime)
        except (OSError, ValueError, KeyError) as error:
            message = f"Could not archive {ref.path.name}: {error}"
            self._archive_warnings[ref.path.name] = message
            self.log("archive", {"save": ref.path.name}, {"error": message})
        else:
            self._archive_warnings.pop(ref.path.name, None)

    # --- tools ----------------------------------------------------------------------------

    def campaign_status(self) -> dict[str, Any]:
        ref = self.newest()
        header = self.document(ref)["header"]
        age = ref.age_seconds
        status = {
            "save_file": ref.path.name,
            "in_game_date": header["date"],
            "saved_minutes_ago": round(age / 60, 1),
            "game_version": header["game_version"],
            "tracked_empire": header["tracked_empire"],
            "players": header["players"],
            "mode": self.config.mode,
            "knowledge": self.config.knowledge,
            "warnings": [*header["warnings"], *self._archive_warnings.values()],
            "saves_available": len(self.saves()),
        }
        if age > STALE_AFTER_SECONDS:
            status["save_is_stale"] = True
            status["warnings"].append(
                f"The newest save is {round(age / 60)} minutes old. Ask the Player to save "
                "again, or to say that they want to work with this save; if they do, name "
                "its age in one sentence and go on."
            )
        return status

    def empire_overview(self, save: str | None = None) -> dict[str, Any]:
        doc = self.document(self.find(save))
        return {
            "date": doc["header"]["date"],
            "empire": doc["empire"],
            "resources": {
                r: {k: v[k] for k in ("label", "stockpile", "net")}
                for r, v in doc["resources"].items()
            },
            "pops": doc["pops"],
            "colonies": len(doc["planets"]),
            "naval_capacity": {k: doc["naval_capacity"][k] for k in ("used", "max")},
            "next_tradition": {
                k: doc["progression"]["next_tradition"][k]
                for k in ("cost", "unity_stockpile", "affordable")
            },
            "wars": [w["name"] for w in doc["military"]["wars"]],
            "warnings": doc["header"]["warnings"],
        }

    def planets(self, save: str | None = None) -> dict[str, Any]:
        doc = self.document(self.find(save))
        return {
            "date": doc["header"]["date"],
            "planets": doc["planets"],
            "district_labels": doc["district_labels"],
        }

    def planet(self, name: str, save: str | None = None) -> dict[str, Any]:
        doc = self.document(self.find(save), planet_detail=True)
        wanted = name.casefold()
        matches = [
            p
            for p in doc["planets"]
            if p["name"].casefold() == wanted or f"{p['name']} ({p['system']})".casefold() == wanted
        ]
        if not matches:
            names = ", ".join(f"{p['name']} ({p['system']})" for p in doc["planets"])
            raise LookupError(f"no planet named {name!r}. Planets: {names}")
        return {
            "date": doc["header"]["date"],
            "planets": matches,
            "district_labels": doc["district_labels"],
        }

    def economy(self, save: str | None = None) -> dict[str, Any]:
        ref = self.find(save)
        doc = self.document(ref)
        snapshot = self.snapshot(ref)
        return {
            "date": doc["header"]["date"],
            "resources": doc["resources"],
            "by_source": data.economy_by_source(snapshot.ctx, snapshot.country),
            "note": "Monthly values as the top bar projects them, monthly market trades included.",
        }

    def military(self, save: str | None = None) -> dict[str, Any]:
        doc = self.document(self.find(save))
        empires = []
        for other in doc["known_empires"]:
            entry = {k: v for k, v in other.items() if k != "full"}
            if self.config.god_mode:
                entry["full"] = other["full"]
            empires.append(entry)
        return {
            "date": doc["header"]["date"],
            "naval_capacity": doc["naval_capacity"],
            "military_power": doc["empire"]["military_power"],
            "fleets": doc["military"]["fleets"],
            "wars": doc["military"]["wars"],
            "known_empires": empires,
            "knowledge": self.config.knowledge,
        }

    def progression(self, save: str | None = None) -> dict[str, Any]:
        doc = self.document(self.find(save))
        return {"date": doc["header"]["date"], **doc["progression"]}

    def timeline(
        self, since: str | None = None, until: str | None = None, save: str | None = None
    ) -> dict[str, Any]:
        ref = self.find(save)
        snapshot = self.snapshot(ref)
        events = data.timeline(snapshot.ctx, snapshot.country, since=since)
        if until:
            events = [e for e in events if e["date"] <= until]
        return {"date": self.document(ref)["header"]["date"], "events": events}

    def compare(self, older: str, newer: str | None = None) -> dict[str, Any]:
        a = self.document(self.find(older))
        b = self.document(self.find(newer))
        return diff_extracts(a, b)

    def graph(self, game_version: str) -> MechanicsGraph:
        """The Mechanics Graph of the save's game version, loaded once per server. A version
        without a knowledge pack raises GraphMissing: no silent fallback (ADR 0003)."""
        with self._lock:
            if game_version not in self._graphs:
                self._graphs[game_version] = MechanicsGraph.load(game_version)
            return self._graphs[game_version]

    def expand_graph(
        self, goals: list[str] | None = None, crisis_goals: list[str] | None = None,
        save: str | None = None,
    ) -> dict[str, Any]:  # fmt: skip
        ref = self.find(save)
        doc = self.document(ref)
        graph = self.graph(doc["header"]["game_version"])
        if not goals:
            return {
                "version": graph.version,
                "date": doc["header"]["date"],
                "goals": catalogue(graph, doc),
                "warnings": doc["header"]["warnings"],
            }
        expansion = expand_graph(graph, goals, doc, crisis_goals=crisis_goals or ())
        if expansion.unknown_goals:
            known = ", ".join(sorted(graph.goals))
            raise LookupError(
                f"unknown Goal(s) {', '.join(expansion.unknown_goals)}. Goals: {known}"
            )
        result = expansion.to_dict()
        result["warnings"] = [*doc["header"]["warnings"], *result["warnings"]]
        result["empires"] = self.snapshot(ref).empire_flags()
        result["expansion_id"] = None  # the turn-log line number, filled in by `log`
        return result

    def retrospective(
        self, since: str | None = None, until: str | None = None, save: str | None = None
    ) -> dict[str, Any]:
        """Debrief's material for a time frame, from the archive. The newest save is read first
        through the normal path so that it is archived; without any save on disk the archive
        alone answers. A save older than the newest archived date is read but the frame stays
        on the archive, and the result warns."""
        warnings: list[str] = []
        try:
            ref = self.find(save)
        except FileNotFoundError:
            if save:
                raise
            ref = None
        if ref is not None:
            read = self.document(ref)["header"]["date"]
        loaded = load_campaign(self.archive)
        if ref is None:
            newest = loaded.dates[-1] if loaded.dates else "none"
            warnings.append(
                f"No save in {self.config.save_dir}: the archive alone answers; its newest "
                f"in-game date is {newest}."
            )
        elif loaded.dates and read < loaded.dates[-1]:
            warnings.append(
                f"{ref.path.name} (in-game {read}) is older than the newest archived date "
                f"{loaded.dates[-1]}; the frame ends there. Read the newest save to refresh."
            )
        warnings.extend(self._archive_warnings.values())
        frame = resolve_frame(loaded.dates, since, until)
        goals = None
        if self.config.mode == "consulting":
            goals = self._goal_symptoms(loaded.documents[frame.start], loaded.documents[frame.end])
        return build_result(
            loaded, frame, mode=self.config.mode, god_mode=self.config.god_mode, goals=goals,
            warnings=warnings,
        )  # fmt: skip

    def _goal_symptoms(self, first: dict[str, Any], last: dict[str, Any]) -> dict[str, Any]:
        """`goals` of a retrospective; a missing or bad knowledge pack is an error in here only."""
        try:
            return goal_symptoms(self.graph(last["header"]["game_version"]), first, last)
        except (GraphMissing, GraphInvalid) as error:
            return {"error": str(error)}

    # --- turn log ---------------------------------------------------------------------------

    def log(
        self, tool: str, args: dict[str, Any], result: Any, number_key: str | None = None
    ) -> int:
        """Append one entry and return its id (line number). A result that already holds
        `number_key` (as a placeholder) gets the id there before it is written, so the entry
        and the tool answer agree."""
        path = turn_log_path(self.config.workspace)
        with self._log_lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            line = count_lines(path) + 1
            if number_key and isinstance(result, dict) and number_key in result:
                result[number_key] = line
            entry = {
                "ts": datetime.now(UTC).isoformat(timespec="seconds"),
                "tool": tool,
                "args": args,
                "result": result,
            }
            with open(path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return line
