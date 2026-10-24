"""Command line: hlidskjalf extract | diff | mcp | setup (campaigns, players, write, check) | graph."""

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

    args = parser.parse_args(argv)
    if args.command == "graph":
        return _graph_validate(args)
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
