# Wartet auf Julian

Dinge, die nur du machen kannst. Die Schleife (Hustlebot) trägt hier ein, woran sie nicht
selbst weiterkommt. Erledigte Punkte bitte abhaken oder löschen.

## 1. Golden-Werte aus dem Spiel ablesen — erledigt am 24.10.2026

Abgelesen für drei Vulkan-Saves und das Zygerrianer-Save 2271.08.25, eingetragen in
`tests/golden_values.py`. Ergebnis:

- Flottenkapazität, Distrikt-Grenzen und alle Distrikt-Maxima stimmen exakt.
- Traditionskosten stimmen bis auf höchstens zwei Einheit. Das Spiel zählt auch die
  Abschlüsse der Traditionsbäume mit.
- Unter Blockern liegende Vorkommen zählt das Spiel schon zum Maximum. Wir weisen sie
  zusätzlich als "behind_blockers" aus.
- Stadt- und Nexus-Distrikte: Distrikt-Grenze plus eins pro Blocker. Diese Regel ist aus vier
  Planeten abgeleitet, darunter nur eine Maschinenwelt.
- Die Monatswerte oben in der Leiste rechnet das Spiel nach dem Laden live neu. Sie weichen
  um bis zu zehn vom gespeicherten Haushalt ab. Der Markthandel ist jetzt enthalten.
- Bevölkerung wird mit "k" angezeigt, 5513 erscheint als "5.5k".

Wenn dir später eine Abweichung auffällt: Save und Wert notieren, dann kommt ein weiteres
Referenz-Save dazu.

## 2. Richtwerte (Benchmarks) von erfahrenen Spielern prüfen lassen

Wofür: Huginn soll später sagen können "für Jahr 2260 ist das wenig". Dafür brauchen wir
Richtwerte pro Jahrzehnt. Wir haben keine Quelle dafür und erfinden nichts: Alle Richtwerte
sind noch leer. Ausgefüllt sind nur die Werte, die in unseren Referenz-Saves stehen (ein
Reich pro Kampagne, also kein Maßstab, nur ein Anhaltspunkt). Solange der Status `draft` ist,
benutzt kein Briefing die Zahlen.

So geht's:

1. `docs/benchmarks-draft.md` öffnen (eine Tabelle pro Kennzahl, am Ende die Fragen an die
   Prüfer) und erfahrenen Spielern zeigen.
2. Fragen: Welche Werte erwartet ihr von einem ordentlichen, nicht optimierten Reich pro
   Jahrzehnt? Sind das die richtigen Kennzahlen? Brutto oder netto?
3. Die Antworten mit kurzer Begründung (eigene Partien, Guide, Rechnung) in
   `knowledge/4.5.2/benchmarks.yaml` unter `values` eintragen, mit `basis: reviewed`, oder mir
   als Liste schicken, dann trage ich sie ein.
4. Erst wenn du mit dem Ergebnis zufrieden bist: `status: reviewed` setzen und
   `uv run python tools/gen_benchmarks.py --page-only` ausführen. Dann dürfen Briefings die
   Werte nutzen.

Hinweis: Die Bevölkerungszahlen im Save sind die Werte, die das Spiel anzeigt (5513 erscheint als
"5.5k", siehe Punkt 1). Absolutwerte für Pops sind also brauchbar.

## 3. Lösungsgraph als Artifact veröffentlichen (einmalig)

Wofür: Die Grafik (`engine/dist/index.html`) ist lokal fertig und getestet. Ob ein Claude-Artifact
sie so laden darf (Bibliotheken vom CDN, Daten aus einer Datei), weiß ich erst, wenn du sie einmal
veröffentlicht hast. Ich veröffentliche selbst nichts.

So geht's:

1. Erst lokal ansehen: in einem Campaign Workspace nach einem Briefing
   `uv run hlidskjalf briefing view briefings/<Datum>/solution-graph.json`
   (aus dem Plugin-Ordner mit `--project`). Der Befehl druckt eine Adresse wie
   `http://127.0.0.1:PORT/`; im Browser öffnen. Ohne Briefing geht auch die Datei
   `/tmp/h6/ws/briefings/2259.12.29/solution-graph.json` (Probe-Briefing von Plexxi, Save 2259.12.25),
   falls sie noch existiert.
2. Als Artifact veröffentlichen: den Inhalt von `engine/dist/index.html` in ein neues Claude-Artifact
   (HTML) einfügen und veröffentlichen. Das mache nur du.
3. Im Artifact eine `solution-graph.json` hochladen oder hineinziehen (Auswahlfeld erscheint, wenn keine
   Daten eingebettet sind).
4. Prüfen und mir sagen:
   - Erscheint die Grafik überhaupt, oder bleibt die Seite leer (dann blockiert das Artifact das CDN)?
   - Stehen die Ziele (Goals) links und die Schlüsselmaßnahmen (Key Actions) rechts?
   - Stimmen die Farben: grüne Heilmittel, rote Hindernisse, ein Hindernis mit roter Linie hinein =
     trifft zu; gestrichelter Rahmen = Modell-Knoten (vom Modell ergänzt, nicht aus dem Spielwissen).
   - Zeigt ein Klick auf einen Knoten rechts die Belege (die Zahlen aus dem Save)?
   - Lässt sich die Grafik ziehen und mit dem Mausrad zoomen? Sie startet bewusst oben links in
     lesbarer Größe; die Schlüsselmaßnahmen stehen zusätzlich als Liste darunter.
5. Falls das Artifact das CDN blockiert: sag mir Bescheid, dann binde ich die Bibliotheken
   (rund 1,5 MB) direkt in die Seite ein.

## 4. Muninn: fühlen sich die Epochen richtig an?

Wofür: Muninn teilt eine Kampagne in Epochen ein (Aufbau, Krieg, Plateau ...). Ob die Grenzen
stimmen und ob die Einteilung dir beim Verstehen hilft, kann nur jemand beurteilen, der die
Partie gespielt hat. Die Probe auf dem Referenz-Spiel (Plexxi, Konföderation von Vulkan, 8 Saves
von 2200.01.01 bis 2298.03.16) ergab fünf Epochen. Alle Grenzen sind durch ein Ereignis der
Timeline oder durch zwei archivierte Daten belegt; ob sie *sinnvoll* sind, ist deine Aufgabe.

So geht's:

1. Die Probe liegt (solange `/tmp` nicht aufgeräumt wurde) in `/tmp/h9/ws/muninn/2200.01.01/epochs.json`
   und die Antwort in `/tmp/h9/answer.md`. Sonst: einen Campaign Workspace mit mehreren gelesenen Saves
   anlegen und Muninn fragen: "Wie sind wir hierher gekommen?" (Skill `hlidskjalf:muninn`).
2. Fünf Epochen: Aufbruch (bis 2230.07.17, Kriegserklärung), Aufrüstung, Krieg und zweite Expansion,
   Nachkrieg und Flottenaufbau, Plateau. Frage dich:
   - Stimmen die Grenzen mit deiner Erinnerung überein? Gab es einen Wendepunkt, den Muninn nicht
     gefunden hat (z. B. eine Entscheidung, die in keinem Save sichtbar ist)?
   - Sind die Titel treffend, und sind "Gut" und "Schlecht" je Epoche das, was du auch so sehen würdest?
   - Sind 5 Epochen zu viele oder zu wenige für 98 Jahre?
3. Wichtige Einschränkung: Zwischen zwei Saves liegen bis zu 25 Jahre. Grenzen "zwischen A und B"
   sind eine Aussage über die Zeitspanne, kein genaues Datum. Je öfter du während des Spiels Saves
   liest, desto genauer werden die Grenzen.
4. Sag mir, was nicht stimmt. Eine Regel für die Einteilung (`REGIME_SERIES` in
   `src/hlidskjalf/muninn/epochs.py`) ändere ich erst auf deinen Wunsch.

Kleinigkeit, die dir auffallen kann: Muninn hat 8 Warnungen des Anspruchsprüfers erzeugt, die
Fehlalarme waren (fett gesetzte Satzanfänge); sie stehen als Vorschlag in `docs/proposals/claims.md`.
