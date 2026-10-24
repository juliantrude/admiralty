---
name: review-blocks
description: Developer skill for Hliðskjálf, not for the Player. Reads the log of the Unverified Claim check (`.hlidskjalf/blocks.jsonl`), sorts every group of blocked claims into a real error of the model or a false positive of the check, and writes a proposal per group into `docs/proposals/claims.md`. Use when a developer asks to review the blocks, the false positives or the Unverified Claim hook.
---

# Reviewing the blocks of the Unverified Claim check

The Stop hook blocks an answer when a number, date or name in it is not in the tool results of
the session. Every block is one line in `<workspace>/.hlidskjalf/blocks.jsonl`. You review that
log for a developer. You **propose**; you never edit code, `knowledge/` or tests, and you never
touch `blocks.jsonl`.

The workspace is the directory the developer names (default: the current directory). Run

```
uv run --quiet --project ${CLAUDE_PLUGIN_ROOT} hlidskjalf blocks summary --workspace DIR
```

Output is JSON: `blocks`, `claims`, `unreadable_lines`, `by_kind`, `groups` and `released`.
Each group is one kind (`number`, `date`, `name`) with one reason code, a `count`, and
`examples` with the answer `sentence`, the claim `text`, the `nearest` value in the tool
results and whether the block was `released`. Without a log the command prints zero blocks:
say so and stop.

## Reason codes

- `no_match`: no value in the tool results rounds to the claim.
- `near_match`: a value within 10 % exists; the model probably rounded or misread it.
- `derived_unexplained`: the item shows two or more backed numbers, but none of their sums,
  differences or ratios gives the total.
- `name_no_match`: a marked name (bold, code, quotes) is in no tool result.
- `released`: the answer was let through after two blocks, so the model could not or would not
  satisfy the check. Read these first.

## Steps

1. Run the summary. Report the counts in one line: blocks, claims, groups, released.
2. Take the groups from the largest down. For each, read every example and decide:
   - **Real error**: the model invented the value, mis-rounded it, added a total it did not
     show, or named something no tool returned. The check did its job.
   - **False positive**: the claim is fine and the check is wrong, for example a figure the
     tool results hold in a form the extractor does not read, a number that is not a claim, a
     name that is only emphasis, or a total the Player can see the addends of.
   Judge from the sentence and the `nearest` value. If the sentence does not settle it, say
   "unclear" and do not guess.
3. For every group write one section into `docs/proposals/claims.md`, replacing the line
   `_No proposals yet._` the first time:
   - the heading: kind, reason code and count;
   - two or three of the sentences, quoted as logged;
   - the verdict: real error, false positive or unclear, with the reason in one sentence;
   - the proposed change: for a false positive, what the extractor or the check should do
     differently (name the module: `claims/extract.py`, `claims/normalise.py`, `claims/check.py`
     or `claims/evidence.py`) or the Playbook Rule or consult-skill sentence that should change;
     for a real error, which skill sentence would have prevented it, or "none".
4. End with the path of the file and the number of sections written.

## Hard rules

- Every figure in a proposal comes from the summary. Do not compute or guess a number.
- A proposal is a text. Do not change the extractor, the check, a skill, a Playbook Rule, a
  benchmark or a test, and do not add anything to `knowledge/`. A new Playbook Rule is
  written only as a proposal in `docs/proposals/playbook.md` format.
- Do not weaken the check to make a group disappear: a false positive needs a narrower rule
  with an example, not a looser match.
- Never print a raw localisation key as a Display Name. If a logged sentence holds one, report
  it as an error of the answer.
- Write to nothing outside `docs/proposals/claims.md`.
