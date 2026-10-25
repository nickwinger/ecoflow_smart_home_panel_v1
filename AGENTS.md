# Agent instructions (all paths)

## Mission and mandatory reading

Build a native, HACS-installable Home Assistant integration for **EcoFlow Smart Home Panel v1 only**.
Before changing code, read: `CODEX_TASK.md`, `docs/MILESTONES.md`, `docs/ARCHITECTURE.md`, `docs/ENTITY_CATALOG.md`, `docs/quota-field-guide.json`, and `docs/REFERENCE_SOURCES.md`.
Treat `nickwinger/homeassistant_config` as a **read-only reference repository**. Never change files there, never install anything on a running HA server, and never send real device commands during development.

## Non-negotiable requirements

1. The integration name is **EcoFlow Smart Home Panel v1**, domain `ecoflow_smart_home_panel_v1`. Do not use 'Urano' in public names or assume SHP2 compatibility.
2. Keep a single shared authenticated EcoFlow client and a Home Assistant DataUpdateCoordinator. Reuse and adapt the HMAC request/signature, quota API and working switching logic in the reference source. Do not blindly copy blocking `requests` or `time.sleep` into the HA event loop.
3. All API keys/secrets/serial numbers are configured per HA config entry and stored only in HA-managed config entry storage; never committed or logged. Validate unique panel serial per entry. Consider reauth.
4. Read all successful `get_quota_all` response `data` leaf properties, including unknown/array-indexed leaf paths. Do NOT limit sensor discovery to hand-picked mappings. Fixed dotted keys and truly nested JSON both exist; traverse carefully and preserve original raw-path identity. Bound malformed/deep/dynamic inputs to protect entity registry and database.
5. Expose each supported scalar leaf via an entity (sensor or appropriate binary_sensor, not an entire JSON dump stored as giant attributes). Important reliable measurements/statuses are initially enabled; noisy/status-internal/unknown diagnostics initially **disabled** via entity registry; users can enable them individually. Discovery should register disabled entities but they must **not** be polled/stored separately.
6. **No shadow archive whatsoever:** no full quota history file, custom database, Influx/CSV writer, snapshots or side-channel recorder by default. Home Assistant Recorder holds history **only for enabled entities**. Disabled entities must not create state updates/history. Existing short/long-term HA retention behavior must be explained accurately.
7. Each known quota path MUST have a human-friendly name and **meaningful description** (prefer German + English localization), original `data` path, evidenced units, enums and confidence level. Use `docs/quota-field-guide.json` as initial metadata. Use `_attr_has_entity_name = True` plus `translation_key`/localized strings where possible; expose explanation as a diagnostic state attribute `description` and `quota_path` or a documented entity catalog, not as a fake HA EntityDescription field. Prefer unrecorded static attributes to minimize Recorder size. Unknown paths must say meaning is unknown; NEVER infer units/scaling/enum meanings without evidence. Explain channel index mapping explicitly.
8. Missing quota fields, partial/invalid API responses, unknown enums and failed writes are `unavailable` or `unknown`, not fabricated `0` / `False` states. Never reuse stale cache as proof of current switching state.
9. Preserve the tested source switching semantics and precise `put_quota` payloads, safety ordering, retry/settle/verification. No optimistic source toggles and no power-routing changes during HA startup or in CI. Control entities initially opt-in via options and commands must serialize.
10. Cover setup, polling, nested/dotted quota, metadata mapping, disabled defaults, history semantics, controls, failures, reauth, entity lifecycle and migration with offline tests. Prefer typed Python, ruff, pytest and relevant hassfest/HACS validation.
11. Keep status honest: the initial repository is a scaffold, **not a finished integration**. Implement in reviewable milestones; update README + milestone status with tests/results; do not publish a GitHub release until user verification.
12. Keep this public repository free of production payloads and identifiers. Derive synthetic fixtures with fake SN and representative field shapes. Never store device credentials in fixtures or CI logs.

## Engineering practices

- Follow current Home Assistant integration, async, config flow, coordinator, entity registry, translations and diagnostics conventions.
- Use a reusable catalog resolver with wildcard paths such as `heartbeat.loadCmdChCtrlInfos[].ctrlSta`; stable unique IDs should use the configured panel serial internally and stable quota identity without exposing serial in entity display names.
- Deterministic IDs must not change on rename; user-facing device/channel names may change independently. Do not assume additional generations' API layouts.
- For HA Recorder: numeric time-series can receive a verified `state_class` and appropriate unit; daily resetting counters require special care and must NOT blindly use `TOTAL_INCREASING`. Text, booleans and arbitrary diagnostics do not automatically get permanent long-term statistics.
- Check effective defaults of sensor/device/entity categories and their opt-in registry enablement with tests.
- Keep existing `nickwinger/homeassistant_config` automation operational until a separate explicit migration.
- DEV onboarding must target only hardcoded loopback IPs: `127.0.0.1:8124` from WSL, or `127.0.0.1:8123` when sharing the isolated DEV HA network namespace via `network_mode: service:homeassistant`, guarded by `ECOFLOW_DEV_BOOTSTRAP=1`. Never replace this with DNS, host networking, redirects, HTTP proxies, a user-provided URL, or any production HA address.
- If you encounter an uncertain capability, investigate/document it before inventing behavior. Avoid scope creep into other EcoFlow integrations or unrelated devices.

## Completion reporting

At the end of each Codex run: state milestone(s), code paths changed, exact tests executed and outcomes, known gaps, manual validation steps (without actually controlling hardware), and commit SHA. Report how many discovered scalar leaves are represented and which are enabled by default.
