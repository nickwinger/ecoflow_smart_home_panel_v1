# Source references and provenance

## Existing functioning system (READ ONLY)

- Repository: https://github.com/nickwinger/homeassistant_config
- API: https://github.com/nickwinger/homeassistant_config/blob/main/ecoflow/ecoflow_api.py
- Cache: https://github.com/nickwinger/homeassistant_config/blob/main/ecoflow/ecoflow_api_cached.py
- Get: https://github.com/nickwinger/homeassistant_config/blob/main/ecoflow/ecoflow_get.py
- Set: https://github.com/nickwinger/homeassistant_config/blob/main/ecoflow/ecoflow_set.py
- Batch: https://github.com/nickwinger/homeassistant_config/blob/main/ecoflow/shp_mode.py
- Helper sync: https://github.com/nickwinger/homeassistant_config/blob/main/ecoflow/ecoflow_sync_to_ha.py
- Reading helpers: https://github.com/nickwinger/homeassistant_config/blob/main/ecoflow/ecoflow_values.py
- Synthetic **reference only** source of shape: `ecoflow/cache.example.json`. Its values may represent a device snapshot and must not be copied verbatim into a public fixture. Any production `cache.json` / `last_good` files must stay private.
- Quota field labels in `docs/quota-field-guide.json` were collected from existing HA diagnostics / SHP v1 documentation on 2026-10-25; provenance notes in JSON. This guide distinguishes facts vs uncertain inferences. It includes local cache metadata that is not part of EcoFlow's raw quota `data`.

## Current upstream conventions

- HACS publishing custom integration: https://www.hacs.dev/docs/publish/integration/
- HACS validation action: https://www.hacs.dev/docs/publish/action/
- HA integration manifest: https://developers.home-assistant.io/docs/creating_integration_manifest/
- HA entity naming/translation: https://contributors.home-assistant.io/core/entities/naming/
- HA entity descriptions and unrecorded attributes: https://contributors.home-assistant.io/core/entities/entity-class/
- HA long-term statistics: https://www.home-assistant.io/docs/configuration/long-term-statistics/

Read current official references before coding; APIs change. Third-party examples are not authoritative.

## Constraints

Do not paste any actual user key, secret, serial, Home Assistant token, proprietary logs, real channel names or live response snapshots into issues, tests, README, CI or public releases. No development-time control commands to an actual SHP v1. Existing production system remains untouched.

## Three supplied HTML references (2026-10-25)

All three documents were read in full. Their original local filenames and public,
sanitized reference copies are:

| Original under `docs/` (unchanged, ignored) | Published reference | Role |
| --- | --- | --- |
| `ecoflow_general_http.html` | [General HTTP API](reference/ecoflow_general_http.html) | HMAC signing, headers, quota endpoints and responses |
| `ecoflow_smart_home_panel_v1_http.html` | [SHP v1 HTTP API](reference/ecoflow_smart_home_panel_v1_http.html) | Command shapes, topology, property definitions and documented enums |
| `ecoflow_shp_v1_property_ergaenzungen.html` | [Property supplements](reference/ecoflow_shp_v1_property_ergaenzungen.html) | 28 property reviews, pinned community sources, conflicting semantics and open questions |

Official manufacturer URL: [EcoFlow Smart Home Panel v1 API](https://developer-eu.ecoflow.com/us/document/PP4?id=2058837749501956098).
The older sanitized text extracts in `reference/ecoflow_general.txt` and
`reference/ecoflow_smart_home_panel_v1.txt` remain available for the initial M1/M2
record. The three linked HTML copies are the current supplied reference set.
Full manufacturer demo credentials and serials in published copies are replaced
with synthetic values and the modified signing vector is recalculated. No owner
credentials, live responses or original files were changed.

The supplement is an owner's research document with community evidence, **not**
a manufacturer guarantee or official HTTP schema. All 28 sections map to catalog
entries via `evidence.review`; `evidence.sources` retains pinned upstream links.
The catalog grows from 81 to 92 patterns. Source confidence and unit confidence
are separate: for example, daily energy is manufacturer-described but its Wh unit
comes from community code. New community units never imply automatic statistics.

Independently inspected primary code at the supplement's pinned revisions:

- `tolwi/hassio-ecoflow-cloud`, revision `de02d680cdfe1adcec60c43047ff3ed3da15e0ee`, SHP implementation blob `d2ff5ba84ca3243eb94f059c52ac895102b94fd1`.
- `rustyy/ecoflow-api`, revision `f9804e04c8712670f28feb2a5317f26c460ba62a`, HTTP property schema blob `80821d14520809f76b599a86ecd1de263c358a6d`.

These confirm source-level mappings and data shapes, not the return values of any
specific firmware. The supplement also pins MichelFR and foxthefox examples and
links the manufacturer app manual. Their interpretation is attributed to the
supplement rather than presented as a hardware test. No third-party storage,
optimistic controls, zero-on-error conversions or calculated power totals were copied.

Remaining conflicts: backup `ctrlSta=2` is off in the manufacturer table but
charging in the working helper; remaining-time sentinels, capacity scales, daily
resets/timezone and physical storage direction remain unresolved. The device list
provides no authoritative model field and no application error-code table was supplied.

Reference documents retain their original authors' ownership; the project MIT
license does not relicense them. Synthetic test fixtures were authored independently.
The read-only working reference repository was never modified or checked out locally.

Reference source blobs inspected: API `81c75b35a0c8c8b00502cd70989acd813f623745`,
cache `bf2b9ff9dbf90842b5fe4bf1ccd5808137ced001`, channel/charge writes
`877c653b71250136536f22044f2a2c1dcb4a31ce`, batch behavior
`5b409c05f51ae15c3fe5f8c32826bf877894eadb`, values
`b037d9c459e0ffe4c0eccc053a523f21d9b9227f`. No blocking reference HTTP or disk-cache
implementation was copied into HA.

## M3 control evidence

The API, setter, batch, cache and value helpers above were read again for M3.
The configuration file's timing assignments alone were inspected without
printing or copying credentials: blob `3d1136e59a7cc0c68faab66178f2daf44be128f3`,
`SETTLE_AFTER_SET_SECONDS = 2`. Source verification follows shp_mode's 10-second
settle / 15-second retry / eight attempts; charging preserves the setter's
2-second settle and adds fresh verification. No reference files were changed.

Current official HA conventions were checked against [select entities](https://contributors.home-assistant.io/core/entities/select/),
[switch entities](https://contributors.home-assistant.io/core/entities/switch/) and
[integration actions](https://contributors.home-assistant.io/core/integrations/actions/),
plus the installed HA 2026.10.3 coordinator, registry and service implementation.

## Live power and mode follow-up (0.3.0)

The supplied [General HTTP API](reference/ecoflow_general_http.html) documents
millisecond `timestamp`/nonce/HMAC headers, POST GetCmdRequest, GET
`/iot-open/sign/certification`, broker credentials and the public
`/open/{account}/{sn}/quota` subscription. The supplied SHP document labels its
specific-quota read as GET instead; the read-only POST probe was accepted.
Reading `heartbeat.time` did not restore power freshness. Cache-control and a
correctly signed extra timestamp query also had no observed effect.

Pinned primary implementation sources inspected for this follow-up:

- [MichelFR SHP implementation](https://github.com/MichelFR/ha-ecoflow-iot/blob/0805a1ea8d4ead69c698172eea78eecac51fdda3/custom_components/ecoflow_iot/devices/whole_home_backup/smart_home_panel.py): public push power uses bare `infoList`, whereas HTTP uses `channelPower.infoList`.
- [tolwi SHP implementation](https://github.com/tolwi/hassio-ecoflow-cloud/blob/de02d680cdfe1adcec60c43047ff3ed3da15e0ee/custom_components/ecoflow_cloud/devices/public/smart_home_panel.py): automatic mode uses `ctrlMode=0, sta=0`; manual holds the current source.
- [foxthefox SHP implementation](https://github.com/foxthefox/ioBroker.ecoflow-mqtt/blob/9df54323e17a90e5c553ba5f10771667bd9ac4fb/lib/dict_data/ef_panel_data.js): distinguishes app commands and SHP data shapes. Guessed heartbeat commands in community code were not adopted.

The owner's read-only reference at `3fa58b227ea5bd9e1a605ebb7177ab002a2a6e10`
was searched across EcoFlow modules and related HA configuration; its current
code has no active MQTT/heartbeat keepalive. No reference files were modified.

An explicitly authorized read-only DEV probe found power reports and HTTP values
both changing with just a passive public MQTT subscription; no MQTT PUBLISH was
needed. This installation-specific evidence underlies the connection added in
0.3.0, not a claim that a documented heartbeat property forces hardware updates.
See [probe results and limitations](LIVE_DATA.md). Installed Paho 2.1 and HA
2026.10.3 code informed thread lifecycle, TLS and entity lifecycle handling;
offline mocks verify no publish, writes on startup or retained-frame freshness.
