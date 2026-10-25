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

Default coordinator interval: 5 seconds, configurable from 1 to 600 seconds. Valid saved intervals are preserved; old out-of-range settings are clamped to 1–600. Entries without an override use the default. API errors should mark affected entities unavailable and use sensible retry/backoff. All I/O must be async or executor-wrapped: never block the HA event loop.

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

Runtime modules: `api.py` (shared GET/PUT transport, pure signing helper), `config_flow.py`,
`coordinator.py`, `quota.py`, `catalog.py`, `entity.py`, `sensor.py`,
`binary_sensor.py`, `diagnostics.py`. M3 adds `controls.py`, `control_entity.py`,
`select.py`, `switch.py`, `button.py`, `telemetry.py`, `services.py` and `services.yaml`. The catalog is installed with the component;
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
Names always use localized Stromkreis/Circuit numbering. Cloud labels are diagnostic metadata only, because the owner observed mismatches with the app.

Config-entry minor version 2 performs a one-time registry migration for the six
newly enabled diagnostic patterns. It enables only INTEGRATION-disabled sensor
entries of the configured panel, within ten circuit/two storage index bounds.
Explicit user/device choices and existing IDs/names are preserved. Diagnostics
category and default enablement are independent; no statistics are added.

M3 correction from the working source: channel grid writes require BOTH
`ctrlMode=0` and `sta=0`; battery requires BOTH to be 1. No such writes are
implemented in M1/M2. Backup `ctrlSta=2` has conflicting documented/runtime
meaning, so no binary charge state is inferred from it.

## Implemented M3 decisions (0.2.0, batch corrected in 0.3.1)

Three options, all false by default, independently gate source, charge and batch
controls. Entry schema remains 1.2; no migration enables controls. Fixed control
IDs are `<serial>:control:source:<zero-based-index>` and
`<serial>:control:charge:<zero-based-index>`, independent of quota raw-path IDs.
The existing 245-leaf fixture and 44 enabled defaults are unchanged.

The current Snapshot also contains bounded derived control states (ten sources,
two charging modes) from the same GET. They are calculated before the lifetime
entity-registry cap and never stored separately. Complete actual arrays and
unambiguous dotted/nested structures are required; fabricated bracketed keys or
partial lists do not confirm individual source/mode/charge commands. Batch confirmation uses the separate reference-compatible decoder described below. No older states are merged.

A per-panel command lock spans preflight GET, PUT, settle, fresh GET verification,
retries and intentional batch operations. HTTP requests share the existing client
lock/cooldown. Control refreshes bypass coordinator debouncing; regular polling
can continue, but cannot substitute for the fresh confirmation request.
Unloading cancels active and queued tasks, with no restoring or rollback writes.

Source control uses the verified shp_mode loop (10 s settle, 15 s retry, eight
attempts); charging retains the single-command reference's 2 s settle and adds
bounded verification. HTTP/API failures end the current channel’s attempt. A batch catches that failure and continues with the next channel after its normal pause. All
circuits run through separately gated explicit buttons or a confirmed action, preserving order
7,6,3,1,2,4,5,8,9,10. As in the script, a channel failure is collected, followed by a 10-second pause and the next channel. Failure is reported only after processing all ten.

Backup charging controls use the reference code’s 2=on / 0,1=off
interpretation; other codes remain unknown. This separate opt-in
does not resolve the manufacturer's contradictory generic enum or change raw
sensor metadata. It describes charge mode, not measured charging power.
Progress is bounded in memory and exposed as unrecorded control attributes plus
aggregate diagnostics. See [CONTROLS.md](CONTROLS.md) for exact commands, limitations
and manual acceptance; no real commands were sent during development.

## Polling and value-change timestamps

The integration asks for quota every configured interval (default 5 seconds),
subject to request duration, scheduling and error/rate-limit backoff. Every
successful response is reported to enabled entities, including identical values.
This does not force EcoFlow to publish a newer physical measurement. No documented
per-field cloud publication cadence or supported forced refresh is established.

HA separates `last_reported` (a state was reported), `last_updated` (value or
attributes changed), and `last_changed` (the value changed). A flat power curve and
an increasing “seconds ago” label can therefore coexist with successful
five-second polling. A power reading is never altered just to move that label,
and `force_update` is not used to create duplicate Recorder history. This follows
[Home Assistant's state reporting semantics](https://contributors.home-assistant.io/blog/2024/03/20/state_reported_timestamp/).

The integration diagnostics download contains `poll_interval_seconds`,
`effective_poll_interval_seconds` (including backoff), `polling_disabled`,
`consecutive_poll_failures`, `successful_quota_refreshes`,
`last_successful_quota_refresh` (UTC) and `last_update_success`. Counts reset on
entry reload; only the last successful timestamp and count are held in memory.
An unsuccessful fetch does not advance either value. Partial successful responses
still count as a fetch; missing individual readings remain unavailable.
These diagnostics are not new entities or attributes on each power reading,
and do not add Recorder rows or any raw archive.

For a particular enabled sensor, inspect `last_reported` directly in HA's
Developer Tools → Template, replacing the example entity ID:

```jinja
{{ states['sensor.your_channel_power'].last_reported }}
```

This reads HA's live state object. The normal frontend/serialized state display
need not redraw for identical reports. A recent quota refresh or state report
proves retrieval/reporting, not the physical measurement's age inside EcoFlow.

## Configuration without a v1 confirmation checkbox (0.2.1)

The integration is explicitly for SHP v1, so setup now asks only for credentials,
serial and API region. It still validates the supported ten-load/two-backup quota
layout and rejects incomplete/unsupported topology. The cloud API does not supply
an authoritative model identifier. Existing entries' legacy `confirm_v1` field
is ignored, including during reauth/reconfigure; no ID or control-option migration
is required. No controls are enabled by removing the checkbox.

## Live power connection and controls (0.3.0)

A shared-client GET to `/iot-open/sign/certification` supplies in-memory MQTT
credentials. A stable client ID and verified TLS connect to the allowlisted
EcoFlow public broker on 8883; one `/open/{account}/{sn}/quota` subscription stays
open with a 30-second MQTT protocol keepalive. No MQTT PUBLISH is implemented.
Paho connection/TLS/thread teardown run outside HA’s event loop; callbacks hand
off bounded receipt information to the loop. Disconnects retry after 30 seconds,
HTTP 429 keeps its longer shared cooldown, auth failures request reauth. A silent
connection is checked every 60 seconds and reconnected if no recent power frame
arrived. Entry unload cancels the worker and stops the network thread.

Only the count and monotonic receipt time of non-retained SHP power frames are
kept. No MQTT readings or extra entities are stored. HTTP `get_quota_all` remains
the source of every entity value and fresh command verification. A current
10/12-entry `infoList` power frame establishes stream activity; absent/disconnected
or older-than-30-second activity makes `channelPower.infoList` leaves unavailable
on the next configured poll. HTTP identities stay registered, and missing HTTP
fields remain missing. MQTT cannot confirm source/mode/charge writes.

Diagnostics add `power_telemetry_connected`, `power_telemetry_reports`,
`power_telemetry_age_seconds`, `power_telemetry_error`, and `batch_controls_enabled`.
These are aggregate connection information, not a guaranteed physical sample age.
See [LIVE_DATA.md](LIVE_DATA.md) for the controlled HTTP/heartbeat/cache/MQTT probes.

Ten mode selects share the source-control option and serialized command lock.
Automatic uses the proven `ctrlMode=0, sta=0` command; manual uses `ctrlMode=1`
with a strictly valid source from the fresh preflight response (including off).
Only the fresh `ctrlMode` confirms success. Three batch buttons use the existing
sequence/controller, with cancellation available even when telemetry fails.
There are no setup/reload/restore actuator writes. Normal interval is 1–600 s,
default 5; failure backoff and EcoFlow rate limits may extend the effective delay.


## Reference-compatible batch execution (0.3.1)

The owner explicitly requested the complete working `shp_mode.py` behavior,
replacing the earlier stop-on-first-error policy. Both grid and battery process
7,6,3,1,2,4,5,8,9,10. Every channel gets a fresh preflight read; if necessary the
exact reference PUT is followed by 10 s settle and fresh verification. A mismatch
or unknown channel gets 15 s retry delay, including after attempt eight. Every
processed channel then gets its 10 s pause, whether successful, already at target,
or failed. No extra retries, parallel channel writes or rollback are added.

`read_batch_sources` supplies ten bounded derived states to the current Snapshot.
It matches the reference: dotted list preferred over nested, positional dict
preferred over a `ch` fallback, `ctrlSta` preferred over `sta`, and Python `int()`
conversion (including the original coercion of strings, floats and booleans).
Only resulting 0/1 confirm grid/battery; missing/invalid values stay unknown.
An incomplete unrelated channel does not invalidate a known channel. This is
scoped to batch verification; stricter individual controls and raw quota sensor
semantics are unchanged. No previous response can confirm a command.

Per-channel exceptions are recorded as circuit numbers in `control_operation.failed`;
confirmed circuits remain in `completed`. The same transaction lock stays held
through every failure and pause. The final localized error lists failed circuits.
No error text, payload or credentials enter progress or history. Cancellation,
unload or removing control permission still stops future commands. Shared HTTP
validation, request timeouts, response-size bounds and rate-limit cooldown remain
transport constraints; a rejected/unavailable cloud cannot guarantee a switch.

Offline differential tests run the actual pinned reference functions with fake
GET/PUT/sleep against the same synthetic scenarios as the async controller.
Complete call traces and per-channel results must match. The test-only reference
copy has a verified Git blob hash; none of its imports or real I/O is executed.
