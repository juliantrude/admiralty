"""Download the pinned engine libraries into the git-ignored cache and check their SRI hashes.

    uv run python tools/fetch_engine_libs.py [--dest DIR] [--force]

Reads engine/pins.json. The cache (default tests/fixtures/engine-libs/) is what the headless-browser
tests load instead of the CDN, so they never touch the network on their own. A file whose hash does
not match is deleted and the run fails.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PINS = ROOT / "engine" / "pins.json"
CACHE = ROOT / "tests" / "fixtures" / "engine-libs"


def load_pins(path: Path = PINS) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["libraries"]


def sri(data: bytes) -> str:
    return "sha384-" + base64.b64encode(hashlib.sha384(data).digest()).decode("ascii")


def fetch(pin: dict, dest: Path, force: bool = False) -> str:
    """Returns "cached" or "downloaded"; raises ValueError when the hash does not match."""
    target = dest / pin["file"]
    if target.exists() and not force and sri(target.read_bytes()) == pin["integrity"]:
        return "cached"
    with urllib.request.urlopen(pin["url"], timeout=60) as response:
        data = response.read()
    got = sri(data)
    if got != pin["integrity"]:
        raise ValueError(
            f"{pin['name']} {pin['version']}: hash {got} does not match the pin {pin['integrity']}"
        )
    dest.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return "downloaded"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dest", type=Path, default=CACHE)
    parser.add_argument(
        "--force", action="store_true", help="download again even if the cache is valid"
    )
    args = parser.parse_args(argv)
    failed = False
    for pin in load_pins():
        try:
            state = fetch(pin, args.dest, args.force)
        except (ValueError, OSError) as error:
            print(f"FAIL {pin['name']}@{pin['version']}: {error}", file=sys.stderr)
            failed = True
        else:
            print(f"{state:10} {pin['name']}@{pin['version']} -> {args.dest / pin['file']}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
