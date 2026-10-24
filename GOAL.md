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
steps to `docs/awaiting-julian.md`, note it in the Blockers line of `## Status`, check the increment off
if only Julian's part remains, and move on to the next increment.

**Out-of-scope systems:**
- Read-only: the game install (`~/.local/share/Steam/steamapps/common/Stellaris`), the
  Player's game data (`~/.local/share/Paradox Interactive/Stellaris`, including saves),
  `~/.claude` and anything outside this repository except `~/.cache/hlidskjalf` and
  temporary directories.
- Reference saves live in `tests/fixtures/saves/` (git-ignored, campaigns `vulkan` and
  `zygerrian`); they contain friends' player names and never enter git or any output
  that leaves the machine.
- M0–M2 code may change when M3–M8 need it, but only with tests, and existing tests and
  the extract schema stay compatible (bump `SCHEMA_VERSION` if a field changes meaning).
- `GLOSSARY.md` and existing ADRs: do not rewrite. A significant new decision gets a new
  ADR in `docs/adr/` (short, in the style of the existing ones).

**Etiquette:**
- Code, docs, commit messages and this file in English, in the domain language of
  `GLOSSARY.md`; `docs/awaiting-julian.md` in German. Skills speak the Player's language
  at runtime (the knowledge stays English).
- Match the existing code style: small deep modules, docstrings that say why, formulas and
  game-file sources written down next to computed values.
- Headless end-to-end checks with `claude -p` (as in M2: a test workspace with
  `campaign.yaml` and an `--mcp-config` pointing at this repo) are allowed, at most two per
  increment, always with `--strict-mcp-config` and an `--allowedTools` list.

**References:**
- `docs/build-plan.md` (milestones, Done-when criteria, Appendix A), `GLOSSARY.md`,
  `docs/adr/`, `CLAUDE.md`.
- Game files via `hlidskjalf.gamefiles.GameData` (Clausewitz parser with inline scripts,
  cached per game build); localisation via `hlidskjalf.extract.names.Localisation`.
- The computed values in `src/hlidskjalf/extract/computed/` are hypotheses pinned by
  pending golden tests; see their docstrings before building on them.
- Order rationale: M3 gives the workspace and archive Muninn needs; M4's graph feeds M5;
  M6 renders M5's Solution Graph; M7 checks M5's Briefings; M8 needs M3's archive and M7.

## Plan

### M3 Campaign Workspace and Campaign Setup
- [x] Study the build plan M3 and GLOSSARY (Campaign Workspace, Campaign Setup, Tracked
      Empire, Fair Play, God Mode); write `docs/plans/M3.md`: workspace layout,
      `campaign.yaml` schema (extends `hlidskjalf.workspace.config`: players with ally or
      rival), archive format, CLI shape for the setup skill
- [x] Workspace module: create and validate a workspace, read and write `campaign.yaml`
      (players, relation, mode, knowledge), with tests
- [x] Archive: every save the MCP service reads is backed up into the workspace and its
      extract stored as `archive/<date>.json.zst`; tests show two saves read leave two
      archived extracts and that Muninn-style reads work after the original save is gone
- [x] `hlidskjalf setup` CLI subcommands (list campaigns in the save folder, list empires
      and players of a save, write `campaign.yaml`) so the skill never hand-writes YAML;
      workspace `CLAUDE.md` template that loads the right skill per mode; tests
- [x] `skills/setup/SKILL.md` (hlidskjalf:setup): the guided conversation from the build
      plan; verify with one headless `claude -p` run in a fresh temp workspace that it
      ends with a valid `campaign.yaml` (scripted answers in the prompt)

### M4 Mechanics Graph and Playbook for 4.5.2
- [x] Study and plan: `docs/plans/M4.md` with the curated graph schema (Causes, Remedies,
      Obstacles, ids, links to generated facts, judgement text) and the generator's scope
- [x] `tools/gen_mechanics.py`: scan `common/` for producers and costs of the key
      quantities listed in the build plan, write `knowledge/4.5.2/generated/*.yaml`; tests
      on known facts (Anchorage +5 naval capacity, Supremacy adoption +20, a naval
      capacity technology)
- [x] JSON Schema for `knowledge/4.5.2/graph/*.yaml` plus a validator
      (`hlidskjalf graph validate`), with tests
- [x] Curated graph, naval capacity domain; test for the M4 criterion: expanding the Goal
      "more naval capacity" from the graph alone yields Supremacy, Anchorages,
      naval-capacity technologies and Soldier jobs, each with its Obstacles
- [x] Curated graph, economy domains: energy, minerals, food, alloys
- [x] Curated graph: Unity and Traditions, influence, research
- [x] Curated graph: pop growth, stability, amenities, housing, building and district slots
- [ ] Playbook seed rules as `knowledge/4.5.2/rules/*.md` (id, date, reason) with a loader
      and tests: Unity against the next Tradition cost; influence at the cap is waste;
      unemployed pops before new colonies
- [ ] Benchmarks draft `knowledge/4.5.2/benchmarks.yaml` (marked draft, with provenance
      and assumptions) and a readable review page `docs/benchmarks-draft.md`; hold point:
      review by experienced players goes to `docs/awaiting-julian.md`

### M5 Huginn in Consulting mode
- [ ] Study and plan: `docs/plans/M5.md` (expansion algorithm, Solution Graph schema,
      Briefing flow, how Key Actions are ranked)
- [ ] `expand_graph` in `src/hlidskjalf/graph/`: Obstacles checked against Snapshot
      numbers, Remedies marked Actionable, Pending or obstructed, depth limit 5 ("too far
      for this Horizon"), loops returned as Vicious Circles, identical nodes merged,
      deterministic; tests
- [ ] Solution Graph JSON Schema and validator (model-added nodes need `source: "model"`),
      with tests
- [ ] `expand_graph` as an MCP tool, logged to the turn log like the others; tests
- [ ] `skills/huginn-consult/SKILL.md` (hlidskjalf:consult): the Briefing flow of the
      build plan, every number from tool results
- [ ] Verification: one headless Briefing on the reference mid-game save
      (`vulkan/2259.12.25.sav`), checked for Playbook Rule ids and for not recommending
      Unity saved for the next Tradition; correctness by golden values is a hold point

### M6 Graph engine
- [ ] `engine/index.html`: Cytoscape.js with ELK.js layered layout, exact pinned CDN
      versions, Goals left, Causes middle, Key Actions right, Vicious Circles coloured,
      model-added nodes marked, click shows evidence; reads `solution-graph.json`
- [ ] Determinism test: the JSON-to-elements transform is a pure function tested with node
      (two Briefings with the same graph data give identical elements and positions);
      publishing as an Artifact is a hold point

### M7 Unverified Claim check
- [ ] Study and plan: `docs/plans/M7.md` (turn boundaries in the turn log, what counts as a
      claim, exemptions, block format)
- [ ] Claim extraction and normalisation module (thousands separators, "7.4k", German and
      English decimal marks, rounding to the stated precision, Display Names), with tests
- [ ] Stop hook script plus `hooks/hooks.json`: reads the turn's tool results from the turn
      log, blocks unmatched numbers and names, appends to `blocks.jsonl`, exempts quoted
      Playbook Rules and Player input; test: a planted wrong district count is blocked
- [ ] `skills/review-blocks/SKILL.md` (developer skill) grouping logged blocks into real
      errors and false positives with proposed fixes
- [ ] Verification on the reference Briefings: normal Briefings pass, false positives at
      most one per Briefing; record the numbers in the log

### M8 Muninn
- [ ] Study and plan: `docs/plans/M8.md` (epochs from archive diffs and Timeline, analysis
      structure, Consulting additions)
- [ ] Epoch detection over archived extracts and Timeline events, tested on the 8-save
      reference Campaign (`vulkan`, 2200 to 2298)
- [ ] `skills/muninn/SKILL.md` (hlidskjalf:muninn) over a chosen time frame
- [ ] Verification: a headless Muninn run over the reference Campaign names its epochs by
      the Timeline and passes the Unverified Claim check

### Closeout
- [ ] Final sweep: everything at spec or documented-blocked in `docs/awaiting-julian.md`;
      DoD checkboxes above updated; README status line updated

## Status

STATUS: READY
**Next action:** M4 increment 8: Playbook seed rules as `knowledge/4.5.2/rules/*.md` (YAML front matter id/date/reason + Markdown body, format in
`docs/plans/M4.md` "Playbook Rules") with a loader and tests. Three approved rules only: `unity-vs-next-tradition` (Unity against the next Tradition cost),
influence at the cap is waste, unemployed pops before new colonies. Check the build plan for the exact ids and wording; the validator already reads rule ids from
`knowledge/<v>/rules/*.md` (`_rule_ids` in `graph/mechanics.py`), so graph nodes may cite them with `rules:` afterwards: add `rules:` links to fitting nodes
(e.g. `unity.*` Obstacles, `influence.*`, the `<domain>.no_spare_pops` Obstacles or `pop_growth.grow_pops`) and keep `graph validate` clean. Further rules go only to
`docs/proposals/playbook.md`. Graph facts: the shared nodes are `unity.raise_income`, `pop_growth.grow_pops`, `jobs.free_jobs` (file `jobs.yaml`, no Goal),
`housing.free_housing`, `slots.more_building_slots` / `slots.more_district_slots`; circle `food_needs_pops` (break point `food.staff_farmers`). Planet-level values
(stability, free housing, amenities, district limit) are not in the metrics registry (empire-level paths only), so those Obstacles are judgement-only. Note
`skills/` is auto-discovered by the plugin; `hooks/` is still empty. The full suite takes ~170 s (run it in the background).
**Blockers:** none for the loop. Waiting for Julian (not blocking): golden values from the
game UI for `tests/golden_values.py` (see `docs/awaiting-julian.md`).

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
