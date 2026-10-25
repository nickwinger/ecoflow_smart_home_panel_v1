# M3: bewusste Quellen- und Lade-Steuerung (0.2.0)

Die Installation und jedes Upgrade bleiben standardmäßig lesend. Es gibt keine
Schaltbefehle beim Start, Neustart, Wiederherstellen, Polling oder bei API-Fehlern.
Bestehende Konfigurationseinträge erhalten keine automatische Steuerfreigabe.
Die Implementierung ist offline geprüft; eine Hardware-Abnahme steht noch aus.

## Freigaben und Entitäten

Unter **Einstellungen → Geräte & Dienste → EcoFlow Smart Home Panel v1 → Optionen**:

| Freigabe (standardmäßig aus) | Wirkung |
| --- | --- |
| Stromkreis-Quellensteuerung | Zehn native `select`-Entitäten mit `grid` / `battery` (übersetzt in der Oberfläche) |
| Lade-Steuerung nach Helper-Semantik | Zwei native `switch`-Entitäten für die Backup-Einträge |
| Sammelschaltung aller zehn Stromkreise | Zusätzlich zur Quellensteuerung nötig für die explizite Sammelaktion |

Die Freigabe allein schaltet nichts. Erst ein Aufruf von `select.select_option`,
`switch.turn_on` / `switch.turn_off` oder der bestätigten Sammelaktion schreibt.
Ein gültiger Kanalname ersetzt die generische Bezeichnung; sonst heißt es
**Stromkreis N** bzw. **Circuit N**. Die Identität bleibt bei Umbenennungen gleich.
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
Nach dem letzten fehlgeschlagenen Versuch entfällt eine nutzlose weitere Pause.

Eine erfolgreiche PUT-Antwort bestätigt nur die Annahme. Erfolg verlangt den
passenden Zustand in einer frischen, vollständigen Kontrollliste. Dotted Keys
und verschachteltes JSON funktionieren; doppelte Strukturen, fehlende Einträge,
abweichende Arraygrößen, widersprüchliche `ch`-Indizes und ungültige Codes bleiben
unbekannt. `ctrlSta` hat Vorrang; `sta` ist nur bei fehlendem `ctrlSta` der belegte
Fallback. Boolesche Werte, Fließkommazahlen und numerische Strings werden nicht
in gültige Codes umgedeutet. Die Quota-Rohwertsensoren bleiben davon unabhängig.

Wie in der Referenz darf ein ausdrücklich angeforderter Befehl auch bei
unvollständigem Status gesendet werden. Dieser Status kann jedoch niemals den
Erfolg bestätigen. HTTP-/API-Fehler brechen sofort ab; sie lösen keine blinden
Wiederholungen von PUT aus. Authentifizierungsfehler starten Reauth; GET und PUT
teilen dieselbe HTTP-429-Sperrfrist. Fehlgeschlagene oder abgebrochene Aufträge
machen die Entitäten nicht verfügbar, bis eine neue gültige Abfrage vorliegt.
Es gibt keine optimistische Anzeige und keinen Rückgriff auf alte Quota.

**Ladezustand:** Der funktionierende Helper interpretiert Backup-`ctrlSta=2` als
Lademodus ein, `0/1` als aus. Die allgemeine Herstellertabelle bezeichnet 2 dagegen
als aus. M3 verwendet für die separat freizugebenden Schalter ausdrücklich die
Helper-Semantik; dies löst den Dokumentationswiderspruch nicht auf. Andere Codes
bleiben unbekannt (anders als der pauschale Off-Fallback des alten Helpers).
Lademodus ein beweist weder positive Ladeleistung noch eine bestimmte Zuordnung
zum `energyInfos`-Array. Der vorhandene Rohcodesensor bleibt unverändert.

## Sammelaktion, Fortschritt und Abbruch

`ecoflow_smart_home_panel_v1.set_all_sources` benötigt einen konkreten
`config_entry_id`, `source: grid` oder `source: battery`, **`confirm: true`** und
beide Quellen-/Sammelfreigaben. Kein automatisches Ziel „alle Panels“.

Reihenfolge: **7, 6, 3, 1, 2, 4, 5, 8, 9, 10**, jeweils erst nach Bestätigung weiter,
mit 10 Sekunden Abstand nach jedem bearbeiteten Stromkreis. Die Sammelaktion
stoppt beim ersten Fehler. Das ist eine bewusste Verschärfung der Referenz,
die nach einem Fehler weitere Stromkreise bearbeitet. Bereits bestätigte
Schaltungen bleiben bestehen; es gibt keine automatische Rückschaltung oder
zusätzliche Lade-/Entladebefehle. Es werden keine elektrischen Verriegelungen
erfunden, die in der Referenz nicht belegt sind.

Alle Quellen-, Lade- und Sammelaufträge eines Panels teilen eine Sperre über den
gesamten Ablauf. Andere Panel-Einträge arbeiten unabhängig. Regelmäßiges
lesendes Polling bleibt möglich. Fortschritt steht im Attribut
`control_operation` der Steuerentitäten und im Diagnose-Download: Zustand,
Auftragsart, Ziel, aktueller Stromkreis/Backup-Eintrag, Versuch und bei Sammelaktionen
bereits bestätigte Stromkreise. Keine Seriennummern oder Kanalnamen im Fortschritt.
Die Aktion kann optional ihre abschließende Ergebnisstruktur zurückgeben.

Ein Sammelauftrag kann mehrere Minuten dauern; ein Timeout der aufrufenden
Oberfläche ist kein bestätigter Abbruch. **Nicht automatisch erneut aufrufen.**
Fortschritt prüfen oder `ecoflow_smart_home_panel_v1.cancel_commands` mit dem
betroffenen `config_entry_id` aufrufen. Diese Aktion beendet laufende und
wartende Aufträge, ebenso wie Entladen/Neustart der Integration. Ein bereits
übertragener PUT kann trotzdem noch am Gerät wirken. Nachfolgende Statusabfragen
prüfen; ein Abbruch sendet keine kompensierenden Befehle.

Fortschritt und statische Beschreibungen werden als unrecorded attributes nicht
in Recorder kopiert. Nur aktivierte Entitäten erzeugen normale Zustandshistorie.
Es gibt kein zusätzliches Befehlsprotokoll, keine Quota-Datei und kein Archiv.

## Manuelle Abnahme ohne Schalten

1. In einer isolierten HA-Instanz aktualisieren, zunächst alle drei Freigaben
   ausgeschaltet lassen. Weiterhin 5 Sekunden Standard-Polling; eigene Werte bleiben.
2. Namen, Messwerte, Verlauf, Reload und fehlende Felder prüfen. Bestehende
   produktive Helper und Automationen unverändert lassen.
3. Für eine reine Oberflächenprüfung können Quellen-/Ladeentitäten freigegeben
   werden, solange keine Automationen oder Aktionen sie ansteuern. Nur Namen,
   Optionen, Zustände und Beschreibungen ansehen; nichts auswählen oder betätigen.
4. Freigaben wieder entfernen; die Steuerentitäten müssen nicht verfügbar werden.
   Eine Freigabe, ein Neustart oder ein Poll allein darf nie schalten.
5. Physische Kanalzuordnung, Ladecode-Semantik, reale Schaltbestätigung und
   Wechselwirkung mit bestehenden Schreibern sind **noch nicht abgenommen**.
   Echte Schaltversuche und Produktivmigration sind ein eigener, vom Besitzer
   ausdrücklich freizugebender Schritt. Keine automatische GitHub-Veröffentlichung.
