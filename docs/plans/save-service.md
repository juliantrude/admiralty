# Save service (Block 5)

Source: `docs/plans/grilling.md` topic 8. The game overwrites autosaves in turn, so what is not
copied while the game runs is lost for Debrief. Today only a save that is read gets archived.

## Pieces

| Step | What | Where |
|---|---|---|
| 16a | `admiralty watch`: poll the save folder, copy every settled new or changed save raw, sorted by in-game date, into the workspace `saves/` or the inbox. The registry tells which folder belongs to which workspace. | `workspace/watch.py`, `workspace/registry.py`, `cli.py` |
| 16b | Ingest: the next read (`CampaignService.document`, `campaign_status`) extracts every waiting copy. After extraction an autosave copy is deleted (extract only); a manual copy stays when `backup_saves` is on, else it is deleted. | `workspace/ingest.py`, `mcp/service.py` |
| 16c | Setup question (offer the service, wait for the answer), autosave interval hint from `settings.txt` (`autosave`: Never, Daily, Monthly, Quarterly, Semiannually, Annually; recommend quarterly when rarer, never change the game settings). | `workspace/setup.py`, `skills/setup/SKILL.md`, `cli.py` |
| 16d | systemd user unit: `admiralty watch install` writes `~/.config/systemd/user/admiralty-watch.service` and enables it, `admiralty watch uninstall` removes it, `admiralty watch status` names the inbox size. | `workspace/watch_unit.py` |
| 17 | Desktop reminder (`save_reminder_minutes`, default 20, 0 = off, in `campaign.yaml`): game running and no new save in the played Campaign for that long gives `notify-send`; the next save withdraws it. | `workspace/watch.py` |

## Decisions made while planning (details the grilling left open)

- **Detect:** poll every 30 s, no library. A save counts as settled when it has not been modified
  for 3 s and its size is unchanged between two looks (the game writes the zip in one go, but a
  slow disk may show half of it).
- **State:** `~/.local/share/admiralty/watch-state.json` holds `(mtime_ns, size)` per file. The
  first run only records what is there (copying hundreds of old saves would be noise); a later
  start copies what changed while the service was down.
- **Names of raw copies:** `<in-game date>.sav` for a manual save, `<in-game date>.autosave.sav`
  for a file called `autosave_*.sav`. The date comes from the `meta` file inside the zip
  (`setup.read_meta`), no gamestate parsing. A save whose meta cannot be read yet stays unseen
  and is looked at again at the next poll.
- **Registry:** `~/.local/share/admiralty/workspaces.json` maps a save folder to its workspace;
  `admiralty setup write` adds the entry. A folder without an entry goes to
  `~/.local/share/admiralty/inbox/<folder name>/`. Writing the entry moves the inbox of that
  folder into the new workspace's `saves/`.
- **Ingest (16b):** `CampaignService.ingest` runs before a new document is built, in
  `campaign_status` and in `retrospective`. A copy is extracted when its date has no extract made
  from a save at least as new (mtime compare, as in the archive); then an autosave copy is
  deleted, a manual copy only when `backup_saves` is off. A copy that fails (half written,
  other empire) stays, goes to the warnings of `campaign_status` and the turn log, and is not
  parsed again until its mtime changes. Ingest runs before the requested save is parsed because
  it drops the cached gamestate.
- **Setup question and hint (16c):** `admiralty setup autosave` reads `autosave=<n>` from the game's
  `settings.txt` (`workspace/autosave.py`; index order of the localisation keys, checked against
  `autosave=4` and the half-yearly autosaves of Mireesh) and returns `setting`, `recommended`
  (Quarterly, only when the interval is rarer or autosave is Never) and `hint`. The skill asks the
  question after Knowledge and passes the answer as `setup write --save-service|--no-save-service`;
  it lands as `save_service` in `campaign.yaml` (no flag keeps an earlier answer). Installing the
  unit on a yes is step 16d.
- **The unit (16d):** `admiralty watch install` writes `~/.config/systemd/user/admiralty-watch.service`
  (`ExecStart=<the running python> -m admiralty.cli watch`, `Restart=on-failure`, `WantedBy=default.target`;
  `--save-root` / `--data-dir` only when given) and runs `daemon-reload`, `enable --now`, `restart`.
  `uninstall` disables, removes the file, reloads; `status` returns `installed`, `enabled`, `active`,
  the inbox (copies and bytes per folder) and the number of registered workspaces. All three print
  JSON; a refusal of systemd is a message on stderr, exit 1. The unit directory (`--unit-dir`) and
  the `systemctl` call are parameters; tests use a recorder. The setup skill runs `watch install`
  after `check` on a yes and never removes a unit on a no (the unit serves every Campaign).
- **The reminder (17):** `save_reminder_minutes` in `campaign.yaml` (default 20, 0 = off, whole
  minutes; `setup write --save-reminder-minutes`, kept when not given). Every poll the watcher
  checks `game_running` (a `/proc/<pid>/comm` of `stellaris`) and takes the Campaign folder with
  the newest save mtime as the one played. Quiet time = now minus the later of that save's mtime
  and the moment the watcher saw the game start (so an old save does not fire the moment the
  game opens). At or over the wait: one `notify-send --print-id`; it is withdrawn through
  `CloseNotification` (gdbus) when a newer save appears, another Campaign takes over, or the game
  ends, and then the wait starts again. Only folders with a registered workspace are reminded (no
  workspace, no way to switch it off); a broken `campaign.yaml` counts as off. `game_running` and
  the notifier are `Watcher` parameters (default none, so tests and `watch --once` in tests touch
  no desktop); the CLI passes the real ones. Without notify-send or a session bus the reminder is
  silently skipped.
- **All paths are parameters** (`state_dir`), so tests run on artificial folders and never touch the
  Player's home.
- **Fair Play / Archive:** the watcher only copies files; it never parses a gamestate and so
  adds no knowledge.

## Done when

An automated test with an artificial save folder (saves appear and are overwritten), and a
game evening of Julian after which every autosave is in the archive (his step in "Abnahme").
