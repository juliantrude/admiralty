# Build plan: Hliðskjálf v1

The terms used here are defined in [GLOSSARY.md](../GLOSSARY.md). Decisions behind them are in [docs/adr/](adr/).

## Scope of v1

In scope:

- **Huginn** in both modes, Consulting and Coaching.
- **Muninn** over any time frame of a Campaign.
- **Campaign Setup** and a **Campaign Workspace** per Campaign.
- The **Mechanics Graph** and **Playbook** for Stellaris 4.5.2.
- The **Unverified Claim** check.

Out of scope for v1: the Trace mod, a save-folder watcher, a second-model checker, an in-game overlay and Obsidian export.

Target: current vanilla Stellaris (4.5.2 Cygnus) with at most cosmetic mods, on Linux first.

## Shape

```
hlidskjalf/                      # this repo = Claude Code plugin + Python package
├── .claude-plugin/plugin.json
├── skills/                      # setup, huginn-consult, huginn-coach, muninn, review-blocks
├── hooks/                       # unverified-claim check, Player Model guard
├── src/hlidskjalf/
│   ├── extract/                 # save → Snapshot extract (parser, names, empire data)
│   ├── mcp/                     # MCP server exposing extracts and graph expansion
│   ├── graph/                   # Mechanics Graph loader, expansion, Solution Graph schema
│   ├── workspace/               # Campaign Workspace, archive, Campaign Setup
│   └── player/                  # Player Model, the only write path to it
├── knowledge/4.5.2/             # Mechanics Graph (YAML), Playbook Rules, Benchmarks
├── engine/                      # static graph renderer page (HTML + JS)
├── tools/                       # developer scripts: graph generator from game files
└── tests/                       # golden tests against reference saves
```

Where data lives at runtime:

| What | Where | Why |
|---|---|---|
| Campaign Workspace | one directory per Campaign, e.g. `~/Stellaris/<campaign>/` | Claude Code runs there; holds setup, archive, save backups, Predictions, block log |
| Player Model | `~/.local/share/hlidskjalf/player/` | the Player learns across Campaigns |
| Mechanics Graph, Playbook | inside the plugin, per game version | ships with the software, maintained by the developer |

Stack: Python 3.14+ (the `rust_parser` crate requires it), uv, the `rust_parser` crate from stellaris-dashboard (MIT) as a git dependency, its `NameRenderer` approach for Display Names, our own Clausewitz parser for the game files (the save parser rejects script syntax), and the official MCP Python SDK (2.x, `MCPServer`).

## Milestones

Each milestone is a vertical slice that ends in something usable. Order matters: everything depends on correct data, and the Coach depends on the graph and the Player Model.

### M0: Skeleton

- Create the uv project, plugin manifest, empty skill and hook folders, ruff and pytest.
- Add `rust_parser` as a git dependency from the stellaris-dashboard repository (subdirectory `stellarisdashboard/parsing/rust_parser`) and check that it builds with maturin.
- Golden-test harness: reference saves live in a git-ignored folder (`tests/fixtures/saves/`), and tests skip with a clear message when the saves are missing. The saves contain friends' player names and stay out of the repository.

**Done when:** `uv run pytest` runs, and a smoke test parses one 4.5.2 save in under 3 s.

### M1: Huginn's extractor

Builds a **Snapshot extract**: a compact, typed JSON document per save and Tracked Empire.

1. **Header:**
   - Read game version, date and player list from `meta` and `gamestate`.
   - Map multiplayer names to countries.
   - Run the version gate: warn if the version differs from the knowledge pack.
   - Run the mod check: read the enabled mods from `dlc_load.json` and warn about non-cosmetic mods.
2. **Display Names:**
   - Render every name from its key and variables block with the game's localisation in the game language (`l_english`), plus mod localisation.
   - Never output a raw key. An unresolvable name is an error, not a fallback.
3. **Empire data:**
   - Resources: stockpile, income and expenses by source.
   - Pops by stratum and species.
   - Jobs per planet, including open jobs and unemployed pops (`civilian` in 4.5).
   - Districts per type: built and maximum.
   - Buildings and deposits, including blockers that give no districts.
   - Planet designation and sector.
   - Naval capacity, used and maximum.
   - Traditions adopted, Unity stockpile and income, and the cost of the next Tradition.
   - Ascension perks, edicts, policies and influence.
   - Wars and fleets, with power and composition.
   - The Timeline events of the Tracked Empire.
   - Per known empire: the intel level and the visible facts (for Fair Play), plus the full facts (for God Mode).
4. **Computed values:** maximum naval capacity, next Tradition cost and maximum districts are not stored in the save.
   - Derive each from the game files and modifiers in one module per value.
   - Record the formula and its sources in the code.
5. **Diff:** compare two extracts of the same Campaign, covering resources, pops, planets gained or lost, wars and Timeline events in between.

**Golden tests:** the Player reads the values in [Appendix A](#appendix-a-golden-values-to-read-from-the-game-ui) off the game UI for three reference saves (early, mid and late game). Cases the tests must cover:

- Planet "2" in system Helam: 3 generator districts and its true maximum.
- Planet "11" in system Kith'Valas: shows as "11".
- The species shows as "Kithri", not as a translation.
- Umlauts survive ("Konföderation von Vulkan").

**Done when:**
- All golden tests pass.
- Extracting one save takes under 5 s end to end.
- An extract for one Tracked Empire stays under about 40k characters, with per-planet detail available on request rather than always included.

### M2: MCP server

Tools (names are working titles):

| Tool | Returns |
|---|---|
| `campaign_status` | Newest save, its in-game date, real-time age, version and mod warnings |
| `empire_overview` | Situation-level numbers for a Tracked Empire |
| `planets` / `planet` | Planet list with designation, districts, jobs and unemployment; full detail for one planet |
| `economy` | Income and expenses by source, per resource |
| `military` | Fleets, naval capacity, wars, known rival strength (respects Fair Play / God Mode) |
| `progression` | Traditions, next Tradition cost, perks, technologies in progress |
| `timeline` | Timeline events in a date range |
| `compare` | Diff between two extracts |

- Caches the parsed save per file and modification time.
- Writes every tool result to the Campaign Workspace's turn log, which the Unverified Claim check (M7) reads.
- A save older than 10 minutes in real time leads to a prompt to save again.

**Done when:** in a Claude Code session in a Campaign Workspace, "how is my economy?" is answered from tool results only, with correct Display Names, in under 15 s.

### M3: Campaign Workspace and Campaign Setup

- `hlidskjalf:setup` skill. It asks which empire is the Player's, who plays along and whether they are allies or rivals, then the mode (Coaching or Consulting) and Fair Play or God Mode. It writes `campaign.yaml`.
- Archive: every save read is backed up and its extract stored compressed in the workspace (`archive/<date>.json.zst`), so Muninn works after the original saves are deleted.
- Workspace layout and a short `CLAUDE.md` template for the workspace that loads the right skill for the chosen mode.

**Done when:** a fresh directory becomes a Campaign Workspace in one guided conversation, and reading two saves leaves two archived extracts.

### M4: Mechanics Graph and Playbook for 4.5.2

1. **Generator** (`tools/gen_mechanics.py`, developer-only):
   - Scans `common/` for everything that produces or costs a key quantity: naval capacity, energy, alloys, minerals, food, Unity, influence, research, pop growth, stability, amenities, housing, building slots and district slots.
   - Writes the hard facts (source, amount, requirement) to `knowledge/4.5.2/generated/`.
2. **Curated graph** (`knowledge/4.5.2/graph/*.yaml`, one file per domain):
   - Nodes are Causes, Remedies and Obstacles with ids, descriptions, links to generated facts, and a hand-written judgement on when each Remedy pays off.
   - A JSON Schema validates the files.
3. **Playbook Rules** (`knowledge/4.5.2/rules/*.md`, one rule per file with id, date and reason). Seed rules include:
   - Judge Unity against the next Tradition cost.
   - Influence at the cap is waste.
   - Unemployed pops before new colonies.
4. **Benchmarks** (`knowledge/4.5.2/benchmarks.yaml`):
   - Provisional values per decade for the main figures, marked as drafts.
   - Exported as a readable page for review by experienced players.

**Done when:**
- The graph validates.
- Expanding the Goal "more naval capacity" from the Mechanics Graph alone yields Supremacy, Anchorages, naval-capacity technologies and Soldier jobs, each with its Obstacles.
- The benchmark draft is ready for review.

### M5: Huginn in Consulting mode

1. **Graph expansion tool** (`expand_graph`, in the MCP server). It takes Goals and a Snapshot extract and walks the Mechanics Graph:
   - It checks each Obstacle against the numbers and marks Remedies as Actionable, Pending or obstructed.
   - It stops at depth 5 and marks the path "too far for this Horizon".
   - It detects loops and returns them as Vicious Circles.
   - It merges identical nodes.
   - The result is deterministic, so the same input gives the same graph.
2. **Solution Graph JSON Schema.** The model adds nodes outside the Mechanics Graph only with `source: "model"`, and the validator rejects malformed graphs.
3. **`hlidskjalf:consult` skill:** the Briefing flow.
   1. Check the save's age.
   2. Situation.
   3. Goals per Horizon, from Symptoms and the Player's stated ambitions.
   4. `expand_graph`.
   5. The model prunes and weighs.
   6. Key Actions ranked by number of Goals served, strength, speed and cost (high, medium or low), with Crisis Goals first.
   7. Strategy.
   8. Action Plan by domain.

   Every number must come from a tool result. A Briefing names as many Key Actions as the evidence supports.

**Done when:** a Briefing on the reference mid-game save is correct by the golden values, cites Playbook Rule ids, and does not recommend spending Unity that is saved for the next Tradition.

### M6: Graph engine

- One static page (`engine/index.html`) with a layered layout for directed graphs, using ELK.js via Cytoscape.js, pinned versions from a CDN. Goals sit on the left, Causes in the middle and Key Actions on the right.
  - Vicious Circles are coloured.
  - Model-added nodes are marked.
  - Clicking a node shows its evidence.
- Published once as an Artifact. Each Briefing uploads only `solution-graph.json`.

**Done when:** two Briefings with the same graph data render identically, and the model never writes HTML.

### M7: Unverified Claim check

1. A Stop hook script, with no model involved:
   - Read the final answer and the tool results of the turn from the workspace turn log.
   - Extract numbers and Display Names from the answer.
   - Normalise them: thousands separators, "7.4k", German and English decimal marks, rounding to the precision stated.
   - Block when a number or name has no match.
   - Append every block to `blocks.jsonl` in the workspace.
2. Exempt: numbers inside quoted Playbook Rules and explicit Player input.
3. A developer skill, `hlidskjalf:review-blocks`, groups the logged blocks into real errors versus false positives and proposes fixes to the extractor, the check or the Playbook.

**Done when:** a planted wrong district count is blocked, a normal Briefing passes, and false positives on the reference Briefings stay at or below one per Briefing.

### M8: Muninn

`hlidskjalf:muninn` skill over a chosen time frame, from the last Play Session up to the whole Campaign since 2200.

1. It reads archived extracts and diffs, and Timeline events.
2. It splits the time frame into the epochs that shaped it.
3. It gives a classic analysis: what went well, what went badly, and what to learn.
4. In Consulting it adds the state of the Goals.

**Done when:** Muninn over the 8-save reference Campaign (2200 to 2298) names its epochs correctly by the Timeline and passes the Unverified Claim check.

### M9: Huginn in Coaching mode

1. **Player Model:**
   - `src/hlidskjalf/player/` is the only write path. A PreToolUse hook blocks direct writes.
   - Mastery per concept changes only by fixed rules from the Hint Level reached and the outcome.
   - Escape Hatch use is recorded, together with the Situation it happened in.
2. **`hlidskjalf:coach` skill:**
   - Builds the Solution Graph like the Consultant but never shows it.
   - Leads with Socratic questions along the Hint Ladder: one level up after a miss, back to the first after a success.
   - Points the Player to where in the game a fact can be checked.
   - Under Fair Play it never states hidden facts. Under God Mode hidden knowledge may also be stated.
   - Lets instructive mistakes happen below Crisis level, and warns clearly at Crisis level while staying in question mode.
   - Skips concepts the Player Model shows as mastered.
3. **Escape Hatch:** a one-off Consulting call inside a Coaching Campaign. Always available, and recorded.
4. **Predictions:**
   - Asked before major decisions only, and stored in the workspace.
   - Checked against the next extract and by Muninn.
5. **Muninn in Coaching:** the Player's self-assessment first, then the analysis, then the Player Model update.

**Done when:** a scripted Coaching dialogue on the reference mid-game save reaches a Key Action without the Coach stating it before the Player's own attempt. The Player Model changes only through the script, and an Escape Hatch shows up in it.

## Risks and how we catch them

| Risk | Mitigation |
|---|---|
| Computed values (naval capacity, Tradition cost, max districts) are wrong in edge cases | One module per value, formula documented, golden tests from the UI; add a reference save whenever the Player finds a mismatch |
| A game patch changes the save format or the mechanics | Version gate warns; knowledge packs are per version; the golden tests fail visibly |
| Fair Play leaks hidden facts | Extract separates visible and full facts per empire; the tools return only the visible part under Fair Play |
| The Unverified Claim check produces too many false positives | Every block is logged and reviewed after the Play Session (M7); tune the normalisation before tightening |
| The Mechanics Graph is incomplete | The model may add nodes marked as model-sourced; frequent additions are promoted into the graph during maintenance |
| The rust_parser dependency stops being maintained | It is small and MIT licensed; vendor it if upstream breaks |

## Appendix A: Golden values to read from the game UI

For each of three reference saves, read these off the game UI once:

1. **Empire:** in-game date, empire name, and naval capacity used and maximum (Fleet Manager).
2. **Unity and Traditions:** Unity stockpile and monthly income, and the cost of the next Tradition (Traditions screen).
3. **Resources:** monthly net of energy, minerals, food, alloys and influence (top bar tooltips).
4. **Two named planets:**
   - Display Name and system name.
   - Built and maximum districts per type.
   - Open jobs and unemployed pops.
   - Designation.
5. **One renamed planet:** it must show the Player's name.
6. **One rival empire:** its Display Name, and the intel level shown in the contact screen.
