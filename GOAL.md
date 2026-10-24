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
- [x] 3. Page core (`engine/index.html`, `engine.js`, `engine.css`: data loading, layered layout, deterministic `engine-state`)
- [x] 4. Encodings and panel (circles, model nodes, status, legend, header, lists, click panel, textContent only)
- [x] 5. Bundle and `briefing view` (`tools/bundle_engine.py`, `engine/dist/index.html`, CLI, "model never writes HTML" static test)
- [x] 6. Verification (real Solution Graph screenshot looked at, `-m network` test, `docs/awaiting-julian.md` Artifact section)

M6 is complete (see Log).

M7 (plan: `docs/plans/M7.md`):
- [x] 1. Plan document
- [x] 2. Normalisation and extraction (`claims/normalise.py`, `claims/extract.py`)
- [x] 3. Evidence and matching (`claims/evidence.py`, `claims/check.py`, `hlidskjalf claims check`)
- [x] 4. The Stop hook (probe real input, `hooks/hooks.json`, `hlidskjalf hook stop`, `blocks.jsonl`, loop guard, `plugin.json`)
- [ ] 5. `review-blocks` (`claims/blocks.py`, `blocks summary` CLI, skill, `docs/proposals/claims.md`)
- [ ] 6. Verification (bold Display Names in consult skill, planted district count, reference Briefings, headless run)

M8: plan increments to be written (see `docs/build-plan.md`).

## Status

STATUS: READY
**Next action:** M7 increment 5, `review-blocks`: `claims/blocks.py` (read `.hlidskjalf/blocks.jsonl`, group by kind and reason code `no_match`/`near_match`/`derived_unexplained`/`name_no_match`/`released`, counts plus the answer sentence per group; block lines hold `unverified[]` with `kind`, `code`, `sentence`, `text`, `nearest`, plus `released`, `session_id`, `prompt_id`), CLI `hlidskjalf blocks summary --workspace DIR` (JSON), `skills/review-blocks/SKILL.md` (developer skill: classify each group as real error or false positive, write a proposal per group into `docs/proposals/claims.md`, edit no code/knowledge/tests; name only commands that exist), `docs/proposals/claims.md` (empty, like `playbook.md`), static skill test and grouping tests on a fixture `blocks.jsonl`. Then increment 6 (verification). Available from increment 4: `claims/hook.py` (`stop`, `decide`, `find_workspace`, `blocks_path`, `BLOCKS_LOG`), `hlidskjalf hook stop`, `hooks/hooks.json` (exec form), manifest `hooks` key. Note: `-m network` is deselected by default.
**Decided in the M7 plan:** derived sums/differences (2 to 4 addends shown in the same item) and percentages are allowed, unexplained totals are blocked;
evidence window = tool results of the whole session. Hook input probed (see plan, open risks): the loop guard counts blocks in `blocks.jsonl` per `session_id`+`prompt_id` because `stop_hook_active` stays true on every pass.
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
- 2026-10-24 — M6 increment 3: `engine/index.html` (3 pinned CDN tags + `engine.js`, `<!-- solution-graph -->` slot, hidden `<pre id="engine-state">`), `engine.js`
  (pure `nodeLabel`/`nodeSize` from the title only, `validateGraph` with the first reason, `loadGraph` embedded > `?data=` > sibling fetch > file picker/drop, elements sorted
  by id/edge, cytoscape-elk layered RIGHT with `layerConstraint` FIRST for Goals and LAST for Key Actions, fixed ELK options, state = ids/types/rounded positions/sizes/edges,
  no timing in the state), `engine.css`. Driver: `script_pin_problems`/`offline_copy` now only look at http(s) script tags (the local `engine.js` is allowed; message
  and existing tests unchanged), `dump_dom(files=)`, `embed_graph`, `render_engine`. `tests/test_engine_page.py` (26 tests: fixtures validate against the schema, pins on
  the real page, no HTML-inserting API in `engine.js`, layers, no overlap, identical render incl. shuffled input, date/empire change nothing, size function, 8 bad-data
  cases, non-JSON, no data -> picker). Tests 404 passed / 31 skipped (243 s), ruff clean
- 2026-10-24 — M6 increment 4: encodings and panel in `engine/engine.js`, `engine.css`, `index.html`. Pure functions `circleInfo` (Okabe-Ito palette without yellow/black, per circle
  in circle order), `tagOf` (second label line in words: `model`, type, horizon, `CRISIS`, status/check_state, `⚑ break point`), `headerOf`, `legendOf` (only encodings that occur),
  `panelOf`/`circlePanelOf` (only JSON fields plus edges in/out and Goals served derived from the edges). Node size now comes from title and tag. Circle members and inner edges take the
  circle colour, break point has a double outline, model nodes dashed, pending Remedy hatched (linear-gradient stripes), obstructed grey, present Obstacle red with red edge, clear muted,
  unknown/judgement dotted, Crisis Goal heavy outline; Key Action `serves` shown as dashed edges on selection (added after layout, not part of it). Header, legend, ranked Key Action list and
  `pruned` list are text-only DOM; click seams `HlidskjalfEngine.click(id)` / `clickBackground()` emit the page's own `tap`, the page fires `engine-ready` after layout and `engine-state`
  gains header, legend, circles, key_actions, pruned, selected, panel. Driver: `engine_dom(after_ready=)`. Tests: `tests/test_engine_encodings.py` (15: circle colours/inner edges, break
  point, legend circle click, model marker, statuses and exact legend list, header/lists, list click, panel contents, evidence strings unchanged, click replace/clear, markup shown as text
  with identical element set). Existing test `test_a_different_date_or_empire_does_not_move_a_node` renamed `..._changes_only_the_header` (assertion now: header differs, rest of the
  state equal; required because the header is now part of the state, as the plan says); the circle fixture's members now hold the whole SCC (obstacles included, as `expand_graph` emits).
  Screenshot of a merged fixture looked at (no defects in encodings; labels small at fit zoom, noted for increment 6). Tests 419 passed / 31 skipped (268 s), ruff clean
- 2026-10-24 — M6 increment 5: `tools/bundle_engine.py` (`bundle()` inlines `engine.css` as `<style>` and `engine.js` as `<script id="engine-script">`, CDN tags stay, refuses `</script`/`</style`/`<!--`
  inside; `--check` exits 1 when stale), `engine/dist/index.html` committed (`.gitignore`: `!engine/dist/`), `graph/view.py` + `hlidskjalf briefing view <file> [--port N]` (bundle and JSON copied
  to a temp dir, stdlib `http.server` bound to 127.0.0.1, random free port, prints the URL; unparsable JSON or missing bundle = stderr + exit 1). Driver: `engine_dom` hooks before
  `<script src="engine.js">` or `<script id="engine-script">` and reads the engine files only when they exist. `tests/test_engine_bundle.py` (16: deterministic, committed bundle not stale, no
  local path, pins on the bundle, bundler refuses a closing tag, bundled = unbundled `engine-state`, hook in the bundle, view on loopback with 200 for page and JSON, `..` paths refused, bad input,
  headless browser against the served page, "model never writes HTML": no skill asks to write .html/.js/.css, consult skill only the overlay and the two commands, schema/overlay keys without
  HTML fields). Tests 435 passed / 31 skipped (275 s), ruff clean
- 2026-10-24 — M6 increment 6 (M6 complete): the M5 headless Solution Graph (50 nodes, 53 edges, validates) rendered from `engine/dist/index.html` and the PNG looked at. Defect: at fit zoom the 11 px labels
  became ~5 px and unreadable. Fix in `engine.js`: `readableView()` after layout keeps zoom >= 0.8 and starts at the top left of the graph (positions and `engine-state` unchanged; reader drags/wheels; the ranked Key
  Action list below holds the whole answer). 0.9 pushed the Key Action column off the stage, 0.8 shows Goals to Remedies/Obstacles and the rest by panning. Not defects: Obstacle titles are cut at the node and shown in
  full in the panel; the first Key Action list item uses `value=rank` on every item on purpose; no Vicious Circle in this graph so back-edge drawing was not exercised on real data. `tests/test_engine_real.py`:
  real Solution Graph built from the vulkan mid-save (3 Goals, fixed overlay) renders identically, also shuffled; no overlap, Goals left of every Key Action; layout 641 ms of a 20 s budget; one `-m network` test
  against the real CDN with SRI passed (marker registered, deselected by default via `addopts`). `docs/awaiting-julian.md` section 3 (German, Artifact publishing). Bundle rebuilt. Tests 438 passed / 31 skipped
  (+1 network), ruff clean. PNG not committed
- 2026-10-24 — M7 increment 1: `docs/plans/M7.md` written (hook protocol and workspace detection, evidence = session turn log plus Player input, number/name extraction and
  normalisation incl. ambiguous `2.794` read both ways, exemptions, derived-sum decision, matching at stated precision, block/log/loop guard (two blocks then release with notice),
  crash-safe exit, `review-blocks` as proposal-only, tests and 6 increments). Docs only; tests 438 passed / 31 skipped, ruff clean
- 2026-10-24 — M7 increment 2: `claims/normalise.py` (`Reading` value + step of the last written digit with `covers` = half-up rounding at the stated precision, separator rules incl. `2.794`/`2,794`
  read both ways, version-shaped tokens are no number, `apply_suffix` k/M, `normalise_name`, `name_forms`) and `claims/extract.py` (`extract_claims` -> `Claim` with kind number/date/name, sentence, line,
  `unit` = list item/table row/paragraph/heading, `quoted` blockquote flag, sign, percent, `within_name`; not-a-claim rules: list/heading numbering, code spans and fences, links/URLs, versions, bare years
  2200 to 2500, digits glued to letters; names only from bold/code/quotes/Name-column cells, not whole-line bold, not one lowercase word, not quotes over 8 words, not commands/paths). Decisions: in-game dates
  are `date` claims matched whole (plan said both "never extracted" and "matched as a whole string"); a number inside a code span name is not extracted (the span is checked as a name). `tests/test_claims_extract.py`
  (61 tests). Tests 499 passed / 31 skipped, ruff clean
- 2026-10-24 — M7 increment 3: `claims/evidence.py` (`build_evidence`: sorted absolute numbers from JSON numbers and numbers in strings, list-of-records lengths count as numbers, dates, all strings case-folded as whole-word name text plus rule ids from `playbook_rules`, rule texts for the blockquote exemption; errors are no evidence; `read_turn_log(since)`, `read_transcript` giving the first timestamp and the Player's own text messages without tool results, meta messages and system reminders) and `claims/check.py` (`check_answer` -> `Verdict`/`Unverified` with reason codes; derived sums/differences of 2 to 4 backed numbers of the same unit and percentage quotients by interval arithmetic over every operand's rounding; ambiguous readings either way; numbers inside a marked name stand with the name; quoted-rule exemption when the results hold rules). Decisions: `derived_unexplained` means the unit shows 2+ backed numbers but none explains the total (a data-wide search for hidden addends would match nearly any number by coincidence), so an unexplained total without shown addends reports `no_match`/`near_match`, and the block reason in increment 4 must say "show the addends or quote the tool's figure" for every number finding; names also match inside longer evidence texts as whole words. CLI `hlidskjalf claims check --workspace --answer [--transcript] [--since]` (JSON, exit 1 on any finding). `tests/test_claims_check.py` (41 tests on synthetic turn logs). Tests 540 passed / 31 skipped, ruff clean
- 2026-10-24 — M7 increment 4: probed the real Stop input (headless `claude -p`, dump hook: fields in `docs/plans/M7.md` open risks; `last_assistant_message` is present; after a block `stop_hook_active`
  is true on every further pass, so the loop guard counts `blocks.jsonl` lines per session and prompt). `claims/hook.py` (`stop`/`decide`: workspace found by walking up to `campaign.yaml` + `.hlidskjalf/`,
  evidence window = transcript start, Player messages exempt, answer from input or last assistant text; block reason lists up to 8 claims with sentence and nearest value plus the rewrite/"show the addends"/
  "do not mention" instruction; `blocks.jsonl` line per block; two blocks then release with `systemMessage`; any exception = exit 0 + `hook-errors.log`), `hlidskjalf hook stop`, `hooks/hooks.json`
  (exec form, `claude plugin validate` clean of hook warnings), `plugin.json` `hooks` key (Claude Code loads the standard file once). Live check with `--plugin-dir` in a temp workspace: a planted `42`
  was blocked, blocked again, released on the third pass (3 lines in `blocks.jsonl`); hook latency ~0.26 s. `tests/test_claims_hook.py` (25 tests). Tests 565 passed / 31 skipped, ruff clean
