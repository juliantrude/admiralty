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

Wofür: Ops soll später sagen können "für Jahr 2260 ist das wenig". Dafür brauchen wir
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

## 3. Lösungsgraph als Artifact veröffentlichen — entfällt (28.10.2026)

Entschieden in `docs/plans/grilling.md`, Thema 5: Admiralty bleibt lokal und veröffentlicht
nichts bei einem Anbieter. Die Graph-Seite läuft weiter über `admiralty briefing view`.

## 4. Debrief: fühlen sich die Epochen richtig an?

Wofür: Debrief teilt eine Kampagne in Epochen ein (Aufbau, Krieg, Plateau ...). Ob die Grenzen
stimmen und ob die Einteilung dir beim Verstehen hilft, kann nur jemand beurteilen, der die
Partie gespielt hat. Die Probe auf dem Referenz-Spiel (Plexxi, Konföderation von Vulkan, 8 Saves
von 2200.01.01 bis 2298.03.16) ergab fünf Epochen. Alle Grenzen sind durch ein Ereignis der
Timeline oder durch zwei archivierte Daten belegt; ob sie *sinnvoll* sind, ist deine Aufgabe.

So geht's:

1. Die Probe liegt (solange `/tmp` nicht aufgeräumt wurde) in `/tmp/h9/ws/debrief/2200.01.01/epochs.json`
   und die Antwort in `/tmp/h9/answer.md`. Sonst: einen Campaign Workspace mit mehreren gelesenen Saves
   anlegen und Debrief fragen: "Wie sind wir hierher gekommen?" (Skill `admiralty:debrief`).
2. Fünf Epochen: Aufbruch (bis 2230.07.17, Kriegserklärung), Aufrüstung, Krieg und zweite Expansion,
   Nachkrieg und Flottenaufbau, Plateau. Frage dich:
   - Stimmen die Grenzen mit deiner Erinnerung überein? Gab es einen Wendepunkt, den Debrief nicht
     gefunden hat (z. B. eine Entscheidung, die in keinem Save sichtbar ist)?
   - Sind die Titel treffend, und sind "Gut" und "Schlecht" je Epoche das, was du auch so sehen würdest?
   - Sind 5 Epochen zu viele oder zu wenige für 98 Jahre?
3. Wichtige Einschränkung: Zwischen zwei Saves liegen bis zu 25 Jahre. Grenzen "zwischen A und B"
   sind eine Aussage über die Zeitspanne, kein genaues Datum. Je öfter du während des Spiels Saves
   liest, desto genauer werden die Grenzen.
4. Sag mir, was nicht stimmt. Eine Regel für die Einteilung (`REGIME_SERIES` in
   `src/admiralty/debrief/epochs.py`) ändere ich erst auf deinen Wunsch.

Kleinigkeit, die dir auffallen kann: Debrief hat 8 Warnungen des Anspruchsprüfers erzeugt, die
Fehlalarme waren (fett gesetzte Satzanfänge); sie stehen als Vorschlag in `docs/proposals/claims.md`.

## 5. Golden-Werte: freie Gebäudeplätze ablesen

Wofür: Die Obstacles "kein freier Gebäudeplatz" (Gebäudeplätze auf Planeten) prüft Admiralty gegen
eine Zahl, die nicht im Save steht. Wir rechnen sie aus den Spieldateien nach: Jede Zone hat Plätze
für Gebäude (Regierungszone sechs, die meisten anderen drei, einige nur einen), gezählt wird nur
in gebauten Zonen. Ob das mit dem Spiel übereinstimmt, kannst nur du ablesen. Bis dahin überspringen
die Tests (`tests/test_building_slots.py`, `test_golden_building_slots`) mit dem Vermerk "pending".

So geht's (Referenz-Save `vulkan`, `2298.03.11`; bei Bedarf auch `2259.12.25` und `2220.04.22`):

1. Save laden und pausieren, wie bei den Werten aus Punkt 1.
2. Diese drei Planeten öffnen. Sie zeigen drei verschiedene Fälle:
   - Unimatrix 1 (System Unimatrix 1): die Hauptwelt, sollte voll sein.
   - 2 (System Astarte): eine Welt mit teilweise belegten Zonen.
   - Asterion Prime Forsch (System Asterion): eine Welt, auf der Distrikte noch eine leere Zonenstelle haben.
3. Auf jedem Planeten in der Planetenansicht ablesen: wie viele Gebäude gebaut sind und wie viele
   Gebäudeplätze der Planet insgesamt hat (belegte und freie zusammen). Wenn das Spiel nur "frei"
   anzeigt oder nur eine Summe, schreib auf, was dort steht, und ob leere Zonenstellen
   mitgezählt werden.
4. In `tests/golden_values.py` beim Save unter dem Schlüssel `"building_slots"` eintragen, je
   Planet (Name, System) das Paar (Gebäude, Gebäudeplätze), so wie es das Spiel zeigt. Oder mir die
   Zahlen schicken, dann trage ich sie ein.
5. Weicht eine Zahl ab: Planet und Save notieren. Die Regel steht in
   `src/admiralty/extract/computed/building_slots.py`; ich suche dann die Abweichung in den
   Spieldateien, bevor ein Obstacle auf diese Zahl gestützt wird.

Hinweis: Die Synaptic Lathe (Kosmogenese) rechnen wir bewusst nicht. Ihre Plätze hängen an der
Planetenklasse und an Distrikt-Modifikatoren. Kommt so eine Zone in einem Save vor, steht das in
den Fehlern des Extrakts, statt zu raten.
