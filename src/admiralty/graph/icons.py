"""Game icons for a Solution Graph (docs/plans/M6-revision.md).

knowledge/<version>/icons.yaml names, per node, a file inside the Player's Stellaris install
(written by tools/gen_icons.py). At compose time the icons are read from that install, turned into
small PNGs and embedded in the graph as data URIs, so the page needs no game files and the
repository holds no game graphics. Goals get their mark (arrow up, arrow down or flag) over their resource icon. The
model never sees the image data: it writes the overlay, the CLI composes and embeds.

No cache: decoding one 20 to 78 px DDS takes about 10 ms, a Briefing has about 50 nodes.
"""

from __future__ import annotations

import base64
import io
from pathlib import Path
from typing import Any

import yaml

from admiralty.graph.mechanics import KNOWLEDGE_ROOT

ICON_PX = 88  # drawn at 44 px; twice that keeps it sharp on high-density screens


def icon_paths(version: str, root: Path | None = None) -> dict[str, str]:
    path = (root or KNOWLEDGE_ROOT) / version.removeprefix("v") / "icons.yaml"
    if not path.exists():
        return {}
    return (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("icons", {})


def _png(image) -> str:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


_GREEN = (70, 220, 120, 255)
_RED = (240, 90, 90, 255)
_OUTLINE = (10, 40, 20, 255)


def _with_mark(image, mark: str):
    """The Goal mark in the lower right corner: a green arrow up for more, a red arrow down for
    less, a flag for a state to reach (docs/plans/grilling.md topic 7)."""
    from PIL import ImageDraw

    draw = ImageDraw.Draw(image)
    s = image.width
    x, half = s * 0.80, s * 0.17
    if mark == "flag":
        draw.rectangle([x - half, s * 0.48, x - half * 0.7, s * 0.98], fill=_OUTLINE)
        draw.polygon(
            [(x - half * 0.7, s * 0.48), (x + half * 1.2, s * 0.58), (x - half * 0.7, s * 0.68)],
            fill=(250, 200, 60, 255),
            outline=_OUTLINE,
        )
        return image
    up = mark == "up"
    fill = _GREEN if up else _RED
    tip, root, base = (s * 0.48, s * 0.72, s * 0.98) if up else (s * 0.98, s * 0.74, s * 0.48)
    draw.polygon([(x, tip), (x + half, root), (x - half, root)], fill=fill, outline=_OUTLINE)
    draw.rectangle(
        [x - half * 0.45, min(root, base), x + half * 0.45, max(root, base)],
        fill=fill,
        outline=_OUTLINE,
    )
    return image


def load_icon(file: Path, mark: str | None = None) -> str | None:
    """A game icon file as a PNG data URI, or None when the file is missing or unreadable. A Goal
    passes its `mark` (up, down, flag) and gets it drawn over the icon."""
    try:
        from PIL import Image

        with Image.open(file) as source:
            image = source.convert("RGBA")
    except OSError, ValueError:
        return None
    # icon sheets (several frames side by side) show their first frame
    if image.width >= 2 * image.height:
        image = image.crop((0, 0, image.height, image.height))
    # most game icons are 20 to 78 px: Lanczos keeps the upscaled ones as crisp as they can be
    image = image.resize((ICON_PX, ICON_PX), Image.Resampling.LANCZOS)
    return _png(_with_mark(image, mark) if mark else image)


def embed_icons(doc: dict[str, Any], install: Path | None, version: str) -> int:
    """Give every graph node of `doc` its game icon as `icon`; returns how many it embedded.
    Model-added nodes and nodes without an icon keep the page's placeholder."""
    if install is None:
        return 0
    paths = icon_paths(version)
    done = 0
    for node in doc["nodes"]:
        rel = paths.get(node["id"])
        if node.get("source") != "graph" or not rel:
            continue
        uri = load_icon(install / rel, mark=node["mark"] if node["type"] == "goal" else None)
        if uri:
            node["icon"] = uri
            done += 1
    return done
