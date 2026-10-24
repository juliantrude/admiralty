# Own extractor on top of the stellaris-dashboard parser, exposed via MCP

The Coach reads Snapshots through our own thin extractor, built on the Rust parser and name rendering of eliasdoehne/stellaris-dashboard (MIT) and served to Claude Code as an MCP server. We tested both existing projects against real 4.5.2 saves on 2026-10-23. stellaris-companion was fast (2–3 s) but reported only "4 districts" per planet, had no per-planet jobs or unemployment, garbled names (unresolved systems, templated species, broken UTF-8) and its parser dropped repeated keys. stellaris-dashboard rendered every Display Name correctly and its parser returns the full gamestate in 2–3 s, but its database lacks per-planet jobs, districts over time and naval capacity, and full ingestion takes over 20 s per save. Neither delivers what a Briefing needs, but the dashboard solved the two hard parts.

## Considered Options

- **Use stellaris-companion's MCP relay as-is**: rejected, wrong districts and names were exactly the prototype's failures.
- **Use the stellaris-dashboard database**: rejected, missing coaching data and slow ingestion.
- **Ad-hoc parsing by the agent per question** (the prototype): rejected, slow and produced wrong planet names and district counts.

## Consequences

Values the save does not store (maximum naval capacity, next Tradition cost, maximum districts) must be computed from modifiers. Each computed value is pinned by golden tests against numbers read off the game UI for a few reference saves.
