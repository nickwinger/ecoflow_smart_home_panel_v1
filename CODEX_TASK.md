# Codex implementation opdracht / development brief

## Outcome

Implement a high-quality, native **EcoFlow Smart Home Panel v1** custom integration, installable via HACS, from this repository. Read `AGENTS.md` and every referenced document first. The repository was scaffolded with documentation and placeholder HA files, **not** a working implementation.

We already have working HTTP read, cache, channel grid/battery switching and battery charge controls in the reference repository; use that code as a functional blueprint instead of reinventing the protocol:

- `https://github.com/nickwinger/homeassistant_config/tree/main/ecoflow`
- `ecoflow_api.py` (HMAC-SHA256 signed cloud requests, quota GET/PUT)
- `ecoflow_api_cached.py` (partial response/last-good semantics)
- `ecoflow_set.py` (channel and charge payloads)
- `shp_mode.py` (ordered batch switching, retry, confirm)
- `ecoflow_sync_to_ha.py` (existing helper mapping, to replace)

**Do not edit the reference repo.** Do not send a real command to any device.

## Priorities / implementation order

**M1 – functioning read-only core**:
- Set up HA UI config flow with access key, secret key, panel SN; no YAML or shell scripts.
- Proper asynchronous EcoFlow API wrapper; GET/PUT signing equivalent to the reference; meaningful error classification and redacted logs.
- Shared DataUpdateCoordinator, configurable/limited polling (initial suggestion: 60 seconds), refresh semantics and device registry.
- Compatibility only with SHP v1. Verify device identification or fail clearly; no false SHP2 claim.
- Offline mocked API tests.

**M2 – exhaustive quota entity coverage, with precise names/descriptions**:
- Handle flattened EcoFlow dotted-key format and nested arrays/objects; produce a stable path for each scalar leaf. Explicitly test unknown/new fields, empty containers and reordered payload keys.
- Known paths resolve via `docs/quota-field-guide.json` (81 metadata patterns, including array wildcards); for each one provide localized German/English friendly name, explanatory text, units/enums only where verified, underlying raw path and confidence.
- Provide per-channel labels (1..10 for load channels, indexes for backup/batteries), surface user-configured channel labels safely without destabilizing IDs.
- Important sensors enabled; numerous raw/constant/diagnostic readings disabled by default. Expose all encountered scalar leaves for manual enablement; **NO** other history storage.
- Recorder controls normal history; `SensorStateClass.MEASUREMENT` only on legitimate numeric measurements and verified units. Energy counters: research semantics (daily reset vs cumulative), document before choosing `TOTAL`/`TOTAL_INCREASING`, avoid bogus statistics/energy totals.
- HA translation `strings.json` + `translations/de.json` and `translations/en.json`; accessible explanations via safe diagnostic metadata attributes with static ones unrecorded where HA supports it, and catalog documentation. Avoid a made-up `description` field on Home Assistant's frozen EntityDescription.
- Disabled entities have no fresh Recorder history; removing/disabling later does not automatically purge old recorder data. Document accurately.
- Device entities and diagnostics organized so users can enable individual readings without source edits.
- Offline tests assert coverage of **every scalar leaf** in a synthetic quota fixture; missing field unavailable not zero, preserve truthful raw unknown enum.

**M3 – safe control**:
- Opt-in, state-backed selects for grid-vs-battery source per load channel and switches for backup charging, adopting exactly the existing GET/PUT command format.
- Use the existing behavior for retries/refresh/settle, preserve sequential circuit ordering `[7,6,3,1,2,4,5,8,9,10]` for intentional batch operations. Batch operations must be gated, explicitly user-initiated, observable and safe. Never trigger on setup/restart, API failure or polling.
- On write, refresh a *fresh quota* and verify the target state before reporting success. Incomplete `loadCmdChCtrlInfos` is unknown, not success; do not incorrectly claim 'grid' from stale or last-good cache.
- No broad switching on first deployment. All controls have appropriate safety notes and optional enablement.
- Mocked tests for signatures/payloads, failures, retries, incomplete status, concurrency and no startup side effects.

**M4 – packaging and release readiness**:
- HACS manual repository installation and HA UI onboarding documented, tests incl. integration reload/remove, no credentials in logs, HACS validation and hassfest (and brand if default listing needed), tests under CI.
- Migration instructions from current input helpers to native entities, keeping historic helper data intact. Testing occurs in parallel, cutover only after explicit approval.
- Finish translations, license/credits (do not introduce unknown third-party licensed code), changelog/release steps.
- Mark as ready only after real device validation by the user. **Do not create a release or auto-deploy**.

## Definition of done

From a clean HA test install, an SHP v1 owner can configure credentials/SN in UI, discover all available quota leaf entities with meaningful labels/descriptions, activate only the ones they want to record, see native Recorder history/statistics where supported, and intentionally use safe verified controls. Failed/partial responses never silently become misleading status. CI passes without contacting EcoFlow, and instructions for HACS install / upgrade / migration exist.

## Work style

Implement milestones incrementally with tests and commits. If one run cannot finish everything, complete the current milestone thoroughly, update `docs/MILESTONES.md`, and give the next exact Codex step. Do not ask for missing details that can be obtained from the referenced source/repo or reliable docs.
