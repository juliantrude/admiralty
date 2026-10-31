# Proposed Playbook Rules

Rules that are not in `knowledge/4.5.2/rules/` yet. Only Julian approves a Playbook Rule: the
three seed rules of the build plan are in. Anything else is written down here, in the format
of a rule file (id, reason, applies_to, body), and moves to `knowledge/` once approved.

## standing-trades-are-not-a-fix (proposed 2026-10-31)

```
---
id: standing-trades-are-not-a-fix
date: 2026-10-31
status: approved   # set by Julian on approval
applies_to:
  - market.steady_trade
  - market.trade_pays_deficit
  - food.clone_vats_eat
reason: >
  From Julian's own game (Mireesh Accord): a standing trade covered food and energy deficits until
  the stocks it drew on ran dry, then it swung between stalling and running while the crisis
  lasted. He solved it by taking all trades out and buying only what was needed.
---
A standing market trade is a bridge, not a fix. Do not advise a standing trade to cover a deficit
that production can cover; if one is already in place, check how many months of stock each sale
and the trade value for purchases still have. A trade whose stock lasts less than a month will
stall and the deficit returns at once. Advise to take the trade out together with a fix in
production, and to buy only as much as the deficit needs, since a large trade also pays more fee
and moves the price against the empire.
```
