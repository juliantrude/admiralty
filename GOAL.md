# GOAL

<!--
  Single source of truth for the /advance-goal loop (driven headless via the
  one-shot systemd chain, or interactively via `/loop /advance-goal`).
  The loop reads and rewrites this file every iteration.
-->

## North star

Build milestones M3 to M8 of Hliðskjálf v1 exactly as specified in `docs/build-plan.md`
(Campaign Workspace and Setup, Mechanics Graph and Playbook for 4.5.2, Huginn in
Consulting mode, the graph engine, the Unverified Claim check, and Muninn), on top of the
finished M0–M2 foundation (extractor in `src/hlidskjalf/extract/`, MCP server in
`src/hlidskjalf/mcp/`). The build plan, `GLOSSARY.md` and `docs/adr/` are authoritative;
`CLAUDE.md` holds the repo rules. M9 (Huginn in Coaching mode) is out of scope: Julian
builds it together with Claude later, because it needs his in-game judgement.

## Definition of Done

- [ ] Each "Done when" criterion of M3, M4, M5, M6, M7 and M8 in `docs/build-plan.md` is
      met and verified by an automated test or a recorded headless check, except the parts
      that need Julian (see Working Agreements, "Hold points"). Those parts are listed in
      `docs/awaiting-julian.md` with exact instructions, and for those parts alone "blocked
      on Julian" counts as done.
- [ ] `HLIDSKJALF_PERF_SLACK=1.5 uv run pytest` passes (skips for pending golden values
      are fine), and `uv run ruff check . && uv run ruff format --check .` is clean.
- [ ] Every skill and hook named in the build plan's "Shape" for M3–M8 exists in the plugin
      (`skills/setup`, `skills/huginn-consult`, `skills/muninn`, `skills/review-blocks`,
      `hooks/` with the Unverified Claim Stop hook) and is wired in the plugin manifest.
- [ ] `docs/awaiting-julian.md` lists everything waiting for Julian, in German, as short
      steps he can do without reading code.

## Working Agreements (read every iteration — these override convenience)

**Priority order per iteration:**
1. If the previous iteration left the test suite red, fix that first.
2. Then take the next unchecked increment from `## Plan`.

**Git workflow:**
- Work directly on `main` in this repository. There is no remote: commit locally, never
  push, never force, never rewrite or amend existing commits, never create other branches.
- One commit per finished increment, message in English: `M<n>: <what>` plus a short body
  on why. End every commit message with
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Verification bar before every commit: `HLIDSKJALF_PERF_SLACK=1.5 uv run pytest` green
  and ruff clean. Never commit with failing tests; never delete or weaken an existing test
  to make it pass (fix the code, or record the blocker).
- New Python dependencies only via `uv add`. No system packages, no global config changes.

**Hold points (things only Julian does — never do them yourself):**
- Golden values: never fill `tests/golden_values.py`, never derive "golden" numbers from
  our own extractor. Tests that need them skip as pending.
- Benchmarks: write them as a clearly marked draft plus a readable review page; review by
  experienced players is Julian's job.
- Playbook Rules: the three seed rules in the build plan are approved. Any further rule is
  only proposed in `docs/proposals/playbook.md`, never added to `knowledge/`.
- Publishing: never publish Artifacts, never upload anything, never send anything outside
  this machine. M6 ends with a locally verified `engine/index.html`; publishing it once is
  Julian's step.
- In-game feel: anything that needs someone playing the game goes to
  `docs/awaiting-julian.md`.
When an increment hits a hold point: do every part that does not need Julian, add precise
steps to `docs/awaiting-julian.md`, note it in the Blockers line of `## Status`, and move on.

## Plan

Milestones M3 and M4 are done (see Log). Each milestone starts with its plan document
`docs/plans/M<n>.md`, whose "Increments" list is the plan for that milestone; M6 to M8 get their plan
document as their first increment.

M5 (plan: `docs/plans/M5.md`):
- [x] 1. Plan document
- [x] 2. `expand_graph` core (`graph/metrics.py`, `graph/expand.py`, `tests/test_expand.py`)
- [x] 3. Solution Graph schema, validator and `compose` with `briefing compose` and `graph check-solution` CLI
- [x] 4. MCP tool `expand_graph` with turn-log entry, `expansion_id`, catalogue mode
- [x] 5. `hlidskjalf:consult` skill (`skills/huginn-consult/`) and its static test
- [x] 6. Verification: one headless Briefing on the reference save, numbers recorded in the Log

M6 (plan: `docs/plans/M6.md`):
- [x] 1. Plan document
- [x] 2. Libraries and driver (pinned versions, `tools/fetch_engine_libs.py`, `tests/engine_driver.py`, pins test)
- [ ] 3. Page core (`engine/index.html`, `engine.js`, `engine.css`: data loading, layered layout, deterministic `engine-state`)
- [ ] 4. Encodings and panel (circles, model nodes, status, legend, header, lists, click panel, textContent only)
- [ ] 5. Bundle and `briefing view` (`tools/bundle_engine.py`, `engine/dist/index.html`, CLI, "model never writes HTML" static test)
- [ ] 6. Verification (real Solution Graph screenshot looked at, `-m network` test, `docs/awaiting-julian.md` Artifact section)

M7, M8: plan increments to be written (see `docs/build-plan.md`).

## Status

STATUS: READY
**Next action:** M6 increment 3 (see `docs/plans/M6.md`): page core. `engine/index.html` (the three pinned `<script>` tags from `engine/pins.json`, same
tags as `PINNED_TAGS` in `tests/test_engine_driver.py`), `engine.js`, `engine.css`: `loadGraph()` (embedded script, `?data=`, sibling fetch, file picker),
validation (schema 1, arrays, edge endpoints), ELK layered RIGHT with FIRST/LAST layer constraints, pure-function node sizes, deterministic options,
`<pre id="engine-state">`. Tests via `tests/engine_driver.py` (`render`, `script_pin_problems` on the real `index.html`): layers, no overlap, identical render
(also with shuffled nodes/edges), rejects bad data. Note: `.gitignore` has `dist/`, so increment 5 must un-ignore `engine/dist/` (`!engine/dist/`) before committing the bundle.
**Carried into M7 (from M5 verification):** the crude "every number is in a tool result" check flags sums the model computes itself (230.36 = 88 + 74.77 +
67.59 research); the M7 hook must decide whether derived sums are allowed (e.g. only with the addends shown) rather than copy the regex.
**Blockers:** none for the loop. Waiting for Julian (not blocking): golden values from the game UI for `tests/golden_values.py`, and expert
review of the benchmarks draft (both in `docs/awaiting-julian.md`).

## Budget

<!-- weekly threshold lowered to leave Julian headroom for his own work this week -->
- session pause threshold: 85%
- weekly pause threshold: 80%

## Log

<!-- Append-only, dated. One line per iteration. Newest at the bottom. -->
- 2026-10-24 03:30 — GOAL.md written by Claude from docs/build-plan.md after M0–M2 were
  built (Julian authorised the hand-off and an unattended start before going to sleep);
  nothing of M3–M8 started yet
- 2026-10-24 — M3 plan written (`docs/plans/M3.md`): layout, campaign.yaml v1, archive by in-game
  date with stdlib `compression.zstd` (no new dependency), `hlidskjalf setup` CLI, CLAUDE.md
  template; tests 66 passed / 31 skipped, ruff clean
- 2026-10-24 — M3 increment 2: `workspace/config.py` (players, backup_saves, SetupInvalid,
  validation, atomic `write_config` keeping unknown keys) and `workspace/layout.py`
  (create/validate); `validate_workspace` takes the save header's players for the empire check and
  does not flag an empty archive (the final `setup check` must be clean on a fresh workspace);
  tests 84 passed / 31 skipped, ruff clean
- 2026-10-24 — M3 increment 3: `workspace/archive.py` (`Archive.store/backup/has/dates/load/list`,
  keyed by save-header date, zstd via stdlib, archive file mtime = save mtime so newer wins and
  re-reads write nothing, corrupt files listed with a problem) and the hook in
  `CampaignService.document()` (compact extract archived on every fresh read, also when a planet
  detail read comes first; save backed up unless `backup_saves: false`; failures go to the turn
  log as tool `archive` and to `campaign_status` warnings). Two reference saves read leave two
  extracts and two backups, and `diff_extracts` works on them after the originals are removed.
  Tests 91 passed / 31 skipped, ruff clean. GOAL.md repaired: a corrupted duplicate of the
  Working Agreements, Plan and an old Status (after the first `**Blockers:**`) was removed
- 2026-10-24 — M3 increment 4: `workspace/setup.py` (`list_campaigns` from save-folder meta only,
  `describe_save`, `write_setup` validating empire/ally/rival against the newest save and
  normalising the empire to the player name, `--reset-archive` moves `archive/` aside to
  `archive.<n>/`, `check_workspace`, `render_workspace_claude_md` routing consult/coach/muninn)
  and `hlidskjalf setup campaigns|players|write|check` in `cli.py` (JSON on stdout, refusal =
  stderr + exit 1); `game.save_root()` added. Tests in `tests/test_setup.py` (reference vulkan has
  only two players, so ally and rival are covered in separate tests); 110 passed / 31 skipped,
  ruff clean
- 2026-10-24 — M3 increment 5: `skills/setup/SKILL.md` (one question per turn, CLI via
  `uv run --quiet --project ${CLAUDE_PLUGIN_ROOT} hlidskjalf setup ...`, never hand-written YAML) and
  `tests/test_setup_skill.py`. Headless `claude -p` in a fresh /tmp workspace with a temp
  `HLIDSKJALF_USER_DIR` (symlink to `vulkan`), answers scripted in German: `campaign.yaml` held
  empire Plexxi, a friend's empire as rival, consulting, fair_play; `CLAUDE.md` written; `setup check` clean.
  M3 complete. GOAL.md repaired again (stale duplicate of Working Agreements/Plan/Status after the
  first `**Blockers:**` removed). Tests 113 passed / 31 skipped, ruff clean
- 2026-10-24 — M4 increment 1: `docs/plans/M4.md` written (three layers generated facts / curated
  graph / rules+benchmarks; fact format and ids; generator scope table per quantity and game-file
  category; node schema with metrics registry and `check` for Obstacles; loader, validator and
  `hlidskjalf graph validate`; rule and benchmark formats; 9 increments with checks). Docs only;
  tests 113 passed / 31 skipped, ruff clean
- 2026-10-24 — GOAL.md repaired a third time (committed corrupted in 2197d28). Root cause: Working
  Agreements quoted the Status marker in inline code, so a search for it from the top of the file hit the
  wrong place and duplicated everything between; that sentence is reworded. Edit `## Status` by line
  range or the `## Status` heading, never by searching for the Blockers marker. M4 increment 2: generator in
  `src/hlidskjalf/graph/{quantities,generator}.py` + `tools/gen_mechanics.py` (+ allow list for 6 internal
  static modifiers); 8305 facts in 14 files under `knowledge/4.5.2/generated/` (deterministic, ~9 s);
  species traits count for pop growth only, leader traits skipped; building slots come from `zones`.
  Known facts pinned (Supremacy +20, Anchorage +5 / office +3, `tech_repeatable_naval_cap` +20 x5 levels,
  Soldier +4 per job) in `tests/test_mechanics_generator.py`; regeneration test keeps the YAML current; tests 142 passed / 31 skipped, ruff clean
- 2026-10-24 — M4 increment 3: `graph/mechanics.schema.json` + `metrics.schema.json` (JSON Schema 2020-12 via
  `uv add jsonschema`), `graph/mechanics.py` (`MechanicsGraph.load/validate`, `GraphInvalid`, lazy cached fact index,
  wildcard facts, dangling links/facts/rules/metrics, wrong link types, dead-end Causes, id/domain/file checks,
  cycles: unnamed = warning, no exit = error, digits in prose = warning), `hlidskjalf graph validate`,
  registry `knowledge/4.5.2/graph/metrics.yaml` (36 metrics, paths checked against the vulkan mid-save extract).
  Tests in `tests/test_mechanics_graph.py` use temp packs with good and bad fixtures; 173 passed / 31 skipped, ruff clean
- 2026-10-24 — M4 increment 4: `knowledge/4.5.2/graph/naval_capacity.yaml` (Goal `naval_capacity.more`, 2 Causes, 6 Remedies:
  Supremacy, Anchorages, Naval Logistics Office, fleet doctrine technologies, Soldier jobs, Fleet Logistics Corps; 8 Obstacles,
  3 checked against the Snapshot, 5 judgement-only) and `MechanicsGraph.reachable(goal_id)`. `tests/test_naval_capacity_graph.py`:
  M4 criterion, linked facts resolve to the known figures, no figures in prose, all-goals walk terminates, no orphans, cycle-safe walk.
  `graph validate` clean; tests 180 passed / 31 skipped, ruff clean
- 2026-10-24 — M4 increment 5: economy domains `energy.yaml`, `minerals.yaml`, `food.yaml`, `alloys.yaml` in
  `knowledge/4.5.2/graph/` (one Goal each; Causes few producers / weak multipliers / heavy upkeep; Remedies staffing the producer
  job, districts and buildings, technologies, minerals decree; Obstacles checked against pops.unemployed, stockpiles, net income,
  research.net, the rest judgement-only). alloys Obstacles `minerals_short` and `energy_short` link to the minerals and energy
  Remedies. `graph validate` clean; `tests/test_economy_graph.py` added; tests 191 passed / 31 skipped, ruff clean
- 2026-10-24 — M4 increment 6: `unity.yaml` (Goal `unity.more`; staffing, Unity buildings, technologies, One Vision, dropping idle edicts; shared
  Remedy `unity.raise_income` now linked from `naval_capacity.supremacy_needs_unity`), `influence.yaml` (force projection perk, Will to Power decree
  linking the Unity cost facts, Colonial Viceroys, staggering projects, Diplomacy tradition, Federation Code) and `research.yaml` (researcher jobs,
  labs, speed technologies, Discovery tree); all Unity-gated Obstacles hand over to `unity.raise_income`. `graph validate` clean;
  `tests/test_progress_graph.py` added; tests 204 passed / 31 skipped, ruff clean
- 2026-10-24 — M4 increment 7: `pop_growth.yaml`, `housing.yaml`, `amenities.yaml`, `stability.yaml`, `slots.yaml` and `jobs.yaml` (shared Remedy
  `jobs.free_jobs`, no Goal) in `knowledge/4.5.2/graph/`. Shared `pop_growth.grow_pops` is now the Remedy of every `<domain>.no_spare_pops` Obstacle and
  `jobs.free_jobs` of every job-slot Obstacle; circle `food_needs_pops` (food.staff_farmers <-> pop_growth.grow_pops) marked, break point on the Farmers
  Remedy. A first draft with energy-upkeep and Unity back-links folded the whole economy into one unnamed cycle, so those links were dropped (reason in
  `slots.yaml`). `graph validate` clean; `tests/test_population_graph.py` added; tests 236 passed / 31 skipped, ruff clean
- 2026-10-24 — M4 increment 8: `graph/playbook.py` (`Rule`, `read_rules` returning rules plus problems, `load_rules` refusing a bad folder with
  `RulesInvalid`; only `status: approved`, id = file name, ISO date, non-empty applies_to/reason/body) and the three seed rules in
  `knowledge/4.5.2/rules/` (`unity-vs-next-tradition`, `influence-at-cap-is-waste`, `unemployed-before-colonies`). The graph validator now reports rule file
  errors and `applies_to` patterns that match no node or Goal (`*` = anything). `rules:` links added to the Unity-spending Remedies and their `*_needs_unity`
  Obstacles, `influence.stagger_projects`, `pop_growth.grow_pops`, `jobs.free_jobs` and every `*.no_spare_pops`. `docs/proposals/playbook.md` created (empty).
  The fixture rule in `tests/test_mechanics_graph.py` was brought to the full rule format (test data, no assertion weakened). Tests 252 passed / 31 skipped, ruff clean
- 2026-10-24 — M4 increment 9 (M4 complete): `graph/benchmarks.py` (format, `load_benchmarks` refusing malformed files, `usable` only when
  `status: reviewed`, `resolve_source`, `render_review_page`), `tools/gen_benchmarks.py` (refreshes `observed` from the git-ignored saves, keeps
  values/status, writes the page), `knowledge/4.5.2/benchmarks.yaml` (11 figures x 9 decades, all benchmark values null: no game-file formula
  covers a whole empire, nothing invented; observed values from vulkan and zygerrian, no player names) and `docs/benchmarks-draft.md`.
  `graph validate` now checks the file; `docs/awaiting-julian.md` section 2 (German) holds the review steps. Tests 269 passed / 31 skipped, ruff clean
- 2026-10-24 — M5 increment 1: `docs/plans/M5.md` written (code/model division of labour; `expand_graph` as BFS with shortest-depth merging, depth 5
  (7 to 16 of 27 to 41 nodes per Goal lie deeper on the unpruned graph), check states present/clear/unknown/judgement, clear Obstacles not walked,
  Remedy status actionable/pending/obstructed, Vicious Circles by SCC with break point, mechanical Key Action ranking with Crisis Goals first; Solution
  Graph schema with `source: "model"` rules, validator, `compose` of a model overlay so the model never hand-copies the graph; MCP tool with catalogue
  mode; skill flow and hard rules; verification; 6 increments). Docs only; tests 269 passed / 31 skipped, ruff clean
- 2026-10-24 — M5 increment 2: `graph/metrics.py` (`dig`, `resolve_metric` moved out of `benchmarks.py`, `Check`, `evaluate`: present / clear / unknown /
  judgement with the compared numbers) and `graph/expand.py` (`expand_graph`, `Expansion.to_dict` with the 40k budget trim, `Candidate`,
  `rank_key_actions`; BFS depth limit 5 with `too_far`, clear Obstacles are leaves, Remedy status actionable/pending/obstructed evaluated directly from
  its Obstacles, iterative Tarjan circles with break point, `serves`/`unlocks`, effects with Display Names, cited rule text); `MechanicsGraph.rules`
  added. `tests/test_expand.py` (34 tests, synthetic packs plus the real graph on vulkan mid-save). Findings on the reference save: per Goal 11 to 24
  nodes, 0 to 4 `too_far`, no circle within depth 5, 1 to 6 Key Action candidates, 10 to 22k characters. A circle that closes only beyond depth 5 is not
  reported (the circle test uses depth_limit 8). No `pending_when` added: no registered metric expresses "jobs that population growth will fill", nothing
  invented. Tests 303 passed / 31 skipped, ruff clean. GOAL.md repaired: the `## Plan` and `## Status` headings had been lost; restored with an M5 checklist

- 2026-10-24 — M5 increment 3: `graph/solution.schema.json` + `graph/solution.py` (`validate_solution_graph`, `compose`, `SolutionInvalid`) and CLI
  `hlidskjalf briefing compose <expansion.json> <overlay.json> --out` and `hlidskjalf graph check-solution <file>`. Graph nodes carry what the code
  computed (status, ratings, check_state, evidence strings built from the compared numbers, rule ids); model nodes need id `model.*` and a reason and
  carry no code-computed field; edges follow the grammar and must exist in the Mechanics Graph between two graph nodes; orphans, dangling ids,
  invented rule ids, obstructed or evidence-less Key Actions, bad ranks and unknown fields are errors. `compose` prunes with a reason (a present Obstacle
  cannot be pruned), drops what only hung on pruned nodes (recorded), re-derives circles after pruning, recomputes the Key Action ranking with
  `rank_key_actions` and requires a `why` per candidate or an `exclude_key_actions` entry (added to the document as `excluded_key_actions`; the
  overlay also needs `empire`). `tests/test_solution.py` (47 tests incl. the real graph on vulkan mid-save); full suite 350 passed / 31 skipped, ruff clean, `graph validate` clean- 2026-10-24 — M5 increment 4: MCP tool `expand_graph(goals, crisis_goals, save)` (`mcp/server.py`, `CampaignService.expand_graph` and `.graph`): no goals =
  catalogue (`graph.expand.catalogue`: id, domain, title, resolved Symptom metrics), with goals = `Expansion.to_dict()` + header warnings + `expansion_id` (the
  turn-log line number; `log()` returns it and fills the placeholder before writing; `workspace/turnlog.py` holds `TURN_LOG`, line counting and
  `read_entry`). Graph loaded once per server by the save's `game_version`; no pack for a version, an unknown Goal (lists the known ones) and a bad pack are
  `{"error": ...}`. CLI `briefing compose` takes `--expansion-id N --workspace DIR` instead of the expansion file. Result size: compact step added to
  `to_dict` and `compose` now takes node text from the graph (the old clear-Obstacle trim would have broken `compose` with a KeyError); mid-save sizes 1 Goal
  15k, 3 Goals 38k, 6 Goals 66k (warning), 13 Goals 128k (warning). One existing test (`test_a_tight_budget_trims_effects_then_clear_obstacle_text`) got a
  computed budget instead of `budget=1` so it still exercises only its two steps; assertions unchanged. Tests 359 passed / 31 skipped, ruff clean, `graph validate` clean

- 2026-10-24 — M5 increment 5: `skills/huginn-consult/SKILL.md` (name `consult`; the eight steps, overlay example and the two commands, hard rules: numbers only from tool
  results, Unity guard sentence with `unity-vs-next-tradition` and `traditions.next_cost`, Playbook Rules quoted from results, no benchmarks, Fair Play, no HTML, tool errors
  stop the step; three Goals in total per Briefing) and `tests/test_consult_skill.py` (frontmatter, tools served, CLI flags exist, overlay example fields equal the
  compose overlay keys, hard-rule sentences, workspace `CLAUDE.md` routes to `hlidskjalf:consult`). Tests 365 passed / 31 skipped, ruff clean
- 2026-10-24 — M5 increment 6 (M5 complete): headless Briefing, `claude -p` in a temp workspace (`/tmp/h6/ws`, temp `HLIDSKJALF_USER_DIR`, Plexxi, consulting,
  fair_play, plugin via `--plugin-dir`, `--strict-mcp-config`, the nine MCP tools plus the two CLI commands allowed). Run 1: the skill's stale-save guard fired
  (reference save 286 min old) and it refused to brief, as designed. Run 2 on a fresh copy of `2259.12.25.sav` (fixture untouched): 13 turns, 80 s wall,
  `campaign_status`, `empire_overview`, `economy`, `progression`, `military`, `expand_graph` (catalogue 2.5k chars), `expand_graph` for energy.more,
  alloys.more, research.more; Write overlay; `compose` (50 nodes) and `check-solution` (0 errors) on the first try. Expansion: 47 nodes (24 Obstacles, 15 Remedies,
  8 Causes), 4 cut at depth 5 (`too_far`), 0 circles, 39k characters (3 Goals; the extract budget warning was not hit), 3 mod warnings relayed. Solution Graph:
  9 Key Actions, all `actionable`; rules cited `unemployed-before-colonies` and `unity-vs-next-tradition` (both exist); Unity 2794.45 < next Tradition 4384
  (`traditions.next_cost`) and the answer says the Unity is earmarked and not to be spent on edicts. Numbers: 25 of 26 appear in tool results; the one that does not
  (230.36) is the sum of the three research nets, computed by the model. Answer in German like the question, no HTML. Correctness against golden values: hold
  point (`docs/awaiting-julian.md`). Tests unchanged (docs only)
- 2026-10-24 — GOAL.md repaired (4915ced dropped Working Agreements tail and `## Plan`: `## Status` also occurs inside the Working Agreements prose; anchor edits on the heading line `\n## Status\n`). Restored; M5 checklist now complete
- 2026-10-24 — M6 increment 1: `docs/plans/M6.md` written (one fixed static page fed only by `solution-graph.json`; data sources embedded / `?data=` / sibling fetch /
  file picker; ELK layered left to right with explicit layer constraints, pure-function node sizes and fixed options for deterministic layout; circle colours,
  model-node marking, status encodings, click panel with evidence, everything inserted as text; pinned CDN versions with SRI; headless Chromium driver reading an
  `engine-state` JSON, tests for identical render, layers, circles, no injected HTML, bad data, bundle, pins; `briefing view` loopback server; Artifact publishing
  as hold point; 6 increments). Docs only; chromium 154 and CDN reachable on this machine
- 2026-10-24 — M6 increment 2: `engine/pins.json` (single source of truth: cytoscape 3.34.4, elkjs 0.12.0, cytoscape-elk 2.3.0, jsDelivr URLs, SRI sha384) and
  `engine/VERSIONS.md`; `tools/fetch_engine_libs.py` (urllib, checks hashes, cache `tests/fixtures/engine-libs/` git-ignored); `tests/engine_driver.py`
  (`/usr/bin/chromium --headless=new --dump-dom` on a temp copy with CDN tags rewritten to the cache, `render()` reads `<pre id="engine-state">`, `script_pin_problems`,
  `skip_reason`) and `tests/test_engine_driver.py` (13 tests: pins check on good/bad tags, pins.json vs VERSIONS.md, offline copy, stub page runs Cytoscape+ELK headless
  and the state reads back). Tests 378 passed / 31 skipped (205 s), ruff clean
