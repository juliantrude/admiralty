# GOAL

<!--
  Single source of truth for the /advance-goal loop (driven headless via the
  one-shot systemd chain, or interactively via `/loop /advance-goal`).
  The loop reads and rewrites this file every iteration.
  The previous chain (M3–M8) is archived in docs/plans/goal-M3-M8.md.
-->

## North star

Turn the grey Obstacles of the curated Mechanics Graph (`knowledge/4.5.2/graph/*.yaml`, those with
`check: {judgement_only: true}`) into Obstacles checked against Snapshot numbers, wherever the save
and the game files allow it. Today 85 Obstacles exist: 46 are checked, 39 are `judgement_only`
(4 ascension perks and traditions, 2 free job slots, 14 unlocks, 11 building and zone slots,
8 real trade-offs). Academy (M9) judges the Player's answers against the Solution Graph and needs
checked Obstacles. Decided by Julian in `docs/plans/grilling.md`, topic 4; that section is
authoritative for scope and order. `docs/build-plan.md`, `GLOSSARY.md`, `docs/adr/` and
`CLAUDE.md` hold the rules.

## Definition of Done

- [x] `docs/plans/obstacle-checks.md` lists all 39 `judgement_only` Obstacles with their group,
      the metric that checks them (or why none can), and the save fields and game files used.
- [x] Every Obstacle in the groups "perks and traditions", "free job slots", "unlocks" and
      "building and zone slots" has a metric check (`check: {metric, op, compare_to}`), or the
      plan document names the concrete reason it cannot have one. The 8 real trade-offs stay
      `judgement_only`.
- [x] Each new computed value has its own module with the formula and its game-file sources in
      the code (`CLAUDE.md`), and a test on the reference saves (`vulkan`, `zygerrian`).
- [x] Free building slots are computed values: their golden tests exist and skip as pending
      until Julian reads the values in the game; the steps for him are in
      `docs/awaiting-julian.md` (German, without code).
- [x] `ADMIRALTY_PERF_SLACK=1.5 uv run pytest` passes (pending skips are fine) and
      `uv run ruff check . && uv run ruff format --check .` is clean.
- [x] One headless Ops Briefing on a reference save shows the newly checked Obstacles as checked
      (numbers recorded in the Log).

## Working Agreements (read every iteration — these override convenience)

**Priority order per iteration:**
1. If the previous iteration left the test suite red, fix that first.
2. Then take the next unchecked increment from `## Plan`.

**Git workflow:**
- Work directly on `main` in this repository. Commit locally only; Julian pushes. Never
  push, never force, never rewrite or amend existing commits, never create other branches.
- One commit per finished increment, message in English: `Obstacles: <what>` plus a short body
  on why. End every commit message with
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Verification bar before every commit: `ADMIRALTY_PERF_SLACK=1.5 uv run pytest` green
  and ruff clean. Never commit with failing tests; never delete or weaken an existing test
  to make it pass (fix the code, or record the blocker).
- New Python dependencies only via `uv add`. No system packages, no global config changes.

**Rules of the domain:**
- Rules are derived from the game files in `~/.local/share/Steam/steamapps/common/Stellaris`
  (version 4.5.2) and cited in the code; never guessed.
- Titles of Obstacles follow `docs/plans/M6-revision.md` (English, a state, uncertain form with
  "may"); do not rewrite existing titles, that is a separate task (grilling topic 2).
- A check must only report the Obstacle as present when the Snapshot shows it; when the data is
  missing the Obstacle stays unchecked, never guessed.

**Hold points (things only Julian does — never do them yourself):**
- Golden values: never fill `tests/golden_values.py`, never derive "golden" numbers from
  our own extractor. Tests that need them skip as pending.
- Publishing: never publish Artifacts, never upload anything, never send anything outside
  this machine (ADR 0004).
- In-game feel: anything that needs someone playing the game goes to
  `docs/awaiting-julian.md`.
When an increment hits a hold point: do every part that does not need Julian, add precise
steps to `docs/awaiting-julian.md`, note it in the Blockers line of `## Status

STATUS: COMPLETE
**Next action:** none. The goal is done; the golden tests for building slots and starbase slots stay pending until
Julian reads the values (`docs/awaiting-julian.md`, sections 5 and 6).
**Blockers:** none.

## Budget

- session pause threshold: 85%
- weekly pause threshold: 80%

## Log

<!-- Append-only, dated. One line per iteration. Newest at the bottom. -->
- 2026-10-28 — GOAL.md written by Claude from `docs/plans/grilling.md` topic 4 after all grilling
  topics were closed; Julian starts the chain tonight.
- 2026-10-28 — Increment 1: wrote `docs/plans/obstacle-checks.md` (39 classified: 4 perks and traditions,
  3 jobs and housing, 16 unlocks, 9 slots, 7 trade-offs without check; counts differ from the grilling,
  explained in the plan). Plan split into 2, 3a, 3b, 4, 5a, 5b, 5c, 6.
- 2026-10-28 — Increment 2a: `room.open_jobs_by_function` (job `tags` from common/pop_jobs: `amenities`;
  `soldier`/`enforcer`) and `room.housing_free` (free_housing now in the planet summary); 3 Obstacles checked
  (order one `only_clears`, since bureaucrats carry no tag). Suite 736 passed, ruff clean. On the reference
  saves: vulkan 2298 amenities 0 / order 0 / housing 28380; zygerrian 2363 amenities 0 / order 2636 /
  housing 100561.6 (raw save units).
- 2026-10-28 — Increment 2b: `computed/ascension_slots.py` (slots = Ledger `ascension_perks_add`, no base
  slot, cap 8; unlocked count equals finished trees + Ascension Theory on 15 saves) and
  `computed/tradition_trees.py` (free tree slots = `@max_tradition_trees` 7 − trees; Discovery traditions left
  from `tradition_categories`). 4 Obstacles checked (`tradition_slot_taken` is derivable after all: the game's
  own slot test is the cap). Suite 743 passed + new progression tests, ruff clean. vulkan 2298: slots free 0,
  trees free 4, Discovery left 3; zygerrian 2291.09.26: slots free 1; 2363: slots free 0, trees free 3.
- 2026-10-28 — Increment 3a: `computed/unlocks.py` (missing technologies with transitive prerequisites, plus
  Traditions; excludes techs with false `potential` or weight 0; undecidable potential gives null) and the
  `only_present` flag (schema, `evaluate`, tests). 4 Obstacles checked: `influence.decree_locked`,
  `naval_capacity.doctrine_prerequisites`, `pop_growth.growth_tech_locked`, `pop_growth.assembly_locked`
  (only_present). Suite 752 passed, ruff clean. vulkan 2298: decree 1, doctrine 1, growth 0, assembly 2;
  zygerrian 2363: decree 1, doctrine 0, growth 0, assembly 0.
- 2026-10-28 — Increment 3b: `computed/capital_tier.py` (tier of a planet = largest `capital_tier` of its
  `capital = yes` buildings; required tier read from the scripted trigger; `country.capital` is a colony id)
  and building families in `computed/unlocks.py` (building `prerequisites`, buildable = `potential` not false
  for the country). 8 Obstacles checked: generator, food processing, purification, labs, unity buildings,
  housing, naval logistics office, capital upgrade. 4 stay `judgement_only` with reasons in the plan
  (ministry, stability buildings, amenity buildings, arcology: not buildable or no technology for machine
  empires). Suite 763 passed, ruff clean. vulkan 2298 missing: generator 2, food 1, purification 2, labs 6,
  unity 3, housing 0, office 1, capital upgrade 1; zygerrian 2363: 0, 1, 0, 0, 1, 0, 0, 1. Remaining
  `judgement_only`: 20 (7 trade-offs, 9 slots, 4 above).
- 2026-10-28 — Increment 4: verification of groups 1 to 3. New tests in `tests/test_extract.py`: no
  metric-checked Obstacle reports `unknown` on the four reference saves, and the 19 planned Obstacles are not
  `judgement_only`. Over all 15 saves 65 of 85 Obstacles have a metric check (20 grey: 7 trade-offs, 9 slots,
  4 unlocks with a named reason) and none is `unknown`. Headless Briefing (all 13 Goals expanded, 173 nodes,
  83 Obstacles, no warnings): vulkan 2298 shows 32 clear / 29 present / 22 judgement, of the 19 newly checked
  18 are in the expansion: 14 present, 2 clear, 2 judgement (only_present or only_clears); zygerrian 2363 shows
  43 clear / 17 present / 23 judgement, newly checked 7 present, 8 clear, 3 judgement. Suite 768 passed,
  ruff clean.
- 2026-10-29 — Increment 5a: `computed/building_slots.py`. Capacity of a zone = its `max_buildings`, else
  `DEFAULT_MAX_PLANET_BUILDINGS_PER_ZONE` 3 (zone_default 6, some zones 1); independent of the district
  level (no zone sets `districts_per_building`); `zone_building_slots_add` is a tooltip modifier only.
  Synaptic Lathe zones (`max_buildings_planet_class`) and the two other capacity flags are left out and
  reported in `errors`. Per planet `building_slots` {capacity, used, free, empty_zone_slots, unsupported}
  in the planet summary, `zones` in the detail. On all 15 saves every building of `buildings_cache`
  stands in exactly one zone and no zone is over capacity. vulkan 2298: Unimatrix 1 21/21, Neu Vulkan
  13/21, Astarte 14/18. Golden test `test_golden_building_slots` pending (key `building_slots` in
  `golden_values.py` is Julian's); German steps in `docs/awaiting-julian.md` section 5. Suite 788 passed,
  3 skipped (pending), ruff clean.
- 2026-10-29 — Increment 5b: `SLOT_FAMILIES`, `zone_admits` and `family_zones` in `computed/building_slots.py`
  (a zone counts for a family when its definition admits a buildable building of it; all 10854 built buildings
  of the 15 saves are admitted by their zone, tested). `room.building_slots_free` and
  `room.building_slots_free_by_family` (None when a family has no buildable building, or when a sum of 0 meets
  a zone type that is not computed); per-planet `free_by_family` only in the planet detail, since the summary
  would break the 40000-character extract budget. 7 Obstacles checked: `jobs.no_building_room`,
  `stability.no_building_slot`, `housing.no_building_slot`, `pop_growth.no_growth_building_slot` (`== 0`) and
  `alloys.no_foundry_slot`, `research.no_lab_slot`, `unity.no_building_slot` (`only_clears`, they need a zone of
  their own). `amenities.no_building_slot` stays `judgement_only`: no amenity building is buildable for either
  reference empire (reason in the plan). `unlocks._buildable` is now public as `is_buildable`. Suite 822 passed,
  3 skipped (pending), ruff clean. vulkan 2298: free slots 61, foundry 34, research 38, unity 34, order 33,
  housing 33, growth 33; zygerrian 2363: 119, 61, 75, 75, 61, 61, 61; all seven read `clear` on both.
- 2026-10-29 — Increment 5c: `computed/starbase_slots.py`. Slots of a starbase = entries of its level's
  `module_slots`/`building_slots`; taken by `modules`/`buildings` or by a queued
  `buildable_starbase_module`/`_building` item (`construction.item_mgr`), which names its slot; owner = owner of
  the station ship's fleet. Waystation/arkship levels and levels without definition go to `unsupported` (sum 0
  then reads unknown). Metric `starbases.slots_free` (`room.starbase_slots.free`); `naval_capacity.no_free_starbase_slot`
  checked `== 0` (no `only_clears` needed). Golden test `test_golden_starbase_slots` pending (key `starbase_slots`),
  German steps in `docs/awaiting-julian.md` section 6. Suite 843 passed, 5 skipped (pending), ruff clean.
  vulkan 2298: 11 starbases, modules 28/54 used, buildings 6/27, free 47; zygerrian 2363: 21 starbases, modules
  50/78, buildings 26/39, free 41; the Obstacle reads clear on both.
- 2026-10-29 — Increment 6: final verification. Full suite `ADMIRALTY_PERF_SLACK=1.5 uv run pytest`: 843 passed,
  5 skipped (pending golden tests), ruff check and format clean. Headless Briefing (CampaignService.expand_graph,
  all 13 Goals expanded, 173 nodes, 83 Obstacle nodes; the only warning is the 40000-character size note of
  expanding all Goals at once): vulkan 2298 shows 40 clear / 29 present / 14 judgement (increment 4: 32 / 29 / 22),
  zygerrian 2363 shows 51 clear / 17 present / 15 judgement (increment 4: 43 / 17 / 23); the eight Obstacles of
  increment 5 moved from judgement to clear, `naval_capacity.no_free_starbase_slot` reads clear on both. Whole graph:
  85 Obstacles, 73 with a metric check, 12 `judgement_only` (7 trade-offs, `amenities.no_building_slot`, and
  4 unlocks with a named reason in `docs/plans/obstacle-checks.md`). Goal COMPLETE; no further run armed.
