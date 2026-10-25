# Skripte – EcoFlow Smart Home Panel v1

Diese Befehle sind **nur für unsere lokale Entwicklungs-/Testumgebung**. Die öffentlichen Installationsschritte stehen in der [README](README.md); die ausführliche WSL-/VS-Code-Anleitung in [docs/LOCAL_LIVE_TEST.md](docs/LOCAL_LIVE_TEST.md).

## Schnellstart

Im **normalen Ubuntu/WSL-Terminal** im Repository:

```bash
bash scripts/dev-ha.sh start
```

Damit startet Home Assistant DEV auf **http://localhost:8124**. Beim ersten Start wird der lokale Testbenutzer **`test` / `test`** automatisch angelegt.

**Komplett frisch installieren (inklusive Entitäten-Reset):**

```bash
bash scripts/recreate.sh
```

Das ist ein lesbarer Alias für `bash scripts/dev-ha.sh reset`.

## Alle Skripte

| Datei | Zweck | Ausführung |
| --- | --- | --- |
| [`scripts/dev-ha.sh`](scripts/dev-ha.sh) | Zentrale Steuerung der isolierten Home-Assistant-DEV-Instanz | WSL-**Host**, außerhalb des VS-Code-Devcontainers |
| [`scripts/recreate.sh`](scripts/recreate.sh) | **Fresh Install:** DEV-Volume löschen, HA neu starten, `test/test` neu anlegen | WSL-**Host** |
| [`scripts/dev_ha_bootstrap.py`](scripts/dev_ha_bootstrap.py) | Beim ersten Start HA-Onboarding automatisieren; bestehenden DEV-Account bei Wiederholungen beibehalten | Automatisch durch `dev-ha.sh` oder den Docker-Compose-Dienst `bootstrap` |
| [`scripts/sync_catalog.py`](scripts/sync_catalog.py) | Quota-Feldkatalog, Entitätsnamen und Übersetzungsdateien aktualisieren oder prüfen | Python-Terminal im VS-Code-Devcontainer |

## `dev-ha.sh` – Befehle

| Befehl | Wirkung |
| --- | --- |
| `bash scripts/dev-ha.sh start` | Startet HA DEV; **vorhandene Daten bleiben erhalten** |
| `bash scripts/dev-ha.sh restart` | Startet HA DEV neu, um Python-Codeänderungen zu übernehmen; **kein Datenverlust** |
| `bash scripts/dev-ha.sh stop` | Stoppt die DEV-HA-Dienste; Registry und Verlauf bleiben erhalten |
| `bash scripts/dev-ha.sh status` | Zeigt den Status der DEV-Container |
| `bash scripts/dev-ha.sh logs` | Zeigt laufende HA-Logs; Beenden mit `Ctrl+C` |
| `bash scripts/dev-ha.sh doctor` | Kontrolliert, ob unser Integrations-Manifest im HA-Container gemountet ist, und zeigt relevante Fehler |
| `bash scripts/dev-ha.sh open` | Öffnet den Integrationsdialog im Browser |
| `bash scripts/dev-ha.sh reset` | **Identisch zu `recreate.sh`:** HA-DEV-Daten löschen und direkt neu starten |
| `bash scripts/dev-ha.sh clean` | HA-DEV-Daten löschen, **ohne** wieder zu starten |
| `bash scripts/dev-ha.sh test` | Startet `pytest`, wenn die Test-Abhängigkeiten in dieser Shell installiert sind |
| `bash scripts/dev-ha.sh help` | Zeigt die aktuelle Hilfe |

`start`, `reset` und `recreate.sh` unterstützen `--no-browser` (z. B. `bash scripts/recreate.sh --no-browser`).

## Fresh Install: Was wird tatsächlich gelöscht?

```bash
bash scripts/recreate.sh
```

Das Skript verwendet die vorhandene Reset-Routine in `dev-ha.sh` und führt diese Schritte aus:

1. Nur die DEV-Dienste `homeassistant` und `bootstrap` stoppen.
2. Die zugehörigen DEV-HA- und Setup-Container entfernen.
3. **Ausschließlich** das Docker-Volume `ecoflow-shp-v1-live-test_ha_config` löschen.
4. Home Assistant DEV mit neuer, leerer Konfiguration/Recorder-Datenbank starten.
5. Den lokalen Benutzer `test/test` über die HA-Onboarding-API erzeugen und den Browser öffnen.

**Dadurch werden in DEV gelöscht:** bisherige 850 (oder andere) Entitäten, Geräte-/Entitätsregister, gesamte DEV-Historie, DEV-Login und EcoFlow-API-Zugangsdaten. Den EcoFlow Access Key, Secret Key und die Seriennummer musst du anschließend **neu** im Integrationsdialog eingeben.

**Nicht betroffen:** Git-Repository, Python-Devcontainer in VS Code, deine Produktiv-Home-Assistant-Konfiguration, produktive Recorder-Daten, produktive Helfer sowie die Einstellungen des physischen EcoFlow-Panels. Das Docker-Image darf gecacht bleiben: **Fresh Install bedeutet neue HA-Daten, keine Neuinstallation von Docker**.

Ein normales `restart` oder **Dev Containers: Reopen in Container** löscht dagegen **keine** Entitäten. Verwende `recreate.sh` insbesondere nach grundlegenden Änderungen am Entity-Naming oder an Unique IDs.

## `sync_catalog.py`

Nach Änderungen an `docs/quota-field-guide.json` im **Python-Devcontainer**:

```bash
python scripts/sync_catalog.py --check  # Prüfen, ob generierte Dateien aktuell sind
python scripts/sync_catalog.py          # Bei Bedarf neu erzeugen
```

Ohne `--check` schreibt das Skript `catalog.json`, `strings.json` und die Übersetzungen der Integration. Es verändert **keine** HA-Entitätsregister oder Recorder-Daten.

## Sicherheit und Umgebung

- Docker-Kommandos nur im **WSL-Host-Terminal**; der Python-Devcontainer hat bewusst keinen Docker-Socket.
- Das DEV-Webinterface ist an **127.0.0.1:8124** gebunden. `test/test` keinesfalls über Tunnel, Portweiterleitungen oder Proxies öffentlich machen.
- Die DEV-Instanz und die Produktivinstallation verwenden **keine gemeinsamen HA-Datenvolumes**.
- Die automatische Anmeldung darf ausschließlich die DEV-Loopback-Adressen erreichen: WSL-Host `127.0.0.1:8124`, Compose-Bootstrap `127.0.0.1:8123` innerhalb des **DEV-HA-Netzwerk-Namespace** (`network_mode: service:homeassistant`). Kein DNS, kein Proxy, keine HTTP-Weiterleitung; für 8123 ist zusätzlich die DEV-Compose-Markierung erforderlich.
- Das reale EcoFlow-Gerät kann mit Cloud-GET-Abfragen gelesen werden. Die Cloud-API-Limits gelten trotz lokaler Trennung weiterhin.
