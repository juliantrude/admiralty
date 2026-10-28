# Admiralty

An AI system that helps a player master Stellaris faster by reading the state of a running Campaign, advising during play and reflecting afterwards. Named after Odin's high seat, from which he overlooks all worlds.

## Language

### People and scope

**Coaching**:
The mode whose aim is that the Player becomes a strong player in the long run, even at the cost of the current Campaign. Uses the Solution Graph internally, never shows it, and leads the Player by Socratic questions.
_Avoid_: Training mode, tutor mode

**Consulting**:
The mode whose aim is that the Player does as well as possible right now. Delivers Briefings and shows the Solution Graph.
_Avoid_: Crisis mode, advisor mode

**Coach**:
The persona in Coaching mode.
_Avoid_: Tutor, agent

**Consultant**:
The persona in Consulting mode.
_Avoid_: Advisor, agent

**Player**:
The human being coached or consulted, in their own language.
_Avoid_: User

**Campaign**:
One playthrough of Stellaris from game start to end, possibly spread over many play sessions and save files.
_Avoid_: Game, run, round

**Campaign Setup**:
The short interview at the start of a Campaign: which empire is the Player's, which friends play along, whether they are allies or rivals, and whether the Campaign runs in Coaching or Consulting mode. The mode never switches on its own.
_Avoid_: Config, onboarding

**Campaign Workspace**:
The directory that belongs to one Campaign, in which its Claude Code sessions run and which holds everything about it: Campaign Setup, archived Snapshot extracts, save backups, Predictions and notes. Debrief's memory of the Campaign.
_Avoid_: Session folder, project

**Play Session**:
One sitting in which the Player plays part of a Campaign, from launching the game to quitting it.
_Avoid_: Session (alone), game session

**Academy**:
The Coaching side of the live phase: the Coach accompanies the Player during a Play Session and trains them with questions. Named after the place where officers learn to decide for themselves.
_Avoid_: Huginn (the old name), live coaching, tutorial

**Ops**:
The Consulting side of the live phase: the Consultant gives a Briefing on the situation and what to do now. Named after the operations staff who keep the picture of the whole front.
_Avoid_: Huginn (the old name), war room, live phase

**Debrief**:
Feedback after the fact over a chosen time frame of a Campaign, from the last Play Session up to the whole Campaign since 2200. Says what went well and what went badly; in Coaching, the Player's own assessment comes first.
_Avoid_: Muninn (the old name), retrospective, retro, game review, post-game analysis

**Fair Play**:
The Campaign Setup option under which Coach and Consultant state only what the Tracked Empire can see in the game. Hidden knowledge may still decide what the Coach asks about and how urgently, but every question and hint, up to the full explanation, points only at what the Player can see (ethics, attitude, borders, the fleet strength intel shows).
_Avoid_: Fog of war mode, fair mode

**God Mode**:
The Campaign Setup option under which Coach and Consultant may state anything in the Snapshot, including what the Tracked Empire cannot see.
_Avoid_: Cheat mode, omniscient mode

**Tracked Empire**:
An empire the player has explicitly selected for analysis, e.g. their own or a friend's in multiplayer. Other empires appear only as context.
_Avoid_: Player empire, target

**Supported Game**:
A campaign on the current vanilla Stellaris version with at most cosmetic mods. Anything else triggers a warning before advice.

### Game data

**Snapshot**:
The complete state of the galaxy at one in-game date, as stored in a save file.
_Avoid_: Save, savegame (for the data; "save file" is the file itself)

**Timeline**:
The game's own dated record of milestone events per empire (wars, deficits, new colonies, ascension perks), carried inside every Snapshot. Holds events, not numbers.
_Avoid_: History, event log

**Trace**:
A continuous, dated record of selected values and events for Tracked Empires, collected from inside the running game between Snapshots.
_Avoid_: Log, tracing, history

**Display Name**:
The name of a planet, system, species or empire exactly as the game client shows it, including names the player gave themselves.
_Avoid_: Internal name, key

### Knowledge

**Playbook**:
The curated body of Stellaris mechanics, rules of thumb and benchmarks that Coach and Consultant reason with. The Player is the final arbiter of what belongs in it.
_Avoid_: Knowledge base, guide, prompt

**Playbook Rule**:
One statement in the Playbook, e.g. "judge stockpiled Unity against the cost of the next Tradition, never as an absolute number".
_Avoid_: Tip, fact

**Benchmark**:
A reference value for a given point in a campaign, e.g. expected research output around 2230, used to judge whether a Tracked Empire is ahead or behind.
_Avoid_: Target, KPI

**Mechanics Graph**:
The campaign-independent network of Causes, Remedies and Obstacles for one game version, e.g. "naval capacity comes from Supremacy, Anchorages, technologies and Soldier jobs". Part of the Playbook.
_Avoid_: Dependency model, tech tree

### Diagnosis

**Goal**:
A desired state of the Tracked Empire within a Horizon, and the only kind of root in a Solution Graph. It either answers a Symptom ("stop the hostile neighbour") or states an ambition of the Player ("wipe out the Vulcan Confederacy").
_Avoid_: Milestone, objective

**Symptom**:
Something observable in the data or reported by the Player that signals an unmet Goal, e.g. a hostile neighbour or mediocre research output.
_Avoid_: Problem, issue

**Cause**:
An answer to "why is this Goal unmet?". Causes chain into further Causes, as deep as the evidence goes.
_Avoid_: Root problem, reason, constraint

**Root Cause**:
A Cause at the bottom of a chain, one that the Mechanics Graph offers Remedies for.
_Avoid_: Underlying issue

**Remedy**:
Something that directly addresses a Cause, e.g. the Supremacy tradition tree or building Anchorages against low naval capacity.
_Avoid_: Solution, fix, zeroth-order solution

**Obstacle**:
A reason a Remedy cannot be carried out yet, e.g. not enough Unity for Supremacy. Each Obstacle gets its own Remedies, which is what makes the graph recursive.
_Avoid_: Blocker (the game uses it for negative planet features), prerequisite

**Actionable**:
A Remedy the Player can carry out now with what the empire has.

**Pending**:
A Remedy that will become Actionable within the Horizon without further Player action, e.g. jobs that population growth will fill, or a research enclave the empire's alloy income will afford in a few months. Treated like Actionable when the graph is expanded.
_Avoid_: Waiting, blocked

**Vicious Circle**:
A loop of Causes that feed each other, e.g. energy needs jobs, jobs need pops, pops need food, food needs energy. Named explicitly, with the cheapest point to break it.
_Avoid_: Cycle, loop, deadlock

**Solution Graph**:
The merged network for one Briefing, running from Goals through Causes, Remedies and Obstacles to Key Actions.
_Avoid_: Solution tree, dependency tree

**Diagnosis**:
The part of a Solution Graph that runs from a Goal down to its Root Causes, each link backed by a number from a Snapshot or Trace.
_Avoid_: Analysis, root cause analysis

### Consulting output

**Briefing**:
The Consultant's analysis of a Tracked Empire at one point in a Campaign: Situation, Goals per Horizon, the Solution Graph behind them, and the Action Plan.
_Avoid_: Analysis, report, Lagebild

**Situation**:
The phase that currently defines a Tracked Empire's campaign, e.g. a war with a neighbour, an expansion phase, or an economic crisis after a defeat.
_Avoid_: Status, overview

**Crisis**:
A Situation that threatens the empire's viability and needs action before anything else, e.g. collapsing energy income or a lost war. Goals that answer a Crisis always come first.
_Avoid_: Problem, issue; not the game's endgame crisis (that is the **Endgame Crisis**)

**Horizon**:
One of three time frames a Briefing sets Goals for: short, medium and long term.
_Avoid_: Phase, timeframe

**Key Action**:
An Actionable Remedy selected for the Action Plan, ranked by how many Goals it serves, how strongly, how fast and at what cost.
_Avoid_: Lever, tip, recommendation, top 3

**Strategy**:
The ordered path through the Solution Graph from the first Key Actions to a Goal. The obvious answer ("build more fleets") is a Goal; how to get there is the Strategy.
_Avoid_: Plan, solution

**Action Plan**:
The Key Actions of a Briefing in order of priority, grouped by domain (economy, military, diplomacy, ...).
_Avoid_: To-do list, recommendations

### Coaching

**Player Model**:
The record of which Stellaris concepts the Player has mastered and how well, derived only from observable facts such as which Hint Level the Player needed. One per Player across all Campaigns; a concept is a node of the Mechanics Graph, and each sits on a Mastery Level.
_Avoid_: Learner profile, skill rating

**Mastery Level**:
How well the Player has mastered one concept, on six levels modelled on the revised Bloom taxonomy, each backed by an observable fact: New, Understand (found the cause in conversation), Apply (a Snapshot shows it done), Analyse (found the cause before the Coach named the domain), Evaluate (chose between Remedies with reasons, or a Prediction came true), Create (avoided the problem unprompted). It drops one level when the cause reappears in two Snapshots a year apart outside a Crisis.
_Avoid_: Score, skill points, checkmark

**Hint Ladder**:
The four levels of help in Coaching: question, hint, partial answer, full explanation. One level up after a failed attempt (two during a Crisis), back to the first after a success.
_Avoid_: Hint system, help levels

**Escape Hatch**:
The Player's request to just be told the answer. Always honoured in Coaching, counted as the top Hint Level and recorded in the Player Model.
_Avoid_: Skip, cheat

**Prediction**:
The Player's stated expectation of what a major decision will achieve, given before the decision and checked against a later Snapshot on a date the Coach proposes. An expectation asked only after the decision is stored apart as a hindsight expectation and weighs less in Debrief.
_Avoid_: Guess, forecast

**Drill**:
One run of Coaching questions about one Snapshot, from the Coach's opening question to the short summary of what the Player means to do. One question at a time; Crises first.
_Avoid_: Lesson, session, round

**Rendezvous**:
The in-game date the Coach and the Player agree on at the end of a Drill: the Player plays until then, saves by hand under an agreed name, and the next Drill starts like a Debrief in Coaching.
_Avoid_: Appointment, meeting, check-in

**Unverified Claim**:
A number or name in a Coach or Consultant answer that does not appear in the game data the answer was based on. Such answers are blocked and logged for review after the play session.
_Avoid_: Hallucination, error
