# M3: Stromkreise und Laden steuern (0.3.1)

Die Installation und jedes Upgrade bleiben standardmäßig lesend. Es gibt keine
Schaltbefehle beim Start, Neustart, Wiederherstellen, Polling oder bei API-Fehlern.
Bestehende Konfigurationseinträge erhalten keine automatische Steuerfreigabe.
Quellenwechsel und Laden wurden vom Besitzer am Gerät bestätigt. Die neuen
Betriebsart-Auswahlen und Sammelschaltungs-Tasten sind offline geprüft; ihre
Hardware-Abnahme steht noch aus. Es werden keine HA-Helper benötigt.

## Freigaben und Entitäten

Unter **Einstellungen → Geräte & Dienste → EcoFlow Smart Home Panel v1 → Optionen**:

| Freigabe (standardmäßig aus) | Wirkung |
| --- | --- |
| Stromkreise steuern (Quelle und Betriebsart) | Zehn Quellen-Auswahlen: Netzstrom/Batterie; zehn Betriebsart-Auswahlen: Automatisch/Manuell |
| Laden steuern | Zwei Ladeschalter für die Backup-Einträge |
| Sammelschaltung | Zusätzlich zur Stromkreis-Freigabe: drei Tasten „Alle auf Netzstrom“, „Alle auf Batterie“, „Schaltung abbrechen“ |

Die bis zu **25 Bedienelemente** erscheinen auf der Geräteseite. Die diagnostische
Anzeige „Control mode“ ist weiterhin ein eigener Sensor; geändert wird die
Betriebsart über die neue Auswahl unter den Bedienelementen. **Automatisch**
überlässt die Versorgung dem Panel; **Manuell** übernimmt die frisch gemeldete
Versorgungsquelle. Ein unbekannter Versorgungszustand verhindert das Setzen von
Manuell. Automatisch kann die Versorgungsquelle ändern.

Die Freigabe allein schaltet nichts. Erst ein Aufruf von `select.select_option`,
`switch.turn_on` / `switch.turn_off`, ein Tastendruck oder die bestätigte
Sammelaktion schreibt. Stromkreise heißen immer **Stromkreis N** bzw. **Circuit N**
entsprechend der HA-Systemsprache. App-Kanalnamen ersetzen diese Nummerierung
nicht; explizite eigene HA-Namen und stabile Entitäts-IDs bleiben erhalten.
Nach einer Freigabe starten die zugehörigen Steuerentitäten aktiviert; einzelne
Entitäten lassen sich weiterhin über das Entitätsregister deaktivieren.

Bei Entzug einer Freigabe werden laufende und wartende Befehle beim Neuladen
abgebrochen. Die alten Registereinträge und ihre Historie bleiben erhalten; HA
kann entfernte Steuerentitäten als nicht verfügbar anzeigen. Explizite
Benutzer-Deaktivierungen bleiben auch nach erneuter Freigabe bestehen.

## Exakte Befehle und Bestätigung

Gemeinsamer authentifizierter Client: `PUT /iot-open/sign/device/quota` mit
`{"sn": <konfigurierte Seriennummer>, "params": <Parameter>}`. Der komplette Body
wird nach dem funktionierenden Referenzalgorithmus signiert. Gerätewerte,
Antworttexte, Schlüssel und Seriennummern werden nicht protokolliert.

| Ziel | Parameter |
| --- | --- |
| Stromkreis N: Netz | `{"cmdSet":11,"id":16,"ch":N-1,"ctrlMode":0,"sta":0}` |
| Stromkreis N: Batterie | `{"cmdSet":11,"id":16,"ch":N-1,"ctrlMode":1,"sta":1}` |
| Stromkreis N: Automatisch | `{"cmdSet":11,"id":16,"ch":N-1,"ctrlMode":0,"sta":0}` |
| Stromkreis N: Manuell | `{"cmdSet":11,"id":16,"ch":N-1,"ctrlMode":1,"sta":S}`; S aus frischem Status: Netz 0, Batterie 1, aus 2 |
| Backup-Eintrag N: Laden ein | `{"cmdSet":11,"id":17,"ch":N+9,"ctrlMode":1,"sta":2}` |
| Backup-Eintrag N: Laden aus | `{"cmdSet":11,"id":17,"ch":N+9,"ctrlMode":0,"sta":0}` |

N liegt bei Stromkreisen in 1–10 und bei Backup-Einträgen in 1–2. `powCh` wird
nicht als Index verwendet. Backup-Einträge sind keine bestätigte physische
Zuordnung zu einer bestimmten DELTA Pro.

Jeder Auftrag fragt zuerst frische Quota ab. Ist das Ziel bereits bestätigt,
entfällt der Schreibbefehl. Andernfalls folgt PUT, eine asynchrone Wartezeit und
nochmals ein **neuer GET**. Quellenwechsel verwenden den verifizierenden Ablauf
von `shp_mode.py`: **10 Sekunden** nach PUT, **15 Sekunden** vor Wiederholungen,
höchstens **acht Versuche**. Ladebefehle übernehmen die **2 Sekunden** aus
`ecoflow_config.SETTLE_AFTER_SET_SECONDS` / `ecoflow_set.py`; die gleiche begrenzte
Wiederholungs- und Bestätigungslogik ergänzt dessen bloße Aktualisierung.
Bei der Sammelschaltung bleibt auch die 15-Sekunden-Pause nach dem achten
erfolglosen Versuch erhalten, genau wie im Referenzscript. Einzelsteuerungen
behalten ihre bisherige begrenzte Wiederholungslogik.

Eine erfolgreiche PUT-Antwort bestätigt nur die Annahme. Erfolg verlangt den
passenden Zustand in einer frischen Antwort. Für Einzelsteuerungen wird eine
vollständige Kontrollliste verlangt. Dotted Keys
und verschachteltes JSON funktionieren; doppelte Strukturen, fehlende Einträge,
abweichende Arraygrößen, widersprüchliche `ch`-Indizes und ungültige Codes bleiben
unbekannt. Betriebsart-Aufträge benötigen zur Bestätigung den passenden frischen
`ctrlMode` (0 automatisch / 1 manuell), mit denselben Zeiten und Versuchslimits
wie Quellenwechsel. `ctrlSta` hat Vorrang; `sta` ist nur bei fehlendem `ctrlSta` der belegte
Fallback. Boolesche Werte, Fließkommazahlen und numerische Strings werden nicht
in gültige Codes umgedeutet. Die Quota-Rohwertsensoren bleiben davon unabhängig.

Die **Sammelschaltung** verwendet dagegen ausdrücklich die kanalweise Auswertung
aus `shp_mode.py`: Eine vorhandene Liste unter dem dotted Key hat Vorrang; sonst
wird die verschachtelte Liste verwendet. Zuerst zählt der Dictionary-Eintrag an
der Kanalposition, andernfalls die Suche nach `ch`. `ctrlSta` hat Vorrang vor
`sta`; die ursprüngliche `int()`-Umwandlung bleibt erhalten. Ein fehlender anderer
Kanal blockiert die Bestätigung des aktuellen Kanals nicht. Fehlende oder nicht
auswertbare Zustände sind weiterhin unbekannt, ohne Ersatz durch alte Werte.

Wie in der Referenz darf ein ausdrücklich angeforderter Quellen-/Ladebefehl auch
bei unvollständigem Status gesendet werden. Für Manuell muss dagegen eine gültige
aktuelle Quelle vorliegen, damit keine geraten wird. Unvollständiger Status kann niemals den
Erfolg bestätigen. HTTP-/API-Fehler beenden den aktuellen Kanalversuch; die
Sammelschaltung fährt nach der Pause mit dem nächsten Kanal fort. Sie lösen keine
zusätzlichen PUT-Wiederholungen außerhalb des Referenzablaufs aus.
Authentifizierungsfehler starten Reauth; GET und PUT
teilen dieselbe HTTP-429-Sperrfrist. Fehlgeschlagene oder abgebrochene Aufträge
machen die Entitäten nicht verfügbar, bis eine neue gültige Abfrage vorliegt.
Es gibt keine optimistische Anzeige und keinen Rückgriff auf alte Quota.

**Technische Herkunft des Ladecodes:** Der funktionierende Referenzcode interpretiert Backup-`ctrlSta=2` als
Lademodus ein, `0/1` als aus. Die allgemeine Herstellertabelle bezeichnet 2 dagegen
als aus. Die Ladeschalter verwenden den bereits bestätigten Referenzablauf;
dies löst den Dokumentationswiderspruch nicht auf. Andere Codes
bleiben unbekannt (anders als der pauschale Off-Fallback des alten Helpers).
Lademodus ein beweist weder positive Ladeleistung noch eine bestimmte Zuordnung
zum `energyInfos`-Array. Der vorhandene Rohcodesensor bleibt unverändert.

## Sammelaktion, Fortschritt und Abbruch

Die Tasten **Alle auf Netzstrom** und **Alle auf Batterie** starten die Folge
direkt nach einem bewussten Tastendruck. Während eines laufenden Auftrags sind
diese beiden Tasten nicht verfügbar. **Schaltung abbrechen** bleibt auch bei
gestörter Datenverbindung bedienbar. Das Aktivieren der Option startet nichts.

Für Automationen bleibt die bisherige Aktion verfügbar:
`ecoflow_smart_home_panel_v1.set_all_sources` benötigt einen konkreten
`config_entry_id`, `source: grid` oder `source: battery`, **`confirm: true`** und
beide Quellen-/Sammelfreigaben. Kein automatisches Ziel „alle Panels“.

Reihenfolge für Netz und Batterie: **7, 6, 3, 1, 2, 4, 5, 8, 9, 10**. Jeder Kanal
wird bis zur Bestätigung, bis zu acht erfolglosen Versuchen oder bis zu einer
Exception bearbeitet. Danach folgen **immer 10 Sekunden Pause**, auch nach
Fehlern, bereits passendem Zustand und dem letzten Kanal.

Ein einzelner Fehler beendet die Folge nicht: Die übrigen Stromkreise werden
weiter bearbeitet. **Erst nach allen zehn** wird das Gesamtergebnis gemeldet;
unbestätigte Stromkreise werden dabei aufgelistet. So entspricht der Ablauf dem
bewährten Referenzscript. Bereits bestätigte
Schaltungen bleiben bestehen; es gibt keine automatische Rückschaltung oder
zusätzliche Lade-/Entladebefehle. Es werden keine elektrischen Verriegelungen
erfunden, die in der Referenz nicht belegt sind.

Wenn alle zehn Stromkreise beim ersten Versuch bestätigt werden, ergeben die
Pausen insgesamt **3 Minuten 20 Sekunden**, zuzüglich API-Antwortzeiten. Sind alle
bereits im gewünschten Zustand, bleiben **1 Minute 40 Sekunden** Kanalpausen.

Alle Quellen-, Betriebsart-, Lade- und Sammelaufträge eines Panels teilen eine Sperre über den
gesamten Ablauf. Andere Panel-Einträge arbeiten unabhängig. Regelmäßiges
lesendes Polling bleibt möglich. Fortschritt steht im Attribut
`control_operation` der Steuerentitäten und im Diagnose-Download: Zustand,
Auftragsart, Ziel, aktueller Stromkreis/Backup-Eintrag, Versuch und bei Sammelaktionen
bereits bestätigte (`completed`) und fehlgeschlagene (`failed`) Stromkreise.
Keine Seriennummern oder Kanalnamen im Fortschritt. Bei vollständigem Erfolg kann
die Aktion ihre Ergebnisstruktur zurückgeben; bei Teilerfolg meldet sie am Ende
einen Fehler mit den betreffenden Stromkreisnummern. Die Listen bleiben in den
Attributen und Diagnosen einsehbar. „Erfolgreich“ bedeutet weiterhin, dass alle
zehn Ziele bestätigt wurden, nicht nur dass alle Befehle angenommen wurden.

Ein Sammelauftrag kann mehrere Minuten dauern; ein Timeout der aufrufenden
Oberfläche ist kein bestätigter Abbruch. **Nicht automatisch erneut aufrufen.**
Fortschritt prüfen und bei Bedarf **Schaltung abbrechen** verwenden oder
`ecoflow_smart_home_panel_v1.cancel_commands` mit dem
betroffenen `config_entry_id` aufrufen. Diese Aktion beendet laufende und
wartende Aufträge, ebenso wie Entladen/Neustart der Integration. Ein bereits
übertragener PUT kann trotzdem noch am Gerät wirken. Nachfolgende Statusabfragen
prüfen; ein Abbruch sendet keine kompensierenden Befehle.

Der Ablauf wurde offline direkt gegen die unveränderten Funktionen aus
[`shp_mode.py`](https://github.com/nickwinger/homeassistant_config/blob/3fa58b227ea5bd9e1a605ebb7177ab002a2a6e10/ecoflow/shp_mode.py)
verglichen: Befehle, Abfragen, alle Pausen und Kanalresultate müssen identisch
sein. Die native HA-Ausführung nutzt asynchrone Wartezeiten und den gemeinsamen
Client ohne Dateicache. Dessen HTTP-Validierung, Zeitlimits und Rate-Limit-Sperren
bleiben bestehen; Abbrechen/Entladen beendet laufende Aufträge weiterhin.

Fortschritt und statische Beschreibungen werden als unrecorded attributes nicht
in Recorder kopiert. Nur aktivierte Entitäten erzeugen normale Zustandshistorie.
Es gibt kein zusätzliches Befehlsprotokoll, keine Quota-Datei und kein Archiv.

## Oberfläche und Daten prüfen

Eine isolierte Instanz ist die eigene DEV-HA-Instanz auf Port 8124. Diese Prüfung
bedeutet: Daten und Oberfläche ansehen, ohne einen Schaltversuch auszuführen.
Sie ersetzt keine Hardware-Abnahme. Die vorhandene produktive HA-Installation
und deren Automationen bleiben unberührt.

1. In einer isolierten HA-Instanz aktualisieren, zunächst alle drei Freigaben
   ausgeschaltet lassen. Standard-Polling: 5 Sekunden; gültige eigene Werte von
   1–600 Sekunden bleiben erhalten.
2. Namen, Messwerte, Verlauf, Reload und fehlende Felder prüfen. Bestehende
   produktive Helper und Automationen unverändert lassen.
3. Für eine reine Oberflächenprüfung können Stromkreis-/Lade-/Sammelentitäten freigegeben
   werden, solange keine Automationen oder Aktionen sie ansteuern. Nur Namen,
   Optionen, Zustände und Beschreibungen ansehen; nichts auswählen oder betätigen.
4. Freigaben wieder entfernen; die Steuerentitäten müssen nicht verfügbar werden.
   Eine Freigabe, ein Neustart oder ein Poll allein darf nie schalten.
5. Quellenwechsel und Laden hat der Besitzer bereits erfolgreich ausprobiert.
   Die neuen Betriebsart- und Sammelbedienelemente sowie die Wechselwirkung mit
   bestehenden Schreibern bleiben vor einer Produktivmigration zu prüfen.
   Der Entwicklungsagent führt keine echten Schaltversuche aus und veröffentlicht
   keine GitHub-Release ohne Benutzerabnahme.
