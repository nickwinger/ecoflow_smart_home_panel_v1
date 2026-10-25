# Quota property catalog, friendly names and descriptions

Source of initial evidence: `docs/quota-field-guide.json`, seeded from the existing EcoFlow SHP v1 `ha_diag__get_ecoflow_field_guide` documentation. The initial seed describes **81 path patterns**; the current catalog contains **92 patterns** after incorporating all three supplied HTML references. Each has German/English names, meaning, type, unit, enums, notes and confidence. Two patterns describe excluded local-cache fields. It is **NOT** an exhaustive list of every scalar leaf; the integration must also register previously unknown fields safely.

## Non-negotiable UI contract

For every represented quota property, provide:
- Stable technical source path (example: `data.heartbeat.loadCmdChCtrlInfos[6].ctrlSta`) and stable entity unique ID.
- Friendly name that says what it means, rather than simply showing `heartbeat.loadCmdChCtrlInfos...`. For circuits, use the valid user-defined channel name alone; otherwise use the localized circuit number. Do not concatenate both labels.
- Short explanation / description in German and English when evidenced: e.g. 'Current power source of load circuit 7; 0=grid, 1=battery; other values unknown.'
- State representation, units/scale, mapping of enums and confidence (`documented`, `community`, `inferred`, `unknown`), wherever appropriate.
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

## M2 implementation and tested defaults

The fixture represents 245 safe scalar leaves as 245 registered entities, with
44 enabled by default: the original 16 essential fields, ten circuit power
readings, ten circuit control modes, and four readings for each of two storage
entries (battery percentage, input power, output power, temperature). The added
28 remain in the diagnostic category even though they are enabled. The other
201 start disabled. Two synthetic input-power fields were added to exercise the
complete requested set; real cloud response totals vary. Extra circuit/storage
indices remain opt-in, including backup power entries 10/11.

The metadata file retains all 81 seed patterns and adds 11 patterns (92 total), including two local-cache fields
and container patterns. Containers are not JSON-dump entities: scalar descendants
receive the nearest container explanation with an explicit subentry note. Unknown
child semantics remain unknown. Local-cache fields are excluded from discovery.
The `catalog.json` shipped inside the integration and de/en entity translations
are generated by `scripts/sync_catalog.py`; `--check` detects drift.

The [28 property supplements](reference/ecoflow_shp_v1_property_ergaenzungen.html)
provide attributed community units for channel power (W), storage input/output
power (W), storage percentage (%), temperature (°C), configured current (A), and
daily grid/backup energy (Wh). These are applied without scaling and without
statistics. Circuit power and the four selected storage readings now start enabled; configured-current diagnostics remain disabled.
`heartbeat.workTime` uses the manufacturer's min unit without statistics or a
claim about its reset point. Remaining-time fields stay raw: community minute
interpretations do not establish valid sentinels, and values above 5000 are never
replaced by a fabricated zero. Capacity fields stay raw with no Wh/kWh conversion.

Energy matrices now have explicit `watth[][]` descriptions: community interprets
the first index as circuit/storage and the second as hour 0–23. Timezone, interval
reference and scale still need validation, so there are no sums or statistics.
Community `powType` (0 grid / 1 battery) and storage 0/1 flag meanings are described,
but these existing sensor entities retain raw codes and stable platform identity.
Unknown codes are never used as proof of a physical state or successful write.

Daily counters remain ineligible for the Energy Dashboard: no TOTAL or
TOTAL_INCREASING is assigned without established reset semantics.
`gridInfo.gridVol` and `gridInfo.gridFreq` are configured nominal values, not live
measurements. Only valid `heartbeat.backupBatPer` has MEASUREMENT; its invalid
raw percentage remains inspectable while its state is unknown.

Load `ctrlSta` codes 0/1/2 are rendered as grid/battery/off, following the supplied
manufacturer table. Backup `ctrlSta` remains a raw code because the table's
2=off contradicts the existing helper's 2=charging. M3 retains that raw sensor and offers separately opted-in charging-mode switches
explicitly following the working helper (2 on, 0/1 off, other codes unknown).
This is not a resolution of the generic vendor enum and does not prove actual
charging power; see [control semantics](CONTROLS.md).

Attributes: `description`, `quota_path` (readable), `quota_access_path` (exact
string/integer token list), `confidence`, seed `documented_unit` and localized
`documented_enum`, plus `unit_confidence` and `evidence_reference` where available. The historical attribute name `documented_unit` refers to the catalog unit; consult its confidence before treating it as a manufacturer fact. Static metadata and the optional `channel_label` are excluded
from Recorder. `raw_value`, when required for an invalid or translated value,
is a bounded scalar and may be recorded for an enabled entity. Unknown raw
booleans remain scalar sensors to preserve platform identity if their type changes;
only documented binary paths use binary_sensor.

User labels from `loadChInfo.info` support strings and contiguous, zero-padded UTF-8 byte arrays. Invalid UTF-8, non-byte values, gaps and ambiguous source structures do not produce a label. Each source byte remains a discoverable disabled scalar. Labels are sanitized, capped at 48 characters and
used as the circuit prefix by themselves. If no valid name exists, use `Stromkreis 1` (German) or `Circuit 1` (English), with no second label in parentheses. The original safe label is also available in `channel_label`. Index 0..9 is circuit 1..10. Storage/backup numbers
are array-entry numbers, not a verified physical-device association. Potential
backup power entries 10/11 are labelled as entries 11/12 without asserting mapping.

Config-entry schema 1.2 upgrades the six selected diagnostic field families once.
Only registry entries disabled by INTEGRATION are enabled; USER, DEVICE and other
explicit disable reasons remain untouched. Categories do not imply disabled status.
No unit, enum, statistics eligibility or API polling behavior changes with these defaults.

M3 adds up to ten source selects and two charge-mode switches only after their
respective option is enabled. These are separate from the 245 quota leaves. Their
names follow the same channel-label rules; descriptions explain confirmation and
the charging-code conflict. `description`, `quota_path` and `control_operation`
are excluded from Recorder attributes. No new statistics or raw history store.
