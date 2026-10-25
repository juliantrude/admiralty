"""Choose a game icon for every node of the curated Mechanics Graph and write icons.yaml.

    uv run python tools/gen_icons.py [--version v4.5.2]

Developer tool (docs/plans/M6-revision.md). A node's icon comes from the first of its `facts`
whose game object has an icon: a fact id reads `<domain>.<kind>.<object>.<what>`, and the object's
icon is looked up the way the game does it, through the sprites in interface/*.gfx (GFX_<object>
or the definition's own `icon`) or the icon folder of its kind. A node without such a fact, and
every Goal, gets its domain's resource icon. The result maps node id -> path inside the game
install; it names files only and holds no game graphics, which never enter this repository. The
Briefing embeds the images at compose time from the Player's own install.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

from hlidskjalf.game import GameEnvironment
from hlidskjalf.gamefiles import GameData
from hlidskjalf.graph.mechanics import KNOWLEDGE_ROOT, MechanicsGraph

ICONS = "gfx/interface/icons"
# Where the game keeps the icons of a kind of object, and the category of its definitions.
KINDS = {
    "job": ("jobs", "pop_jobs", ["job_{id}"]),
    "building": ("buildings", "buildings", ["{id}"]),
    "technology": ("technologies", "technology", ["{id}"]),
    "tradition": ("traditions", "traditions", ["{id}"]),
    "ascension_perk": ("ascension_perks", "ascension_perks", ["{id}"]),
    "district": ("districts", "districts", ["{id}"]),
    "edict": ("edicts", "edicts", ["{id}"]),
    "policy": ("policies", "policies", ["{id}"]),
    "starbase_module": ("modules", "starbase_modules", ["sb_{id}", "{id}"]),
    "starbase_building": ("modules", "starbase_buildings", ["sb_{id}", "{id}"]),
}
# The icon of a domain: its resource where it has one, else the closest planet icon.
DOMAIN_ICON = {
    "alloys": f"{ICONS}/resources/alloys.dds",
    "energy": f"{ICONS}/resources/energy.dds",
    "minerals": f"{ICONS}/resources/minerals.dds",
    "food": f"{ICONS}/resources/food.dds",
    "unity": f"{ICONS}/resources/unity.dds",
    "influence": f"{ICONS}/resources/influence.dds",
    "research": f"{ICONS}/resources/physics_research.dds",
    "amenities": f"{ICONS}/planet_amenities.dds",
    "housing": f"{ICONS}/planet_housing.dds",
    "pop_growth": f"{ICONS}/pop.dds",
    "jobs": f"{ICONS}/pop_job.dds",
    "slots": f"{ICONS}/building_icon.dds",
    "naval_capacity": f"{ICONS}/fleet_size_icon.dds",
    "stability": f"{ICONS}/stability.dds",
}
SPRITE = re.compile(r'name\s*=\s*"(?P<name>[^"]+)"\s*texturefile\s*=\s*"(?P<file>[^"]+)"', re.I)


def sprite_index(install: Path) -> dict[str, str]:
    """Sprite name -> texture file, from every interface/*.gfx."""
    index: dict[str, str] = {}
    for path in sorted((install / "interface").rglob("*.gfx")):
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        for match in SPRITE.finditer(text):
            index.setdefault(match.group("name"), match.group("file").replace("\\", "/"))
    return index


def object_icon(
    kind: str, object_id: str, game: GameData, sprites: dict, install: Path
) -> str | None:
    if kind not in KINDS:
        return None
    folder, category, patterns = KINDS[kind]
    definition = game.category(category).get(object_id)
    own = definition.get("icon") if isinstance(definition, dict) else None
    names = [p.format(id=object_id) for p in patterns]
    if isinstance(own, str):
        names.insert(0, own.removeprefix("GFX_"))
    for name in names:
        for candidate in (sprites.get(f"GFX_{name}"), f"{ICONS}/{folder}/{name}.dds"):
            if candidate and (install / candidate).exists():
                return candidate
    return None


def choose(
    graph: MechanicsGraph, game: GameData, install: Path
) -> tuple[dict[str, str], list[str]]:
    sprites = sprite_index(install)
    icons: dict[str, str] = {}
    fallback: list[str] = []
    for goal_id in sorted(graph.goals):
        if goal_id.split(".")[0] in DOMAIN_ICON:
            icons[goal_id] = DOMAIN_ICON[goal_id.split(".")[0]]
    for node_id, node in sorted(graph.nodes.items()):
        domain = node_id.split(".")[0]
        found = None
        if node.get("type") != "goal":
            fact_ids = [f.get("id", "") for f in graph.node_facts(node_id)] or node.get("facts", [])
            for fact in fact_ids:
                parts = fact.split(".")
                if len(parts) >= 3:
                    found = object_icon(parts[1], parts[2], game, sprites, install)
                if found:
                    break
        if not found:
            found = DOMAIN_ICON.get(domain)
            if node.get("type") != "goal":
                fallback.append(node_id)
        if found:
            icons[node_id] = found
    return icons, fallback


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--version", default="v4.5.2")
    args = parser.parse_args(argv)
    env = GameEnvironment.detect()
    graph = MechanicsGraph.load(args.version)
    icons, fallback = choose(graph, GameData(env.install_dir), env.install_dir)
    missing = sorted((set(graph.nodes) | set(graph.goals)) - set(icons))
    out = KNOWLEDGE_ROOT / args.version.removeprefix("v") / "icons.yaml"
    header = (
        "# Game icon per node: a path inside the Player's Stellaris install, never a copy of the\n"
        "# image. Written by tools/gen_icons.py; correct a line by hand if the match is poor.\n"
    )
    out.write_text(
        header + yaml.safe_dump({"version": args.version, "icons": icons}, sort_keys=True)
    )
    print(
        f"{len(icons)} icons, {len(fallback)} from the domain fallback, {len(missing)} without icon"
    )
    for node_id in missing:
        print("  no icon:", node_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
