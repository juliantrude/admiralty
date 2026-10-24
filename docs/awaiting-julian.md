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
