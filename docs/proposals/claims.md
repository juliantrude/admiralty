# Proposed changes to the Unverified Claim check

Changes to `src/admiralty/claims/` (extractor, matching) or to the Playbook that the
`admiralty:review-blocks` skill proposes after reading `.admiralty/blocks.jsonl`. Nothing here
is applied: Julian decides, and the code, `knowledge/` and the tests change only afterwards.

One section per group of blocks: kind and reason code, how often it happened, the answer
sentences, whether it is a real error or a false positive, and the proposed change.

## Known blind spot: small whole numbers match anywhere in the tool results (found in M7 verification)

**Decided 2026-10-24 (Julian): not applied.** The blind spot stays; recall is not traded for more
false positives on prose.

Kind `number`, would-be reason `no_match`. Not blocked, so not seen in `blocks.jsonl`; found by
planting. On the reference mid-save a wrong sentence "6 Nexus-Distrikte der ersten Stufe" passes
because some other planet's data contains a 6: the evidence is a flat set of numbers from the whole
session, so small integers are easy to hit by coincidence. A wrong figure that no number in the data equals is caught
(a planted 19 against a count of 17 was blocked, with 18 as nearest). Proposal, not applied:
for claims whose value is below 20 also require the claim's sentence to contain a name or key
present in the same tool result entry. Costs: more false positives on prose such as "3 Ziele".
Julian decides whether the check should trade recall for that.


## Name claims on bold sentence leads and code spans (found in M8 verification)

**Decided 2026-10-24 (Julian): applied.** All three parts are in: bold sentences and code
identifiers are no names (`src/admiralty/claims/extract.py`), and the consult and debrief skills
forbid tool and command names in the answer. The quoted epoch title stays a known false positive.

Kind `name`, reason code `name_no_match`. One headless Debrief run over the reference Campaign (150 claims
checked on the first pass) was blocked once with 8 findings, all false positives; the rewrite passed with
149 claims and no finding. Sentences:

- Four bold sentences leading a list item, ending in a full stop: `**Energie ist das Dauerproblem.** In drei von
  fünf Epochen ...`, `**Die Flotte stößt an ihre Grenze.**` and two more. The M7 rule "bold lead of a line ending in
  a colon is a label" does not cover them; they are emphasis sentences, not Display Names.
- Three code spans naming a tool, a command or a tool message: `` `campaign_status` ``, `` `check-epochs` ``,
  `` `no saves in /tmp/h9/src` ``. The code-span rule treats every span as a name to check.
- One quoted phrase of the model's own epoch title: „Aufrüstung ohne Wachstum". The title is the model's text, not a
  tool result.

Proposal, not applied: (1) a bold span that ends in `.`/`!`/`?` or holds more than 6 words is emphasis, not a name;
(2) a code span that is a snake_case/kebab-case identifier or holds a path is no name; (3) the skill could tell the
model not to put tool names in the answer at all (they are no help to the Player). Cost of (1): a long real name in
bold would pass unchecked; Display Names in the reference data are at most 5 words.

## Fehlalarm im Setup (Fund aus dem Ops-Test, 2026-10-31)

**Umgesetzt 2026-10-31** (GOAL.md, Inkrement 1): `admiralty setup` schreibt seine Ergebnisse ins Turn Log,
verschachtelt Fettes wird als innerer Name plus äußerer Satz gelesen, `skills/setup` setzt nur Display Names fett.

Die Prüfung zählt als Beleg nur MCP-Ergebnisse aus dem Turn Log und den Text des Players. Das Setup
läuft über `admiralty setup` per Shell, seine Ergebnisse landen nicht im Turn Log. Deshalb galten
wahre Werte als unbelegt ("Die Borg", `2294.01.01`), und die fett gesetzte Beispielfrage galt als Name.
Vorschlag: `admiralty setup` schreibt seine Ergebnisse ins Turn Log; `skills/setup` setzt nur
Display Names fett. Das Etikett "Stop hook error" stammt von Claude Code; der Hook selbst blockt wie
vorgesehen, die zweite Antwort kam ohne Fehler durch.
