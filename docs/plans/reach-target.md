# Reaching a target (block 3, increments 11 to 13)

Source: `docs/proposals/ops.md` entry 10. A Goal that needs a target the Tracked Empire cannot reach
("The target is neither reachable nor assessed") is not solved by "Build warships": the way there
crosses other empires, and the model cannot know them (the extract only says `shares_border`).
Routing therefore runs in the Python core, without a model.

## 11. The map the Tracked Empire may use (`extract/galaxy.py`)

What the save stores, checked on Mireesh 2294.01.01 (591 systems):

- `galactic_object[id]`: `name`, `coordinate` (x, y), `hyperlane` (list of `to`, `length`; every lane
  is stored on both ends; `bridge = yes` marks the lanes that joined the map's partitions at
  generation, see `map/setup_scenarios/*.txt` `min_bridges`; they are ordinary lanes), `bypasses`
  (ids), `starbases`.
- Owner of a system: the owner of its starbase's station ship (`starbase_mgr.starbases[id].station`
  → `ships[station].fleet` → `fleet_owner`). All 416 systems of the `sectors` table agree; 118
  more systems have an owner without a sector. Only countries of type `default` count as empires.
- Known systems (Fair Play): `country[id].terra_incognita.systems` is the list of systems the
  empire has found, not the list of unknown ones: all 23 systems with the Player's starbases and
  every system of the 9 contacted empires' starbases but a few are in it. `data` is a run-length
  coded 256x256 fog bitmap and is not needed. God Mode ignores the list.
- `bypasses[id]`: `type` (`wormhole`, `gateway`), `active`, `linked_to` (wormhole), `connections` and
  `active_connections` (gateway), `lock_remaining_days`, `is_manual_lock`, `lock_country`. A system
  lists the bypasses it holds in `bypasses`. Rules from `common/bypass/00_bypasses.txt`: a wormhole
  needs `tech_wormhole_stabilization` and must have been explored (we take: both ends known);
  a gateway needs `tech_gateway_activation` and is active only when the save says so.

Result: `Galaxy` with systems (name, position, owner, known) and links (hyperlane, wormhole,
gateway), already filtered for the knowledge mode. Names go through `ctx.name`, never a raw key.

## 12. Routes (`extract/routes.py`, MCP tool `routes_to`)

Dijkstra on the links; for each empire crossed once, ban it and search again; routes that cross the
same set of empires count once. Each route lists length (hyperlane length, bypass jumps count as
0), the empires crossed in order, and each empire's attitude from `known_empires` (opinion,
hostile, borders, power band). A target that is unreachable says so and why (no known path, only
through a locked bypass). Check on Mireesh 2294.01.01 against the Swarm and against United
Wi-Zerakian Authority, which Julian names as a second way.

Done: see `docs/proposals/ops.md` entry 10 for the check. The game spells it Wi-Zirakian.

## 13. Every Cause has a Remedy (`graph check-solution`, page, skill)

A Cause on the way from an Obstacle to a Goal with no fitting Remedy is marked unresolved in the
Solution Graph (not hidden), `check-solution` reports it, the skill tells the model to name it.
