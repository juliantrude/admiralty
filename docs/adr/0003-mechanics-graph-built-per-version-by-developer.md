# Mechanics Graph is generated once per game version by the developer

The campaign-independent network of Causes, Remedies and Obstacles is generated once per Stellaris version from the game files (numbers and sources) and curated by hand (judgement on when each Remedy is worth it). It ships with the Coach, and the developer keeps it up to date, not the Player. Per Briefing the Coach only instantiates it: it marks which Symptoms are present and which Obstacles are active, using the Snapshot. The language model then weighs, prunes and explains, and may add nodes the graph lacks as long as it labels them as not from the model. The prototype re-derived mechanics from the game files on every question, which was slow and produced errors. A fixed graph per version makes Briefings faster, reproducible and testable.

## Consequences

A game update can make the graph stale; the Coach warns when a Snapshot's version differs from the graph's version.
