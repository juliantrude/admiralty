# Vorschläge für Debrief

Aus Julians Durchsicht der Epochen auf der Kampagne `vulkan` (2026-10-31). Beide sind entschieden
und gebaut (2026-10-31, Schritt 15).

## 1. Bei negativer Bilanz die Reichweite des Vorrats nennen

Der Fund `net_negative` nennt nur die Bilanz. Auf `vulkan` lagen 2259 über 6000 Energie im Vorrat,
bei minus 55 im Monat; das ist ein Polster, keine Krise, und so hat Julian es auch erlebt. Der Fund
soll die Reichweite in Monaten mitliefern (Vorrat geteilt durch Bilanz), damit das Modell ein
Polster nicht zum Alarm macht.

Umgesetzt (2026-10-31, Schritt 15): `net_negative` trägt `reserve_months` (Vorrat am Ende des Intervalls
geteilt durch die Bilanz, eine Dezimale; fehlt der Vorrat, fehlt das Feld). Der Skill sagt dem Modell,
die Reichweite neben die Bilanz zu stellen.

## 2. Die Zahl der Systeme verfolgen

Die Reihen enthalten Planeten, aber keine Systeme. Vulkan hat Julian früh Systeme abgenommen, er hat
sie zurückerobert; davon ist in Debrief nichts zu sehen, weil die Zahl der Planeten gleich bleibt.
Systeme kommen als Reihe dazu und zählen auch für die Kandidaten der Epochengrenzen
(`REGIME_SERIES` in `src/admiralty/debrief/epochs.py`). Die Regel ändert sich damit auf Julians
Wunsch.

Umgesetzt (2026-10-31, Schritt 15): `empire.systems` im Extrakt zählt die Systeme, deren Sternenbasis dem
Tracked Empire gehört (`owned_system_count` in `extract/galaxy.py`, derselbe Weg wie die Besitzer der
Karte). `systems` ist eine Reihe und steht in `REGIME_SERIES`. Ältere Archiv-Extrakte ohne die Zahl
ergeben für `systems` kein Intervall. Auf `vulkan` zählt der Extrakt 1, 19, 35, 37, 45, 47, 47, 47
Systeme über die acht Saves; ob das zu Julians Erinnerung passt, prüft er in der Abnahme.

## Beobachtung, nicht entschieden

Was am Tisch abgesprochen wird, steht in keinem Save: Vulkan war Julians Kumpel, Julian hat nach dem
Krieg bewusst nicht weiter angegriffen, und das Spiel endete, weil die Lage für den Mitspieler
aussichtslos war. Das "Plateau" war also eine Entscheidung, keine Stagnation. Debrief kann das nur
erfahren, wenn der Player es erzählt.
