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

## Supplied manufacturer copies (2026-10-25)

- [Official SHP v1 API](https://developer-eu.ecoflow.com/us/document/PP4?id=2058837749501956098), supplied locally as `docs/reference/ecoflow_smart_home_panel_v1.txt`.
- General signing/API reference supplied as `docs/reference/ecoflow_general.txt`.
- The copies define topology, basic status enums and configuration fields, but do not establish all units in the seed. Backup `ctrlSta=2` conflicts with the working charging helper. The device list has no authoritative model field; no HTTP application error-code table is supplied.


The original `.htm` browser exports remain local and unchanged. Versioned text
under `docs/reference/` removes scripts/styles, replaces full manufacturer demo
identifiers with synthetic values and recalculates the modified signing example.
These are vendor reference documents, not production telemetry or MIT-licensed
project code. Synthetic fixtures were authored independently, not copied from the
reference cache. The reference repository was read only and was never checked out
or changed locally.

Reference source blobs inspected: API `81c75b35a0c8c8b00502cd70989acd813f623745`,
cache `bf2b9ff9dbf90842b5fe4bf1ccd5808137ced001`, channel/charge writes
`877c653b71250136536f22044f2a2c1dcb4a31ce`, batch behavior
`5b409c05f51ae15c3fe5f8c32826bf877894eadb`, values
`b037d9c459e0ffe4c0eccc053a523f21d9b9227f`. No blocking reference HTTP or disk-cache
implementation was copied into HA.
