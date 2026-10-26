# Übergabe an die nächste Session (Stand 2026-10-26)

Für Julian und für die nächste Claude-Code-Session. Lies zuerst `CLAUDE.md`, `GLOSSARY.md`,
`docs/build-plan.md`, `docs/plans/M6-revision.md` und `docs/awaiting-julian.md`.

## Was steht

- **Name:** Das Projekt heißt jetzt **Admiralty** (vorher Hliðskjálf). Live-Begleitung im
  Coaching heißt **Academy**, im Consulting **Ops**, das Feedback hinterher **Debrief**
  (vorher Huginn und Muninn). Paket `admiralty`, Befehl `admiralty`, Skills `admiralty:ops`,
  `admiralty:debrief`, `admiralty:setup`, `admiralty:review-blocks`; `admiralty:academy` ist der
  Name für den noch nicht gebauten Coach. Umgebungsvariablen `ADMIRALTY_*`, Workspace-Ordner
  `.admiralty/`. Pläne in `docs/plans/` und ADRs behalten bewusst die alten Namen.
- **Meilensteine:** M0 bis M8 sind gebaut (M0 bis M2 von Claude, M3 bis M8 von Hustlebot),
  alle Tests grün. Die Golden-Werte sind eingetragen und bestätigt.
- **Graph-Seite:** überarbeitet nach Julians Review, alle Entscheidungen in
  `docs/plans/M6-revision.md`.
- **Hustlebot:** Kette fertig (`GOAL.md` ist abgeschlossen und bleibt als Protokoll).

## Was Julian noch selbst tun muss

1. **Ordner umbenennen** (geht nicht aus einer Session heraus, die darin läuft). Danach die
   Hustlebot-Units des alten Pfads entfernen und den Demo-Dienst neu starten:

   ```
   systemctl --user stop hlidskjalf-demo
   bash ~/.claude/plugins/cache/trude-claude/hustlebot/*/scripts/hustle-setup.sh --uninstall /home/julian/Work/stellaris/hlidskjalf
   mv /home/julian/Work/stellaris/hlidskjalf /home/julian/Work/stellaris/admiralty
   cd /home/julian/Work/stellaris/admiralty && uv sync
   systemd-run --user --unit=admiralty-demo --working-directory=/home/julian/Work/stellaris/admiralty \
     /usr/bin/uv run admiralty briefing view --port 8766 /home/julian/Work/stellaris/demo/solution-graph-gewichtet.json
   ```

   Die Claude-Erinnerungen hängen am Pfad: den Ordner
   `~/.claude/projects/-home-julian-Work-stellaris-hlidskjalf/memory` nach
   `~/.claude/projects/-home-julian-Work-stellaris-admiralty/memory` kopieren.
2. **Nebenbei prüfen** (aus `docs/awaiting-julian.md`): Debriefs Epochen der Vulkan-Kampagne,
   das Probe-Briefing in `/home/julian/Work/stellaris/demo/briefing-antwort.md`, eine echte
   Ende-zu-Ende-Abnahme mit installiertem Plugin und eigenem Campaign Workspace.
3. **Benchmarks** von erfahrenen Spielern prüfen lassen (`docs/benchmarks-draft.md`).

## Was die nächste Session noch grillen muss

1. **Academy (M9, der Coach)** — der große offene Block. Sokratische Fragen, Hint Ladder,
   Escape Hatch, Player Model, Predictions, Fair Play beim Fragen; siehe `docs/build-plan.md` M9
   und das Glossar. Braucht Julians Spielgefühl, deshalb gemeinsam bauen, nicht über Hustlebot.
2. **Formulierungen im kuratierten Graphen** (vereinbart, noch nicht gemacht): alle Titel nach den
   Regeln in `docs/plans/M6-revision.md` umschreiben. Klären: wer prüft das Ergebnis, Julian
   stichprobenartig oder ganz?
3. **Ein echtes Ops-Briefing mit vom Modell vergebenen Gewichten.** Die Gewichte im Demo-Graphen
   hat Claude von Hand gesetzt. Klären: Sind die Begründungen des Modells brauchbar, und stimmt die
   Größenwirkung im Graphen dann noch?
4. **Restliche graue Hindernisse:** Gebäudeplätze (Zonen in den Spieldateien) und Freischaltungen
   (erforschte Technologien im Save auswerten). Klären: lohnt der Aufwand, welche zuerst?
5. **Veröffentlichen der Graph-Seite als Artifact** (privat): klappt das Laden der Bibliotheken
   vom CDN dort, und sollen die eingebetteten Spielsymbole (Paradox-Grafiken) in ein
   veröffentlichtes Artifact? Rechtlich vorsichtig: privat ja, öffentlich teilen eher nicht.
6. **Symbole:** Einige Bereichssymbole sind unscharf (Quellen nur 20 bis 30 px). Option: eigene
   Vektorsymbole im Stil des Spiels für die gut zehn Bereiche. Entscheiden, ob gewünscht.
7. **Kleinere offene Punkte:** Zielpfeil zeigt immer nach oben (auch bei "weniger X"-Zielen?);
   Debrief-Fehlalarm bei zitierten Epochentiteln (`docs/proposals/claims.md`); ob die Rangliste
   der Key Actions unten ihr endgültiger Platz ist.

## Praktisches

- Demo: `http://127.0.0.1:8766/index.html`, Graph-Daten in `/home/julian/Work/stellaris/demo/`.
  Server immer als Benutzerdienst starten (`systemd-run --user`), nie als Hintergrund-Shell.
- Tests: `ADMIRALTY_PERF_SLACK=1.5 uv run pytest` (rund sechs Minuten), Engine neu bündeln mit
  `uv run python tools/bundle_engine.py`, Symbole neu zuordnen mit `uv run python tools/gen_icons.py`.
- Die Referenz-Saves liegen ignoriert in `tests/fixtures/saves/` (vulkan, zygerrian).
