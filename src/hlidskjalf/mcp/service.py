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

from hlidskjalf.extract import empire as data
from hlidskjalf.extract.diff import diff_extracts
from hlidskjalf.extract.snapshot import Extractor, Snapshot
from hlidskjalf.workspace.config import CampaignConfig

TURN_LOG = "turn-log.jsonl"
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
                self._documents[key] = self.snapshot(ref).document(planet_detail)
                while len(self._documents) > 32:
                    self._documents.popitem(last=False)
            return self._documents[key]

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
            "warnings": list(header["warnings"]),
            "saves_available": len(self.saves()),
        }
        if age > STALE_AFTER_SECONDS:
            status["save_is_stale"] = True
            status["warnings"].append(
                f"The newest save is {round(age / 60)} minutes old. Ask the Player to save "
                "again before answering about the current situation."
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
            "note": "Monthly values of the last complete month.",
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

    # --- turn log ---------------------------------------------------------------------------

    def log(self, tool: str, args: dict[str, Any], result: Any) -> None:
        state = self.config.state_dir
        state.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": datetime.now(UTC).isoformat(timespec="seconds"),
            "tool": tool,
            "args": args,
            "result": result,
        }
        with open(state / TURN_LOG, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
