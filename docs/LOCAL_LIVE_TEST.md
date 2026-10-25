# Isolated WSL2 + VS Code Dev Container + live EcoFlow read test

**Status:** local developer test recipe; Docker start and real hardware connectivity must be verified on your machine. This repository has an M1/M2 **GET-only** integration. Do not enable power switching, charging, or third-party production integrations in this test instance. **No production Home Assistant data or volumes are shared.**

The two containers are deliberately independent:

1. **VS Code Python 3.14 Dev Container** builds from `.devcontainer/Dockerfile` and reads/writes only the Git working tree. It runs the offline pytest suite. No Docker socket is mounted into it.
2. **Disposable Home Assistant 2026.10.3 Container** starts from `.devcontainer/ha.compose.yml`, binds localhost:8124, uses a private Docker `ha_config` volume for its user accounts, Recorder DB and entity/device registries, and mounts only this repository's `custom_components/` read-only. It connects to EcoFlow's cloud over outbound HTTPS **using credentials provided to the test HA UI**.

Home Assistant and VS Code containers do **not** use host networking, production HA APIs, production tokens, production `/config`, or production Recorder volumes. Sharing one EcoFlow Cloud account/device still means live **GET quota/all** reads on the physical panel. The existing Home Assistant production polling continues separately; concurrent polling can hit EcoFlow API limits.

## Requirements

- Windows with WSL2 Ubuntu, VS Code + WSL + Dev Containers extensions.
- Docker CLI/Compose working from a WSL host terminal (Docker Desktop WSL integration, or a WSL Docker Engine).
- Keep the clone in the Linux filesystem (`~/dev`), **not** `/mnt/c`.

## 1. Clone and open the Python Dev Container

From the WSL **host** shell:

```bash
mkdir -p ~/dev
cd ~/dev
git clone git@github.com:nickwinger/ecoflow_smart_home_panel_v1.git
cd ecoflow_smart_home_panel_v1
docker compose version
code .
```

In VS Code: Command Palette → **Dev Containers: Reopen in Container**. The Python 3.14 development image installs `requirements-test.txt`; it does not run Home Assistant itself.

In the VS Code Dev Container terminal:

```bash
ruff check custom_components tests scripts
ruff format --check custom_components tests scripts
python scripts/sync_catalog.py --check
pytest -q --timeout=30
```

The offline test setup blocks Internet access to tests via pytest-socket. No real EcoFlow device is touched by pytest.

## 2. Start separate Home Assistant DEV container (WSL host)

Open **another WSL terminal outside the Dev Container** and navigate to the same clone:

```bash
cd ~/dev/ecoflow_smart_home_panel_v1
docker compose -f .devcontainer/ha.compose.yml up -d
docker compose -f .devcontainer/ha.compose.yml logs -f homeassistant
```

The first Compose start runs a tiny `seed` one-shot container and creates a **new** `ha_config` Docker volume containing only our minimal `configuration.yaml`. It does not copy anything from your existing HA installation. The integration Python folder is mounted read-only at `/config/custom_components`.

Browse to **http://localhost:8124** (Windows/WSL host), complete first-time Home Assistant onboarding and create a **separate DEV login**. Keep the host port bound to 127.0.0.1; change **8124** in Compose if occupied. Do **not** import a backup or connect this instance to your production HA.

A bridge network is sufficient for Cloud HTTP; this test instance intentionally lacks host network, D-Bus, USB, privileged access, and other production-device discovery integrations. It tests the EcoFlow custom integration and Recorder, **not** Home Assistant OS/Supervisor/HACS installation.

## 3. Connect your real EcoFlow SHP v1, READ-ONLY

In the **DEV** Home Assistant UI:

1. **Settings → Devices & services → Add integration → EcoFlow Smart Home Panel v1**.
2. Enter your normal EcoFlow **access key, secret key and panel serial**, and choose `eu`/`global` as appropriate. Enter credentials **only in this local DEV HA UI**, not in repository files, shell history, tests, GitHub Issues or logs.
3. Confirm first-generation SHP hardware. First setup requires a sufficiently complete quota response with 10 load and 2 backup channels. EcoFlow occasionally omits parts of a response; retrying setup may be necessary.
4. In integration **Options**, increase polling from default 60 seconds to **180–300 seconds** while production also polls the same hardware, to reduce additional Cloud API traffic and rate limiting.
5. Check registered entity names/descriptions/technical quota paths, channel names, live values and default enablement. Enable a few additional diagnostics individually; look at **History** and Developer Tools/States.

**The currently reviewed 0.1.0 M1/M2 code contains a cloud GET client and no PUT/write API or control platforms.** A Docker container **alone does not make future write-capable integration code safe**: before M3, require an explicit read-only guard/option and separate user-approved write tests. Do not install M3 controls here and assume isolation prevents physical actions.

### Acceptance checks before considering production installation

- Integration loads without contacting, updating or migrating your production HA.
- Live grid status, known battery readings and per-circuit state match expected device behavior.
- Actual list of quota keys is discoverable even for disabled diagnostics. Synthetic fixture has **243 scalar entities**, of which **16 enabled, 227 disabled**; live counts can differ.
- Friendly names and **descriptions** match the actual SHP v1 fields; unknown codes/units remain marked uncertain.
- A disabled entity produces no **new** Recorder history; enabling it produces history after the next live state update. Existing prior history is not automatically erased by disabling.
- Restarting HA DEV retains entity identities when its test volume is retained.
- Missing/partial quota fields yield unknown/unavailable rather than fabricated zeros or obsolete good states.
- Poll interval/backoff stays well behaved alongside production Cloud activity.
- Re-running with a **fresh** test database and entity registry does not mutate any production history.

## 4. Edit source and restart *only* the DEV HA

Edit Python in VS Code / Dev Container, then from a WSL host shell:

```bash
docker compose -f .devcontainer/ha.compose.yml restart homeassistant
docker compose -f .devcontainer/ha.compose.yml logs --tail=150 homeassistant
```

This restarts just the isolated HA test service. Integration Python source is bound from the repository, so changes are visible after restart. Translation/catalog changes need an HA restart. You may reload the integration from the DEV UI for supported changes.

## 5. Keep the test history, or erase EVERYTHING in DEV

Stop while retaining entities, account and test history:

```bash
docker compose -f .devcontainer/ha.compose.yml down
```

Remove only this Compose project's test containers **and its isolated HA config volume**, including DEV credentials, entities, Recorder DB and history; then recreate from scratch:

```bash
docker compose -f .devcontainer/ha.compose.yml down -v
docker compose -f .devcontainer/ha.compose.yml up -d
```

`down -v` is **destructive to the DEV test volume only**; the unique Compose project name is `ecoflow-shp-v1-live-test`. Inspect the current Compose file and project before running destructive commands. It does not touch a separately installed HA OS production instance, its Docker volumes, backups, Git repository or cloud device.

The DEV config volume contains unencrypted-in-rest-orchestrator-sense HA-managed secrets and test user credentials; do not share it or upload its contents. No secrets are written to this git repository, but anyone with access to your Docker daemon or host can inspect volumes.

## Known limitations / useful separation

- The Docker test has **Home Assistant Core Container** features, not HA OS, Supervisor or add-ons. HACS isn't required for our live integration test; installing via HACS can be verified separately later.
- No HACS code is installed into DEV: the repository's integration folder is directly mounted. That tests the runtime behavior, not distribution packaging.
- Physical EcoFlow hardware and the cloud API are shared with production, so reads may affect shared rate limits even though no device settings are changed.
- Docker security prevents accidental filesystem sharing but does **not** block a future integration's network **PUT** if such code is added. This reviewed M1/M2 version is read-only; re-evaluate before introducing controls.
- No claim that these steps have already run on your workstation. Verify `docker compose ... config`, actual startup and UI onboarding locally.
