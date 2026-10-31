# Titles of the curated graph (increment 18)

Decisions: `docs/plans/grilling.md` topic 2 and `docs/plans/M6-revision.md` "Agreed but not done yet".

## Where titles live

| Place | What | Rule enforced by |
|---|---|---|
| `knowledge/<v>/graph/*.yaml` | `title` of every Goal, Cause, Remedy, Obstacle; `uncertain_title` of every Obstacle | `admiralty.graph.titles.lint`, `tests/test_titles.py` |
| Goals, Causes, Remedies, Obstacles the model adds in a Briefing | `title` in `add_nodes` | `skills/ops/SKILL.md` ("Titles of nodes you add"); the Academy skill gets the same paragraph in M9 |
| Debrief epochs | `title` of an epoch | already: `debrief check-epochs` warns on digits (`skills/debrief/SKILL.md`) |
| `knowledge/<v>/generated/*.yaml`, `metrics.yaml` | facts and metrics, no titles | none |

## Rules

English; game objects named as in the English interface; no figures in any title.

- **Goal:** the wanted state as a phrase, at most five words, no request. An amount with its
  direction first ("More alloy income"), otherwise the state reached ("Stable planets").
- **Cause:** a short state, at most six words (house limit): "Few staffed Metallurgist jobs".
- **Remedy:** an imperative of at most five words, starting with a verb from `REMEDY_VERBS`.
- **Obstacle:** says what is missing, at most twelve words (house limit). `uncertain_title` is the
  same sentence with "may" and is shown while the check is judgement-only or unknown.

## Done

- 69 titles rewritten (all Causes that were not short states, Remedies over five words, the
  Goals "Amenities for every pop" and "Unity income for Traditions", "Enact" for edicts, one long
  Obstacle). The old titles are kept in `titles-before.json`.
- `tests/test_titles.py` lints the real pack and the review page for staleness.
- `tools/titles_review.py` writes `docs/plans/titles-review.html`: old and new side by side, every
  Goal and Remedy, the energy domain in full, a fixed sample of ten Causes and Obstacles, then
  everything by domain. Julian reads it in the "Abnahme" (more than two bad ones in the sample:
  read all).
