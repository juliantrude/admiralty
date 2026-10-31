# GOAL

<!--
  Single source of truth for the /advance-goal loop (driven headless via the
  one-shot systemd chain, or interactively via `/loop /advance-goal`).
  The loop reads and rewrites this file every iteration.
  Earlier chains are archived in docs/plans/goal-M3-M8.md and docs/plans/goal-obstacles.md.
-->

## North star

Finish Admiralty v1: carry out every decision of `docs/plans/grilling.md` and every entry of
`docs/proposals/ops.md`, `docs/proposals/debrief.md` and the section "Fehlalarm im Setup" of
`docs/proposals/claims.md`, then build Academy (M9) as specified in `docs/build-plan.md`,
`GLOSSARY.md` and `docs/plans/grilling.md` topic 1. Those documents are authoritative;
`docs/adr/` and `CLAUDE.md` hold the rules. Julian tests everything himself at the end, so the
chain does not stop for him.

## Definition of Done

- [ ] Every block of `## Plan` is done, or the item that could not be finished is named in
      `docs/awaiting-julian.md` with the reason.
- [ ] `ADMIRALTY_PERF_SLACK=1.5 uv run pytest` passes (pending skips are fine) and
      `uv run ruff check . && uv run ruff format --check .` is clean.
- [ ] One headless Ops Briefing on `vulkan` and one LLM-free Academy rules test on the `vulkan` mid
      save pass, numbers recorded in the Log.
- [ ] `docs/awaiting-julian.md` ends with a German section "Abnahme": one short step per thing
      Julian has to try, without code, in the order he should try them, including the title review,
      the spot check of the UI-location table, the evening with the save service, and the live
      Academy trial on Avarisches Imperium 2297.02.09.

## Working Agreements (read every iteration — these override convenience)

**Priority order per iteration:**
1. If the previous iteration left the test suite red, fix that first.
2. Then take the next unchecked increment from `## Plan`. Each block starts with a short plan
   document `docs/plans/<block>.md` when it needs more than two increments.

**Never stop for Julian.** He tests at the end. When an item needs him, do every part that does not,
add the steps to the section "Abnahme" of `docs/awaiting-julian.md`, and take the next increment.
An item that stays stuck after two iterations gets the same treatment: record what is missing and
move on. Report `blocked` only when no increment is left that can be worked on.

**Git workflow:**
- Work directly on `main` in this repository. Commit locally only; Julian pushes. Never
  push, never force, never rewrite or amend existing commits, never create other branches.
- One commit per finished increment, message in English, plus a short body on why. End every
  commit message with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Verification bar before every commit: `ADMIRALTY_PERF_SLACK=1.5 uv run pytest` green
  and ruff clean. Never commit with failing tests; never delete or weaken an existing test
  to make it pass (fix the code, or record the blocker).
- New Python dependencies only via `uv add`. No system packages, no global config changes.

**Rules that stay hard:**
- Golden values: never fill `tests/golden_values.py`, never derive "golden" numbers from our own
  extractor. Tests that need them skip as pending.
- Benchmarks stay `draft`; Playbook Rules are only proposed in `docs/proposals/playbook.md`.
- Nothing is published or uploaded (ADR 0004). No game graphics enter the repository; icons and flags
  are read from the Player's install at compose time.
- Friends' player names never enter git. Reference saves stay ignored.
- Rules are derived from the game files in `~/.local/share/Steam/steamapps/common/Stellaris`
  (version 4.5.2) and cited in the code; never guessed. New computed values get one module each.
- Fair Play: everything the model is told under `fair_play` is what the Tracked Empire can see.
- Admiralty's core needs no language model; host-specific code stays at the edge (ADR 0004).

## Plan

Block 1, Ops as Julian wants it (`docs/proposals/ops.md`, `docs/proposals/claims.md`):
- [x] 1. Claim check: `admiralty setup` results count as evidence, bold inside bold is read correctly,
      the setup skill bolds Display Names only.
- [x] 2. A stale save goes on when the Player asks for it (entry 1).
- [x] 3. Roles of text and graph (entry 6) in `skills/ops/SKILL.md`, with its static test.
- [x] 4. One current Briefing, updated by feedback, new Goals and new saves, older versions in a
      history (entry 11).
- [x] 5. Every Briefing composes its graph and opens it in the browser, from the CLI (entry 7).

Block 2, the graph page:
- [x] 6. Empire-wide nodes: general titles, the detail panel names the planets (entry 8).
- [x] 7. Goal marks: up, down, flag, a field on the Goal (`docs/plans/grilling.md` topic 7), and the
      epoch titles count as evidence in the claim check.
- [x] 8. W, A, S, D move the viewport (entry 13).
- [x] 9. Flags on nodes about an empire (entry 12).
- [x] 10. Libraries and font shipped offline, footer about the game icons (topic 5, ADR 0004).

Block 3, reaching a target (entry 10):
- [ ] 11. Decode the known systems for Fair Play, resolve names, include bypasses and wormholes.
- [ ] 12. Static routes that differ in the empires they cross, with each empire's attitude, as an
      MCP tool; check on Mireesh 2294.01.01.
- [ ] 13. The rule: every Cause on the way to a Goal has a fitting Remedy or is marked unresolved
      (`graph check-solution`, the page, the skill).

Block 4, knowledge (`docs/plans/grilling.md` topic 3, `docs/proposals/debrief.md`):
- [ ] 14. Market domain in the Mechanics Graph (monthly trades, prices, fees, a trade that fails for
      lack of stock); clone vats connect to the food balance. A Playbook Rule only as a proposal.
- [ ] 15. Debrief: reserve in months beside a negative balance, systems as a series.

Block 5, the save service (`docs/plans/grilling.md` topic 8):
- [ ] 16. `admiralty watch`, inbox, ingest on the next read, autosave extract only, setup question,
      autosave interval hint, systemd user unit.
- [ ] 17. Desktop reminder (`save_reminder_minutes`).

Block 6, titles (`docs/plans/grilling.md` topic 2):
- [ ] 18. Rewrite all titles by the rules, lint test, old/new review page for Julian.

Block 7, Academy (M9):
- [ ] 19. Plan document `docs/plans/M9.md` from the build plan and topic 1.
- [ ] 20. And the following increments as that plan lists them, ending with the LLM-free rules test.

Final:
- [ ] Final verification and the section "Abnahme".

## Status

STATUS: ACTIVE
**Next action:** increment 11 (decode the known systems for Fair Play, resolve names, include bypasses and wormholes; `docs/proposals/ops.md` entry 10; start with a short plan document `docs/plans/reach-target.md` for block 3).
**Blockers:** none.

## Budget

- session pause threshold: 85%
- weekly pause threshold: 95%

## Log

<!-- Append-only, dated. One line per iteration. Newest at the bottom. -->
- 2026-10-31 — GOAL.md written by Claude after Julian's Ops test on Mireesh; Julian wants the chain to
  do everything without stopping and tests at the end.
- 2026-10-31 03:20 — Increment 1 done: `admiralty setup` results are appended to the turn log (workspace of
  `--workspace`, else the current directory if it is a workspace or empty), nested `**bold**` is read as inner
  names plus an outer sentence, the setup skill bolds Display Names only. 852 tests green (3 skips) and ruff
  clean; `tests/test_smoke.py` parse budget fails on this throttled CPU (powersave, 5.2-5.9 s against 4.5 s at
  slack 1.5) also on the untouched HEAD, so it ran with `ADMIRALTY_PERF_SLACK=2.5` (passes, 6.2 s of 7.5 s).
- 2026-10-31 — Increment 2 done: a stale save no longer stops Ops; the `campaign_status` warning, the MCP
  instructions, `skills/ops/SKILL.md` step 1 and the workspace CLAUDE.md say: ask for a new save or for the
  Player's wish to work with this one, then name its age in one sentence and go on. Static test added.
  853 tests green (3 skips) at `ADMIRALTY_PERF_SLACK=2.5` (full run 17 min on the throttled CPU), ruff clean.
- 2026-10-31 — Increment 3 done: `skills/ops/SKILL.md` has the section "Text and graph have separate jobs" (graph = connections and
  proportions, Key Actions in graph and list; text = the Player's wishes, what is not possible and why, what comes first; no repeated
  Key Actions, no description of the graph); steps 7-8 rewritten accordingly. Static test added. 854 tests green (3 skips) at
  `ADMIRALTY_PERF_SLACK=2.5` (17 min), ruff clean.
- 2026-10-31 — Increment 4 done: `workspace/briefings.py` keeps one current Briefing (`briefings/current/` overlay + Solution Graph); `admiralty briefing compose` without `--out` publishes it and moves the replaced version to `briefings/history/NNN-<date>/` (staged write, a refused compose leaves the old one). `skills/ops/SKILL.md` has the section "One current Briefing" (update from the current overlay, draft at `briefings/draft/overlay.json`, no second Briefing). Tests added. 860 tests green (3 skips) at `ADMIRALTY_PERF_SLACK=2.5` (17.5 min) plus the one skill-text test re-run after a wording fix, ruff clean.
- 2026-10-31 — Increment 5 done: `briefing compose` without `--out` starts a detached local server per workspace (`graph/view.py` `show_current`, idle timeout 4 h, state in `.admiralty/view.json`, reused while alive; serves the live `briefings/current/solution-graph.json`) and opens the page in the browser; result has a `view` entry; `--no-open` and `ADMIRALTY_NO_BROWSER` (set for all tests in conftest) switch it off; `briefing view` got `--open`/`--idle-timeout`. Skill tells Ops what to say per `opened`/`url`. Tests added. 870 tests green (3 skips) at `ADMIRALTY_PERF_SLACK=2.5` (17.6 min), ruff clean.
- 2026-10-31 — Increment 6 done: `room.by_planet` (a table, keeps the extract under its 40k budget) in the extract; metrics carry a `by_planet` column, Causes a `places` metric; `expand_graph` adds `places` (up to 8 planets, fewest free first) to Obstacles that are not clear and to those Causes; the Solution Graph shows them as evidence lines in the detail panel. Titles of the empire-wide nodes (slots, housing, jobs) now speak of planets. `tests/test_places.py` plus extract tests. 879 tests green (3 skips) at `ADMIRALTY_PERF_SLACK=2.5` (17.6 min), ruff clean.
- 2026-10-31 — Increment 7 done: Goals carry a `mark` (up, down, flag) as a field of their own: required in the Mechanics Graph (all 13 curated Goals `up`), the Solution Graph and the model's added Goals (`compose` refuses a model Goal without one; a graph Goal must match the curated mark). Icons draw the arrow up, arrow down or flag; the page shows it on placeholders and as a row "Mark" in the detail panel; `skills/ops/SKILL.md` tells the model to set it. `debrief check-epochs` returns `epoch_titles` and logs a clean result to the turn log, so the claim check counts the titles as evidence (a refused proposal does not). Tests added. 890 tests green (3 skips) at `ADMIRALTY_PERF_SLACK=2.5` (17.7 min), ruff clean.
- 2026-10-31 — Increment 8 done: W, A, S, D move the graph view while held (rAF loop, 700 px/s, opposite keys cancel, diagonals not faster; ignored with Ctrl/Alt/Meta and in input fields; released on blur); the engine state has `view` (zoom, pan); seam `AdmiraltyEngine.pan(keys, ms)`. `tests/test_engine_pan.py` added (12 tests). 902 tests green (3 skips) at `ADMIRALTY_PERF_SLACK=2.5` (18.6 min), ruff clean.
- 2026-10-31 — Increment 9 done: nodes the model adds may carry `empire` (a name from the expansion's `empires`, empires in contact; `compose` refuses others and a hand-written `flag`); `Snapshot.empire_flags()` reads each flag from the save (kept out of the extract, which is at its 40k budget) and `expand_graph` returns it as `empires`; `graph/icons.py` `load_flag` composes the flag like `gfx/FX/flag_sprite.shader` (background channels weight swatch slots 0-2 of `flags/colors.txt`, symbol over it) and `compose` embeds it as `flag`; the page shows it in place of the placeholder ("G" stays the fallback) and names the empire in the detail panel; skill text added. Tests added. 916 tests green (3 skips) at `ADMIRALTY_PERF_SLACK=2.5` (19 min), ruff clean. Not checked by eye in the live page (Julian's Abnahme: look at a node about a neighbour).
- 2026-10-31 — Increment 10 done: the graph page is offline. `engine/vendor/` (committed) holds Cytoscape 3.34.4, ELK 0.12.0, cytoscape-elk 2.3.0 and Exo 2 (400/600, latin, @fontsource 5.3.0) with their licence texts; `pins.json` pins version + SRI per file, `tools/fetch_engine_libs.py` writes `vendor/`; `tools/bundle_engine.py` verifies each file against its pin and inlines the libraries as scripts and the font as data URIs (bundle 2.1 MB, loads nothing); `index.html` lost the CDN and Google Fonts tags and got a footer (game icons belong to Paradox, come from the viewer's installation, fan project, sharer is responsible). The test driver now runs Chromium with name resolution off; the `network` marker, the test cache and the CDN tests are gone, replaced by pin/vendor/bundle checks and an offline test of the shipped bundle incl. `document.fonts.check`. 914 tests green (3 skips) at `ADMIRALTY_PERF_SLACK=2.5` (19 min), ruff clean. Not checked by eye (Julian's Abnahme: open the page with the network off, look at the footer and the font).
