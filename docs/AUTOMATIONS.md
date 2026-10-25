# Alle Stromkreise in einer Automation umschalten

Verwende die Aktion (den Dienst)
**`ecoflow_smart_home_panel_v1.set_all_sources`** direkt als Schritt deiner
Automation. Sie wartet auf die gesamte Schaltfolge einschließlich Bestätigungen,
Wiederholungen und letzter Pause. Die nächste Aktion beginnt erst nach Erfolg.
Ein zusätzlicher Timer oder ein Helper ist nicht erforderlich.

Unter den Integrationsoptionen müssen **Stromkreise steuern** und
**Sammelschaltung freigeben (Automationen und Tasten)** eingeschaltet sein.
Die Freigaben allein führen keine Schaltung aus.

Optional lässt sich in denselben Optionen **Dauerhafte Benachrichtigung bei
fehlgeschlagener Sammelschaltung** aktivieren. Die Meldung ergänzt den
Automationsfehler und zeigt unbestätigte Stromkreise; sie verändert das Warten
und Stoppen der Automation nicht. [Verhalten der Benachrichtigung](CONTROLS.md#optionale-dauerhafte-fehlerbenachrichtigung).

## Im Automationseditor

1. Füge die EcoFlow-Aktion zum Umschalten aller Stromkreise hinzu.
2. Wähle den Integrationseintrag deines Panels, Netzstrom oder Batterie und
   aktiviere die Bestätigung für die Sammelschaltung.
3. Ordne die nächste gewünschte Aktion direkt danach an.
4. Lasse „Bei Fehler fortfahren“ ausgeschaltet. Für eine einzelne laufende
   Schaltfolge eignet sich der Automationsmodus **Einzeln** (`single`).

Der folgende YAML-Ausschnitt gehört in eine bestehende Automation; Auslöser und
nachfolgende Aktionen sind anwendungsabhängig. Der grafische Editor trägt die
`config_entry_id` durch die Panel-Auswahl ein. Sie ist die ID des
**Integrationseintrags**, nicht die Geräte-ID aus der Browseradresse.

```yaml
mode: single
actions:
  - action: ecoflow_smart_home_panel_v1.set_all_sources
    data:
      config_entry_id: "DEIN_INTEGRATIONSEINTRAG"
      source: battery
      confirm: true
    response_variable: shp_ergebnis
  # Weitere Aktionen hier: Sie starten erst nach vollständigem Erfolg.
```

Für Netzstrom verwende `source: grid`. `response_variable` ist optional und
beeinflusst das Warten nicht. Bei Erfolg enthält das Ergebnis unter anderem
`state: succeeded`, `completed: [7, 6, 3, 1, 2, 4, 5, 8, 9, 10]` und `failed: []`.
Bei Fehlschlag gibt es stattdessen einen Aktionsfehler.

## Erfolg, Fehler und Abbruch

- **Erfolg:** Jeder Stromkreis wurde anhand einer frischen EcoFlow-Antwort am
  Ziel bestätigt. Auch die letzte Pause ist abgeschlossen. Erst dann kehrt der
  Dienst erfolgreich zurück und die Automation fährt fort.
- **Einzelner Stromkreis schlägt fehl:** Die bewährte Folge bearbeitet trotzdem
  die übrigen Stromkreise. Nach allen zehn meldet der Dienst die unbestätigten
  Nummern als Fehler. Die nächste Automationsaktion wird nicht ausgeführt.
- **Abbruch:** „Schaltung abbrechen“, `cancel_commands`, Stoppen der Automation
  oder Entladen der Integration unterbrechen den Auftrag. Nachfolgende Aktionen
  der abgebrochenen Sequenz starten nicht. Ein bereits gesendeter Befehl kann
  noch wirken; es erfolgt keine automatische Rückschaltung.

Die Bestätigung gilt jeweils zum Prüfzeitpunkt des Stromkreises. Sie ist keine
elektrische Verriegelung und verhindert keine späteren Änderungen durch das
Panel, die App oder andere Automationen. Bei Cloud-/Gerätefehlern kann die
Integration keinen vollständigen Erfolg garantieren; sie meldet den Fehler.

Ohne Wiederholung dauern die Pausen beim tatsächlichen Umschalten insgesamt
**3 Minuten 20 Sekunden**, zuzüglich API-Laufzeiten. Sind alle Stromkreise bereits
am Ziel, bleiben **1 Minute 40 Sekunden** Kanalpausen. Wiederholungen verlängern
den Ablauf. Diese Zeiten und die Reihenfolge entsprechen dem Referenzscript;
sie werden für Automationen nicht verkürzt.

`single` verhindert überlappende Ausführungen derselben Automation. Wenn weitere
Auslösungen später abgearbeitet werden sollen, ist `queued` möglich. `restart`
bricht eine bereits laufende Folge ab. Für das gewünschte Warteverhalten den
Dienst direkt in der Sequenz aufrufen, nicht in einem parallelen Zweig oder über
`script.turn_on`, das ein anderes Script nur startet. Kein
`continue_on_error: true` hinzufügen: Das würde die Fehlerbehandlung ausdrücklich
übergehen. [HA-Aktionsabläufe](https://www.home-assistant.io/docs/automation/building-blocks/),
[Automationsmodi](https://www.home-assistant.io/docs/automation/modes/).

## Warum für diesen Fall der Dienst?

Die Tasten und der Dienst verwenden denselben Schaltcontroller mit denselben
Befehlen, Bestätigungen und Pausen. Eine verfügbare Taste wird bei einem direkten
Automationsaufruf ebenfalls abgewartet. Home Assistant kann allerdings eine
**nicht verfügbare Button-Entität überspringen** und anschließend fortfahren.
Der direkte EcoFlow-Dienst prüft den Integrationseintrag und die Freigaben und
meldet einen Fehler, wenn er die Folge nicht ausführen kann. Daher ist er für
eine Automation, deren nächster Schritt vollständigen Erfolg voraussetzt, die
passende Schnittstelle. Dieses Verhalten ist mit echten HA-Script-Sequenzen und
simulierten Geräteantworten getestet.

Der Zeitstempel einer Taste bezeichnet den Tastendruck und bestätigt keinen
Schalterfolg. [HA-Button-Dokumentation](https://www.home-assistant.io/integrations/button/).
Details und Fehlerursachen stehen im [Home-Assistant-Protokoll](CONTROLS.md#fehler-im-home-assistant-protokoll)
und im Ablaufprotokoll der Automation; der aktuelle Fortschritt ist außerdem
unter `control_operation` in den Steuerentitäten und Diagnosen sichtbar.
