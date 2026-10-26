# M6 revision: the Solution Graph page after Julian's review (2026-10-24 to 2026-10-26)

Decisions from the grilling and the review rounds on the demo Briefing (Plexxi, vulkan
2259.12.25). Code: `engine/`, `src/admiralty/graph/` (icons, metrics, solution), `tools/gen_icons.py`.

## Kept

- **The whole graph stays on screen.** A click on a node or a Key Action focuses its chain: the
  chain stays, the rest fades to 15 %. A background click or Esc ends the focus. A selection adds
  no lines. Tried and dropped: a speech bubble at the node (it hid the edges), hiding everything
  outside the chain with a centred re-layout (lost the eye's bearings, nodes overlapped), the same
  with a shape-keeping animation (technically fine, less clear). The attempts are in the history.
- **Columns come from the edges only**, Goals pinned left. Key Actions were pinned right before,
  which made chains zigzag when one Key Action unblocks another. Now every edge points right and a
  chain reads as a plan: do the right end first, each step frees the next one to the left.
- **The view moves to the focused chain** (whole chain if readable, else the clicked part).
- **Details in the panel on the right, the ranked Key Actions below the graph.**
- **Node size = impact on the Goals.** The overlay weighs every edge into a Cause (high, medium,
  low, with a reason from the numbers; compose refuses a missing one); edges into a Remedy take its
  strength; weights multiply along the strongest way and add up over Goals; three size steps;
  Goals stay the same size. Edge width follows the weight (thick high, thin, dashed low).
- **States by colour and border only:** actionable bright green border, pending hatched,
  obstructed greyed and dashed. Holding Obstacles are red with a red line into them. Obstacles
  checked and clear leave the drawing and are listed in their Remedy's details ("Checked, not in
  the way"). Unchecked Obstacles are grey, dotted, and their title is in the conditional
  (`uncertain_title`, e.g. "The planet may have no free building slot").
- **Nodes show the title alone**, whole, on one line, 15 px; the node grows with the text, which
  is measured in the drawn font. No type, state or rank words, no badges.
- **Game icons** on the left of every node (35 px drawn, 88 px embedded): matched per node through
  its facts to the game object and its sprite (`tools/gen_icons.py` -> `knowledge/4.5.2/icons.yaml`),
  else the domain's technology icon; Goals get a green up arrow. Read from the Player's install at
  compose time and embedded as PNG; no game graphics in the repository; the model never sees them.
- **Stellaris-like dark theme by default**, light theme on a toggle; Exo 2.
- **Legends** for the node encodings and for the kinds of line.

## Data changes that came with it

- Extract section `room`: free district slots (all, per rural type) and open jobs by produced
  resource; eight "no free slot" Obstacles check against it. `only_clears` lets a metric that
  covers part of an Obstacle rule it out but not confirm it.

## Agreed but not done yet

- **Wording rules for all node titles** (F2): Causes short states ("Few staffed Metallurgists"),
  Remedies imperatives of at most five words ("Open more job slots"), Obstacles say what is missing,
  no figures, English. Every title of the curated graph still needs the pass.

## Appendix: Julian's first feedback (docs/Feedback Graph.md, 2026-10-24)

Visual: a game icon left in every tile (alloys icon plus green up arrow for "More alloy income");
blocked Remedies visibly disabled; selecting a node brings its whole chain into focus and puts the
rest in the background. Content: the Goal to Cause link reads oddly ("More alloy income" ->
"The multipliers on alloy output are small"); either Goals become problems or Causes become
solutions (decided: keep as is for now); clearer wording such as "Open more job slots".
