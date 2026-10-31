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
- [ ] 1. Claim check: `admiralty setup` results count as evidence, bold inside bold is read correctly,
      the setup skill bolds Display Names only.
- [ ] 2. A stale save goes on when the Player asks for it (entry 1).
- [ ] 3. Roles of text and graph (entry 6) in `skills/ops/SKILL.md`, with its static test.
- [ ] 4. One current Briefing, updated by feedback, new Goals and new saves, older versions in a
      history (entry 11).
- [ ] 5. Every Briefing composes its graph and opens it in the browser, from the CLI (entry 7).

Block 2, the graph page:
- [ ] 6. Empire-wide nodes: general titles, the detail panel names the planets (entry 8).
- [ ] 7. Goal marks: up, down, flag, a field on the Goal (`docs/plans/grilling.md` topic 7), and the
      epoch titles count as evidence in the claim check.
- [ ] 8. W, A, S, D move the viewport (entry 13).
- [ ] 9. Flags on nodes about an empire (entry 12).
- [ ] 10. Libraries and font shipped offline, footer about the game icons (topic 5, ADR 0004).

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
**Next action:** increment 1.
**Blockers:** none.

## Budget

- session pause threshold: 85%
- weekly pause threshold: 80%

## Log

<!-- Append-only, dated. One line per iteration. Newest at the bottom. -->
- 2026-10-31 — GOAL.md written by Claude after Julian's Ops test on Mireesh; Julian wants the chain to
  do everything without stopping and tests at the end.
