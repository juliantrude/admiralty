"""Game icons for a Solution Graph (docs/plans/M6-revision.md).

knowledge/<version>/icons.yaml names, per node, a file inside the Player's Stellaris install
(written by tools/gen_icons.py). At compose time the icons are read from that install, turned into
small PNGs and embedded in the graph as data URIs, so the page needs no game files and the
repository holds no game graphics. Goals get a green upward arrow over their resource icon. The
model never sees the image data: it writes the overlay, the CLI composes and embeds.

No cache: decoding one 20 to 60 px DDS takes about 10 ms, a Briefing has about 50 nodes.
"""

from __future__ import annotations

import base64
import io
from pathlib import Path
from typing import Any

import yaml

from hlidskjalf.graph.mechanics import KNOWLEDGE_ROOT

ICON_PX = 44  # drawn at 22 px; twice that keeps it sharp on high-density screens


def icon_paths(version: str, root: Path | None = None) -> dict[str, str]:
    path = (root or KNOWLEDGE_ROOT) / version.removeprefix("v") / "icons.yaml"
    if not path.exists():
        return {}
    return (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("icons", {})


def _png(image) -> str:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def _with_arrow(image):
    """The Goal mark: a green arrow pointing up in the lower right corner."""
    from PIL import ImageDraw

    draw = ImageDraw.Draw(image)
    s = image.width
    tip, base, half = (s * 0.80, s * 0.48), s * 0.98, s * 0.17
    draw.polygon(
        [(tip[0], tip[1]), (tip[0] + half, s * 0.72), (tip[0] - half, s * 0.72)],
        fill=(70, 220, 120, 255),
        outline=(10, 40, 20, 255),
    )
    draw.rectangle(
        [tip[0] - half * 0.45, s * 0.71, tip[0] + half * 0.45, base],
        fill=(70, 220, 120, 255),
        outline=(10, 40, 20, 255),
    )
    return image


def load_icon(file: Path, goal: bool = False) -> str | None:
    """A game icon file as a PNG data URI, or None when the file is missing or unreadable."""
    try:
        from PIL import Image

        with Image.open(file) as source:
            image = source.convert("RGBA")
    except OSError, ValueError:
        return None
    # icon sheets (several frames side by side) show their first frame
    if image.width >= 2 * image.height:
        image = image.crop((0, 0, image.height, image.height))
    image = image.resize((ICON_PX, ICON_PX))
    return _png(_with_arrow(image) if goal else image)


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
        uri = load_icon(install / rel, goal=node["type"] == "goal")
        if uri:
            node["icon"] = uri
            done += 1
    return done
