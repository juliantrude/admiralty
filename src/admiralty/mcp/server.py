"""MCP server: exposes a Campaign's Snapshot extracts to Claude Code as tools.

Run in a Campaign Workspace: `admiralty mcp` (stdio). Every number a Briefing states
must come from one of these tool results; each result is appended to the workspace turn
log so the Unverified Claim check can compare the answer against it.
"""

from __future__ import annotations

import functools
import inspect
import os
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer

from admiralty.mcp.service import CampaignService
from admiralty.workspace.config import CampaignConfig, SetupMissing

INSTRUCTIONS = """\
Admiralty reads the Player's Stellaris saves. Call campaign_status first in a turn: it
names the newest save, its in-game date and how old it is. If it says the save is stale,
ask the Player to save again or to say they want to work with this save; if they do, name its
age in one sentence and go on. Use only numbers and names from tool results; never derive
game values yourself. Fair Play: known_empires show only what the Player's intel shows.
"""


# Tools whose logged result carries its own turn-log id under this key.
NUMBERED = {"expand_graph": "expansion_id"}


def build_server(workspace: str | Path | None = None, warm_up: bool = False) -> MCPServer:
    root = Path(workspace or Path.cwd())
    server = MCPServer(name="admiralty", instructions=INSTRUCTIONS)
    holder: dict[str, CampaignService] = {}

    def service() -> CampaignService:
        # Loaded lazily so the server starts even before the Campaign Setup exists; the
        # tools then answer with what is missing.
        if "service" not in holder:
            holder["service"] = CampaignService(CampaignConfig.load(root))
        return holder["service"]

    def logged(func: Callable[..., dict[str, Any]]) -> Callable[..., dict[str, Any]]:
        @functools.wraps(func)
        def wrapper(**kwargs: Any) -> dict[str, Any]:
            try:
                svc = service()
            except SetupMissing as missing:
                return {"error": str(missing)}
            try:
                result = func(svc, **kwargs)
            except (LookupError, FileNotFoundError, ValueError) as error:
                result = {"error": str(error)}
            svc.log(
                func.__name__,
                {k: v for k, v in kwargs.items() if v is not None},
                result,
                number_key=NUMBERED.get(func.__name__),
            )
            return result

        # The tool's schema must not show the injected service parameter.
        signature = inspect.signature(func)
        wrapper.__signature__ = signature.replace(
            parameters=list(signature.parameters.values())[1:]
        )
        wrapper.__annotations__ = {k: v for k, v in func.__annotations__.items() if k != "svc"}
        return wrapper

    if warm_up:

        def warm() -> None:
            try:
                service().warm_up()
            except SetupMissing:
                pass

        threading.Thread(target=warm, name="admiralty-warm-up", daemon=True).start()

    @server.tool()
    @logged
    def campaign_status(svc: CampaignService) -> dict[str, Any]:
        """Newest save: file, in-game date, minutes since it was saved, game version,
        Tracked Empire, mode, Fair Play or God Mode, and version and mod warnings."""
        return svc.campaign_status()

    @server.tool()
    @logged
    def empire_overview(svc: CampaignService, save: str | None = None) -> dict[str, Any]:
        """Situation-level numbers for the Tracked Empire: resources (stockpile and monthly
        net), pops, colonies, naval capacity, next Tradition cost, wars.
        save: file name or in-game date of an older save; default the newest."""
        return svc.empire_overview(save)

    @server.tool()
    @logged
    def planets(svc: CampaignService, save: str | None = None) -> dict[str, Any]:
        """All colonies: designation, pops, unemployed, open jobs, stability, districts
        built and maximum per type, district limit."""
        return svc.planets(save)

    @server.tool()
    @logged
    def planet(svc: CampaignService, name: str, save: str | None = None) -> dict[str, Any]:
        """Full detail for one planet by Display Name, or "Name (System)" when names repeat:
        jobs with open slots, buildings, deposits and blockers, production and upkeep."""
        return svc.planet(name, save)

    @server.tool()
    @logged
    def economy(svc: CampaignService, save: str | None = None) -> dict[str, Any]:
        """Monthly income and expenses per resource, also broken down by source."""
        return svc.economy(save)

    @server.tool()
    @logged
    def military(svc: CampaignService, save: str | None = None) -> dict[str, Any]:
        """Fleets with power and composition, naval capacity with its sources, wars, and
        known empires (visible facts under Fair Play, full facts under God Mode)."""
        return svc.military(save)

    @server.tool()
    @logged
    def routes_to(svc: CampaignService, target: str, save: str | None = None) -> dict[str, Any]:
        """Static routes from the Tracked Empire to a target: a system or an empire, by Display
        Name. Routes that cross different sets of empires, shortest first; each lists its length,
        the empires crossed with the systems used and what is known about each (opinion, hostile,
        borders, relative power), and the path. Fair Play routes over the systems the Tracked
        Empire has found only. A route with needs_technology uses a wormhole or gateway that is
        not researched yet. Empty routes say why the target is unreachable."""
        return svc.routes_to(target, save)

    @server.tool()
    @logged
    def progression(svc: CampaignService, save: str | None = None) -> dict[str, Any]:
        """Traditions, next Tradition cost, ascension perks, edicts, policies, government,
        research in progress."""
        return svc.progression(save)

    @server.tool()
    @logged
    def timeline(
        svc: CampaignService,
        since: str | None = None,
        until: str | None = None,
        save: str | None = None,
    ) -> dict[str, Any]:
        """Timeline events of the Tracked Empire, optionally between two in-game dates
        (YYYY.MM.DD)."""
        return svc.timeline(since, until, save)

    @server.tool()
    @logged
    def compare(svc: CampaignService, older: str, newer: str | None = None) -> dict[str, Any]:
        """Diff between two saves of this Campaign (file names or in-game dates; newer
        defaults to the newest): resources, pops, planets gained or lost, wars, Timeline."""
        return svc.compare(older, newer)

    @server.tool()
    @logged
    def expand_graph(
        svc: CampaignService,
        goals: list[str] | None = None,
        crisis_goals: list[str] | None = None,
        save: str | None = None,
    ) -> dict[str, Any]:
        """Mechanics Graph for this save. Without goals: the catalogue of every Goal with
        title, domain and its Symptom metrics resolved. With goals (ids from the catalogue):
        the expansion into Causes, Remedies and Obstacles, each Obstacle checked against the
        save, Remedy status, Vicious Circles, ranked Key Action candidates, Playbook Rules,
        and expansion_id for `admiralty briefing compose`. crisis_goals: the Goals that
        answer a Crisis (ranked first). Keep to a few Goals per call: results are large."""
        return svc.expand_graph(goals, crisis_goals, save)

    @server.tool()
    @logged
    def retrospective(
        svc: CampaignService,
        since: str | None = None,
        until: str | None = None,
        save: str | None = None,
    ) -> dict[str, Any]:
        """Debrief's material for a look back, from the archive of every save that was read:
        per archived in-game date the series (planets, pops, power, naval capacity, resources,
        known empires), per interval the changes with percentages and years, the merged Timeline,
        boundary candidates for epochs (exact from the Timeline, or between two archived dates),
        finding candidates and, in Consulting, the Goals' Symptoms at both ends of the frame.
        since: in-game date (YYYY.MM.DD) or "all"; default the last two archived dates.
        until: in-game date. Dates are moved to archived dates and the result names them."""
        return svc.retrospective(since, until, save)

    # The Academy (Coaching Campaigns only; a Consulting Campaign gets an error answer).

    @server.tool()
    @logged
    def academy_open(svc: CampaignService, goals: list[str] | None = None) -> dict[str, Any]:
        """Start or continue the Drill, the first Academy call of a turn. Checks for a newer save,
        runs the Snapshot rules on the Player Model (`changes`: level changes and drops to say
        openly, `ask_once` to ask), names decisions the save announces or shows (`announced`,
        `happened`), the Rendezvous position, and returns the current topic with its Hint Ladder
        level and how many topics wait. The topic carries no Cause and no answer until the Ladder
        reaches its top level. goals: Goal ids the Player named; without them (and no open Drill)
        the answer lists the Goals to pick from."""
        return svc.academy.academy_open(goals)

    @server.tool()
    @logged
    def academy_attempt(
        svc: CampaignService,
        outcome: str,
        text: str | None = None,
        domain_named: bool = True,
        support: dict[str, Any] | None = None,
        situation: str | None = None,
    ) -> dict[str, Any]:
        """Report the outcome of the Player's answer to the current topic: cause, remedy, support,
        miss, partial, full_explanation or escape_hatch. The tool moves the Hint Ladder and the
        Player Model; the answer says where the Ladder stands and what to announce. support: for
        outcome `support` the figure of the Snapshot the answer rests on, {path, op, value};
        text: the Player's answer in a sentence. domain_named: False when the question did not
        name the domain. situation: required with escape_hatch."""
        return svc.academy.academy_attempt(outcome, text, domain_named, support, situation)

    @server.tool()
    @logged
    def academy_next(svc: CampaignService) -> dict[str, Any]:
        """Next topic: skips the current one unless it is over. `finished` when none waits."""
        return svc.academy.academy_next()

    @server.tool()
    @logged
    def academy_escape(
        svc: CampaignService, situation: str, concepts: list[str] | None = None
    ) -> dict[str, Any]:
        """The Player asks to just be told: Ladder level 4, the answer is revealed, the Escape
        Hatch is recorded with its Situation (what the Player was doing when asking).
        concepts: further Cause ids a full Briefing the Player asked for covered."""
        return svc.academy.academy_escape(situation, concepts)

    @server.tool()
    @logged
    def academy_close(svc: CampaignService, summary: str) -> dict[str, Any]:
        """End the Drill with the summary of what the Player means to do (two or three
        sentences). Answers with the proposed Rendezvous (`proposal`) and the one agreed, if any."""
        return svc.academy.academy_close(summary)

    @server.tool()
    @logged
    def prediction_add(
        svc: CampaignService,
        kind: str,
        sentence: str,
        check_date: str | None = None,
        basis: str = "foretold",
        subject: str | None = None,
        concepts: list[str] | None = None,
        expect: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Store the Player's Prediction: one sentence about what a decision will achieve. kind:
        war, ascension_perk, tradition_tree, megastructure, federation or world_designation.
        check_date: in-game date, at most five years ahead (default two years). basis: foretold
        (before the decision) or hindsight. expect: {path, op, value} on the extract, to be
        decided by the data. concepts: Cause ids a confirmed Prediction counts for."""
        return svc.academy.prediction_add(
            kind, sentence, check_date, basis, subject, concepts, expect
        )

    @server.tool()
    @logged
    def prediction_check(
        svc: CampaignService,
        id: str | None = None,
        verdict: str | None = None,
        note: str | None = None,
    ) -> dict[str, Any]:
        """Check the open Predictions against the saves: those whose date has come and that carry a
        measurable expectation are decided; `needs_verdict` lists those the Player must judge.
        id and verdict (confirmed, refuted, unclear) store the Player's verdict on one Prediction."""
        return svc.academy.prediction_check(id, verdict, note)

    @server.tool()
    @logged
    def rendezvous_set(
        svc: CampaignService, date: str, save_name: str | None = None
    ) -> dict[str, Any]:
        """Agree on the Rendezvous (the proposal of academy_close or the Player's own date, at most
        five years ahead) or move it. `unchecked` lists open Predictions due after it."""
        return svc.academy.rendezvous_set(date, save_name)

    @server.tool()
    @logged
    def player_model(svc: CampaignService) -> dict[str, Any]:
        """What the Coach knows about the Player: every Cause with its level, drops and Escape
        Hatch uses, and the latest events with their reasons. Read only."""
        return svc.academy.player_model()

    return server


def run(workspace: str | Path | None = None) -> None:
    # Claude Code starts plugin servers from the plugin directory; the Campaign Workspace
    # is the project the session runs in.
    workspace = workspace or os.environ.get("CLAUDE_PROJECT_DIR") or Path.cwd()
    build_server(workspace, warm_up=True).run("stdio")
