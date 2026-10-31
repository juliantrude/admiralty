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

## 4. Debrief: fühlen sich die Epochen richtig an? — vorläufig erledigt am 31.10.2026

Durchgegangen auf der Kampagne `vulkan`: Die fünf Epochen und ihre Grenzen passen, soweit Julian
sich erinnert. Die Kampagne ist länger her, deshalb gilt das Urteil nur vorläufig; endgültig prüft
er es an einer frischeren Kampagne. Die Regel für die Einteilung bleibt. Zwei Änderungen stehen in
`docs/proposals/debrief.md`.

## 5. Golden-Werte: freie Gebäudeplätze ablesen — erledigt am 30.10.2026

Abgelesen im Save `vulkan` 2298.03.11 an drei Planeten, eingetragen in `tests/golden_values.py`:
alle drei stimmen mit der Berechnung überein. Gezählt werden nur fertige Gebäude.

## 6. Golden-Werte: freie Sternenbasis-Plätze ablesen — erledigt am 30.10.2026

Abgelesen im selben Save an drei Sternenbasen (Thrish, Menkar, Talemes Mar), eingetragen in
`tests/golden_values.py`: alle drei stimmen mit der Berechnung überein.

## 7. Lizenz des offiziellen Paradox-Wikis — geprüft am 31.10.2026

Geprüft auf `central.paradoxwikis.com/Central:Copyrights` (die Copyright-Seite des Stellaris-Wikis
leitet dorthin weiter). Ergebnis: Die Texte stehen unter Creative Commons Attribution-Share Alike
3.0 (CC BY-SA 3.0): Weitergabe und Bearbeitung nur mit Namensnennung samt Link auf das Wiki und
unter gleicher Lizenz. Bilder und andere Dateien haben je eigene Lizenzen; Inhalte aus den Spielen
gehören Paradox. Folge: Admiralty übernimmt keinen Wiki-Text und keine Wiki-Bilder. Die Liste der
Lesetipps aus dem Wiki bleibt leer (Entscheidung 6 in `docs/plans/M9.md`), der Coach nennt keinen
Wiki-Link. Wenn du später doch Links (keinen Text) willst, ist das deine Entscheidung; Links zu
nennen ist urheberrechtlich unkritisch, die Auswahl der Seiten müsstest du aber selbst prüfen.

Die Tabelle "Wo im Spiel" (`knowledge/4.5.2/ui_locations.yaml`) stammt allein aus den
Interface- und Lokalisierungsdateien deiner Installation. Die Stichprobe dazu kommt in den
Abschnitt "Abnahme".
