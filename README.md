# EcoFlow Smart Home Panel v1 — Home Assistant

**M1 + M2 implemented and verified offline.** Native, read-only integration for the first-generation EcoFlow Smart Home Panel. Hardware acceptance, safe controls (M3) and release readiness (M4) remain open. No GitHub release has been published. SHP2/3 and other EcoFlow devices are unsupported.

## Isolated local live-device test

For a **separate Docker Home Assistant 2026.10.3** on `http://localhost:8124`, a Python 3.14 VS Code Dev Container, disposable local Recorder/registry state and live **read-only** EcoFlow Cloud polling, see [docs/LOCAL_LIVE_TEST.md](docs/LOCAL_LIVE_TEST.md). Do **not** test against production Home Assistant. HACS is not needed for this local runtime test.

## What works

- UI configuration of per-panel access key, secret key, serial and EU/global API endpoint; duplicate-serial prevention, reauthentication and credential replacement.
- One asynchronous, signed EcoFlow client and one DataUpdateCoordinator per panel. Default polling is 60 seconds, configurable from 30–900 seconds, with failure backoff and rate-limit handling.
- Every safe scalar quota leaf is discoverable, including dotted keys, nested objects, arrays, nulls and new fields. Raw access identity is preserved even when two display paths collide.
- German/English friendly names and explanations for 92 catalog patterns (all 81 seed patterns plus 11 additions), including indexed container fallbacks. Device channel labels support strings and valid zero-padded UTF-8 byte lists without changing entity identity.
- Native sensor/binary_sensor entities, stable device identity, dynamic discovery, clean unload/reload and safe aggregate diagnostics.
- History exclusively through HA Recorder for enabled entities. No quota archive, extra database, snapshots or per-entity API requests.

The independent synthetic fixture contains **243 scalar leaves → 243 registry entities**. **16 start enabled; 227 start disabled.** Real totals depend on the fields the cloud returns. The registry limit is 4,096 identities per entry, including previously discovered fields across reloads.

| Enabled by default | Count in fixture | Interpretation |
| --- | ---: | --- |
| Grid availability | 1 | Documented binary 0/1 |
| Backup battery percentage | 1 | Only 0–100; valid readings support measurement statistics |
| Circuit supply source | 10 | 0 grid, 1 battery, 2 off; other codes unknown |
| Nominal grid voltage/frequency | 2 | Configuration values, not live measurements |
| Daily grid/backup energy fields | 2 | Community unit Wh; no statistics until resets and scale are verified |

Channel power and per-storage percentages/power/temperature remain individually enableable diagnostics. The supplementary sources now support explicit **community units** (W, %, °C); they receive no automatic statistics. Configured channel currents use A and documented operating time uses min. Unresolved capacity scales, remaining-time sentinels and energy-interval timing remain raw. Backup `ctrlSta=2` conflicts between the manufacturer table and the existing charging helper, so it remains a raw code. The [entity catalog](docs/ENTITY_CATALOG.md) explains these decisions.

## Installation in an isolated test instance

Requires **Home Assistant 2026.10 or newer / Python 3.14**; offline tests use HA 2026.10.3. Earlier versions have not been tested.

1. In HACS, add `https://github.com/nickwinger/ecoflow_smart_home_panel_v1` as a custom repository of type **Integration**. Download the default branch, then restart the test instance. Alternatively copy only `custom_components/ecoflow_smart_home_panel_v1` into its `custom_components` directory.
2. Under **Settings → Devices & services → Add integration**, choose **EcoFlow Smart Home Panel v1**.
3. Enter credentials and panel serial, select the API region, and confirm that the hardware is first-generation SHP. No YAML, shell job or external helper is required.
4. Setup requires a quota response with ten load-control and two backup-control entries. A partial first response may need a retry. The published device-list API has no model identifier: confirmation plus topology is a conservative compatibility check, not authoritative hardware detection.
5. Open the device's entities, include disabled entities in the list, and enable only the diagnostics you want. Explanations are available in the entity's state attributes and the catalog; HA does not necessarily display them directly under the entity name.
6. Configure the polling interval through **Options**. Use **Reconfigure** to replace keys; HTTP 401/403 starts reauth automatically. Unknown application error codes produce a generic cloud error, because an authoritative code table was not supplied.

No device is controlled by this version. Existing Python jobs, helpers, dashboards and their history remain untouched. See [migration and manual validation](docs/MIGRATION.md). Installation has not been performed on a running user system.

## Recorder history and statistics

An enabled entity publishes states, which Recorder stores unless excluded by the user's Recorder configuration. A disabled entity has no live state or fresh history. Discovery still uses the shared panel poll so new fields can appear in the registry; disabled fields never cause separate requests or archival writes.

Detailed states and five-minute statistics are normally kept for **10 days**, configurable via Recorder. Eligible hourly long-term statistics are not automatically purged. Text, raw numbers without a verified state class, and binary sensors do not gain indefinite numeric statistics. Disabling/removing an entity does not automatically delete previous history. Static descriptions, source paths and evidence metadata are marked unrecorded. [Home Assistant statistics documentation](https://www.home-assistant.io/docs/configuration/long-term-statistics/).

Only the documented panel battery percentage currently receives `MEASUREMENT`. Daily counter scale, reset timing and timezone semantics remain unverified; no `TOTAL`/`TOTAL_INCREASING` is assigned, and these counters are not advertised as Energy Dashboard inputs. Missing fields become `unavailable`; null, invalid percentages and unknown enums become `unknown`. A small `raw_value` attribute preserves invalid/unknown codes where useful. Failed polls make enabled entities unavailable.

## Development and verification

```sh
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements-test.txt
.venv/bin/ruff check custom_components tests scripts
.venv/bin/ruff format --check custom_components tests scripts
.venv/bin/python scripts/sync_catalog.py --check
.venv/bin/python -m compileall -q custom_components
.venv/bin/pytest -q --timeout=30 --cov=custom_components.ecoflow_smart_home_panel_v1 --cov-report=term-missing
```

Latest local result: **221 tests passed, 99% line coverage**. Tests use invented data, mocked HTTP and an in-memory HA Recorder database. `pytest-socket` blocks Internet access. The current sandbox blocks asyncio's internal self-pipe, so local tests run outside that sandbox with the same network-blocking pytest configuration. CI runs Ruff, catalog consistency, compilation, pytest, official hassfest and HACS custom-repository checks. [Official hassfest and the offline CI suite](https://github.com/nickwinger/ecoflow_smart_home_panel_v1/actions/runs/40178236653) passed; [HACS](https://github.com/nickwinger/ecoflow_smart_home_panel_v1/actions/runs/40178236718) passed all 8 active checks. For this custom repository, HACS **brands** and **topics** checks are explicitly deferred to M4/default listing. The topics check previously caused repeated metadata-only failure emails; it is excluded at the owner's request. Technical HACS checks remain enabled. The optional manifest category is deferred because the currently published hassfest container rejects the newer `categories` key; HACS reports this only as a warning.

`scripts/sync_catalog.py` packages the field guide and generates entity translations inside the HACS install directory. All runtime files are self-contained there. Changes to catalog text must regenerate those resources. See [milestones and validation results](docs/MILESTONES.md).

## Sources and privacy

- [Official EcoFlow Smart Home Panel v1 API](https://developer-eu.ecoflow.com/us/document/PP4?id=2058837749501956098).
- [Read-only working Python reference](https://github.com/nickwinger/homeassistant_config/tree/main/ecoflow), particularly signing, indexed channel interpretation and fresh-status behavior.
- All **three supplied HTML documents** were read and incorporated: [General HTTP/signing](docs/reference/ecoflow_general_http.html), [SHP v1 HTTP/properties](docs/reference/ecoflow_smart_home_panel_v1_http.html), and [28 property supplements](docs/reference/ecoflow_shp_v1_property_ergaenzungen.html). The third document is a community-source review, not an official EcoFlow schema.
- [Source/evidence details](docs/REFERENCE_SOURCES.md) identify the original filenames and pinned source revisions. Published reference copies substitute synthetic demo credentials/serials; the three owner-supplied originals remain local and unchanged.

Credentials are stored in HA-managed config entries; serials also participate in HA-managed registry identities, never display names. The integration logs neither request URLs nor payloads. Sensitive quota subtrees are excluded, diagnostics contain only counts/status, and malformed/dynamic inputs are bounded. Treat HA backups/config entry storage as private.

Project code is MIT-licensed; supplied manufacturer documentation retains its original ownership. This project is independent of EcoFlow and Home Assistant.
