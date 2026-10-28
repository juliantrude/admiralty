# Plan: check the grey Obstacles against Snapshot numbers

Goal: turn the 39 Obstacles with `check: {judgement_only: true}` into `check: {metric, op, compare_to}`
wherever the save and the game files allow it (`GOAL.md`, `docs/plans/grilling.md` topic 4).
Version 4.5.2, game files in `~/.local/share/Steam/steamapps/common/Stellaris/common`.

## How a check works today (what a new check has to fit)

- One comparison per Obstacle: `{metric, op, compare_to}`; `metric` is a name from
  `knowledge/4.5.2/graph/metrics.yaml` (a dotted path into the Snapshot extract, a `sum`, or a `ratio`).
- `present` when the comparison holds, `clear` when not, `unknown` when the extract has no value
  (`src/admiralty/graph/metrics.py`). `only_clears: true` means: the number can only rule the
  Obstacle out; where the comparison holds the answer stays `judgement`.
- Every metric path is tested against the reference extract (`tests/test_mechanics_graph.py`), so a
  new extract section needs its metrics registered in the same increment.
- A new computed value gets its own module in `src/admiralty/extract/computed/` with the formula and
  the game-file sources in the docstring (`CLAUDE.md`), and a test on `vulkan` and `zygerrian`.

## Counts: what the grilling said and what the files show

Grilling topic 4 counted 4 + 2 + 14 + 11 + 8 = 39. That count cannot be reproduced one to one from
the titles (the file does not record which Obstacle went where), so this plan re-sorts all 39 by what
the check needs. The result differs a little:

| Group | Grilling | Here | Why it moved |
|---|---|---|---|
| 1. Ascension perks and traditions | 4 | 4 | same |
| 2. Free job slots and free housing | 2 | 3 | `pop_growth.no_free_housing` is in the extract already (`free_housing` per planet) |
| 3. Unlocks | 14 | 16 | `slots.capital_upgrade_locked` and `naval_capacity.doctrine_prerequisites` are unlock questions |
| 4. Building and starbase slots | 11 | 9 | the grilling's eleven included Obstacles that this sort puts in group 2 or 5 |
| 5. Real trade-offs, no check | 8 | 7 | one of the grilling's eight turns out to have a number (it is in group 3 or 4 here) |

The Definition of Done (`GOAL.md`) is met by the plan, not by the counts: every Obstacle in groups 1
to 4 gets a check or a named reason, and group 5 stays `judgement_only`.

## Group 1: ascension perks and traditions (4)

| Obstacle | Metric (new) | Check | Save fields | Game files |
|---|---|---|---|---|
| `influence.no_ascension_slot` | `ascension.slots_free` = slots unlocked − perks taken | `== 0` | `country.ascension_perks`; slots from the Ledger key `ascension_perks_add` | `traditions/*` (`ascension_perks_add` in finish bonuses), `technology/00_soc_tech.txt:5960` (tech `ascension_perks_add = 1`), `defines/00_defines.txt:1226` `ASCENSION_PERKS_SLOTS = 8` as the cap |
| `unity.no_ascension_slot` | same metric | `== 0` | same | same |
| `naval_capacity.tradition_slot_taken` | `traditions.trees_free` = trees allowed − trees adopted | `== 0` | `country.tradition_categories` (already `progression.tradition_trees`) | `defines/00_defines.txt:1432` `TRADITION_CATEGORIES_MAX = 7`; the rule that unlocks further tree slots is **not yet found**, see Open questions |
| `research.discovery_tree_unfinished` | `traditions.discovery_left` = Discovery traditions in `tradition_categories_discovery` − adopted | `> 0` | `country.traditions` | `tradition_categories/00_discovery.txt` (list of the tree), `traditions/00_discovery.txt` |

Notes. The perk slot count is a computed value (not stored in the save): module
`extract/computed/ascension_slots.py`, reusing the Ledger of `computed/modifiers.py`, which already
collects modifiers from traditions, perks and techs. A full slot list means the Obstacle holds, so
`== 0` needs no flag; a free slot clears it. The perk's own technology prerequisite is not in the
Obstacle title and stays out of the number.
`traditions.discovery_left` counts the tree's traditions not yet adopted; a tree that is not adopted at
all gives the full tree size, which still fits "has Traditions left to take".

## Group 2: free job slots and free housing (3)

| Obstacle | Metric (new) | Check | Save fields | Game files |
|---|---|---|---|---|
| `amenities.no_amenity_slot` | `room.open_jobs_by_function.amenities` | `== 0` | `pop_jobs` table: `max_workforce`, `workforce` (as `room()` already reads them) | `pop_jobs/*`: jobs whose `planet_amenities_add` is set (entertainer, healthcare, clerk, see the Remedy facts) |
| `stability.no_order_slot` | `room.open_jobs_by_function.order` | `== 0` | same | `pop_jobs/*`: jobs whose `planet_stability_add` is set (soldier, enforcer, bureaucrat) |
| `pop_growth.no_free_housing` | `housing.free` = sum of `free_housing` over planets, clamped at 0 per planet | `== 0` | `planets[].free_housing` (extract) | none; the value is stored |

Notes. `room.open_jobs_by_output` groups jobs by produced resource and has no place for amenities or
order, so the function groups are a second table in the same `room` section, built with the same loop
(`extract/empire.py:282`). The mapping job → function is read from the job definition, not typed in.
"Free housing": the Obstacle title says the planets have none; the check is on the empire sum with
negative planets clamped at 0 so a crowded planet does not hide a free one.

## Group 3: unlocks (16)

Common rule, one module `extract/computed/unlocks.py` (and `capital_tier.py` for the capital part):

- Technology part: for the key buildings, technologies or edicts named in the linked Remedy's facts, read
  `prerequisites` (a list of technology keys) from the game file; missing = those not in
  `country.tech_status.technology` (the same set `Triggers.techs` in `computed/modifiers.py` holds).
- Capital part: `allow = { has_upgraded_capital }` means `capital_tier >= 2`,
  `has_major_upgraded_capital` means `capital_tier >= 3`
  (`scripted_triggers/01_scripted_triggers_buildings.txt`). `capital_tier` of a planet comes from its
  capital building: `building_capital` family = 1, `major_capital` = 2, `system_capital`/imperial = 3.
  (Exact tier numbering is confirmed against the file in the increment.)
- The metric is one number per Obstacle, `unlocks.<name>.missing` = missing technologies + 1 if the
  capital requirement is not met on the capital planet. `present` when `> 0`.

Because the check schema holds one comparison and `only_clears` expresses only "can rule out", an
Obstacle with an extra clause beyond the unlock ("or the planet is no city world", "some also need a
fitting planet or government") needs the opposite flag, `only_present`: the comparison `missing > 0`
proves the Obstacle, anything else is still `judgement`. Adding this flag is a small change to
`mechanics.schema.json`, `evaluate` and `tests/test_metrics_only_clears.py`; it is done once in the
first unlock increment (3a).

Settled in 3a: metric names have one dot (schema), so the registry names are `unlocks.<name>_missing`
and point at `unlocks.<family>.missing` in the extract. `missing` counts distinct technologies and
Traditions lacking, including the transitive `prerequisites` of each target; a technology whose
`potential` is false for the empire, or with `weight = 0` (never offered, `tech_universal_marcophage`),
is not counted; an undecidable `potential` makes `missing` null and the Obstacle `unknown`. The
extract lists the missing names under `unlocks.<family>`. `only_present` exists in the schema and
`evaluate`. Facts: Ascension Theory is not researched on any of the four reference saves checked
(vulkan 2220, 2298, zygerrian 2271, 2363), so `influence.decree_locked` is present on all of them.

| Obstacle | Metric | Technologies / conditions (from the game files) | Flag |
|---|---|---|---|
| `alloys.ministry_locked` | `unlocks.production_ministry.missing` | `building_ministry_production`: `tech_global_production_strategy`, major upgraded capital | none |
| `energy.generator_building_locked` | `unlocks.generator_buildings.missing` | `building_energy_grid` `tech_power_hub_1`; `building_energy_nexus` `tech_power_hub_2` + upgraded capital | none |
| `food.processing_locked` | `unlocks.food_processing.missing` | `building_food_processing_facility` `tech_food_processing_1`; `..._center` `tech_food_processing_2` + upgraded capital | none |
| `minerals.purification_locked` | `unlocks.purification.missing` | `building_mineral_purification_plant` `tech_mineral_purification_1`; `..._hub` `tech_mineral_purification_2` + upgraded capital | none |
| `research.lab_locked` | `unlocks.labs.missing` | `building_physics_lab_2/3`, `building_biolab_2/3`, `building_nanolab_2/3` and their technologies; higher levels need the capital tier | none |
| `unity.building_locked` | `unlocks.unity_buildings.missing` | `building_heritage_site` `tech_heritage_site` + upgraded capital; `building_hypercomms_forum` `tech_hypercomms_forum` + major upgraded capital | `only_present` (branch office, civic) |
| `stability.building_locked` | `unlocks.stability_buildings.missing` | buildings carrying `planet_stability_add`; family chosen from the Remedy facts (`building_order_keep`, `building_psi_corps`, which have no technology) | `only_present` (planet or government type) |
| `amenities.building_locked` | `unlocks.amenity_buildings.missing` | `building_paradise_dome` `tech_paradise_dome` + upgraded capital; `building_luxury_residence` has none | `only_present` |
| `housing.dwelling_locked` | `unlocks.housing_buildings.missing` | better housing buildings: `building_paradise_dome`/`communal_housing_large` `tech_paradise_dome`, `building_drone_megastorage` `tech_micro_replicators`, `building_expanded_warren` `tech_housing_2`; only those the empire can build (`potential`) | `only_present` |
| `housing.arcology_locked` | `unlocks.arcology.missing` | arcology district/zone and its technology (found in `districts/` and `zones/` in the increment); the planet must be a city world | `only_present` |
| `influence.decree_locked` | `unlocks.decree_missing` | edict `will_to_power` has `potential = { has_technology = tech_ascension_theory }` (`edicts/02_ambitions.txt`) | none |
| `naval_capacity.office_needs_technology` | `unlocks.logistics_office.missing` | starbase building/module for the Naval Logistics Office: technology from `starbase_buildings/` and `starbase_modules/`; also needs an Anchorage (that part stays judgement) | `only_present` |
| `naval_capacity.doctrine_prerequisites` | `unlocks.doctrine_missing` | chain `tech_doctrine_navy_size_1..4` then `tech_repeatable_naval_cap` (`technology/00_soc_tech.txt:3600-3697`, `00_soc_tech_repeatable.txt:216`); missing = chain steps not researched | none |
| `pop_growth.growth_tech_locked` | `unlocks.growth_techs_missing` | the technologies in the Remedy facts (`tech_genome_mapping`, `tech_universal_marcophage`, ...) | none |
| `pop_growth.assembly_locked` | `unlocks.assembly_missing` | `tech_micro_replicators`, `tech_self_assembling_components`, tradition `tr_versatility_finish`; the civic is a start-of-game choice and stays outside the number | `only_present` |
| `slots.capital_upgrade_locked` | `unlocks.capital_upgrade.missing` | next capital building in the family of the capital planet: its `prerequisites` (`tech_planetary_government`, `tech_colonial_centralization`, `tech_galactic_administration`) and `sapient_pop_amount>=` from `allow`; the alloy cost is not part of the number | `only_present` |

If, while building the family for an Obstacle, no building in it has a prerequisite the empire could
still lack (as for the housing buildings without technology), the family is reduced to those that do.
An Obstacle whose family turns out empty on both reference saves is not given a check that is always
clear; it is recorded here with that reason and left `judgement_only`.

## Group 4: building and starbase slots (9)

Free building slots are computed values: they are not in the save. The save stores the zones
(`gamestate.zones`: `{type, buildings}`) and links them through the planet's districts
(`colony.districts` → `districts[].zones`), and `buildings_cache` lists the buildings. The rule is in
the game files:

- `common/zones/*.txt`: per zone type `max_buildings`, `districts_per_building` (districts needed per
  building slot), `max_buildings_planet_class`, `is_capped_by_modifier`, `include`/`exclude` and
  `included_building_sets` (which buildings fit), see `99_HOW_TO_ZONE.txt`.
- `common/zone_slots/*.txt`: when a slot exists (`unlock`, e.g. `has_upgraded_capital`, a technology).
- `common/buildings/*.txt`: `building_sets` of each building, to decide which zone can host it.

Formula (module `extract/computed/building_slots.py`): free slots of a zone = capacity − buildings in
it, where capacity = min(`max_buildings`, floor(districts of the zone ÷ `districts_per_building`)),
changed by the planet-class cap and modifier cap as the zone says. Free slots for a family =
free slots in zones whose included sets contain a building of that family. All of this is rebuilt from
the files and cited in the code; it is not guessed. Golden tests exist and skip as pending until
Julian reads free slots on two or three planets in the game (`docs/awaiting-julian.md`, German).

| Obstacle | Metric (new) | Check | Family (building sets / modifier) |
|---|---|---|---|
| `jobs.no_building_room` | `room.building_slots_free` | `== 0` | all zones |
| `alloys.no_foundry_slot` | `room.building_slots_free_by_family.foundry` | `== 0` | `building_sets` foundry; also zone slots for foundry zones (district part: free district slots exist already as `room.districts_free`) |
| `research.no_lab_slot` | `...by_family.research` | `== 0` | research buildings |
| `unity.no_building_slot` | `...by_family.unity` | `== 0` | unity buildings |
| `stability.no_building_slot` | `...by_family.order` | `== 0` | buildings with `planet_stability_add` |
| `amenities.no_building_slot` | `...by_family.amenities` | `== 0` | buildings with `planet_amenities_add` |
| `housing.no_building_slot` | `...by_family.housing` | `== 0` | buildings with `planet_housing_add` |
| `pop_growth.no_growth_building_slot` | `...by_family.growth` | `== 0` | clone vats, genomic facility (growth modifiers) |
| `naval_capacity.no_free_starbase_slot` | `starbases.module_slots_free` | `== 0` | module and building slots by starbase level (`starbase_levels`, `starbase_modules`, `starbase_buildings`); module `extract/computed/starbase_slots.py`; the save lists each starbase's modules (`computed/naval_capacity.py` already reads them) |

The empire-level number says whether any planet has room. The per-planet number goes into the
planet detail (`planets[].building_slots`) so Ops can name the planet. Where the zone sum covers only
the zones and not the districts ("No free zone or building slot for foundries"), the check is
`only_clears: true`, like `energy.no_generator_slot` is today.

## Group 5: real trade-offs, no check (7)

These stay `judgement_only`. The reason each cannot have a number:

| Obstacle | Reason |
|---|---|
| `energy.upkeep_buys_something` | Whether the upkeep pays for something the empire uses depends on what the Player values; no Snapshot value separates a useful from a wasted building. |
| `influence.project_cannot_wait` | A deadline lives in the Player's plans, not in the save. |
| `naval_capacity.soldier_jobs_cost_output` | A cost of staffing; always true when Soldier jobs exist, and whether it is worth it is a weighing. |
| `slots.weak_building_unknown` | The files do not rank buildings (stated in the Obstacle). |
| `stability.faction_demands_conflict` | Whether two demands conflict needs the Player's willingness to spend; the save holds the demands but not the weighing. |
| `unity.edict_still_needed` | Whether the edict's goal still lasts is the Player's plan. |
| `amenities.tech_empire_type` | True for every empire by construction: the two technologies have opposite `potential` (`NOT has_ethic = ethic_gestalt_consciousness` vs `is_gestalt = yes`), so exactly one applies. No number distinguishes empires, and the Remedy's facts already show which applies. |

## Increments (the plan in `GOAL.md` is split like this)

- **2.** Groups 1 and 2 (7 Obstacles). Modules `ascension_slots.py`; tradition tree slots and Discovery
  left in `progression`; `room.open_jobs_by_function`; `housing.free`. Tests on both reference saves.
- **3a.** Technology prerequisites: `computed/unlocks.py`, the `only_present` flag, and the four
  unlocks that need no capital tier: `influence.decree_locked`, `naval_capacity.doctrine_prerequisites`,
  `pop_growth.growth_tech_locked`, `pop_growth.assembly_locked`.
- **3b.** Capital tier: `computed/capital_tier.py`, then the unlocks with a capital requirement
  (`alloys.ministry_locked`, `energy.generator_building_locked`, `food.processing_locked`,
  `minerals.purification_locked`, `research.lab_locked`, `unity.building_locked`,
  `stability.building_locked`, `amenities.building_locked`, `housing.dwelling_locked`,
  `housing.arcology_locked`, `slots.capital_upgrade_locked`, `naval_capacity.office_needs_technology`).
- **4.** Verification of 2 and 3.
- **5a.** Zone rules: `computed/building_slots.py`, free slots per planet, golden tests pending,
  steps for Julian in `docs/awaiting-julian.md`.
- **5b.** Family metrics and the eight planet-level slot checks.
- **5c.** Starbase slots: `computed/starbase_slots.py`, `naval_capacity.no_free_starbase_slot`, golden
  test pending.
- **6.** Final verification.

## Open questions (decided inside the increment that needs them)

1. **Tradition tree slots.** Settled in increment 2b. The game's own test for "Requires an empty
   Tradition Tree slot" is `num_tradition_categories < @max_tradition_trees` (7; `ascension_perks/
   00_ascension_paths.txt:72`, `scripted_variables/07_scripted_variables_machine_age.txt:47`), and no
   game file changes the limit. So `traditions.trees_free` = 7 − trees unlocked
   (`computed/tradition_trees.py`). Ascension slots: no base slot, one per finished tree plus one for
   `tech_ascension_theory` (`computed/ascension_slots.py`, checked on 15 saves).
2. **Capital tier numbering** for each empire type (regular, machine, hive, habitat, wilderness). Read
   from the capital building keys and `capital_tier` use in the scripted triggers.
3. **Zone capacity corner cases.** `max_buildings_planet_class` and `is_capped_by_modifier` zones; the
   wilderness and habitat zones. If the rule cannot be rebuilt for a zone type, that type is excluded
   and the exclusion is reported in the extract's `errors`, never guessed.
4. **Starbase slots.** Whether `starbase_levels` plus modules give a clean free-slot number; the
   Hustlebot stops at this point after two failed iterations (`GOAL.md`, Model).
