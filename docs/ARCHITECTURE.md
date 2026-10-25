# Architecture and data behavior

## Hardware and API scope

This integration supports the **first-generation EcoFlow Smart Home Panel (v1)** using the currently working signed EcoFlow Open API. It does not generalize the endpoints or control format to Smart Home Panel 2/3 or unrelated EcoFlow devices.

Source endpoint behavior (read-only reference code):

- GET `/iot-open/sign/device/quota/all` using params `{"sn": <panel serial>}`.
- PUT `/iot-open/sign/device/quota` with body `{"sn": <panel serial>, "params": {...}}`.
- Header signing: timestamp (ms), nonce, accessKey, HMAC-SHA256 over sorted flattened request params + accessKey/nonce/timestamp. Refer to `ecoflow/ecoflow_api.py` rather than guessing signing semantics.
- Response success is identified by `code == "0"` (string); nonzero or malformed is error.
- EcoFlow responses can intermittently omit `heartbeat.loadCmdChCtrlInfos` or other fields. The existing code deliberately distinguishes current incomplete responses from last good debugging cache. Do not interpret missing channel status as an actual switch transition.
- This is a cloud API; no local IP/protocol is assumed.

## Native HA architecture

```text
EcoFlow Cloud GET quota/all ──► async EcoFlow client (per config entry)
                                        │
                                  DataUpdateCoordinator
                                        │
                       raw quota object for current poll
                                        │
                flatten scalar leaves (dotted + nested/list)
                                        │
                    metadata & wildcard field catalog
                                        │
              native sensors / binary_sensors / selects / switches
                                        │
                           HA State Machine / Recorder
                           (enabled entities only)
```

The integration does not need an external job, helper updates or a second storage engine. A single quota/all poll can populate every enabled entity. Don't produce one HTTP request per sensor. Cache is in-memory for coordination/confirmation; avoid saving full JSON snapshots to disk. No full quota history archive.

Default coordinator interval: 5 seconds, configurable from 5 to 900 seconds. Explicitly saved intervals are preserved; entries without an override use the default. API errors should mark affected entities unavailable and use sensible retry/backoff. All I/O must be async or executor-wrapped: never block the HA event loop.

## Representation and ID rules

- A quota payload can contain literal dotted keys such as `"heartbeat.gridSta"`, nested dictionaries, and nested arrays. Flatten recursively but distinguish dots in original keys from actual nesting when extracting values.
- Each scalar leaf found under `data` should be discoverable as a registrable entity, including raw unknowns. Use named catalog patterns with `[]` wildcard for list indices; derive per-instance concrete paths like `channelPower.infoList[6].chWatt`.
- Preserve both the **exact source access path** (for lookup) and a human-readable display path (for catalog/diagnostics) to avoid collisions when a dotted literal key and equivalent nested map are simultaneously present. Define an unambiguous serialization for unique IDs.
- Avoid entity storms from attacker-controlled or evolving dynamic keys: validate types, depth, total entity count, array sizes, unexpected dynamic strings and sensitive response metadata. Default unknowns off.
- Correlate indices with channels only when supported. SHP v1 currently presents ten load channels and two backup channels. Do not claim confirmed mapping for backup channels where only inferred.
- Per-entry device registry identity is stable; names are allowed to change without changing unique IDs.
- Make all fields opt-in capable even if they are never observed at installation; new ones can be registered after future polls, safely/boundedly.
- Metadata includes localized friendly name, short meaning/description, raw path, confidence, unit/device class where verified, enum mappings and category/default enablement. Do not re-store large quota dictionaries or sample payloads in attributes.

## Historic data and space constraints

**Only HA Recorder is allowed.**

- Selected sensor/status entities and the explicitly requested circuit/storage diagnostics are enabled by default; remaining diagnostic and unknown raw entities are registered but start disabled through `entity_registry_enabled_default=False` or equivalent platform description settings.
- Disabled entities do not emit states and must not generate history. No hidden archival of disabled values.
- Numeric sensor history can produce long-term statistics if it has an accurate numeric state, suitable `state_class`, consistent units and is recorded by HA Recorder.
- Text/boolean diagnostic states have HA Recorder state history when enabled but no automatic indefinite long-term numeric statistics.
- Home Assistant typically keeps detailed history for 10 days by default; its hourly long-term numeric statistics are retained indefinitely unless manually deleted or database maintenance intervenes. Read HA docs for exact current behavior.
- Disabling entities later **does not automatically delete pre-existing history**.
- Persistent diagnostic explanations may be exposed as static state attributes but mark them as unrecorded when supported; avoid adding raw JSON and high-cardinality metadata to every recorded change.
- If a user eventually wants raw indefinite per-second histories even for nonnumeric properties, that is a **separate opt-in future scope** requiring explicit storage requirements; do not build it now.

## Control path (separate from read-only polling)

Existing tested load-channel target:
```json
{"cmdSet":11,"id":16,"ch":0,"ctrlMode":1,"sta":1}
```
This example means channel 1 (zero-based `ch=0`) target battery `1`; grid target is `0`. Preserve exact values from reference source. Do not mix observed `ctrlSta` with desired settings without proof.

Existing charge path (first backup channel when `index=1`):
```json
{"cmdSet":11,"id":17,"ch":10,"ctrlMode":1,"sta":2}
```
For off, `ctrlMode=0`, `sta=0`. The `ch` offset follows the existing script and must be regression-tested. Treat grid/battery and charging commands as distinct.

Batch source switching reference order: `[7,6,3,1,2,4,5,8,9,10]`, with verification and delays. Serial commands must have explicit user initiation; never execute during restore, startup, polling, install, or CI. Failed verification is a failure/unknown, not success.

## Safety/provenance

No invented unit conversion or enum labels. The field guide distinguishes `documented`, `community`, `inferred`, `unknown`, `local_implementation`. Some example values conflict with nominal scales; reflect this uncertainty in names/descriptions, not guessed computed values.

## Implemented M1/M2 decisions

Runtime modules: `api.py` (GET only, pure signing helper), `config_flow.py`,
`coordinator.py`, `quota.py`, `catalog.py`, `entity.py`, `sensor.py`,
`binary_sensor.py`, `diagnostics.py`. The catalog is installed with the component;
it never reads repository docs at runtime. Resource loading uses HA's executor.
The HA-managed HTTP session is shared; the client serializes requests and does
not follow redirects. HTTP 429 applies a 30–3600 second cooldown; other failures
back off up to 900 seconds. A success resets the normal interval.

Each source path is a tuple of literal string keys and integer array indices.
Unique IDs are `<configured-serial>:quota:<compact JSON token list>`.
`["heartbeat.gridSta"]` and `["heartbeat","gridSta"]` remain distinct.
Changing payload key order, device title or channel label preserves identity;
changing actual source structure intentionally creates another identity.
HA entity-registry identities are the only persistent discovery inventory. This
retains absent entities across reloads without storing prior quota values.

Two platform discovery listeners keep one shared poll running even if all
entities are disabled. Disabled entities are registered but never added to the
HA state machine or subscribed as entity listeners. Missing leaves are unavailable;
invalid scalar values are unknown. Whole-request failures invalidate availability
of all enabled entities, even though the coordinator may still hold its previous
in-memory snapshot internally.

Limits: 1 MiB decoded HTTP body; depth 16; array length 128; 20,000 visited nodes;
4,096 object members/scalar leaves and lifetime registry identities; key length
128; serialized path length 512; scalar text length 255. Structural limit breaches
reject the snapshot. Invalid/nonfinite/oversized scalar values retain their path
with an unknown value. Empty containers have no scalar leaf. Credential/serial
subtrees, local cache markers, unsafe key syntax and known configured secrets in
keys/values are excluded. Registry churn beyond 4,096 identities is refused and
reported by aggregate diagnostics, including across reloads. No pruning silently
recycles identities. These limits intentionally bound exotic future layouts.

Manufacturer evidence and the three supplied HTML references are distinguished
in catalog metadata. Supplementary community evidence supports explicit W, °C,
%, A and daily Wh units without scaling or automatic statistics. Daily reset,
timezone, capacity scale and remaining-time sentinels remain unresolved; no
TOTAL_INCREASING or Energy Dashboard claim is made. Only documented, valid panel
battery percentage has MEASUREMENT. Nominal settings are not live measurements.
`unit_confidence` and the supplementary evidence reference are unrecorded static
attributes; community units never silently become manufacturer guarantees.

Channel names may be strings or zero-padded UTF-8 bytes. Reconstruction uses only
the current safe scalar snapshot, requires one unambiguous contiguous byte array,
and never mutates raw values or identities. Invalid bytes/gaps produce no label.
Each byte remains an independently selectable diagnostic, with no new archive.
A valid channel name replaces the generic circuit prefix. Only unnamed circuits
use localized Stromkreis/Circuit numbering; both labels are never concatenated.

Config-entry minor version 2 performs a one-time registry migration for the six
newly enabled diagnostic patterns. It enables only INTEGRATION-disabled sensor
entries of the configured panel, within ten circuit/two storage index bounds.
Explicit user/device choices and existing IDs/names are preserved. Diagnostics
category and default enablement are independent; no statistics are added.

M3 correction from the working source: channel grid writes require BOTH
`ctrlMode=0` and `sta=0`; battery requires BOTH to be 1. No such writes are
implemented in M1/M2. Backup `ctrlSta=2` has conflicting documented/runtime
meaning, so no binary charge state is inferred from it.
