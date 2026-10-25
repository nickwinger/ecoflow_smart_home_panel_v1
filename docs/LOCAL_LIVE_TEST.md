# EcoFlow SHP v1 — lokaler Devcontainer-Workflow

**Ziel:** `code .` → VS Code Dev Container öffnen → eigenständiges Home Assistant DEV startet und öffnet den Browser beim EcoFlow-Integrationsdialog. Der DEV-Benutzer **test / test** wird beim ersten Start automatisch angelegt. Echte EcoFlow-Cloud-Daten sind möglich, aber die Produktion bleibt unberührt.

> **Sicherheit:** Die absichtlich schwachen Zugangsdaten `test/test` sind NUR für diese lokale Wegwerf-Instanz. Das Webinterface ist über `127.0.0.1:8124` gebunden. Nicht über Port-Forwarding, Tunnel oder Proxy öffentlich machen. Keine Prod-HA-Konfiguration/Volume/API mounten. Der gegenwärtige Integrationsstand M1/M2 macht nur GET-Requests; ein späteres M3 muss vor Live-Tests neu auf Schreibsicherheit geprüft werden.

## Einmalige Voraussetzungen

- Windows 11, Ubuntu/WSL2, VS Code mit **WSL** und **Dev Containers** Extensions.
- Docker Desktop mit aktivierter WSL-Integration für Ubuntu (oder Docker Engine + Compose v2 in WSL).
- Repository **unter `~/dev` in WSL**, nicht unter `/mnt/c`.
- Python 3 auf dem WSL-Host für das lokale DEV-Onboarding-Skript.

Beim ersten Klonen:

```bash
mkdir -p ~/dev && cd ~/dev
git clone git@github.com:nickwinger/ecoflow_smart_home_panel_v1.git
cd ecoflow_smart_home_panel_v1
code .
```

### Schnellstart: automatisch über VS Code

1. Öffne den Projektordner in VS Code (in WSL mit `code .`).
2. Wähle **Dev Containers: Reopen in Container**. Die `initializeCommand` startet **vom WSL-Host aus** den separaten Home-Assistant-Container, wartet auf die API, erzeugt bei frischem Volume automatisch `test/test`, schließt die Onboarding-Schritte ab und öffnet den Browser direkt unter:

   **http://localhost:8124/config/integrations/add?domain=ecoflow_smart_home_panel_v1**

3. Melde dich beim erstmaligen Öffnen des Browsers mit **test / test** an. Der Browser merkt sich die Anmeldung normalerweise für spätere Sitzungen.
4. **Nur beim ersten Einrichten des EcoFlow-Integrationsdialogs**: EcoFlow Access Key, Secret Key, Geräte-Seriennummer, Region (EU/global) und SHP-v1-Bestätigung eingeben. Die Daten landen nur in der **eigenen DEV-HA-Konfiguration**, niemals in Git oder in einem Skript.
5. **Integration jetzt live testen**: Geräte und Entitäten öffnen; Default-Deaktivierungen, Friendly Names, Erklärungen, Quota-Pfade, Statuswerte, Kanalnamen und Recorder-Verlauf prüfen. Gegen das echte Smart Home Panel lesen wir, **nicht schalten**.

Das sind die einzigen erwarteten manuellen UI-Schritte. **Eine neue DEV-Instanz benötigt ein einmaliges Browser-Login und die echten EcoFlow-Zugangsdaten.** Solche Cloud-Secrets übernehmen wir bewusst nicht aus deinem produktiven HA.

Wenn VS Code beim Reopen eine Fehlermeldung wegen fehlendem Docker meldet, Docker Desktop starten, WSL-Integration prüfen und den Befehl erneut ausführen.

### Schnellstart: ohne VS Code

Im **normalen WSL-Host-Terminal** (nicht im Python-Devcontainer):

```bash
cd ~/dev/ecoflow_smart_home_panel_v1
bash scripts/dev-ha.sh start
```

Das Kommando validiert Docker/Compose, startet Home Assistant DEV, wartet auf den Onboarding-Endpunkt, erzeugt `test/test` beim ersten Start, und öffnet unter Windows den Browser. Es ist idempotent: Ein erneuter Aufruf **behält** Nutzer, Geräte, Registry und Historie.

## Aufgaben im Alltag

Alle Docker-Kommandos werden im normalen **WSL-Host-Terminal** ausgeführt:

| Aufgabe | Kommando | Wirkung |
| --- | --- | --- |
| Starten + Browser öffnen | `bash scripts/dev-ha.sh start` | DEV starten, bei Bedarf automatisch initialisieren |
| Integrationsdialog öffnen | `bash scripts/dev-ha.sh open` | Nur Browser öffnen |
| Python-Quellcode neu laden | `bash scripts/dev-ha.sh restart` | Nur DEV Home Assistant neu starten |
| Logs | `bash scripts/dev-ha.sh logs` | Live-Logs von DEV anzeigen (mit `Ctrl+C` verlassen) |
| Status | `bash scripts/dev-ha.sh status` | DEV-Container anzeigen |
| Stoppen | `bash scripts/dev-ha.sh stop` | Container stoppen, **alle DEV-Daten behalten** |
| Vollständig zurücksetzen | `bash scripts/dev-ha.sh reset` | **Nur DEV-Volume löschen**, neu starten, neuen `test/test`-Benutzer anlegen |
| DEV-Daten löschen ohne Neustart | `bash scripts/dev-ha.sh clean` | **Nur DEV** einschließlich Recorder/Auth/Entities entfernen |

Im **VS-Code-Devcontainer-Terminal** (offline, ohne Docker-Socket) die Tests starten:

```bash
ruff check custom_components tests scripts
ruff format --check custom_components tests scripts
python scripts/sync_catalog.py --check
pytest -q --timeout=30
```

Alternativ bietet `bash scripts/dev-ha.sh test` denselben pytest-Lauf (in einer Python-Umgebung mit installierten Testanforderungen).

## Reset: frische Entitäten ohne Seiteneffekte

Bei Änderungen an `unique_id`, Quota-Paths, Entity-Katalog, Registry-Migration oder Default-Enablement:

```bash
bash scripts/dev-ha.sh reset
```

Ablauf:
1. Löscht ausschließlich das Compose-Projekt `ecoflow-shp-v1-live-test` samt dessen benanntem **DEV-`ha_config`-Volume**.
2. Entfernt **nur** dort gespeicherte DEV-Benutzer, Registry, Quota-Entitäten, Historie, Integrationsoptionen und EcoFlow-Credentials.
3. Erstellt eine frische DEV-Konfiguration und `test/test`, öffnet wieder den Integrationsdialog.
4. **EcoFlow Access/Secret/SN danach erneut eingeben**, weil diese zusammen mit dem DEV-Volume gelöscht wurden.

**Kein Reset nötig** bei normalen Änderungen an Python-Sensor-/API-Code: `restart` reicht meistens. Auch nach einfachen Änderungen an Friendly Names/Translations zunächst `restart` testen; bei persistierten HA-Namen/Entitäten ggf. `reset` verwenden.

**Was bleibt beim Reset unberührt?** Das Git-Repository, der VS Code Python-Devcontainer, dein produktives Home Assistant mit allen Entitäten/Datenbanken/Helfern/Automationen und das Smart Home Panel. Ein Reset setzt *keine physischen Geräte* zurück.

Das isolierte Compose-Projekt verwendet nur:
- Port `127.0.0.1:8124` zum DEV-HA-Container, niemals deinen produktiven HA-Port.
- Ein **eigenes Docker-Volume** für `/config` und Recorder.
- Einen **Read-only**-Mount auf `custom_components/` aus diesem Git-Repository.
- Keine produktiven Home-Assistant-Tokens, Configs, Datenbank-Volumes oder weitere Geräte-Mounts.

Die Integration wird **direkt aus deinem Checkout** geladen, nicht über HACS. HACS-Paketinstallation kann separat getestet werden; unser lokaler Funktionstest benötigt HACS nicht.

## Live-Checkliste

- [ ] `http://localhost:8124` öffnet die DEV-Instanz, **test/test** funktioniert.
- [ ] Unsere Integration erscheint unter **Einstellungen → Geräte & Dienste** und lässt sich per DEV-Zugangsdaten einrichten.
- [ ] Gerät wird als **EcoFlow Smart Home Panel v1** erkannt.
- [ ] Quota-Entitäten erscheinen mit korrekten freundlichen Namen und erklärenden Metadaten.
- [ ] Bekannte Werte stimmen mit dem echten Panel überein; bei fehlenden API-Feldern keine erfundenen Nullen.
- [ ] In DEV-Integrationsoptionen das Polling anfangs auf **180–300 Sekunden** stellen (Prod fragt das Gerät ebenfalls ab).
- [ ] Einige unwichtige Diagnose-Entitäten bleiben deaktiviert. Nach manuellem Aktivieren erhalten nur diese und andere aktive Entitäten **neue** Recorder-Historie.
- [ ] `restart` bewahrt die Entitäts-IDs; `reset` erzeugt einen komplett sauberen neuen Registry-Stand.
- [ ] Keine PUT-Aufrufe, kein Schalten oder Laden; M3 ist noch nicht implementiert.

## Fehlersuche

**Docker nicht erreichbar:** Docker Desktop starten und in Einstellungen → Resources → WSL Integration das Ubuntu aktivieren. Im WSL-Host `docker compose version` und `docker info` prüfen.

**Port 8124 belegt:** Keine fremde Instanz auf 8124 überschreiben. `bash scripts/dev-ha.sh status` kontrollieren und bei Bedarf fremden Dienst gezielt stoppen. Das Skript bindet absichtlich nur localhost.

**Skript öffnet keinen Browser:** Angezeigte URL manuell öffnen. Unter WSL versucht das Skript `wslview`, dann `powershell.exe`, sonst `xdg-open`.

**Login passt nicht:** `test/test` wird **nur auf einer brandneuen DEV-Datenbank** automatisch eingerichtet; existierende Benutzer werden nicht überschrieben. Wenn du die alten DEV-Daten nicht brauchst, `reset` ausführen.

**Cloud/API Fehler oder unvollständige Quota-Antwort:** `logs` lesen, richtige EU/global-Region und Seriennummer prüfen. Die API antwortet teils mit unvollständigen Kanalsteuerfeldern; ggf. Integration erneut konfigurieren. Nicht einfach Polling hochdrehen – bei gleichzeitiger Prod-Abfrage eher 180–300 Sekunden nehmen.

**Onboarding-Skriptfehler:** Nur die lokalen DEV-Onboarding-APIs werden verwendet, kein Editieren von `.storage` oder Prod-Konfiguration. Wenn der DEV-User zwar existiert, aber der Bootstrap nicht alle Schritte abschließen kann, `bash scripts/dev-ha.sh reset` bei wegwerfbaren DEV-Daten erneut versuchen; sonst manuell im Browser beenden.

**Manueller Docker-Start (falls nötig):**

```bash
docker compose -f .devcontainer/ha.compose.yml up -d
python3 scripts/dev_ha_bootstrap.py
```

Die Anleitung und die Automatisierung wurden gegen Home Assistants API-Quellcode 2026.10.3 erstellt. **Docker/Browser/echte EcoFlow-Credentials müssen auf deinem WSL-Rechner erstmals praktisch verifiziert werden.**
