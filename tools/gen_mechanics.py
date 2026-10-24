"""Regenerate knowledge/<version>/generated/*.yaml from the installed game.

    uv run python tools/gen_mechanics.py [--out DIR]

Exit code 1 when a source with facts has no Display Name and is not listed in
tools/gen_mechanics_allow_unnamed.txt (the names are in generated/unresolved.txt).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from hlidskjalf.extract.names import Localisation
from hlidskjalf.game import GameEnvironment
from hlidskjalf.gamefiles import GameData
from hlidskjalf.graph.generator import game_version, generate, load_allow_list, write

ROOT = Path(__file__).resolve().parent.parent
ALLOW_UNNAMED = Path(__file__).with_name("gen_mechanics_allow_unnamed.txt")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--out", type=Path, help="output folder (default knowledge/<version>/generated)"
    )
    args = parser.parse_args(argv)

    env = GameEnvironment.detect()
    version = game_version(env.install_dir)
    out = args.out or ROOT / "knowledge" / version.removeprefix("v") / "generated"
    game = GameData(env.install_dir)
    loc = Localisation.from_files(env.localisation_files())

    generated = generate(game, loc, load_allow_list(ALLOW_UNNAMED))
    write(generated, out)
    total = sum(len(facts) for facts in generated.facts.values())
    print(f"{version}: {total} facts in {len(generated.facts)} files -> {out}")
    if game.errors:
        print(
            f"{len(game.errors)} game files did not parse, e.g. {game.errors[0]}", file=sys.stderr
        )
    if generated.unresolved:
        print(
            f"{len(generated.unresolved)} sources have no Display Name (see unresolved.txt); "
            f"list internal ones in {ALLOW_UNNAMED.name} with a reason",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
