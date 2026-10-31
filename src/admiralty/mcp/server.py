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

    return server


def run(workspace: str | Path | None = None) -> None:
    # Claude Code starts plugin servers from the plugin directory; the Campaign Workspace
    # is the project the session runs in.
    workspace = workspace or os.environ.get("CLAUDE_PROJECT_DIR") or Path.cwd()
    build_server(workspace, warm_up=True).run("stdio")
