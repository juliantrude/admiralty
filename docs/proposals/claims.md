# Proposed changes to the Unverified Claim check

Changes to `src/hlidskjalf/claims/` (extractor, matching) or to the Playbook that the
`hlidskjalf:review-blocks` skill proposes after reading `.hlidskjalf/blocks.jsonl`. Nothing here
is applied: Julian decides, and the code, `knowledge/` and the tests change only afterwards.

One section per group of blocks: kind and reason code, how often it happened, the answer
sentences, whether it is a real error or a false positive, and the proposed change.

## Known blind spot: small whole numbers match anywhere in the tool results (found in M7 verification)

Kind `number`, would-be reason `no_match`. Not blocked, so not seen in `blocks.jsonl`; found by
planting. On the reference mid-save a wrong sentence "6 Nexus-Distrikte der ersten Stufe" passes
because some other planet's data contains a 6: the evidence is a flat set of numbers from the whole
session, so small integers are easy to hit by coincidence. A wrong figure that no number in the data equals is caught
(a planted 19 against a count of 17 was blocked, with 18 as nearest). Proposal, not applied:
for claims whose value is below 20 also require the claim's sentence to contain a name or key
present in the same tool result entry. Costs: more false positives on prose such as "3 Ziele".
Julian decides whether the check should trade recall for that.

