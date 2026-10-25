# Live circuit power with the EcoFlow app closed (0.3.0)

The owner reproduced a real freshness problem: circuit power changed while the
phone app was open, then froze after closing it. Home Assistant continued making
successful HTTP requests every five seconds. A recent HTTP response therefore
did not prove that EcoFlow had received a new measurement.

## What was checked

Read-only probes on 2026-10-25 used the existing credentials in the dedicated
DEV instance. Only counts, timing and connection status were reported. No live
payload, readings, serials or credentials were saved; no switching, charging,
RTC-setting or other actuator command was sent.

| Probe | Observation |
| --- | --- |
| HTTP polling, app closed | 7–8 successful reads per 36-second window, no circuit-power changes |
| HTTP polling, owner opened app | 7 reads and 6 power changes in 36 seconds |
| After closing the app again | 8 reads, no changes; the unchanged value was already 175 seconds old |
| Read `heartbeat.time` after every quota/all request | All 10 POST read requests accepted; no power changes |
| `Cache-Control: no-cache` | 6 accepted reads; no changes |
| Added, correctly signed `?ts=…` | 6 accepted reads; no changes |
| Passive public MQTT subscription, no PUBLISH | 8 MQTT power reports with 7 changes, and 8 HTTP reads with 7 changes, over 40 seconds |

The first HTTP observations alone could not distinguish a steady load from a
frozen cloud value. The owner's repeated app-open/app-closed observations and
the subsequent passive-connection comparison motivated the implemented fix.
These are observations on this installation, not a guaranteed EcoFlow protocol
contract for every firmware or region.

## Timestamp, heartbeat and MQTT keepalive

Every request already includes `accessKey`, a six-digit `nonce`, a UTC Unix
`timestamp` in **milliseconds**, and HMAC `sign`. The timestamp participates in
the signature and is generated for each request. It is not a device measurement
timestamp. The no-cache and signed-query probes did not restore fresh values,
so no extra `ts` query parameter was added to normal polling.

The supplied general API documents `GetCmdRequest` as
`POST /iot-open/sign/device/quota`, with `params.quotas: ["heartbeat.time"]`.
The SHP-specific document labels this read differently; the POST was accepted
in the live probe. This is a **read of a heartbeat property**, not an established
command to keep power reporting active. The tested API helper remains covered
offline, but regular polling does not issue this ineffective extra request.

The integration now obtains MQTT credentials through the shared signed HTTP
client and keeps a verified TLS connection to EcoFlow's public broker on port
8883. It subscribes only to the panel's public quota topic. MQTT protocol
keepalive is 30 seconds. There is **no MQTT PUBLISH**, device wakeup command,
second login, local broker or HA helper to configure. The existing
`homeassistant_config` reference at revision `3fa58b2` was inspected read-only;
its current EcoFlow code and related configuration contain no active keepalive.

## Values, availability and troubleshooting

HTTP quota/all remains the source of entity values, discovery and control
verification. The passive MQTT connection keeps reports flowing on the tested
device. Only a packet count and receipt time are retained, with no additional
measurement store or history. Stable entity identities and Recorder history
remain intact; the synthetic catalog still covers 245 leaves, 44 enabled by
default and 201 disabled.

Non-retained, bounded SHP power frames indicate stream activity. If that stream
disconnects or no such report arrives for 30 seconds, the HTTP power-array
entities become unavailable on the next configured poll. Other available quota
fields remain readable. Reconnection retries after 30 seconds; a silent
connection is checked every 60 seconds. API rate-limit cooldown can extend this.

In the integration's downloaded diagnostics, check:

- `successful_quota_refreshes` and `last_successful_quota_refresh` for HTTP reads.
- `power_telemetry_connected` and `power_telemetry_reports` for the live connection.
- `power_telemetry_age_seconds` for time since receipt of a valid power frame.
- `power_telemetry_error` for a sanitized connection failure category.
- `effective_poll_interval_seconds` for polling/backoff, separately from MQTT.

Normal polling is configurable from **1 to 600 seconds**, default **5**. This
does not force the panel or EcoFlow to produce a new physical measurement at that
rate. Receipt age also does not prove physical sample age. Unchanged valid values
keep their usual HA last-change timestamp and need no duplicate Recorder rows.

For manual observation, close the phone app, leave the DEV device page open and
compare live values and the diagnostic counters over several minutes. Outbound
TLS 8883 must be allowed. Do not press control buttons for this read-only check.
See [the source references](REFERENCE_SOURCES.md#live-power-and-mode-follow-up-030)
for protocol evidence and [milestones](MILESTONES.md) for final DEV results.
