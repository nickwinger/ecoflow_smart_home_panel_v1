# Quota property catalog, friendly names and descriptions

Source of initial evidence: `docs/quota-field-guide.json`, seeded from the existing EcoFlow SHP v1 `ha_diag__get_ecoflow_field_guide` documentation. It describes **81 path patterns** (including a couple of local-cache-only fields) with German-friendly name, meaning, type, unit, enum, comments and confidence. It is **NOT** an exhaustive list of every scalar leaf; the integration must also register previously unknown fields safely.

## Non-negotiable UI contract

For every represented quota property, provide:
- Stable technical source path (example: `data.heartbeat.loadCmdChCtrlInfos[6].ctrlSta`) and stable entity unique ID.
- Friendly name that says what it means, rather than simply showing `heartbeat.loadCmdChCtrlInfos...`. Include channel/battery number and, if useful, user-defined channel name.
- Short explanation / description in German and English when evidenced: e.g. 'Current power source of load circuit 7; 0=grid, 1=battery; other values unknown.'
- State representation, units/scale, mapping of enums and confidence (`documented`, `inferred`, `unknown`), wherever appropriate.
- Entity classification: default enabled vs default disabled, measurement vs diagnostic; expose all raw scalar leaves for opt-in.

For Home Assistant: use the *actual* `SensorEntityDescription`/`EntityDescription` supported fields plus `has_entity_name` and translations. **EntityDescription does not have a generic 'description' field**: place explanations in a discoverable safe place such as an entity attribute `description` or `quota_description` (mark static metadata unrecorded when appropriate), and in human-oriented documentation/catalog. Do not assume a long description magically appears beneath an HA entity name in every UI.

## Suggested default-enabled high-value fields

- `heartbeat.gridSta` — grid availability, if observed and valid.
- `heartbeat.backupBatPer` — backup battery percent *only if value is 0..100, otherwise unknown and raw diagnostic (no guessed scaling)*.
- `channelPower.infoList[].chWatt` — circuit power watts; explicitly verify unit/scale and bounds before marking as measured W.
- `heartbeat.loadCmdChCtrlInfos[].ctrlSta` — per-channel grid vs battery if code is known (0/1).
- `heartbeat.energyInfos[].batteryPercentage` — battery/device percentage with validity checks.
- `heartbeat.energyInfos[].outputPower` — raw/output watts only if evidenced.
- `gridInfo.gridVol` and `gridInfo.gridFreq` — nominal voltage and frequency when available and validated.
- `heartbeat.gridDayWatth` and `heartbeat.backupDayWatth` — daily energy readings, with special attention to reset semantics. Do not falsely integrate them as cumulative lifetime counters.

These are suggestions: use observed data and documentation to make the final choice. Do not enable hundreds of diagnostics just because they exist.

## Default-disabled diagnostic examples

Internal `cmdSet`/`id` markers, `RTC` fields, debug/self-test/raw error arrays, raw `powType` codes, undocumented numeric scales, region/serial metadata, raw channel configuration, scheduler internals, unknown fields and constant values. They must remain individually enableable where safe (sensitive credentials are never entities). Avoid long-term statistics on unverified raw numbers.

## Naming examples

| Raw quota property | de friendly name | Explanation |
| --- | --- | --- |
| `heartbeat.gridSta` | Netzverfügbarkeit | Whether mains supply is available (0 no, 1 yes) |
| `heartbeat.loadCmdChCtrlInfos[6].ctrlSta` | Stromkreis 7 – Versorgungsquelle | Where circuit 7 currently receives power (known grid/battery enum) |
| `channelPower.infoList[6].chWatt` | Stromkreis 7 – Leistung | Raw instantaneous channel power, measured in watts if verified |
| `heartbeat.energyInfos[0].batteryPercentage` | Speicher 1 – Batteriestand | Battery percent if reading is within range |
| `selfCheck.result` | Selbsttest – Ergebniscode | Raw self-test code; enum undocumented |
| `channelPower.infoList[6].powType` | Stromkreis 7 – Leistungstyp (Rohwert) | Meaning unknown; do not label code as 'grid'/'battery' |

Use the catalog's array wildcard `[]` to match numbered array indices. Also support literal EcoFlow dotted keys. Retain exact raw value when scale unknown; no multiplication/division without evidence.

## Testable completeness

For a synthetic representative GET quota/all response:
1. Recursively enumerate scalar leaves under `data` while retaining original access paths, including literal dotted keys and list indices.
2. Build the set of discoverable entity source paths after validation.
3. Assert the two sets match exactly (except documented security exclusions), including unknown fields. Verify disabled flags for diagnostics.
4. Assert that a missing field becomes unavailable (never a stale 'healthy' value), and that unknown code/state yields unknown.
5. Assert meaningful labels + explanations for all 81 seed patterns, including wildcard paths, and that unsupported enums/units are not silently invented.
6. Assert no file/database writes of raw quota and no history for disabled entities.

No need for a separate feature that archives all JSON values; that would violate the intentionally storage-efficient design.
