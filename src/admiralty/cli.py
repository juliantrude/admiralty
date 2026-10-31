"""Command line: admiralty extract | diff | mcp | watch | setup (campaigns, players, autosave, write, check) | graph |
briefing | claims | blocks | hook."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from admiralty.extract.diff import diff_extracts
from admiralty.extract.snapshot import Extractor
from admiralty.workspace.config import KNOWLEDGE, MODES


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="admiralty")
    commands = parser.add_subparsers(dest="command", required=True)

    extract = commands.add_parser("extract", help="print the Snapshot extract of a save")
    extract.add_argument("save")
    extract.add_argument("--empire", help="player name, empire name or country id")
    extract.add_argument("--detail", action="store_true", help="include per-planet detail")

    diff = commands.add_parser("diff", help="compare two saves of the same Campaign")
    diff.add_argument("older")
    diff.add_argument("newer")
    diff.add_argument("--empire")

    mcp = commands.add_parser("mcp", help="run the MCP server on stdio")
    mcp.add_argument("--workspace", help="Campaign Workspace directory (default: cwd)")

    watch = commands.add_parser(
        "watch", help="the save service: copy every new save of the game while it runs"
    )
    watch.add_argument("--once", action="store_true", help="look once and exit")
    watch.add_argument("--interval", type=float, default=30, help="seconds between looks")
    watch.add_argument("--save-root", help="default: the 'save games' folder of the game")
    watch.add_argument("--data-dir", help="default: ~/.local/share/admiralty")
    unit = watch.add_subparsers(dest="watch_command", metavar="{install,uninstall,status}")
    for name, text in (
        ("install", "run the save service as a systemd user unit, started with the session"),
        ("uninstall", "stop the save service unit and remove it"),
        ("status", "is the unit running, and how many saves wait in the inbox"),
    ):
        sub = unit.add_parser(name, help=text)
        sub.add_argument("--unit-dir", help="default: ~/.config/systemd/user")
        sub.add_argument("--data-dir", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
        if name == "install":
            sub.add_argument("--save-root", default=argparse.SUPPRESS, help="written into the unit")

    _add_setup_commands(commands)

    graph = commands.add_parser("graph", help="the Mechanics Graph").add_subparsers(
        dest="graph_command", required=True
    )
    validate = graph.add_parser(
        "validate", help="check knowledge/<version>/graph (exit 1 if any error)"
    )
    validate.add_argument("--version", default="v4.5.2")
    validate.add_argument("--knowledge-root", type=Path, help="default: knowledge/ of the plugin")
    check_solution = graph.add_parser(
        "check-solution", help="validate a solution-graph.json (exit 1 if any error)"
    )
    check_solution.add_argument("file", type=Path)
    check_solution.add_argument(
        "--knowledge-root", type=Path, help="default: knowledge/ of the plugin"
    )

    briefing = commands.add_parser("briefing", help="Briefing files").add_subparsers(
        dest="briefing_command", required=True
    )
    compose = briefing.add_parser(
        "compose", help="build solution-graph.json from an expansion and the model's overlay"
    )
    compose.add_argument("expansion", type=Path, nargs="?", help="JSON of expand_graph")
    compose.add_argument(
        "--expansion-id",
        type=int,
        help="read the expansion from this turn-log entry (the expansion_id of expand_graph) "
        "instead of a file",
    )
    compose.add_argument(
        "--workspace", type=Path, default=Path.cwd(), help="Campaign Workspace (default: cwd)"
    )
    compose.add_argument("overlay", type=Path, help="JSON the model wrote")
    compose.add_argument(
        "--out",
        type=Path,
        help="write the Solution Graph here; default: it becomes the current Briefing of the "
        "workspace and the one it replaces moves into the history",
    )
    compose.add_argument("--knowledge-root", type=Path, help="default: knowledge/ of the plugin")
    compose.add_argument(
        "--no-open",
        action="store_true",
        help="do not open the current Briefing in the browser (it is not opened with --out)",
    )

    view = briefing.add_parser(
        "view",
        help="look at a solution-graph.json in the browser (local server, publishes nothing)",
    )
    view.add_argument("file", type=Path)
    view.add_argument("--port", type=int, default=0, help="default: a random free port")
    view.add_argument("--open", action="store_true", help="open the page in the browser")
    view.add_argument(
        "--idle-timeout", type=float, help="end after this many seconds without a request"
    )

    claims = commands.add_parser("claims", help="the Unverified Claim check").add_subparsers(
        dest="claims_command", required=True
    )
    claims_check = claims.add_parser(
        "check",
        help="check an answer against the turn log (exit 1 if any claim is unverified)",
    )
    claims_check.add_argument("--workspace", type=Path, default=Path.cwd())
    claims_check.add_argument(
        "--answer", type=Path, required=True, help="file holding the answer text"
    )
    claims_check.add_argument(
        "--transcript", type=Path, help="Claude Code transcript: the Player's messages count too"
    )
    claims_check.add_argument(
        "--since",
        help="only turn log entries from this ISO time on (default: the transcript start)",
    )

    blocks = commands.add_parser(
        "blocks", help="the log of the Unverified Claim check"
    ).add_subparsers(dest="blocks_command", required=True)
    blocks_summary = blocks.add_parser(
        "summary", help="group .admiralty/blocks.jsonl by kind and reason code (JSON)"
    )
    blocks_summary.add_argument("--workspace", type=Path, default=Path.cwd())

    debrief = commands.add_parser("debrief", help="the retrospective").add_subparsers(
        dest="debrief_command", required=True
    )
    check_epochs = debrief.add_parser(
        "check-epochs",
        help="check proposed epochs against the Timeline and the archived intervals (JSON, exit 1 on error)",
    )
    check_epochs.add_argument("--workspace", type=Path, default=Path.cwd())
    check_epochs.add_argument("--epochs", type=Path, required=True, help="epochs.json")
    check_epochs.add_argument(
        "--since", help="frame start: an in-game date, `last` (default) or `all`"
    )
    check_epochs.add_argument(
        "--until", help="frame end: an in-game date (default: the newest archived)"
    )

    hook = commands.add_parser("hook", help="Claude Code hooks (stdin: the hook event)")
    hook_events = hook.add_subparsers(dest="hook_event", required=True)
    hook_events.add_parser("stop", help="Unverified Claim check on the final answer")

    args = parser.parse_args(argv)
    if args.command == "hook":
        from admiralty.claims.hook import stop

        return stop(sys.stdin, sys.stdout)
    if args.command == "claims":
        return _claims_check(args)
    if args.command == "debrief":
        return _check_epochs(args)
    if args.command == "blocks":
        from admiralty.claims.blocks import summarise

        json.dump(summarise(args.workspace), sys.stdout, ensure_ascii=False, indent=1)
        print()
        return 0
    if args.command == "graph":
        if args.graph_command == "check-solution":
            return _check_solution(args)
        return _graph_validate(args)
    if args.command == "briefing":
        return _view(args) if args.briefing_command == "view" else _compose(args)
    if args.command == "watch":
        return _watch(args)
    if args.command == "setup":
        return _setup(args)
    if args.command == "mcp":
        from admiralty.mcp.server import run

        run(args.workspace)
        return 0

    extractor = Extractor()
    start = time.perf_counter()
    if args.command == "extract":
        result = extractor.extract(args.save, args.empire, planet_detail=args.detail)
    else:
        result = diff_extracts(
            extractor.extract(args.older, args.empire), extractor.extract(args.newer, args.empire)
        )
    json.dump(result, sys.stdout, ensure_ascii=False, indent=1)
    print(f"\n# {time.perf_counter() - start:.2f} s", file=sys.stderr)
    return 0


def _add_setup_commands(commands) -> None:
    setup = commands.add_parser(
        "setup", help="Campaign Setup (used by the admiralty:setup skill; JSON on stdout)"
    ).add_subparsers(dest="setup_command", required=True)

    campaigns = setup.add_parser(
        "campaigns", help="list the Campaigns in the Stellaris save folder"
    )
    campaigns.add_argument("--save-root", help="default: the 'save games' folder of the game")

    players = setup.add_parser("players", help="list the players and empires of a Campaign")
    players.add_argument("save_dir_or_save", help="Campaign folder (newest save) or one .sav file")

    write = setup.add_parser(
        "write", help="create the workspace, write campaign.yaml and CLAUDE.md"
    )
    write.add_argument("--workspace", required=True)
    write.add_argument("--save-dir", required=True)
    write.add_argument("--empire", required=True, help="player name, empire name or country id")
    write.add_argument("--mode", default="consulting", choices=MODES)
    write.add_argument("--knowledge", default="fair_play", choices=KNOWLEDGE)
    write.add_argument("--ally", action="append", default=[], metavar="NAME")
    write.add_argument("--rival", action="append", default=[], metavar="NAME")
    write.add_argument("--no-backup", action="store_true", help="do not copy saves into saves/")
    write.add_argument(
        "--save-service",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="the Player's answer to the offer of the save service (default: keep the earlier one)",
    )
    write.add_argument(
        "--reset-archive", action="store_true", help="move archive/ aside if the empire changes"
    )

    autosave = setup.add_parser(
        "autosave", help="the game's autosave interval and a hint (never changes the game)"
    )
    autosave.add_argument("--user-dir", help="default: the game's data folder")

    check = setup.add_parser("check", help="report problems of a workspace (exit 1 if any)")
    check.add_argument("--workspace", default=".")


def _graph_validate(args) -> int:
    from admiralty.graph.mechanics import GraphMissing, validate

    try:
        problems = validate(args.version, args.knowledge_root)
    except GraphMissing as error:
        print(f"admiralty graph: {error}", file=sys.stderr)
        return 1
    errors = [p for p in problems if p.severity == "error"]
    for problem in problems:
        print(problem)
    print(f"{len(errors)} error(s), {len(problems) - len(errors)} warning(s)")
    return 1 if errors else 0


def _read_json(path: Path, what: str):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise SystemExit(f"admiralty: cannot read {what} {path}: {error}") from error


def _load_graph(version: str, root: Path | None):
    from admiralty.graph.mechanics import GraphInvalid, GraphMissing, MechanicsGraph

    try:
        return MechanicsGraph.load(version, root)
    except (GraphMissing, GraphInvalid) as error:
        raise SystemExit(f"admiralty: {error}") from error


def _read_expansion(workspace: Path, expansion_id: int) -> dict:
    from admiralty.workspace.turnlog import read_entry

    try:
        entry = read_entry(workspace, expansion_id)
    except (LookupError, ValueError) as error:
        raise SystemExit(f"admiralty: cannot read expansion {expansion_id}: {error}") from error
    result = entry.get("result")
    if entry.get("tool") != "expand_graph" or not isinstance(result, dict) or "nodes" not in result:
        raise SystemExit(
            f"admiralty: turn-log entry {expansion_id} is not an expansion "
            f"(tool {entry.get('tool')!r}); use the expansion_id of an expand_graph call with goals"
        )
    return result


def _claims_check(args) -> int:
    from datetime import datetime

    from admiralty.claims.check import check_answer
    from admiralty.claims.evidence import build_evidence, read_transcript, read_turn_log

    try:
        answer = args.answer.read_text(encoding="utf-8")
        since = datetime.fromisoformat(args.since) if args.since else None
    except (OSError, ValueError) as error:
        raise SystemExit(f"admiralty claims: {error}") from error
    started, player = read_transcript(args.transcript) if args.transcript else (None, [])
    evidence = build_evidence(read_turn_log(args.workspace, since or started), player)
    verdict = check_answer(answer, evidence)
    json.dump(verdict.to_dict(), sys.stdout, ensure_ascii=False, indent=1)
    print()
    return 0 if verdict.ok else 1


def _check_epochs(args) -> int:
    from admiralty.debrief.epochs import candidates_for_frame, check_epochs, place_events
    from admiralty.debrief.frame import FrameError, load_campaign, resolve_frame
    from admiralty.workspace.archive import Archive

    epochs = _read_json(args.epochs, "epochs")
    loaded = load_campaign(Archive(args.workspace))
    try:
        frame = resolve_frame(loaded.dates, args.since, args.until)
    except FrameError as error:
        print(f"admiralty debrief: {error}", file=sys.stderr)
        return 1
    material = candidates_for_frame(loaded, frame)
    result = check_epochs(epochs, material["candidates"], frame.start, frame.end)
    if not result["errors"]:
        result["epoch_titles"] = [e["title"] for e in epochs]
        result["events_by_epoch"] = place_events(epochs, material["timeline"]["events"])
    result = {"frame": {"from": frame.start, "to": frame.end, "request": frame.request}, **result}
    if not result["errors"]:
        # the titles an accepted proposal names are evidence for the Unverified Claim check
        _log_result(args.workspace, "debrief_check_epochs", _logged_args(args), result)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=1)
    print()
    return 1 if result["errors"] else 0


def _check_solution(args) -> int:
    from admiralty.graph.solution import unresolved_notes, validate_solution_graph

    doc = _read_json(args.file, "solution graph")
    version = doc.get("game_version") if isinstance(doc, dict) else None
    graph = _load_graph(version or "v4.5.2", args.knowledge_root)
    problems = validate_solution_graph(doc, graph, graph.rules)
    for problem in problems:
        print(problem)
    notes = unresolved_notes(doc) if not problems else []
    for note in notes:
        print(note)
    print(f"{len(problems)} error(s), {len(notes)} unresolved Cause(s)")
    return 1 if problems else 0


def _embed_icons(doc: dict, version: str, empires: dict | None = None) -> int:
    """Game icons and empire flags from the Player's install; without an install the page shows
    placeholders."""
    from admiralty.game import GameEnvironment
    from admiralty.graph.icons import embed_icons

    try:
        install = GameEnvironment.detect().install_dir
    except FileNotFoundError:
        return 0
    return embed_icons(doc, install, version, empires)


def _compose(args) -> int:
    from admiralty.graph.solution import SolutionInvalid, compose

    if (args.expansion is None) == (args.expansion_id is None):
        raise SystemExit("admiralty: give either an expansion file or --expansion-id")
    expansion = (
        _read_expansion(args.workspace, args.expansion_id)
        if args.expansion is None
        else _read_json(args.expansion, "expansion")
    )
    overlay = _read_json(args.overlay, "overlay")
    graph = _load_graph(expansion.get("version", "v4.5.2"), args.knowledge_root)
    try:
        doc = compose(expansion, overlay, graph)
    except SolutionInvalid as error:
        for problem in error.problems:
            print(problem, file=sys.stderr)
        return 1
    icons = _embed_icons(doc, expansion.get("version", "v4.5.2"), expansion.get("empires"))
    result: dict = {}
    if args.out is None:
        from admiralty.workspace import briefings

        archived = briefings.publish(args.workspace, overlay, doc)
        result = {
            "out": str(briefings.current_graph(args.workspace)),
            "replaced": str(archived) if archived else None,
        }
        if not args.no_open:
            from admiralty.graph.view import show_current

            result["view"] = show_current(args.workspace, briefings.current_graph(args.workspace))
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        result = {"out": str(args.out)}
    result |= {
        "nodes": len(doc["nodes"]),
        "icons": icons,
        "key_actions": [a["node"] for a in doc["key_actions"]],
    }
    print(json.dumps(result, indent=1))
    return 0


def _view(args) -> int:
    from admiralty.graph.view import ViewUnavailable, serve

    try:
        serve(args.file, args.port, open_browser=args.open, idle_seconds=args.idle_timeout)
    except (ViewUnavailable, OSError) as error:
        print(f"admiralty briefing view: {error}", file=sys.stderr)
        return 1
    return 0


def _watch_unit(args) -> int:
    from admiralty.workspace import watch_unit

    unit_dir = Path(args.unit_dir).expanduser() if args.unit_dir else None
    data_dir = Path(args.data_dir).expanduser() if args.data_dir else None
    try:
        if args.watch_command == "install":
            save_root = Path(args.save_root).expanduser() if args.save_root else None
            result = watch_unit.install(unit_dir, data_dir=data_dir, save_root=save_root)
        elif args.watch_command == "uninstall":
            result = watch_unit.uninstall(unit_dir)
        else:
            result = watch_unit.status(unit_dir, base=data_dir)
    except (watch_unit.UnitError, OSError) as error:
        print(f"admiralty watch {args.watch_command}: {error}", file=sys.stderr)
        return 1
    json.dump(result, sys.stdout, ensure_ascii=False, indent=1)
    print()
    return 0


def _watch(args) -> int:
    from admiralty.game import save_root
    from admiralty.workspace import registry, watch

    if args.watch_command:
        return _watch_unit(args)
    root = Path(args.save_root).expanduser() if args.save_root else save_root()
    base = Path(args.data_dir).expanduser() if args.data_dir else registry.data_dir()
    watcher = watch.Watcher(root, base)

    def report(copy: watch.Copy) -> None:
        print(f"{copy.source.parent.name}/{copy.source.name} -> {copy.target}", flush=True)

    if args.once:
        for copy in watcher.poll():
            report(copy)
        return 0
    print(f"watching {root} every {args.interval:g} s", file=sys.stderr, flush=True)
    try:
        watch.run(watcher, args.interval, report)
    except KeyboardInterrupt:
        return 0
    return 0


def _setup(args) -> int:
    """Every answer is JSON on stdout; a refused answer is a plain message on stderr, exit 1."""
    from admiralty.game import save_root, user_dir
    from admiralty.workspace import setup
    from admiralty.workspace.autosave import autosave_hint
    from admiralty.workspace.config import SetupMissing
    from admiralty.workspace.layout import NotAWorkspace

    try:
        if args.setup_command == "campaigns":
            root = Path(args.save_root).expanduser() if args.save_root else save_root()
            result = {"save_root": str(root), "campaigns": setup.list_campaigns(root)}
        elif args.setup_command == "players":
            result = setup.describe_save(Path(args.save_dir_or_save))
        elif args.setup_command == "autosave":
            result = autosave_hint(Path(args.user_dir) if args.user_dir else user_dir())
        elif args.setup_command == "write":
            result = setup.write_setup(
                Path(args.workspace),
                Path(args.save_dir),
                args.empire,
                mode=args.mode,
                knowledge=args.knowledge,
                allies=tuple(args.ally),
                rivals=tuple(args.rival),
                backup_saves=not args.no_backup,
                save_service=args.save_service,
                reset_archive=args.reset_archive,
            )
        else:
            problems = setup.check_workspace(Path(args.workspace))
            result = {"ok": not problems, "problems": problems}
            _log_setup_result(args, result)
            json.dump(result, sys.stdout, indent=1)
            print()
            return 1 if problems else 0
    except (setup.SetupRefused, SetupMissing, NotAWorkspace, FileNotFoundError) as error:
        print(f"admiralty setup: {error}", file=sys.stderr)
        return 1
    _log_setup_result(args, result)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=1)
    print()
    return 0


def _log_setup_result(args, result: dict) -> None:
    _log_result(
        getattr(args, "workspace", None), f"setup_{args.setup_command}", _logged_args(args), result
    )


def _logged_args(args) -> dict:
    skipped = {"command", "setup_command"}
    return {
        k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items() if k not in skipped
    }


def _log_result(workspace: Path | None, tool: str, params: dict, result: dict) -> None:
    """Put the result of a command that runs by shell into the workspace turn log, where the
    Unverified Claim check looks for evidence (only MCP calls land there by themselves).
    `campaigns` and `players` of the setup run before the workspace exists: they log into the
    current directory only if it is a workspace already or empty, so the log never turns another
    folder into a workspace."""
    from admiralty.workspace.layout import is_workspace
    from admiralty.workspace.turnlog import append_entry

    folder = Path(workspace or ".").expanduser()
    if not folder.is_dir() or not (is_workspace(folder) or not any(folder.iterdir())):
        return
    try:
        append_entry(folder, tool, params, result)
    except OSError:
        pass  # a log that cannot be written must not fail the command


if __name__ == "__main__":
    raise SystemExit(main())
