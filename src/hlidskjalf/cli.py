"""Command line: hlidskjalf extract <save> [--empire NAME] [--detail]."""

from __future__ import annotations

import argparse
import json
import sys
import time

from hlidskjalf.extract.diff import diff_extracts
from hlidskjalf.extract.snapshot import Extractor


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

    args = parser.parse_args(argv)
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


if __name__ == "__main__":
    raise SystemExit(main())
