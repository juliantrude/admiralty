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
- **All paths are parameters** (`state_dir`), so tests run on artificial folders and never touch the
  Player's home.
- **Fair Play / Archive:** the watcher only copies files; it never parses a gamestate and so
  adds no knowledge.

## Done when

An automated test with an artificial save folder (saves appear and are overwritten), and a
game evening of Julian after which every autosave is in the archive (his step in "Abnahme").
