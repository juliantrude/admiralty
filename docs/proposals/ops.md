# Vorschläge für Ops

Funde aus dem Ops-Test auf Mireesh Accord (2026-10-31).

## 1. Ein altes Save auf Wunsch trotzdem auswerten

`skills/ops/SKILL.md` Schritt 1 hält an, sobald das neueste Save älter als zehn Minuten ist
(`STALE_AFTER_SECONDS` in `src/admiralty/mcp/service.py`), und bietet keinen Ausweg. Wer abends
ohne laufendes Spiel fragt, kommt nicht weiter. Vorschlag: Sagt der Player, er wolle mit diesem
Save arbeiten, nennt Ops das Alter in einem Satz und macht weiter.

## 2. Briefing doppelt

Der Hook hat die erste Fassung geblockt (`blocks.jsonl`, 00:54): Das Modell setzte Listenanfänge
fett und darin Namen ("**Mehr **Bureaucrat**-Jobs besetzen:**"); die Prüfung las das als unbekannten
Namen. Die Antwort wird dann neu geschrieben, beide Fassungen bleiben sichtbar.

## 3. Maximale Flottenkapazität 272 statt 276

Mireesh 2294.01.01: Admiralty rechnet 272, Julian sieht 276. Noch offen, ob 276 aus demselben Save
stammt. Vermutung, ungeprüft: ein Warrior-Drone-Job mehr, das Spiel rechnet nach dem Laden neu.

## 4. Titel ohne Bezug

"The planet has no building slots left" (`slots.yaml`) nennt keinen Planeten, obwohl die Prüfung für
das ganze Reich zählt.

## 5. Eigene Ziele des Players

Das Modell nahm Ziele an. Julian hat danach eigene genannt (Reich stabilisieren, dann den Omnivorous
Inarian Swarm auslöschen); Ergebnis steht aus.

## 6. Rollen von Graph und Text (entschieden, 2026-10-31)

Nicht "Graph zuerst", sondern getrennte Aufgaben. Der Graph zeigt Verbindungen und Verhältnisse, die
Key Actions stehen in ihm und in der Liste darunter. Der Text geht auf die Wünsche des Players ein:
was nicht geht und warum (Beispiel: Stärke des Ziels unbekannt, keine gemeinsame Grenze), was zuerst
nötig ist. Er wiederholt keine Key Actions und beschreibt den Graphen nicht nach.

## 7. Graph kommt von selbst (entschieden)

Jedes Briefing erzeugt den Graphen und öffnet ihn im Browser. Das Öffnen macht Admiralty selbst,
nicht Claude Code (ADR 0004).

## 8. Reichsweite Knoten (entschieden)

Titel allgemein ("Planets are running out of building slots"); das Detailfeld nennt die betroffenen
Planeten mit ihren freien Plätzen. Gilt für alle Knoten, die das ganze Reich betreffen.

Umgesetzt (2026-10-31): `room.by_planet` im Extrakt (Tabelle), `by_planet` an den Metriken, `places` an
den Knoten; die Evidenz im Detailfeld nennt bis zu acht Planeten, die wenigsten freien Plätze zuerst.
Die Titel der Knoten aus Summen über die Planeten sprechen von "Planets".

## 9. Flottenkapazität offen

Julian kann nicht sagen, ob 276 direkt nach dem Laden stand; Zahlen schwanken dann erfahrungsgemäß.
Kein belegter Fehler. Prüfen, sobald ein Wert aus einem laufenden Spiel vorliegt.

## 10. Fehlender Weg zum Ziel

Zum Swarm liegen drei Reiche dazwischen, eines feindlich. Der Graph nennt "The target is neither
reachable nor assessed", behandelt aber den Weg nicht; "Build warships" löst das nicht. Das Modell
kann es auch nicht wissen: Der Extrakt liefert nur `shares_border`.

Entschieden: Das Routing läuft statisch im Python-Kern, ohne Modell, und liefert mehrere Routen, die
sich in den durchquerten Reichen unterscheiden, je mit der Haltung dieser Reiche. Jede Ursache auf
dem Weg zu einem Ziel braucht eine passende Abhilfe oder wird sichtbar als ungelöst markiert.

Die Karte steht im Save: `galactic_object` mit `hyperlane` (Ziel, Länge) und `coordinate`, Besitzer
über Sternenbasis und Flotte, dazu `bypasses` und `natural_wormholes`. Prototyp auf Mireesh
2294.01.01: Dijkstra, je durchquertes Reich einmal gesperrt, ergibt zwei Routen (Länge 714 und 833).
Offen: Fair Play braucht die bekannten Systeme (`terra_incognita`, Format noch nicht entschlüsselt);
Julian nennt als zweite Route United Wi-Zerakian Authority, das muss mit echter Namensauflösung und
Bypässen nachgeprüft werden.

## 11. Mehrere Briefings

Nach Feedback entstand ein zweites Briefing mit eigenem Graphen, das auf das erste verweist. Der
Player will nur ein aktuelles.

Entschieden: Es gibt ein aktuelles Briefing mit einem Graphen. Feedback, neue Ziele und ein neues Save
aktualisieren es, noch Gültiges wird übernommen, alte Fassungen liegen in einem Verlauf.

## 12. Flagge statt "G"

Knoten zu anderen Reichen sollen deren Flagge zeigen. Die Teile liegen in der Spielinstallation
(`flags/`), der Save beschreibt die Flagge jedes Reichs.

Entschieden: Knoten bekommen ein Feld für das Reich, Admiralty setzt die Flagge beim Erzeugen wie die
Symbole zusammen; das "G" bleibt als Rückfall, die Farben dürfen leicht abweichen.

## 13. WASD im Graphen (entschieden)

Der Ausschnitt lässt sich mit W, A, S, D bewegen, wie im Spiel.
