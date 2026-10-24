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
steps to `docs/awaiting-julian.md`, note it in the Blockers line of `## Status

STATUS: READY
**Next action:** M5 increment 2: `expand_graph` core, as specified in `docs/plans/M5.md` ("Expansion" and increment 2). Move
`_resolve_metric` from `graph/benchmarks.py` into `graph/metrics.py` as `resolve_metric` (benchmarks imports it, behaviour unchanged), write
`graph/expand.py` (`expand_graph(graph, goals, extract, crisis_goals=(), depth_limit=5)` -> `Expansion` with `to_dict()`; check states
present/clear/unknown/judgement; Remedy status actionable/pending/obstructed; BFS depth with `too_far`; Vicious Circles via SCC with break point;
ranked Key Action candidates; `effects` from linked facts; `playbook_rules` text) and `tests/test_expand.py`. First confirm `svc.document(ref)` has the
shape of the metric paths (test on the reference save). Add `pending_when` to Remedies only where a registered metric expresses it. Reference-save
extracts: `Extractor().extract(path, "Plexxi")` (~4 s). The full suite takes ~180 s (run it in the background). `hooks/` is still empty; `skills/` is
auto-discovered by the plugin.
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
