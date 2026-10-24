"""Reading a Stellaris save file into its two parsed parts, meta and gamestate."""

from __future__ import annotations

import gc
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import rust_parser


@dataclass(frozen=True)
class Save:
    path: Path
    meta: dict[str, Any]
    gamestate: dict[str, Any]


def load_save(path: str | Path) -> Save:
    """Parse a .sav file. The gamestate goes through the Rust parser's file reader;
    meta is small, so we read it from the zip ourselves and parse it as a string."""
    path = Path(path)
    with zipfile.ZipFile(path) as archive:
        meta_text = archive.read("meta").decode("utf-8")
    meta = rust_parser.parse_save_from_string(meta_text)
    # Building millions of small dicts triggers the cyclic garbage collector over and
    # over although none of them can form cycles yet; pausing it saves about a quarter.
    collecting = gc.isenabled()
    gc.disable()
    try:
        gamestate = rust_parser.parse_save_file(str(path))
    finally:
        if collecting:
            gc.enable()
    return Save(path=path, meta=meta, gamestate=gamestate)
