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

## 8. Abnahme

Hier sammelt sich alles, was nur du prüfen kannst, in der Reihenfolge, in der du es probieren
solltest. Der Abschnitt wird im letzten Schritt der Kette um die übrigen Punkte (Ops, Titel,
Speicherdienst) ergänzt. Bis dahin steht hier die Academy (M9).

### Academy

1. Stichprobe der Tabelle "Wo im Spiel" (`knowledge/4.5.2/ui_locations.yaml`): Öffne im Spiel
   drei oder vier Einträge nach Wahl, zum Beispiel Einfluss, Unity, Forschung und Markt. Stimmt
   das Fenster, das hinter einem Klick auf die Zahl in der oberen Leiste aufgeht, mit dem Pfad in
   der Tabelle überein? Falsche Einträge notierst du; sie werden dann korrigiert, nicht geraten.
2. Wiki-Lizenz: Lies Abschnitt 7 oben. Bist du einverstanden, dass die Liste der Lesetipps leer
   bleibt und der Coach keinen Wiki-Link nennt?
3. Sechs Planungsentscheidungen aus `docs/plans/M9.md` ("Decisions made while planning"), jeweils
   bestätigen oder ändern:
   1. Ein Konzept ist ein Ursachen-Knoten (Cause) des Mechanik-Graphen, kein Remedy.
   2. Ob ein Remedy "im Snapshot zu sehen" ist, sagt nur das Feld `applied_when`; ohne das Feld
      fragt der Coach dich, und die Stufe bleibt Understand.
   3. Ob eine Ursache vorhanden ist, sagt nur das Feld `present_when`; ohne das Feld kann sie
      weder fallen noch Create erreichen.
   4. Eine Krise (Crisis) entscheidet allein der Code aus den Ressourcen des Snapshots; das Modell
      darf keine ausrufen.
   5. Das Player Model ist die Wiedergabe eines Ereignisprotokolls (`events.jsonl`); `model.json`
      ist nur ein Zwischenspeicher.
   6. Die Wiki-Liste bleibt leer (siehe Schritt 2).
4. Lebender Test auf der Kampagne Avarisches Imperium, Stand 2297.02.09: Starte den Coach in
   dieser Kampagne und sag ihm, was du erreichen willst. Lass dich durch eine Übung führen und
   versuche zuerst selbst, die Ursache zu nennen. Dabei muss gelten:
   - Der Coach nennt keine Schlüsselaktion, bevor du es selbst versucht hast.
   - Kommst du nicht weiter, hilft er in Stufen (zwei Stufen, wenn eine Krise vorliegt) und gibt
     erst am Ende die ganze Erklärung.
   - Ein Hinweis oder die volle Erklärung zählt nicht als eigene Leistung. Sag einmal, dass du
     aussteigen willst: Der Notausgang (Escape Hatch) muss danach im Player Model stehen.
   - Frag den Coach, was er über dich weiß. Er muss es klar sagen, und es muss zu dem passen, was
     du erlebt hast.
   - Im Ordner `player-model/` der Kampagne hast du nichts von Hand geändert; ein Hook sperrt das
     ohnehin.
5. Treffpunkt (Rendezvous): Lege am Ende der Übung mit dem Coach ein Datum im Spiel fest, spiele
   bis dahin weiter und lade den Save. Der Coach muss ihn als Debrief führen: erst deine
   Selbsteinschätzung, dann die Vorhersagen (Predictions) mit dem Ergebnis, die Rückschau mit
   weniger Gewicht, zuletzt das Player Model.
6. Platzhalter, die du nach dem Test einstellst, wenn sie sich falsch anfühlen: der
   Treffpunkt-Horizont von zwei Jahren, die Toleranz von 30 Tagen beim Datum und die Krisenschwelle
   von zwölf Monaten Vorrat.
