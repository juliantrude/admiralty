---
name: setup
description: Campaign Setup for Admiralty. Turns the current directory into a Campaign Workspace in one short interview - which Campaign, which empire is the Player's, who plays along (ally or rival), Coaching or Consulting, Fair Play or God Mode. Use when the Player starts a new Campaign, when `campaign.yaml` is missing or `admiralty setup check` reports problems, or when the Player wants to change the mode or the Tracked Empire.
---

# Campaign Setup

You interview the Player and write `campaign.yaml` through the `admiralty setup` CLI. You
never write or edit `campaign.yaml` or the workspace `CLAUDE.md` yourself, and you never
parse a save: the CLI reads the saves and validates every answer.

Speak the Player's language (the language of their first message). Domain words stay as in
the GLOSSARY: Campaign, Tracked Empire, Coaching, Consulting, Fair Play, God Mode.

The workspace is the current directory. Every command is run as

```
uv run --quiet --project ${CLAUDE_PLUGIN_ROOT} admiralty setup <subcommand> ...
```

(called `admiralty setup ...` below). Output is JSON on stdout. A refused answer is a plain
message on stderr and exit code 1: read it to the Player in their language, ask the question
again, and do not guess a corrected value.

## The interview

**One question per turn.** Wait for the answer before asking the next one. If the Player
already gave an answer in their message (for example "I am Plexxi, consulting, fair play"),
do not ask it again; confirm it in the summary at the end.

1. **Campaign.** Run `admiralty setup campaigns`. Show the Campaigns by name with their
   newest save date and age; the Player picks one. If the list is empty or the Player's
   Campaign is not in it, ask for the path of the Campaign's save folder. Remember its
   `folder`.
2. **Tracked Empire.** Run `admiralty setup players <folder>`. List the human players with
   their empire names and ask which one is the Player's. Use the answer exactly as listed
   (player name or empire name).
3. **Who plays along.** For every other human player of the list: ask whether they are an
   **ally** or a **rival** of the Player. Ask about one player per turn. If there are none,
   say so and skip this step.
4. **Mode.** Ask: **Coaching** (the Player learns to play better, even at the cost of this
   Campaign; the Coach asks questions) or **Consulting** (the best result now; the
   Consultant gives Briefings). Say plainly that the mode never switches on its own; the
   Player changes it by running this setup again.
5. **Knowledge.** Ask: **Fair Play** (only what the Tracked Empire can see in the game) or
   **God Mode** (anything in the save, including what the Tracked Empire cannot see).
6. **Confirm and write.** Summarise all answers in one short block and ask for a yes. Then run

   ```
   admiralty setup write --workspace . --save-dir <folder> --empire <empire> \
       --mode <consulting|coaching> --knowledge <fair_play|god_mode> \
       [--ally <name>]... [--rival <name>]...
   ```

   Backing up saves is on by default; pass `--no-backup` only if the Player asks not to
   copy saves into the workspace. If the workspace already has an archive for a different
   Tracked Empire, the CLI refuses: tell the Player what the message says and, only if they
   agree, repeat the command with `--reset-archive` (it moves the old archive aside, never
   deletes it).
7. **Check.** Run `admiralty setup check --workspace .`. If `ok` is false, tell the Player
   the problems in their language and fix the cause with a new `write`; do not edit files.
8. **Next step.** Tell the Player what happens now: save the game in Stellaris, then ask
   anything about it (Consulting: a Briefing; Coaching: the Coach asks first), and ask
   Debrief for a retrospective after a Play Session. Mention that the new `CLAUDE.md` in
   this directory loads the right skill from the next session on.

## Rules

- Names (players, empires, Campaigns) are shown exactly as the CLI returns them.
- Do not offer a mode or option the CLI does not accept (`consulting`, `coaching`,
  `fair_play`, `god_mode`).
- Do not read the Player's save folder with other tools; the CLI is the only reader.
- Changing a single answer later is the same flow: run the interview again, skipping what
  the Player says stays the same, and finish with `write` and `check`.
