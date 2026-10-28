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

- [ ] `docs/plans/obstacle-checks.md` lists all 39 `judgement_only` Obstacles with their group,
      the metric that checks them (or why none can), and the save fields and game files used.
- [ ] Every Obstacle in the groups "perks and traditions", "free job slots", "unlocks" and
      "building and zone slots" has a metric check (`check: {metric, op, compare_to}`), or the
      plan document names the concrete reason it cannot have one. The 8 real trade-offs stay
      `judgement_only`.
- [ ] Each new computed value has its own module with the formula and its game-file sources in
      the code (`CLAUDE.md`), and a test on the reference saves (`vulkan`, `zygerrian`).
- [ ] Free building slots are computed values: their golden tests exist and skip as pending
      until Julian reads the values in the game; the steps for him are in
      `docs/awaiting-julian.md` (German, without code).
- [ ] `ADMIRALTY_PERF_SLACK=1.5 uv run pytest` passes (pending skips are fine) and
      `uv run ruff check . && uv run ruff format --check .` is clean.
- [ ] One headless Ops Briefing on a reference save shows the newly checked Obstacles as checked
      (numbers recorded in the Log).

## Working Agreements (read every iteration — these override convenience)

**Priority order per iteration:**
1. If the previous iteration left the test suite red, fix that first.
2. Then take the next unchecked increment from `## Plan`.

**Git workflow:**
- Work directly on `main` in this repository. There is no remote: commit locally, never
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
steps to `docs/awaiting-julian.md`, note it in the Blockers line of `## Status`, and move on.

**Model:** the loop runs on Sonnet with high effort. If the zone rules (increment 5) are still
not working after two iterations, write that into Blockers and stop the chain; Julian then
switches `.hustle/config` to Opus.

## Plan

- [ ] 1. Plan document `docs/plans/obstacle-checks.md`: classify all 39, name metric, save fields
      and game files per Obstacle, and split groups 3 and 5 into increments if they are large.
- [ ] 2. The 6 quick ones (perks and traditions, free job slots): data already in the extract.
- [ ] 3. The 14 unlocks: researched technologies from the save, prerequisites from the game files.
- [ ] 4. Verification of 2 and 3: tests on the reference saves, one headless Briefing.
- [ ] 5. The 11 building and zone slots: rebuild the zone rules from the game files, golden tests
      pending for Julian, steps in `docs/awaiting-julian.md`.
- [ ] 6. Final verification: full suite, ruff, one headless Briefing, numbers in the Log.

## Status

STATUS: ACTIVE
**Next action:** increment 1, the plan document.
**Blockers:** none.

## Budget

- session pause threshold: 85%
- weekly pause threshold: 80%

## Log

<!-- Append-only, dated. One line per iteration. Newest at the bottom. -->
- 2026-10-28 — GOAL.md written by Claude from `docs/plans/grilling.md` topic 4 after all grilling
  topics were closed; Julian starts the chain tonight.
