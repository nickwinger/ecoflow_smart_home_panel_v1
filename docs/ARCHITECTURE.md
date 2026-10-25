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

Recommended initial coordinator interval: 60 seconds, optionally configurable with safe bounds (prevent API hammering). API errors should mark affected entities unavailable and use sensible retry/backoff. All I/O must be async or executor-wrapped: never block the HA event loop.

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

- Selected sensor/status entities are enabled by default; diagnostic and unknown raw entities are registered but start disabled through `entity_registry_enabled_default=False` or equivalent platform description settings.
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

No invented unit conversion or enum labels. The field guide distinguishes `documented`, `inferred`, `unknown`, `local_implementation`. Some example values conflict with nominal scales; reflect this uncertainty in names/descriptions, not guessed computed values.
