# Offene Grill-Themen (ab 2026-10-26)

Quelle: `docs/handoff.md`, Abschnitt "Was die nächste Session noch grillen muss". Pro Thema wird
gegrillt, bis keine Frage mehr offen ist; die Entscheidungen landen dann unter dem Thema (oder in
einem eigenen Plan bzw. ADR, wenn sie groß genug sind). Reihenfolge = Bearbeitungsreihenfolge.

| # | Thema | Status | Ergebnis |
|---|---|---|---|
| 1 | Academy (M9, der Coach) | fertig (2026-10-28) | Entscheidungen unten; Glossar und `docs/build-plan.md` M9 nachgezogen |
| 2 | Formulierungen im kuratierten Graphen: wer prüft, stichprobenartig oder ganz | fertig (2026-10-28) | Entscheidungen unten |
| 3 | Echtes Ops-Briefing mit vom Modell vergebenen Gewichten | fertig (2026-10-28) | — |
| 4 | Restliche graue Hindernisse (Gebäudeplätze, Freischaltungen): lohnt es, welche zuerst | fertig (2026-10-28) | — |
| 5 | Graph-Seite als privates Artifact veröffentlichen, Spielsymbole darin | fertig (2026-10-28) | — |
| 6 | Eigene Vektorsymbole für die Bereiche | fertig (2026-10-28) | — |
| 7 | Kleinkram: Zielpfeil bei "weniger X" und bei Zielen ohne Menge ("Kel-Azaan wiped out"), Debrief-Fehlalarm bei Epochentiteln, Platz der Key-Action-Rangliste | fertig (2026-10-28) | — |
| 8 | Hintergrunddienst, der jedes Save sofort archiviert (damit Debrief keine Autosaves verpasst) | fertig (2026-10-28) | — |
| 9 | Tracing über den Bildschirm: Interface-Mod zeigt Werte, ein lokaler Dienst liest sie per Bildschirmfoto | verworfen (2026-10-28) | Erinnerung im Save-Dienst statt Barcode (Thema 8) |

## 1. Academy

Grundlage: `docs/build-plan.md` M9 und das Glossar (Coaching, Hint Ladder, Escape Hatch,
Player Model, Prediction, Fair Play).

### Entscheidungen

- **Erfolg eines Versuchs (R1 Q3):** zwei getrennte Signale. Die Hint Ladder folgt der Antwort im
  Gespräch (Ursache oder Abhilfe genannt: zurück auf Stufe eins, sonst eine Stufe höher). Die
  Beherrschung im Player Model ändert sich erst, wenn ein späterer Snapshot zeigt, dass der Player
  es umgesetzt hat. (Präzisiert durch die Stufen in R3 Q1: "Verstehen" entsteht im Gespräch,
  alles ab "Anwenden" braucht einen Snapshot.)
- **Escape Hatch (R1 Q5):** standardmäßig die Antwort zum aktuellen Thema wie vom Consultant
  (Ursache, Abhilfe, Key Action, ohne Graph). Ein volles Briefing nur auf ausdrücklichen Wunsch;
  es zählt dann als Escape Hatch für jedes darin vorkommende Konzept.

- **Wer fängt an (R1 Q1, R2 Q1):** der Player jederzeit; der Coach von sich aus, aber nur
  innerhalb einer Antwort, denn Claude Code ist passiv. Bei jeder Player-Nachricht prüft er zuerst,
  ob ein neueres Save da ist, und stellt dann genau eine Einstiegsfrage zum neuesten Save.
- **Konzept (R2 Q2):** ein Eintrag im Player Model pro Knoten des Mechanik-Graphen; Bereiche nur
  zur Anzeige. Beherrschung ist nicht endgültig: zeigen spätere Saves, dass ein Konzept offenbar
  doch nicht sitzt, darf sie wieder sinken (Regel: Runde 3).
- **Takt (R2 Q3):** eine Frage auf einmal; der Coach nennt die Zahl der anstehenden Themen ohne
  sie zu verraten; "nächstes Thema" jederzeit; Krisen zuerst. Vorläufig, nach den ersten echten
  Sitzungen überprüfen.
- **Umsetzungsfenster (R2 Q4):** fünf Spieljahre. Umsetzung sichtbar: Beherrschung steigt. Keine
  Umsetzung: keine Änderung, einmal nachfragen, was den Player abgehalten hat.
- **Predictions (R2 Q5):** feste Liste großer Entscheidungen (Krieg erklären, Aufstiegsvorteil,
  Traditionsbaum, Megastruktur, Föderation, Welt umwidmen); ein Satz plus vom Coach vorgeschlagenes
  Prüfdatum. Der Coach soll solche Entscheidungen auch selbst erkennen (Wie: Runde 3).
- **Stufen der Beherrschung (R3 Q1, R4):** sechs Stufen, angelehnt an die überarbeitete
  Bloomsche Taxonomie (Anderson und Krathwohl 2001), jede mit beobachtbarem Beleg. Versuchsweise.

  | Stufe | Bloom | Beleg |
  |---|---|---|
  | 0 Neu | — | nichts beobachtet, oder nur mit Teilantwort, voller Erklärung oder Escape Hatch |
  | 1 Verstehen | Erinnern + Verstehen | im Gespräch selbst auf die Ursache gekommen (Frage oder höchstens Hinweis) |
  | 2 Anwenden | Anwenden | ein Save zeigt die Umsetzung, nachdem der Coach das Thema angesprochen hat |
  | 3 Analysieren | Analysieren | Ursache selbst erkannt, bevor der Coach den Bereich nannte (offene Einstiegsfrage, Selbsteinschätzung im Debrief) |
  | 4 Bewerten | Bewerten | zwischen Abhilfen mit Begründung gewählt, oder eine Prediction zum Thema hat sich bestätigt |
  | 5 Erschaffen | Erschaffen | vorausschauend vermieden: zweimal ohne Anstoß umgesetzt, Ursache im Umsetzungsfenster nicht aufgetaucht |

  Ab Stufe 4 überspringt der Coach das Konzept; auf Stufe 3 fragt er nur noch offen, ohne den
  Bereich zu nennen.
- **Ton (R3 Q4):** ruhiger Ausbilder: duzt, kurze Sätze, leichter Flottenton ("Wie schätzt du
  die Lage ein?"), keine Dauer-Anrede als Kadett, kein Rollenspiel, nie herablassend. Vorbild:
  "Neues Save, Juni 2247. Mir fallen zwei Dinge auf, fangen wir mit dem wichtigsten an. Deine
  Energiebilanz ist seit drei Jahren negativ. Wie schätzt du die Lage ein, woran liegt das?"
- **Ort des Player Models (R4 Q1):** eines pro Player über alle Kampagnen, im Benutzerordner;
  die Workspace hält nur das Protokoll der Belege dieser Kampagne. Ändert ein Patch einen
  Zusammenhang deutlich, fällt das Konzept auf "Verstehen" zurück (Kriterium: Runde 5).
- **Lehrreiche Fehler (R4 Q3):** keine Warnung unterhalb einer Krise; der Coach fragt einmal nach
  der Erwartung ("Was erwartest du, wie sich das in zwei Jahren zeigt?") und lässt es dann
  geschehen.
- **Krise (R4 Q4):** die Hint Ladder steigt pro Fehlversuch um zwei Stufen. Warnung im
  Fragemodus: "Das ist ernst. Deine Energie ist in vier Monaten aufgebraucht. Was tust du zuerst?"
- **Andere richtige Antworten (R4 Q5):** an den Daten des Saves prüfen; gestützt zählt als
  Erfolg und wird als Kandidat für den Mechanik-Graphen vorgemerkt; nicht gestützt: nachfragen,
  wo der Player das sieht.
- **Wo im Spiel nachsehen (R4 Q6):** fester, gepflegter Eintrag pro Bereich und wichtiger
  Kennzahl; Claude entwirft aus den Oberflächendateien, Julian prüft stichprobenartig. Ohne
  Eintrag nennt der Coach nur den Bereich.
- **Wiki (R5 Q3):** das offizielle Paradox-Wiki ist Quelle für die Einträge "wo im Spiel
  nachsehen"; etwas veraltet ist dafür in Ordnung (Lizenz vor dem Bau prüfen). Auf der Stufe
  "volle Erklärung" darf der Coach einen Link aus einer gepflegten Liste als Lesetipp geben.
  Kein Live-Abruf während des Spiels, keine Zahlen aus dem Wiki.
- **Treffen (R5 Q4, Julians Idee):** am Ende eines Durchgangs schlägt der Coach einen Termin im
  Spiel vor ("Spiel bis Januar 2290, speichere von Hand unter dem Namen Akademie 2290"). Abstand
  höchstens fünf Spieljahre und so, dass offene Predictions prüfbar sind; der Player kann
  verschieben. Gespeichert in der Workspace. Früher melden: der Coach hilft und erinnert an den
  Termin. Später: neuestes Save, Hinweis auf den verpassten Termin. Ablauf des Treffens wie ein
  Debrief im Coaching: Selbsteinschätzung, Predictions prüfen, neue Themen.
- **Patch-Kriterium (R5 Q1):** ein Zusammenhang gilt als geändert, wenn sich zwischen zwei
  Versionen des Mechanik-Graphen seine Formel oder eine seiner Verbindungen ändert; reine
  Zahlenänderungen behalten die Stufe.
- **Pfad (R6 Q1):** `~/.local/share/admiralty/player-model/`, ein Player Model pro
  Benutzerkonto; `ADMIRALTY_DATA_DIR` lenkt `~/.local/share/admiralty` um (auch für Tests).
- **Fair Play beim Fragen (R5 Q2, R6 Q2):** verborgenes Wissen darf Thema und Dringlichkeit
  bestimmen. Frage und jeder Hinweis, auch die volle Erklärung, zeigen nur auf Sichtbares
  (Ethiken, Haltung, Grenzen, Rivalitäten, die vom Nachrichtendienst angezeigte Flottenstärke).
  Nie etwas, das nur mit dem verborgenen Wissen Sinn ergibt. Aufklärung ist zusätzlich ein
  normales Lernkonzept. Glossar: im Kern wie bisher, um diese Regel geschärft.
- **Eigene Ziele (R6 Q3):** beim ersten Gespräch einer Kampagne und bei jedem Treffen fragt der
  Coach nach dem Ziel des Players bis zum nächsten Termin und richtet den Lösungsgraphen danach
  aus; Krisen zuerst; ein unpassendes Ziel darf er sokratisch hinterfragen.
- **Ende eines Durchgangs (R6 Q4):** alle Themen besprochen oder der Player will weiterspielen;
  der Coach fasst in zwei, drei Sätzen das Vorhaben zusammen und schlägt den nächsten Termin vor.
- **Abnahme (R6 Q5):** ein automatischer Test ohne Sprachmodell für die festen Regeln (Stufen,
  Absinken, Leiter, Escape Hatch, Treffen, einziger Schreibweg) auf dem mittleren Vulkan-Save,
  und eine Probesitzung mit Julian als Schüler auf einem frischen eigenen Save (Wahl: Runde 7).
- **Namen (R7 Q2):** das vereinbarte Treffen heißt **Rendezvous**, ein Durchgang (Fragen zu
  einem Save bis zur Zusammenfassung) heißt **Drill**. Ins Glossar aufnehmen.
- **Save für die Probesitzung (R7 Q1):** Avarisches Imperium, 2297.02.09, Version 4.5.2
  (Kampagne läuft, Energiekrise zieht auf, Stärke wird nicht umgesetzt). Die Probesitzung in einer
  echten Campaign Workspace ist zugleich die Ende-zu-Ende-Abnahme. Mireesh Accord (2294.01.01,
  überstandene Wirtschaftskrise) bleibt ein guter Fall für einen Debrief.
- **Absinken (R3 Q2):** taucht die Ursache zu einem Konzept in zwei Saves hintereinander
  (mindestens ein Spieljahr Abstand) wieder auf, sinkt es um eine Stufe; während einer Krise zählt
  das nicht. Der Coach sagt offen, dass er das Konzept wieder als offen betrachtet.
- **Predictions selbst erkennen (R3 Q3):** vorher als echte Prediction, wo das Save die
  Entscheidung ankündigt (Einheit reicht für den nächsten Traditionsbaum, freier Platz für einen
  Aufstiegsvorteil, ...); hinterher aus dem Vergleich zweier Saves als "nachträgliche Erwartung",
  getrennt gespeichert und von Debrief schwächer gewichtet.
- **Neues Grill-Thema 8:** Hintergrunddienst, der jedes Save sofort archiviert.

### Offene Äste

Keine. Gemeinsames Verständnis von Julian bestätigt am 2026-10-28.

## 2. Formulierungen im kuratierten Graphen

Grundlage: `docs/plans/M6-revision.md`, "Agreed but not done yet". Umfang: 13 Ziele, 31 Ursachen,
60 Abhilfen, 85 Hindernisse, jedes mit einem Titel in der Möglichkeitsform (85).

### Entscheidungen

- **Sprache (R1 Q1):** Titel bleiben englisch, denn Julian spielt auf Englisch
  (`settings.txt`: `l_english`). Spielobjekte heißen genau wie in der englischen Oberfläche.
  Eine deutsche Fassung erst, wenn jemand auf Deutsch spielt.
- **Ungeprüfte Hindernisse (R1 Q2):** derselbe Satz wie das geprüfte Hindernis, mit "may".
- **Automatische Prüfung (R1 Q2, R2 Q1):** ein Test meldet Ziffern in Titeln, Abhilfen über
  fünf Wörter und Ziele über fünf Wörter.
- **Ziele (R2 Q1):** der gewünschte Zustand als Wortgruppe, höchstens fünf Wörter, keine Zahlen,
  keine Aufforderung. Mengen mit der Richtung vorn ("More alloy income"), sonst der erreichte
  Zustand ("Stable planets", "Kel-Azaan wiped out"). Gilt auch für Ziele, die das Modell selbst
  einführt (Ops-Skill und Academy-Skill bekommen die Regel). Der grüne Pfeil nach oben passt dazu
  nicht immer: siehe Thema 7.
- **Prüfung (R2 Q2):** Claude schreibt alle Titel in einem Durchgang um und erzeugt eine
  Prüfseite (alt und neu nebeneinander, pro Bereich). Julian liest alle Ziele und Abhilfen, einen
  Bereich ganz (etwa Energie) und eine Stichprobe von etwa zehn Ursachen und Hindernissen aus den
  übrigen. Mehr als zwei schlechte in der Stichprobe: alles lesen.

### Offene Äste

Keine.

## 3. Echtes Ops-Briefing mit vom Modell vergebenen Gewichten

### Entscheidungen

- **Save (R1 Q1):** Mireesh Accord (Julians Reich heißt dort "Die Borg"), nicht das Avarische
  Imperium, damit die Academy-Probesitzung unverdorben bleibt. Das Save vom 2294.01.01.
- **Begründungen (R1 Q2):** vorher automatisch prüfen, dass jede Begründung sich auf eine Zahl
  aus den Werkzeugergebnissen stützt. Julian markiert jede mit "stimmt", "falsch" oder "nicht
  nachvollziehbar". Brauchbar, wenn höchstens eine von fünf "falsch" ist.
- **Größen (R1 Q3):** Julian nennt vor dem Ansehen die drei wichtigsten Ursachen; mindestens
  zwei davon müssen unter den drei größten Knoten sein. Sonst klären: Gewichte oder Rechnung.
- **Ablauf (R1 Q4):** Julian startet das Briefing selbst in einer echten Campaign Workspace mit
  installiertem Plugin; das ist der Ops-Teil der Ende-zu-Ende-Abnahme.

### Offene Äste

Keine.

- **Vergleich mit Julians Lösung (R2):** verschoben. Keines der vier Saves (2288.02.26 bis
  2294.01.01) liegt in der Krise: letztes Defizit laut Timeline 2292.06.01, ab 2293.04.12 alle
  Monatswerte positiv; Verläufe zwischen Saves speichert das Spiel nicht (ADR 0002). Der Vergleich
  folgt, sobald es ein Save mitten aus einer echten Krise gibt. Der Fall ist das Hauptargument für
  Thema 8 (die rotierenden Autosaves von 2292 wären archiviert worden). Die Trace-Mod bleibt zu,
  bis sich zeigt, dass auch der Hintergrunddienst Krisen verpasst.

## 4. Restliche graue Hindernisse

Stand: 85 Hindernisse, 46 an Zahlen geprüft, 39 nur per Urteil (`check: judgement_only`):
4 Aufstiegsvorteile und Traditionen, 2 freie Job-Plätze, 14 Freischaltungen, 11 Gebäude- und
Zonenplätze, 8 echte Abwägungen.

### Entscheidungen

- **Lohnt es (R1 Q1):** ja; Academy beurteilt Antworten am Lösungsgraphen und braucht geprüfte
  Hindernisse. Die 8 echten Abwägungen bleiben beim Modell.
- **Reihenfolge (R1 Q2):** erst die 6 schnellen (Daten schon im Extrakt), dann die 14
  Freischaltungen (erforschte Technologien im Save, Voraussetzungen aus den Spieldateien), zuletzt
  die 11 Gebäude- und Zonenplätze (Zonenregeln aus den Spieldateien nachbauen).
- **Wer (R1 Q3):** Hustlebot, mit Sonnet und hohem Aufwand wie bei M3 bis M8. Wechsel auf Opus nur,
  wenn die Zonenregeln hängen bleiben (eine Zeile in `.hustle/config`). Freie Gebäudeplätze sind
  berechnete Werte: Julian liest sie für zwei, drei Planeten im Spiel ab; bis dahin bleiben die
  Golden-Tests dazu ausstehend. Vor dem Start die Hustlebot-Units des alten Pfads entfernen und
  neu einrichten (`docs/handoff.md`).

### Offene Äste

Keine.

## 5. Graph-Seite veröffentlichen, Spielsymbole

### Entscheidungen

- **Kein Artifact (R1 Q1):** Admiralty veröffentlicht nichts auf claude.ai. Alles, was ein
  Artifact brächte (Zugriff von anderen Geräten, Sammlung alter Briefings, Kommentare), lässt sich
  lokal bauen, und Julian will keine Bindung an Anthropic. Punkt 3 in `docs/awaiting-julian.md`
  entfällt.
- **Spielsymbole und Disclaimer (R1 Q2):** die Symbole bleiben in der lokalen Seite; die
  Verantwortung beim Weitergeben liegt beim Nutzer. Unter jeder Graph-Seite steht ein Hinweis:
  Symbole sind Eigentum von Paradox Interactive und stammen aus der Spielinstallation des
  Betrachters; Admiralty ist ein nicht kommerzielles Fanprojekt ohne Verbindung zu Paradox; wer die
  Seite weitergibt, ist dafür verantwortlich.

- **Offline (R2 Q1):** die drei Bibliotheken (Cytoscape, ELK, cytoscape-elk) und die Schrift Exo 2
  kommen mit fester Version und Lizenz im Plugin mit; kein CDN, kein Google Fonts.
- **Anbieterunabhängigkeit (R2 Q2):** ADR 0004. Nichts bei einem Anbieter ablegen; der Kern bleibt
  ein Python-Paket ohne Sprachmodell; Hostspezifisches nur in Skills, Hooks und MCP-Server.
  Langfristig auch Codex oder Cursor, aber noch nicht geplant; bis dahin nicht tiefer an Claude
  Code binden.

### Offene Äste

Keine.

## 6. Bereichssymbole

Unscharf sind genau vier Bereiche: Einfluss (18 px), Amenities (25 px), Jobs (23 x 32 px),
Stabilität (27 px); alle anderen nutzen schon Technologiesymbole mit 52 px.

### Entscheidungen

- **Alles bleibt, wie es ist (R1 Q1, R2):** Julian hat auf einer lokalen Übersichtsseite je fünf
  bis sechs größere Spielsymbole pro Bereich mit den heutigen verglichen und keins vorgezogen.
- **Keine eigenen Vektorsymbole (R1 Q2):** vorerst nicht; nur für einen Bereich ohne passendes
  großes Spielsymbol.

### Offene Äste

Keine.

## 7. Kleinkram

### Entscheidungen

- **Zeichen der Ziele (R1 Q1):** drei Zeichen statt immer Pfeil nach oben: Pfeil nach oben für
  "mehr", Pfeil nach unten für "weniger", Fahne für Zustandsziele ("Kel-Azaan wiped out"). Das
  Zeichen steht als eigenes Feld am Ziel, im kuratierten Graphen wie bei Zielen, die das Modell
  einführt; nie aus dem Titel gelesen. Heute: `_with_arrow` in `src/admiralty/graph/icons.py`.
- **Fehlalarm bei Epochentiteln (R1 Q2):** das Debrief-Kommando gibt die Epochentitel in seinem
  Ergebnis zurück, die Prüfung auf unbelegte Behauptungen zählt sie als Beleg. Erfundene
  Spielnamen fallen weiter auf (`docs/proposals/claims.md`).
- **Key-Action-Rangliste (R1 Q3):** bleibt vorerst unter dem Graphen; Prüfpunkt beim Ops-Briefing
  auf Mireesh Accord 2294.01.01 (Thema 3).

### Offene Äste

Keine.

## 8. Hintergrunddienst für Saves

Stand: archiviert wird heute nur, was gelesen wird (`_archive` in `src/admiralty/mcp/service.py`).
Das Spiel überschreibt Autosaves reihum; Mireesh speichert halbjährlich (`autosave=4` in
`settings.txt`, Stufen Never, Daily, Monthly, Quarterly, Semiannually, Annually). Ein Save hat zwei
bis drei Megabyte. Ein Auszug braucht das Reich aus `campaign.yaml`, also einen Workspace.

### Entscheidungen

- **Erkennen (R1 Q1):** neues Kommando `admiralty watch` im Kern, fragt den Save-Ordner alle
  30 Sekunden ab, ohne neue Bibliothek; unter Linux als systemd-Benutzerdienst (ADR 0004).
- **Was passiert (R1 Q2):** rohe Kopie sofort, sortiert nach Datum im Spiel; kein Auszug während
  des Spiels. Der Workspace zieht beim nächsten Lesen alle wartenden Kopien nach.
- **Welche Kampagnen (R1 Q3):** alle Ordner unter "save games". Mit Workspace direkt in dessen
  `saves/`, sonst in `~/.local/share/admiralty/inbox/<save-ordner>/`; übernommen, sobald ein
  Workspace für die Kampagne entsteht.
- **Speicherplatz (R1 Q4):** nach dem Archivieren wird die rohe Kopie gelöscht, außer
  `backup_saves` ist an (Standard); kein festes Limit, die Statusanzeige nennt die Größe.
- **Einrichtung (R1 Q5):** die Campaign Setup fragt einmal und richtet den Dienst auf Wunsch ein;
  Abschalten mit einem Befehl. Andere Betriebssysteme erst bei Bedarf.
- **Fertig wenn (R1 Q6):** automatischer Test mit künstlichem Save-Ordner (Saves tauchen auf und
  werden überschrieben) und ein Spielabend von Julian, nach dem jedes Autosave im Archiv liegt.

- **Autosave-Takt (R2 Q2):** empfohlen ist vierteljährlich. Die Campaign Setup liest `autosave`
  aus `settings.txt` und schlägt vierteljährlich vor, wenn der Takt seltener ist; sie ändert die
  Spieleinstellungen nie selbst.
- **Speicher bei dichtem Takt (R2 Q3):** von Autosaves bleibt nach dem Archivieren nur der
  komprimierte Auszug; manuelle Saves folgen weiter `backup_saves`.
- **Kein Eingriff in die Prüfsumme:** einen Patch am Spiel, der Autosave für Clients einschaltet
  und die Prüfsummenprüfung im Mehrspieler umgeht, baut Admiralty nicht (Julians Frage in R2 Q1).

- **Saves als Client (R3 Q1, Q2):** weder eingespielte Tastendrücke noch die Autosaves des Hosts
  (bräuchte geteilte Ordner über VPN, so viel Aufwand wie der Trace-Mod). Als Client bleiben nur
  manuelle Saves; der Trace-Mod bleibt die langfristige Lösung (ADR 0002).
- **Erinnerung an Saves (R4, aus Thema 9):** läuft Stellaris und kam in der gerade gespielten
  Kampagne seit `save_reminder_minutes` (Standard 20, 0 = aus, in `campaign.yaml`) echter Zeit
  kein neues Save, schickt der Dienst eine Desktop-Benachrichtigung; sie verschwindet mit dem
  nächsten Save. Autosaves zählen mit, als Host meldet sie sich also nur bei zu seltenem oder
  abgeschaltetem Autosave. Das Datum im Spiel braucht sie nicht.
- **Prüfsumme (Fakten, R3):** `checksum_manifest.txt` umfasst nur `common`, `events` und `map`;
  Interface und Lokalisierung nicht, die ausführbare Datei nicht. Kein spielbarer Wert schaltet
  Autosave für Clients ein; der einzige Speicher-Wert ist `INCREMENTAL_SAVE_FREQUENCY` in
  `common/defines` (Startoption `-incrementalsaves`, alle 25 Jahre) und läge in der Prüfsumme.

### Offene Äste

Keine.

## 9. Tracing über den Bildschirm (verworfen)

Julians Idee (2026-10-28): Das Interface kann Werte nur auf den Bildschirm bringen, keine Datei
und kein Netzwerk; Interface und Schriften liegen außerhalb der Prüfsumme. Also blendet ein
Interface-Mod die Werte ein, und ein lokaler Dienst fotografiert das Spielfenster und liest sie aus.
Im Spiel läuft nichts automatisch, es wird nichts gedrückt; Fair Play ist eingebaut.

- Ein echter QR-Code geht nicht: das Interface rechnet nicht (keine Kompression, keine
  Fehlerkorrektur). Machbar ist eine eigene Bitmap-Schrift, deren Ziffern Blockmuster sind; so
  wird der Text zum Strichcode, ohne Texterkennung.
- Offen: welche Werte das Interface überhaupt zeigen kann (an Fenster gebundene Felder,
  Lokalisierungsfunktionen); ob Hyprland das Spielfenster gezielt abfotografieren kann; erster
  Schritt wäre ein Prototyp, der nur die obere Leiste des Grundspiels liest.

### Entscheidung (R1)

Verworfen. Ein Interface-Mod kommt nur an Felder, die das Spiel selbst befüllt; dauerhaft
sichtbar ist praktisch nur die obere Leiste (Datum, Vorräte, Bilanzen), Planeten und Flotten nur
bei offenem Fenster, und die Übersetzungsfunktionen liefern fast nur Namen. Das zeigt, dass eine
Krise läuft, aber nicht warum; dafür kosten Schrift, ein Mod, der `interface/main.gui` ganz
überschreibt, Bildschirmfotos und Dekoder viel Pflege. Den größeren Hebel hat die Erinnerung an
Saves (Thema 8). Wieder aufmachen nur, wenn Saves trotz Erinnerung zu dünn sind; die beste Quelle
bleibt der Trace-Mod für Gruppen, die ihn alle installieren (ADR 0002).
