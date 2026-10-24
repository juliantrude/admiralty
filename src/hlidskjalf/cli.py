"""Command line: hlidskjalf extract | diff | mcp | setup (campaigns, players, write, check) | graph |
briefing."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from hlidskjalf.extract.diff import diff_extracts
from hlidskjalf.extract.snapshot import Extractor
from hlidskjalf.workspace.config import KNOWLEDGE, MODES


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hlidskjalf")
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
    compose.add_argument("--out", type=Path, required=True)
    compose.add_argument("--knowledge-root", type=Path, help="default: knowledge/ of the plugin")

    view = briefing.add_parser(
        "view",
        help="look at a solution-graph.json in the browser (local server, publishes nothing)",
    )
    view.add_argument("file", type=Path)
    view.add_argument("--port", type=int, default=0, help="default: a random free port")

    args = parser.parse_args(argv)
    if args.command == "graph":
        if args.graph_command == "check-solution":
            return _check_solution(args)
        return _graph_validate(args)
    if args.command == "briefing":
        return _view(args) if args.briefing_command == "view" else _compose(args)
    if args.command == "setup":
        return _setup(args)
    if args.command == "mcp":
        from hlidskjalf.mcp.server import run

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
        "setup", help="Campaign Setup (used by the hlidskjalf:setup skill; JSON on stdout)"
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
        "--reset-archive", action="store_true", help="move archive/ aside if the empire changes"
    )

    check = setup.add_parser("check", help="report problems of a workspace (exit 1 if any)")
    check.add_argument("--workspace", default=".")


def _graph_validate(args) -> int:
    from hlidskjalf.graph.mechanics import GraphMissing, validate

    try:
        problems = validate(args.version, args.knowledge_root)
    except GraphMissing as error:
        print(f"hlidskjalf graph: {error}", file=sys.stderr)
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
        raise SystemExit(f"hlidskjalf: cannot read {what} {path}: {error}") from error


def _load_graph(version: str, root: Path | None):
    from hlidskjalf.graph.mechanics import GraphInvalid, GraphMissing, MechanicsGraph

    try:
        return MechanicsGraph.load(version, root)
    except (GraphMissing, GraphInvalid) as error:
        raise SystemExit(f"hlidskjalf: {error}") from error


def _read_expansion(workspace: Path, expansion_id: int) -> dict:
    from hlidskjalf.workspace.turnlog import read_entry

    try:
        entry = read_entry(workspace, expansion_id)
    except (LookupError, ValueError) as error:
        raise SystemExit(f"hlidskjalf: cannot read expansion {expansion_id}: {error}") from error
    result = entry.get("result")
    if entry.get("tool") != "expand_graph" or not isinstance(result, dict) or "nodes" not in result:
        raise SystemExit(
            f"hlidskjalf: turn-log entry {expansion_id} is not an expansion "
            f"(tool {entry.get('tool')!r}); use the expansion_id of an expand_graph call with goals"
        )
    return result


def _check_solution(args) -> int:
    from hlidskjalf.graph.solution import validate_solution_graph

    doc = _read_json(args.file, "solution graph")
    version = doc.get("game_version") if isinstance(doc, dict) else None
    graph = _load_graph(version or "v4.5.2", args.knowledge_root)
    problems = validate_solution_graph(doc, graph, graph.rules)
    for problem in problems:
        print(problem)
    print(f"{len(problems)} error(s)")
    return 1 if problems else 0


def _compose(args) -> int:
    from hlidskjalf.graph.solution import SolutionInvalid, compose

    if (args.expansion is None) == (args.expansion_id is None):
        raise SystemExit("hlidskjalf: give either an expansion file or --expansion-id")
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
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "out": str(args.out),
                "nodes": len(doc["nodes"]),
                "key_actions": [a["node"] for a in doc["key_actions"]],
            },
            indent=1,
        )
    )
    return 0


def _view(args) -> int:
    from hlidskjalf.graph.view import ViewUnavailable, serve

    try:
        serve(args.file, args.port)
    except (ViewUnavailable, OSError) as error:
        print(f"hlidskjalf briefing view: {error}", file=sys.stderr)
        return 1
    return 0


def _setup(args) -> int:
    """Every answer is JSON on stdout; a refused answer is a plain message on stderr, exit 1."""
    from hlidskjalf.game import save_root
    from hlidskjalf.workspace import setup
    from hlidskjalf.workspace.config import SetupMissing
    from hlidskjalf.workspace.layout import NotAWorkspace

    try:
        if args.setup_command == "campaigns":
            root = Path(args.save_root).expanduser() if args.save_root else save_root()
            result = {"save_root": str(root), "campaigns": setup.list_campaigns(root)}
        elif args.setup_command == "players":
            result = setup.describe_save(Path(args.save_dir_or_save))
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
                reset_archive=args.reset_archive,
            )
        else:
            problems = setup.check_workspace(Path(args.workspace))
            json.dump({"ok": not problems, "problems": problems}, sys.stdout, indent=1)
            print()
            return 1 if problems else 0
    except (setup.SetupRefused, SetupMissing, NotAWorkspace, FileNotFoundError) as error:
        print(f"hlidskjalf setup: {error}", file=sys.stderr)
        return 1
    json.dump(result, sys.stdout, ensure_ascii=False, indent=1)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
