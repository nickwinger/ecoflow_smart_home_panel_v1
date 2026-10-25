# Installation über HACS und Wechsel in den Betrieb

Version **0.4.0** ist für die Installation als **HACS Custom Repository** vorbereitet.
Die Installation schreibt ausschließlich die Integration nach
`custom_components/ecoflow_smart_home_panel_v1`. Einrichtung, Neustart und
Optionsänderungen senden keine Schaltbefehle.

## Voraussetzungen und Installation

- Home Assistant Core **2026.10.0 oder neuer**; geprüft mit 2026.10.3/Python 3.14.
- Installiertes HACS und ein Smart Home Panel **v1**.
- EcoFlow Developer Access Key, Secret Key, Panel-Seriennummer und richtige
  API-Region. Zugangsdaten werden im HA-Konfigurationseintrag gespeichert.
- Ausgehende Verbindungen zu EcoFlow über HTTPS/443 und MQTT mit TLS/8883.
  Kein eigener Broker, Helper oder Zugriff von außen auf HA ist nötig.

1. Erstelle vor dem Wechsel eine normale Home-Assistant-Sicherung.
2. Öffne **HACS → ⋮ → Benutzerdefinierte Repositories**.
3. Trage `https://github.com/nickwinger/ecoflow_smart_home_panel_v1` ein und wähle
   den Typ **Integration**.
4. Lade **EcoFlow Smart Home Panel v1** herunter. Ohne GitHub-Release liefert
   HACS `main`; falls eine Auswahl angezeigt wird, wähle `main`.
5. Starte Home Assistant neu. Öffne **Einstellungen → Geräte & Dienste →
   Integration hinzufügen → EcoFlow Smart Home Panel v1** und richte das Panel ein.
6. Prüfe zuerst Netzstatus, Stromkreisleistung und Speicherwerte, auch bei
   geschlossener EcoFlow-App. Die Steuerfreigaben starten ausgeschaltet.
7. Unter **Optionen**: Abfrageintervall 1–600 Sekunden, Standard 5 Sekunden;
   Quellen-/Betriebsartsteuerung, Laden und Sammelschaltung separat freigeben.
   Die optionale dauerhafte Fehlermeldung ist eine weitere, unabhängige Checkbox.

Ein Release-Tag oder Aufnahme in den HACS-Standardkatalog ist hierfür nicht
erforderlich. [HACS-Installationsregeln](https://www.hacs.dev/docs/publish/integration/),
[Custom Repositories](https://www.hacs.dev/docs/faq/custom_repositories/).
Die README-Versionsnummer und die Datei `manifest.json` zeigen die installierte
Integrationsversion; HACS kann für `main` zusätzlich eine Commit-ID anzeigen.

## Vorhandene Installation aktualisieren

In HACS nach Updates suchen bzw. das Repository erneut herunterladen, danach HA
neu starten. Die Integration nicht aus **Geräte & Dienste** löschen: Derselbe
Konfigurationseintrag erhält Zugangsdaten, Entitäts-IDs, eigene Namen, deaktivierte
Entitäten und Optionen. 0.4.0 ändert das Eintragsschema 1.2 nicht. Die neue
Benachrichtigung bleibt für bestehende Einträge aus, bis du sie aktivierst.

Eine zuvor manuell installierte Kopie im gleichen Integrationsverzeichnis kann
HACS durch die Repository-Installation verwalten. Lege keine zweite Kopie unter
anderem Ordnernamen an und ändere keine Dateien im installierten Verzeichnis:
HACS ersetzt dieses beim Upgrade. Konfiguration und Recorder-Daten liegen in HA,
nicht im Integrationsordner.

## Vorhandene EcoFlow-Scripts ablösen

Nur `homeassistant_config/ecoflow/` ist die gültige Referenz.
`pyscript/shp_mode.py` ist laut Besitzer veraltet und wird nicht übernommen.
Bestehende Scripts und Automationen werden durch Installation nicht verändert.

Ordne erst die bisherigen Messwerte und Bedienelemente den neuen Entitäten zu.
Entferne anschließend beim gewünschten Umstieg die alten Aufrufe aus den
betroffenen Automationen, bevor du die neuen Schreibaktionen aktivierst.
Für „alle Stromkreise“ verwende direkt
`ecoflow_smart_home_panel_v1.set_all_sources`; die nächste Aktion wartet auf den
vollständigen Erfolg. [Automationsbeispiel](AUTOMATIONS.md),
[Zuordnung und Erhalt der Historie](MIGRATION.md).

Alte Helper-Historien bleiben erhalten, werden aber nicht automatisch mit den
neuen Entitäten zusammengeführt. Die neue Integration steuert keine alten Helper.

## Rückkehr zur vorherigen Installation

Stoppe zunächst laufende Sammelschaltungen über **Schaltung abbrechen** und
deaktiviere die zugehörigen Automationen. Spiele bei Bedarf die vorherige
HA-Sicherung ein. Alternativ kann ausschließlich der Integrationsordner aus
einer bekannten Commit-ZIP wiederhergestellt werden; anschließend HA neu starten.
Ein Downgrade stellt nicht automatisch einen physischen Schaltzustand wieder her.
Alte Scripts erst wieder als Schreiber aktivieren, wenn neue Schreibautomationen
deaktiviert sind. Entitätsregister oder Recorder-Daten nicht pauschal löschen.

## Was geprüft wurde und was offen bleibt

Der offizielle HACS-Code prüft Paketstruktur, Manifeste, lokale Brand-Dateien und
Repository-Metadaten. Seine tatsächliche Installationsroutine installiert das
Paket in ein temporäres HA-Verzeichnis und aktualisiert eine Kopie von 0.3.2 auf
0.4.0. Ein separater Python-Prozess lädt ausschließlich die installierten Dateien
und prüft Einrichtung, Optionen, unveränderte Identitäten, Reload und Entfernung.
Alle Cloud-Antworten sind synthetisch; Netzwerkzugriffe sind gesperrt.

Der Besitzer hat Quellenwechsel und Laden bestätigt; Live-Leistung bei
geschlossener App wurde in DEV lesend beobachtet. Die native Sammel- und
Betriebsartsteuerung sind offline geprüft, einschließlich vollständigem Vergleich
mit dem gültigen Referenzscript. Ihre reale Hardware-Abnahme sowie das Klicken
des HACS-Dialogs auf der persönlichen Installation werden dadurch nicht ersetzt.
Der vollständige [Prüfbericht](MILESTONES.md) unterscheidet diese Nachweise.

Bekannte Grenzen: EcoFlow-Cloud-Verfügbarkeit und Messwertaktualität, ungeklärte
Hersteller-/Community-Einheiten einzelner Rohdiagnosen und Tagesenergie-Zähler,
die derzeit nicht für das Energy Dashboard freigegeben sind. Kein SHP2/3-Support.
Es wird keine pauschale elektrische Sicherheitsgarantie gegeben.
