# Wartet auf Julian

Dinge, die nur du machen kannst. Die Schleife (Hustlebot) trägt hier ein, woran sie nicht
selbst weiterkommt. Erledigte Punkte bitte abhaken oder löschen.

## 1. Golden-Werte aus dem Spiel ablesen

Wofür: Drei Werte stehen nicht im Save und werden berechnet (maximale Flottenkapazität,
Kosten der nächsten Tradition, maximale Distrikte). Die Berechnung ist nur so gut wie der
Abgleich mit dem, was das Spiel anzeigt. Die Tests dafür warten, bis die Werte eingetragen
sind.

So geht's:

1. Spiel starten und das jeweilige Save laden (Multiplayer-Saves gehen auch als Einzelspieler
   über "Laden"). Du spielst Plexxi, also "Die Borg".
2. Die Werte unten ablesen.
3. In `tests/golden_values.py` eintragen (oder mir einfach als Liste schicken, dann trage ich
   sie ein).

Saves (Kampagne "Konföderation von Vulkan"): `2220.04.22`, `2259.12.25`, `2298.03.11`.
Pro Save:

- Datum oben in der Leiste und Reichsname.
- Flottenkapazität benutzt und maximal (Flottenmanager).
- Einheit: Vorrat und monatliches Einkommen; Kosten der nächsten Tradition
  (Traditionen-Bildschirm).
- Monatliches Netto von Energie, Mineralien, Nahrung, Legierungen und Einfluss (Tooltips
  oben in der Leiste).
- Zwei Planeten: Name, System, gebaute und maximale Distrikte pro Typ, offene Jobs,
  Arbeitslose, Planetentyp (Designation).
- Ein umbenannter Planet: wie er im Spiel heißt.
- Ein rivalisierendes Reich: Name und Geheimdienststufe (Kontaktbildschirm).
- Bevölkerung der Hauptwelt, genau so wie die Planetenansicht sie zeigt. Damit klären wir,
  ob das Spiel die Bevölkerung als "7908" oder als "79,08" darstellt.

Zusätzlich in der Kampagne "Zygerrianisches Imperium", Save `2271.08.25`:

- Planet "2" im System Helam: gebaute und maximale Generator-Distrikte (wir lesen 3 gebaut;
  berechnet sind 3 maximal). Das war der Fehler im Prototyp.
- Planet "11" im System Kith'Valas: maximale Distrikte pro Typ.

Zwei offene Fragen, die diese Werte beantworten:

- Zählt die Annahme eines Traditionsbaums als Tradition für die Kosten? Aktuell zählen wir sie
  mit (`COUNT_ADOPTIONS` in `src/hlidskjalf/extract/computed/tradition_cost.py`).
- Sind Stadt- und Nexus-Distrikte durch die Planetengröße begrenzt? Aktuell geben wir dafür
  nur ein "district_limit" pro Planet aus und lassen das Maximum offen.

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

Hinweis: Die Bevölkerungszahlen im Save sind vermutlich mit 100 multipliziert (siehe Punkt 1,
"Bevölkerung der Hauptwelt"). Bis das geklärt ist, taugen für Pops nur Verläufe, keine Absolutwerte.

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
