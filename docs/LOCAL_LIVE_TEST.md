# EcoFlow Smart Home Panel v1 – Entwicklungsworkflow (VS Code / WSL2)

**Empfohlen: VS Code → Dev Containers: Reopen in Container.** Die Konfiguration startet jetzt den Python-Arbeitscontainer und Home Assistant DEV als **zwei Dienste im selben Docker-Compose-Projekt**. Der Benutzer `test/test` wird beim ersten Start automatisch durch einen dritten, kurzlebigen Setup-Dienst angelegt. Der Python-Container hat **keinen Docker-Socket** und keinerlei Zugang zu Produktiv-HA-Konfigurationen.

**Netzwerksicherheit des Bootstrap-Skripts:** Beim Start aus WSL verwendet `dev_ha_bootstrap.py` `127.0.0.1:8124` (die lokale DEV-Portfreigabe). Der Docker-Compose-Dienst `bootstrap` verwendet `127.0.0.1:8123`, teilt dafür aber mit `network_mode: service:homeassistant` **ausschließlich den Netzwerk-Namespace des DEV-HA-Containers**. Das ist ausdrücklich **nicht** die Produktivinstallation und kein DNS-Hostname. Der interne Modus erfordert zusätzlich `ECOFLOW_DEV_BOOTSTRAP=1` aus der DEV-Compose-Konfiguration. HTTP-Proxies und Weiterleitungen sind deaktiviert; falls DEV nicht erreichbar ist, wird abgebrochen statt einen fremden Host zu kontaktieren.

**Sicherheitsgrenze:** Dieses `test/test` ist bewusst nur für eine lokale Wegwerf-Testinstanz. Kein Tunnel, Portforward zu anderen Hosts oder öffentliches Netzwerk! Home Assistant DEV lauscht am Host auf `127.0.0.1:8124`. Seit M3 (0.2.0) gibt es optionale echte PUT-Befehle. Für diese Leseprüfung **alle drei Steuerfreigaben ausgeschaltet lassen** und keine Schreibaktionen oder Steuerautomationen aufrufen. Ein Container schützt das reale Panel nicht vor Cloud-Befehlen. Details und Abbruchverhalten: [CONTROLS.md](CONTROLS.md). Die EcoFlow Cloud und ihre API-Limits sind trotz lokaler HA-Isolation **echt**.

## 1. Einmalig: VS Code starten

Voraussetzung: Docker Desktop mit aktivierter Ubuntu-WSL-Integration; **sowohl** `docker version` unter WSL **als auch** in Windows PowerShell muss einen **Server** anzeigen. WSL kann funktionieren, während Windows/VS Code wegen einer fehlenden `dockerDesktopLinuxEngine`-Pipe trotzdem hängen bleibt. In diesem Fall ist der Docker-Desktop-Zugriff von Windows zu reparieren, nicht die EcoFlow-Integration.

Im **normalen WSL-Terminal**:

```bash
cd ~/dev/ecoflow_smart_home_panel_v1
git pull --ff-only
code .
```

Unten links muss `WSL: Ubuntu` stehen. In VS Code `Ctrl+Shift+P` → **Dev Containers: Rebuild and Reopen in Container** (bei späteren Starts genügt **Reopen in Container**).

**Was VS Code nun automatisch übernimmt:**
1. Baut den Python-3.14-Arbeitscontainer aus `.devcontainer/Dockerfile`.
2. Startet `homeassistant` mit einer **eigenen** Konfiguration/Recorder-Datenbank und bindet die **lokalen** Projekt-Python-Dateien unter `/config/custom_components` read-only ein.
3. Startet `bootstrap`, das die Home-Assistant-DEV-Einrichtung bei einem neuen Testvolume mit `test/test` abschließt (ohne `.storage` direkt zu manipulieren). Existierende DEV-Daten bleiben erhalten.
4. VS Code versucht, den weitergeleiteten HA-Port automatisch im Browser zu öffnen (je nach Portbelegung kann das ein dynamischer localhost-Port sein). Die feste Adresse **http://localhost:8124** bleibt unabhängig davon verfügbar.

Es gibt **kein** `initializeCommand` mehr, das vor dem Devcontainer-Aufbau seinerseits Docker Desktop startet und blockiert. Ein unter Windows defekter Docker-Client verhindert allerdings weiterhin den eigentlichen Devcontainer-Aufbau; siehe Fehlerbehebung.

## 2. Integration im Browser konfigurieren

1. **http://localhost:8124** öffnen und mit **test / test** einloggen. VS Codes automatisch geöffneter Forwarding-Port führt zur *selben* HA-DEV-Instanz, er kann aber eine eigene Browser-Anmeldung benötigen.
2. Unter **Einstellungen → Geräte & Dienste → Integration hinzufügen** nach **EcoFlow Smart Home Panel v1** suchen. Die Übersichtsseite zeigt *nur bereits eingerichtete* Integrationen; die neue Integration steht deshalb **nicht schon als Kachel auf der Übersichtsseite**.
3. Einmalig Access Key, Secret Key, Seriennummer und EU/global-Region des **echten SHP v1** eingeben. Die Secrets liegen ausschließlich im lokalen DEV-Volume und werden nicht in Git oder in Skripte übernommen.
4. Den Gerätestatus, Friendly Names, technische Quota-Pfade, Diagnosesensoren und History kontrollieren. Bei paralleler Produktiv-Abfrage empfehlen wir zunächst **180–300 Sekunden** Polling in den Optionen, um EcoFlow-API-Limits zu schonen.

Nach erfolgreicher Einrichtung brauchst du diese Schritte bei normalen Neustarts **nicht** erneut. Die Testinstanz verwendet dasselbe Volume. Nach einem vollständigen Reset musst du dagegen die EcoFlow-Credentials wieder eingeben.

## 3. Alle Befehle: Start, Neustart, Diagnose, Reset

Docker-Kommandos im **WSL-Host-Terminal** ausführen (nicht im isolierten Python-Devcontainer):

| Aktion | Befehl | Ergebnis |
| --- | --- | --- |
| Nur HA DEV starten + Browser öffnen | `bash scripts/dev-ha.sh start` | Verwendet bestehendes DEV-Volume, baut **nicht** den Python-Container |
| Integration/Mount prüfen | `bash scripts/dev-ha.sh doctor` | Kontrolliert Manifest im HA-Container, zeigt relevante Logmeldungen |
| Quellcode in HA neu laden | `bash scripts/dev-ha.sh restart` | Startet **nur HA DEV** neu, Entitätsregister bleibt |
| Status | `bash scripts/dev-ha.sh status` | Zeigt laufende DEV-Dienste |
| Logs | `bash scripts/dev-ha.sh logs` | Live-Log (`Ctrl+C` beendet nur die Ansicht) |
| Nur HA DEV stoppen | `bash scripts/dev-ha.sh stop` | Testdaten und Python-Arbeitscontainer bleiben |
| **Komplett neu anfangen (Fresh Install)** | `bash scripts/recreate.sh` (oder `bash scripts/dev-ha.sh reset`) | Löscht **nur** das HA-DEV-Volume, startet HA mit `test/test` neu |
| DEV-Daten nur löschen | `bash scripts/dev-ha.sh clean` | Löscht die isolierte HA-Konfiguration ohne Neustart |

Beim `reset` werden ausschließlich die HA-DEV-Konten, eingerichteten EcoFlow-Schlüssel, Geräte-/Entitätsregister und Recorder-Historie gelöscht. Das Git-Repository, der geöffnete Python-Devcontainer und deine produktive Home-Assistant-Installation bleiben bestehen. Die Funktionen greifen **nicht** auf produktive `/config`-Pfade oder produktive Docker-Volumes zu.

Wenn du nur neue Python-Sensorlogik, den Katalog oder Übersetzungen testest, zuerst `restart` verwenden. `reset` brauchst du, um Entitäts-IDs und Registry-Migrationen gegen eine vollständig neue Installation zu testen.

Eine vollständige Befehlsübersicht steht in [scripts.md](../scripts.md). Das Fresh-Install-Skript ist [scripts/recreate.sh](../scripts/recreate.sh). 

## 4. Integration fehlt in „Integration hinzufügen“?

Zunächst **in der Integrationsauswahl suchen**, nicht in der Kachelübersicht. Wenn EcoFlow dort wirklich nicht vorhanden ist:

```bash
bash scripts/dev-ha.sh doctor
```

Erwartet wird `OK: EcoFlow manifest is visible.` Das prüft diesen Pfad *im laufenden DEV-Container*:

```text
/config/custom_components/ecoflow_smart_home_panel_v1/manifest.json
```

Bei Fehlern `bash scripts/dev-ha.sh logs` ausführen, insbesondere nach `ecoflow_smart_home_panel_v1`, `custom_components`, `Setup failed` suchen. Wenn das Manifest vorhanden ist und keine Fehler auftreten, HA DEV mit `restart` neu laden und im Browser **Ctrl+F5** für einen Hard Refresh drücken. Home Assistant kann den Integrationsauswahldialog zwischenspeichern.

**Direkter Konfigurationsdialog nach dem Login:** http://localhost:8124/config/integrations/add?domain=ecoflow_smart_home_panel_v1 (nach Erst-Login ggf. nochmals öffnen, da HA zur Übersicht zurückspringen kann).

## 5. Python-Tests direkt in VS Code

Im **Terminal des Python-Devcontainers** laufen die Offline-Tests ohne Zugriff auf echte Geräte:

```bash
ruff check custom_components tests scripts
ruff format --check custom_components tests scripts
python scripts/sync_catalog.py --check
pytest -q --timeout=30
```

Änderungen an `custom_components/ecoflow_smart_home_panel_v1/` landen durch die geteilte Quellcode-Einbindung direkt im HA DEV. Nach Python-Codeänderungen `restart` aus einem **zweiten WSL-Host-Terminal** ausführen; es wird kein HACS-Installationsprozess benötigt. Der Devcontainer selbst hat bewusst keinen Docker-Zugriff und kann nicht versehentlich andere Container verwalten.

## 6. Falls VS Code wieder „Starting Docker“ meldet

Unter Windows **PowerShell**:

```powershell
docker version
docker context ls
```

Erst wenn `docker version` auch unter Windows einen **Server** zurückliefert, kann die VS-Code-Dev-Containers-Erweiterung dort Docker verwenden. `docker version` in WSL allein beweist nur, dass der WSL-Client funktioniert. Bei defektem Windows-Docker-Zugang kannst du bis zur Behebung trotzdem direkt aus WSL mit `bash scripts/dev-ha.sh start` weiter testen.

Wenn Windows-Docker funktioniert, im WSL-Fenster von VS Code **Rebuild and Reopen in Container** aufrufen. Die aktualisierte Compose-Konfiguration ruft **kein zusätzliches `Docker Desktop.exe`** über einen Start-Hook mehr auf. Eventuell durch die VS-Code-Erweiterung selbst ausgelöste Docker-Desktop-Starts lassen sich dagegen nicht allein mit einer Projektdatei verhindern.

## Bekannte Grenzen

- Diese lokale Umgebung ist **Home Assistant Container**, kein HA OS/Supervisor.
- Für den funktionalen Test wird die Integration direkt aus Git eingebunden; HACS-Installation selbst ist ein separater M4-Test.
- Nur aktivierte Entitäten erhalten neue Recorder-Historie, standardmäßig deaktivierte Diagnose-Entitäten nicht.
- `test/test` ist kein sicheres Passwort. DEV niemals veröffentlichen.
- Docker-/Browser-Start und reale EcoFlow-Anbindung können nur auf deinem Rechner praktisch geprüft werden; GitHub Actions prüfen die Syntax, Abhängigkeiten und simulierte Tests, nicht die reale Windows-Docker-Desktop-Instanz.
