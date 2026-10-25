# Development milestones

Milestone status below distinguishes repository scaffolding from functioning Home Assistant functionality.

## M0 — project bootstrap [DONE]

- [x] Public dedicated SHP v1 repository and HACS-compatible directory layout.
- [x] README, license, AGENTS.md, CODEX_TASK.md, source map, entity/history contract.
- [x] Quota metadata catalog seed with German labels and evidenced explanations.
- [x] Minimal HA manifest/module placeholders and GitHub Actions starting points.

Acceptance: files present in GitHub. **No claim of a working integration at this milestone.**

## M1 — UI configuration, API and polling [IMPLEMENTED / OFFLINE VERIFIED]

- [x] Asynchronous signed EcoFlow Cloud client, credentials via HA config flow, unique config entries by panel serial.
- [x] Connection and version checks (SHP v1 only), reauth and meaningful errors.
- [x] One DataUpdateCoordinator with shared timed fetch and appropriate rate/error handling.
- [x] Test config setup/unload/reload and cloud responses offline.

Acceptance: read-only HA integration loads in isolated HA 2026.10.3 tests and fetches synthetic SHP v1 quota. Current setup checks the v1 topology without a redundant confirmation checkbox; the manufacturer list API has no model field. Read-only DEV checks now also cover continuous power reporting with a passive MQTT connection (0.3.0 record below).

Validation: `pytest -q --tb=short --show-capture=no --timeout=30` (40 tests), `ruff check custom_components tests`, `ruff format --check custom_components tests`. Commit: [`223d1f7`](https://github.com/nickwinger/ecoflow_smart_home_panel_v1/commit/223d1f7d24d4fa5fcff6bf4d9ac65607b7f7d67b) (`feat: implement M1 signed read-only cloud core`). M2 entities are still pending at this commit.

## M2 — complete selectable entity model [IMPLEMENTED / OFFLINE VERIFIED]

- [x] Generic raw quota leaf coverage incl. dotted keys, nested dicts and indexed lists.
- [x] All 81 seed descriptions plus 11 supplementary patterns integrated (92 total), plus truthful fallback for unknown paths.
- [x] Stable unique IDs, friendly de/en names, path, description, confidence, verified states/units.
- [x] Essential sensors and selected diagnostics enabled, remaining diagnostics disabled; no independent historical storage.
- [x] Valid state classes/long-term statistics for supported numeric readings.
- [x] Unit tests comparing fixture leaves to entity catalog, missing fields and enablement defaults.

Acceptance verified in isolated HA: all 245 synthetic scalar leaves register, all can be enabled; 44 enabled and 201 disabled by default (0.1.1 fixture includes both storage input powers). A real in-memory Recorder test proves disabled entities have no rows, static metadata is omitted and prior history survives disabling. No shadow store. All 92 patterns have German/English metadata and truthful fallbacks.

Default-enabled: grid availability (1), panel battery percentage (1), ten load supply states (10), nominal grid settings (2), daily energy counters with community Wh units (2). Additionally, ten circuit powers, ten circuit control modes and four readings for each of two storage entries are enabled diagnostics. They retain their evidence and receive no new statistics. Only the valid documented panel battery percentage has measurement statistics.

M2 commit: [`544287c`](https://github.com/nickwinger/ecoflow_smart_home_panel_v1/commit/544287cf29a868aaf29b4ad0b645a7be080bca9e), `feat: expose complete bounded quota entities with selective history`. Current local checks: Ruff, formatter, catalog regeneration check, compileall, and the full offline pytest suite. See the verification record below for the final count and CI results.

## M3 — explicit source, mode and charge control [IMPLEMENTED / PARTLY OWNER VERIFIED]

Implementation commit: [`888fd96`](https://github.com/nickwinger/ecoflow_smart_home_panel_v1/commit/888fd96da2e44756839abee0292615b79a14b862), `feat: implement M3 verified opt-in source and charging controls` (0.2.0), published to main.

- [x] Ten source selects, ten mode selects and two charging switches; opt-in and no startup switching.
- [x] Exact signed PUT payloads, source/charge settle timings, bounded retries, fresh pre/post reads and unknown-safe confirmation.
- [x] Separately gated batch buttons plus confirmed automation action; original script sequence, continuation after channel failures, final aggregate result, progress, cancellation and serialized transactions.
- [x] Offline transport, command/state/error, concurrency, HA services, options, lifecycle and Recorder tests; documented manual hardware QA.

Acceptance: the current full suite has 511 offline tests, 99% overall coverage and 100% command-controller/telemetry coverage. The batch controller is also compared directly with the original script in both directions. Official local hassfest passes. The owner confirmed source switching and charging work, and the original batch script's reliability. The native mode and batch controls still need hardware acceptance; the development agent sent no actuator commands and changed no production installation. [Control contract and acceptance checklist](CONTROLS.md).

## M4 — HACS and release readiness [TODO]

- [ ] Integration UI and HA diagnostics reviewed; full quality checks, hassfest, HACS validation.
- [ ] HACS custom-repository install, upgrade and migration tested.
- [ ] Translations/developer docs/security reviewed.
- [ ] Optional HACS default listing, repository topics and Home Assistant brands contribution.
- [ ] First release only after user confirms real-hardware acceptance.

Acceptance: repeatable install with no unrelated HA changes or data loss.

Each completed milestone must include commit link, test commands/outcomes and remaining risks. Never mark an untested milestone complete.

## Verification record (2026-10-25)

- Python 3.14.4, Home Assistant 2026.10.3; no real EcoFlow requests or hardware writes.
- `ruff check custom_components tests scripts` and `ruff format --check custom_components tests scripts`: **passed** (22 Python files).
- `python scripts/sync_catalog.py --check` and `python -m compileall -q custom_components`: **passed**.
- `pytest -q --tb=short --show-capture=no --timeout=30 --cov=custom_components.ecoflow_smart_home_panel_v1 --cov-report=term-missing`: **221 passed**, 99% line coverage (609 statements, 8 uncovered), 10.87 seconds.
- [Official hassfest and offline CI](https://github.com/nickwinger/ecoflow_smart_home_panel_v1/actions/runs/40177067830): **passed** on M2. Docker is unavailable in this WSL environment.
- [Initial HACS check](https://github.com/nickwinger/ecoflow_smart_home_panel_v1/actions/runs/40177067803): 8/9 passed, only repository topics failed. At the owner's request, `topics` joins `brands` as deferred default-listing metadata; all technical checks stay enabled. The optional category remains a warning: adding the documented `categories` key fails the currently published hassfest container, so it is deferred until validator versions agree. The available connector cannot edit repository topics.
- All three new HTML references fully reviewed; all 28 supplementary property sections linked to catalog evidence. Additional tests cover sourced units, raw sentinel preservation and UTF-8 byte names. [HACS with the metadata exception](https://github.com/nickwinger/ecoflow_smart_home_panel_v1/actions/runs/40178104005) is **green**. The separate [hassfest run](https://github.com/nickwinger/ecoflow_smart_home_panel_v1/actions/runs/40178104033) exposed the category-key compatibility issue; the optional key was removed and validation rerun.
- Remaining: user hardware read validation, actual HACS installation/upgrade acceptance, authoritative model/error metadata, inferred units/scales and daily counter reset semantics. M3 controls and M4 release approval remain open.

Supplementary sources commit: [`7acb057`](https://github.com/nickwinger/ecoflow_smart_home_panel_v1/commit/7acb05745451b483094caec62f22ae1331e8b32f). HACS workflow correction: [`87d3474`](https://github.com/nickwinger/ecoflow_smart_home_panel_v1/commit/87d3474043ac2a0b2c26ce32e36cdf92778206e7).

## Final CI acceptance

Validated code commit: [`9dcf39d`](https://github.com/nickwinger/ecoflow_smart_home_panel_v1/commit/9dcf39daf45a7dccf499bd630ed3e1837517f40e).

- [HACS custom repository validation](https://github.com/nickwinger/ecoflow_smart_home_panel_v1/actions/runs/40178236718): **SUCCESS**, all 8 active checks passed. Only default-listing `brands` and `topics` checks are deferred. Missing categories is a non-failing warning because the published hassfest container does not yet accept that optional key.
- [Offline validation and official hassfest](https://github.com/nickwinger/ecoflow_smart_home_panel_v1/actions/runs/40178236653): **SUCCESS**, both jobs. Ruff/format, generated catalog and compilation passed; **221 tests passed in 7.04 seconds, 99% coverage** (609 statements, 8 uncovered).
- Working Python reference and the three supplied HTML originals remain unchanged. No live device commands, running-HA installation or release was performed.
- This final results update changes documentation only; `[skip ci]` avoids repeating identical technical checks for the recorded outcome.

## M2 follow-up — requested names and defaults (0.1.1)

- Named circuits use the configured channel name alone; unnamed circuits use localized `Stromkreis <number>` / `Circuit <number>`, followed by the reading name.
- Channel power/control mode for circuits 1–10 and battery level/input power/output power/temperature for both storage entries start enabled in Diagnostics.
- One-time config-entry 1.1 → 1.2 migration enables only former integration defaults; explicit disables, custom names, IDs and history remain intact.
- Offline tests cover both languages, missing/invalid/string/UTF-8 names, index bounds, registry migration, scope, idempotence and actual Recorder history for the selected diagnostics.
- `pytest -q --tb=short --show-capture=no --timeout=30 --cov=custom_components.ecoflow_smart_home_panel_v1 --cov-report=term-missing`: **256 passed**, **99% coverage** (637 statements, 7 uncovered), 15.11 seconds.
- `ruff check custom_components tests scripts`, `ruff format --check custom_components tests scripts` (26 Python files), `python scripts/sync_catalog.py --check`, `python -m compileall -q custom_components`, and `git diff --check`: **passed**.
- No hardware commands or production installation. Update/restart the isolated instance and verify names plus the selected Diagnostics; explicit user disables remain manual choices.

- Merged the parallel DEV-environment updates before the final test run. `docker compose -f .devcontainer/ha.compose.yml config -q` and `bash -n scripts/dev-ha.sh`: **passed**. GitHub workflows remain manual-only; no workflow was dispatched for this update.

## M1 follow-up — five-second default polling (0.1.2)

- Default and minimum interval are now 5 seconds; maximum remains 900 seconds. English/German options labels and validation match the new range.
- Entries without a saved override automatically use the new default after restart; explicitly configured intervals are preserved. No config-entry schema migration is needed.
- Error backoff and HTTP 429 cooldown remain active; a successful refresh restores the selected interval.
- Tests cover the actual five-second scheduled poll, unload cancellation, options defaults and bounds, retained custom selections, error backoff and recovery.
- `pytest -q --tb=short --show-capture=no --timeout=30 --cov=custom_components.ecoflow_smart_home_panel_v1 --cov-report=term-missing`: **260 passed**, **99% coverage** (637 statements, 7 uncovered), 16.07 seconds.
- `ruff check custom_components tests scripts`, `ruff format --check custom_components tests scripts`, `python scripts/sync_catalog.py --check`, `python -m compileall -q custom_components`, and `git diff --check`: **passed**.
- Entity coverage/defaults remain 245/245 leaves, 44 enabled and 201 disabled. No live device commands or deployment; GitHub Actions remain manual-only.

## M3 verification record (2026-10-25, 0.2.0)

- [Issue #1](https://github.com/nickwinger/ecoflow_smart_home_panel_v1/issues/1)
  closed as completed at the owner's request; all M1/M2 checklist items checked.
- Default remains read-only; source, charging and batch options each default to
  false. Existing entries/IDs/history/polling choices remain intact; no automatic
  option migration. Default polling remains 5 seconds.
- `api.py`, `controls.py`, `coordinator.py`, `control_entity.py`, `select.py`,
  `switch.py`, `services.py`, options and de/en translations implement M3.
  `scripts/sync_catalog.py` now preserves control translations while generating
  the complete quota catalog. README, architecture, entity catalog, migration,
  source references and DEV instructions describe the final behavior.
- `.venv/bin/pytest -q --tb=short --show-capture=no --timeout=30 --cov=custom_components.ecoflow_smart_home_panel_v1 --cov-report=term-missing`:
  **361 passed**, **99% coverage** (909 statements, 8 uncovered), 25.30 seconds.
  All tests run with internet sockets blocked; API writes are mocks only.
- `.venv/bin/ruff check custom_components tests scripts`,
  `.venv/bin/ruff format --check custom_components tests scripts` (33 Python files),
  `.venv/bin/python scripts/sync_catalog.py --check`,
  `.venv/bin/python -m compileall -q custom_components`, `git diff --check`: **passed**.
- `docker compose -f .devcontainer/ha.compose.yml config -q` and
  `bash -n scripts/dev-ha.sh`: **passed**; no HA service was started or changed.
- Official local validation:
  `docker run --rm --network none -v /home/nick/dev/ecoflow_smart_home_panel_v1:/github/workspace:ro ghcr.io/home-assistant/hassfest:latest`:
  **1 integration, 0 invalid**. Image digest
  `sha256:e5828f7e305518506d8b4e8346411357d68358531b761bd118fe6a1631feff44`.
  Network disabled, repository mounted read-only.
- Quota coverage remains **245/245 scalar leaves**, **44 enabled / 201 disabled**:
  16 essential fields plus 20 circuit and 8 storage diagnostics. Opt-in controls
  add at most 12 entities. Recorder tests verify control metadata/progress is not
  recorded and disabled raw leaves remain without history. No shadow archive.
- Proven source sequence/timings retained. Intentional differences: stop a batch
  at its first failure, reject ambiguous/invalid/partial confirmation data, and
  add bounded fresh verification to charging. No inferred automatic interlocks.
- Remaining: actual hardware and HACS install/upgrade acceptance, backup code-2
  conflict and physical mapping, authoritative model/error metadata, daily
  counter/statistics uncertainties. M4 and release approval remain open.
- GitHub workflows remain manual-only; none were dispatched. HACS workflow was
  not rerun, so prior HACS results above are not a claim for this new version.
- Reference repository, supplied HTML originals and production HA untouched.
  Manual next step: isolated read-only update and the checks in CONTROLS.md;
  no real switching performed by development.

Final merged validation: the concurrent icon, DEV loopback-security and scripts
documentation commits through `4ec3579` are preserved. Two formatting-only issues
in the merged bootstrap/test files were corrected. The same full pytest command
then reported **364 passed in 23.59 seconds**, **99% coverage** (909 statements,
8 uncovered). Ruff check/format now pass for **34 Python files**; catalog,
compileall, diff and Compose checks also pass, as does
`bash -n scripts/dev-ha.sh scripts/recreate.sh`. Official hassfest was also rerun
after including the brand icon: **1 integration, 0 invalid**.

## DEV follow-up — Austrian country default (2026-10-25)

- `.devcontainer/ha-configuration.yaml` now sets `homeassistant.country: AT`
  alongside `Europe/Vienna`. YAML-managed general settings remain locked in HA UI.
- Existing DEV volumes are not replaced by the seed. The owner's running
  `ecoflow-shp-v1-live-test` instance received only the missing country setting
  and was restarted without resetting accounts, integration entries or history.
- Runtime `/api/config` on the dedicated DEV loopback confirmed `country=AT`,
  `time_zone=Europe/Vienna`, `state=RUNNING`. The live Repairs API confirmed
  the country warning is absent; persisted registry files can retain inactive
  historical entries. Temporary verification tokens were
  revoked; no credentials were printed or committed.
- `.venv/bin/pytest -q tests/test_devcontainer_compose.py tests/test_dev_ha_bootstrap.py tests/test_scripts_documentation.py --tb=short --show-capture=no --timeout=30`:
  **14 passed in 0.58 seconds**. HA's country/time-zone validators,
  `docker compose -f .devcontainer/ha.compose.yml config -q` and `git diff --check`: **passed**.
- M1/M2/M3 behavior unchanged: 245 quota leaves, 44 enabled (16 essential,
  20 circuit diagnostics and 8 storage diagnostics), 201 disabled. No device
  commands, production changes or GitHub workflow dispatch. Manual check: refresh
  the existing DEV General settings page and verify Austria. M4 remains open.

## M1/M2 follow-up — remove checkbox and distinguish polling from changes (0.2.1)

- Removed the redundant v1-confirmation checkbox, its validation and de/en labels.
  Setup now asks for keys, panel serial and API region only. The supported v1
  quota-topology check remains. Old `confirm_v1` data is ignored during reauth
  and reconfigure; no entry recreation or control-option migration.
- Five-second polling was already operating. Read-only DEV observation confirmed
  repeated reports around the configured interval while the channel value stayed
  unchanged. No raw values, labels, credentials or response snapshots were saved.
- Explicit `always_update=True` preserves the coordinator's existing behavior.
  Diagnostics now expose successful refresh count, last success UTC timestamp,
  effective interval/backoff, failures and HA's polling-disabled setting.
  This distinguishes retrieval/reporting from value changes and cloud measurement
  age without forced state changes, duplicate Recorder rows or a new archive.
- `.venv/bin/pytest -q tests/test_config_flow.py tests/test_setup.py tests/test_recorder.py --tb=short --show-capture=no --timeout=30`: **44 passed**.
- `.venv/bin/pytest -q --tb=short --show-capture=no --timeout=30 --cov=custom_components.ecoflow_smart_home_panel_v1 --cov-report=term-missing`:
  **370 passed in 27.27 seconds**, **99% coverage** (910 statements, 8 uncovered).
  Tests cover setup without confirmation, old entry flags during credential
  replacement, recurring identical power reports, changed power, diagnostic
  counters/backoff and no duplicate Recorder history for identical polls.
- `.venv/bin/ruff check custom_components tests scripts`,
  `.venv/bin/ruff format --check custom_components tests scripts` (34 files),
  `.venv/bin/python scripts/sync_catalog.py --check`,
  `.venv/bin/python -m compileall -q custom_components`, `git diff --check`: **passed**.
- Official local hassfest, with network disabled and repository read-only:
  **1 integration, 0 invalid**, using the image/command recorded under M3 above.
- Quota defaults unchanged: **245/245 fixture leaves**, **44 enabled** (16 essential,
  10 circuit powers, 10 control modes, 8 storage measurements), **201 disabled**.
- Physical data freshness still depends on EcoFlow. A recent fetch does not prove
  a new physical measurement; no guaranteed per-field cloud update rate is known.
  M4 remains open; no real device commands, production changes or workflow runs.

Read-only DEV acceptance after restart: the live setup form contains exactly
access key, secret key, serial and region, with no confirmation checkbox. The
subsequent observation confirmed seven successful quota retrievals during a
36-second window and one actual channel-power value change. The new diagnostic
counter/timestamp and five-second effective interval were present. The temporary
empty setup flow was closed and verification tokens revoked. No device write,
raw measurement log or payload archive was created.

## M1/M2/M3 follow-up — live power and visible controls (0.3.0)

Implementation commit: [`3dfee82`](https://github.com/nickwinger/ecoflow_smart_home_panel_v1/commit/3dfee82e0b4841df8967f0917c663cf0f167db22),
`fix: keep SHP power live and expose mode and batch controls`.

- Resolved the reproduced app-dependent freshness problem with one passive
  public MQTT subscription per entry, authenticated through the shared HTTP
  client, verified TLS and 30-second protocol keepalive. No MQTT PUBLISH or
  startup actuator command. Connection/thread cleanup, reconnection, silent
  stream detection, rate limits and reauth are covered offline.
- HTTP remains the sole source of entity readings and command verification.
  After missing/stale MQTT power reports, power-array entities become unavailable
  on the next poll. No MQTT value cache, new raw identities or history archive.
  See [controlled heartbeat/cache/MQTT comparisons](LIVE_DATA.md).
- Every request already had the timestamp header in milliseconds and a fresh
  nonce/signature. Reading `heartbeat.time`, `no-cache` and a signed `ts` query
  were accepted but did not restore changes. They are not added to normal polling.
- Normal interval **1–600 seconds**, default **5**; old out-of-range values are
  normalized. Source opt-in also exposes ten automatic/manual mode selects.
  Batch opt-in adds three visible device-page buttons using the existing ordered
  controller. Plain de/en labels replace the confusing helper terminology.
- Circuits always use localized **Stromkreis N / Circuit N**. Cloud labels remain
  metadata only; explicit HA names, identities and existing history are retained.
- Runtime changes: `api.py`, `telemetry.py`, `coordinator.py`, `const.py`,
  `config_flow.py`, `controls.py`, `control_entity.py`, `select.py`, `button.py`,
  `entity.py`, setup, diagnostics, manifest/dependencies and translations.
  README, control guide, migration, architecture, catalog, task and reference
  documentation describe the resulting behavior.
- `.venv/bin/pytest -q --disable-socket --allow-unix-socket --tb=short --show-capture=no --timeout=30 --cov=custom_components.ecoflow_smart_home_panel_v1 --cov-report=term-missing`:
  **456 passed in 33.49 seconds**, **99% coverage** (1,147 statements, 8 uncovered).
  Telemetry and command-controller line coverage are **100%**. All actuator calls
  are mocked and internet sockets are blocked. Added checks include broker
  rejection, subscription failure, disconnect, silent/stale streams, unload,
  retained/ambiguous frames, TLS, no publish, interval bounds, modes and buttons.
- `.venv/bin/ruff check custom_components tests scripts`,
  `.venv/bin/ruff format --check custom_components tests scripts` (**38 files**),
  `.venv/bin/python scripts/sync_catalog.py --check`,
  `.venv/bin/python -m compileall -q custom_components`, `git diff --check`: **passed**.
- Official local hassfest, with the network-disabled command and image digest
  recorded above: **1 integration, 0 invalid**. Paho uses the validator-required
  minimum dependency syntax. GitHub workflows remain manual-only; none dispatched.
  HACS was not rerun, so earlier CI results do not claim validation of 0.3.0.
- Read-only acceptance on the existing DEV instance after restart: **36 successful
  HTTP refreshes and 36 power-value changes in 180 seconds**; 37 observed state
  reports at **4.95–5.06-second** intervals. MQTT stayed connected, report count
  increased from 132 to 168, and the power entity remained available. The system
  language is now German; the fixed German circuit prefix, **20 selects and three
  buttons** were verified without operating them. Verification tokens revoked.
- Quota coverage unchanged: **245/245 synthetic scalar leaves**, **44 enabled**
  (16 essential, ten circuit powers, ten control modes, eight storage readings),
  **201 disabled**. Up to **25 additional opt-in control entities**. Recorder
  history remains selective; the live probes saved only aggregate results here.
- Follow-up request confirmed: `heartbeat.gridSta` is already default-enabled
  as the grid-status binary sensor. Existing offline state/lifecycle tests cover
  it; a read-only DEV registry/state check also confirmed one enabled, available
  grid-status entity. No control opt-in or migration is required for that default.
- Remaining: longer owner observation with the app closed, new mode/batch hardware
  acceptance, physical storage mapping/vendor enum conflicts and actual HACS
  install/upgrade acceptance. EcoFlow controls physical measurement cadence;
  neither a recent HTTP fetch nor MQTT receipt proves the measurement's age.
  M4 and GitHub release approval remain open. Reference repository and production
  HA were not changed; no actual switching or charging commands were sent.

Manual next step: refresh the DEV device page, inspect the new controls and fixed
names, and observe live power with the phone app closed. No control action is
needed for this verification.

## M3 correction — preserve the original complete batch sequence (0.3.1)

Implementation commit: [`e0e9beb`](https://github.com/nickwinger/ecoflow_smart_home_panel_v1/commit/e0e9bebcfe5ac2a6608795376d940557679b52b7),
`fix: restore original all-circuit switching sequence`.

- The owner explicitly rejected the additional stop-on-first-error policy and
  required the established `shp_mode.py` behavior. The 0.2.0/0.3.0 descriptions
  above are historical; this correction supersedes their batch behavior.
- `controls.py` now processes all ten channels in the original order for both
  directions. An individual failure is collected and followed by the original
  10-second pause and next channel. All original PUTs, pre/post reads, eight
  attempts, 10-second settles and 15-second retry pauses (including after the
  last failed attempt) are retained. Final success requires all ten confirmations;
  otherwise a localized error lists all failed channels after the sequence ends.
- Batch-only status decoding matches the original positional lookup, `ch`
  fallback, dotted-list preference, `ctrlSta`/`sta` priority and `int()` conversion.
  A missing unrelated channel no longer prevents current-channel confirmation.
  Individual source/mode/charge controls and raw quota interpretation are unchanged.
- The shared native async client, no-cache verification, command lock, opt-ins,
  cancellation/unload and transport response limits/cooldown remain. No automatic
  rollback or extra device command was added. Progress records only bounded
  completed/failed circuit numbers, excluded from Recorder attributes.
- Added an unchanged test-only copy of the owner's script from reference commit
  `3fa58b227ea5bd9e1a605ebb7177ab002a2a6e10`, verified against Git blob
  `5b409c05f51ae15c3fe5f8c32826bf877894eadb`. Only selected AST functions/constants
  execute with synthetic memory-only GET/PUT/cache/log/sleep substitutes; imports
  and CLI startup never execute. No source repository changes or live payloads.
- `tests/test_batch_reference.py`: **36 complete trace comparisons** (18 scenarios
  × grid/battery), **14 parser comparisons**, three cancellation stages, reauth and
  lock serialization after a channel failure. The native GET/PUT/delay trace,
  simulated outcome and completed/failed lists must match the reference exactly.
  Existing tests now assert continuing through the remaining channels.
- Initial focused run:
  `.venv/bin/pytest -q tests/test_batch_reference.py tests/test_controls.py tests/test_control_entities.py tests/test_control_mode.py --tb=short --show-capture=no --timeout=30`:
  **173 passed in 20.32 seconds**. One additional serialization regression was
  subsequently included in the complete run below. Test configuration blocks
  internet sockets and permits only local Unix sockets for HA internals.
- Final full run:
  `.venv/bin/pytest -q --disable-socket --allow-unix-socket --tb=short --show-capture=no --timeout=30 --cov=custom_components.ecoflow_smart_home_panel_v1 --cov-report=term-missing`:
  **511 passed in 45.91 seconds**, **99% coverage** (1,187 statements, 8 uncovered);
  **100% command-controller coverage**. All actuator calls mocked.
- `.venv/bin/ruff check custom_components tests scripts`,
  `.venv/bin/ruff format --check custom_components tests scripts` (**40 files**),
  `.venv/bin/python scripts/sync_catalog.py --check`,
  `.venv/bin/python -m compileall -q custom_components`, `git diff --check`: **passed**.
- Local official validation:
  `docker run --rm --network none -v /home/nick/dev/ecoflow_smart_home_panel_v1:/github/workspace:ro ghcr.io/home-assistant/hassfest:latest`:
  **1 integration, 0 invalid**, using the previously recorded cached image.
  GitHub workflows remain manual-only; no HACS run or release was triggered.
- README, task contract, architecture, controls, migration and source references
  updated. Version is 0.3.1; entity defaults, polling and MQTT behavior unchanged:
  **245/245 leaves**, **44 enabled / 201 disabled**. Enabled: grid availability,
  panel battery percentage, ten supply states, two nominal grid settings, two
  daily counters, ten circuit powers, ten control modes and eight storage readings.
- Remaining: native batch/mode hardware acceptance and M4/HACS installation and
  release acceptance. A cloud/device failure may still leave a target unconfirmed,
  just as in the reference. No live switching, production installation, DEV
  restart or reference-repository change was performed in this correction.

Manual check without switching: after the normal update/reload, inspect the
revised batch-action description and the three device-page buttons. An actual
batch run remains an owner action; no button press is needed for the UI check.

## M1/M3 follow-up — awaited automations and useful HA logs (0.3.2)

Implementation commit: [`a6fe221`](https://github.com/nickwinger/ecoflow_smart_home_panel_v1/commit/a6fe2215bbcf64ad3f27d5b4a7ea780bf141197f),
`fix: verify automation completion and report actionable HA errors`.

- The owner needs all-circuit switching from an automation that waits for full
  completion. The existing `set_all_sources` handler directly awaits the shared
  controller; no detached task, helper, extra timer or new switching algorithm
  was added. The next sequential automation action runs only after all ten fresh
  confirmations and the final pause. Partial failure is reported after all ten
  channels and stops the automation; explicit cancellation also stops it.
- Added real HA Script tests for success, partial failure, cancellation, invalid
  integration-entry targets and unavailable-button behavior. The tests hold the
  first and final pauses open and assert that no following action starts early.
  HA may skip an unavailable button entity, so the documented automation example
  uses the direct entry-scoped action and the default stop-on-error behavior.
- `controls.py`, `coordinator.py`, `telemetry.py`, `config_flow.py` and the new
  `logging_utils.py` report classified failures through standard HA logging.
  Control errors include circuit, target, step, attempt and bounded result lists;
  arbitrary exception text, response bodies, credentials and serials are excluded.
  Repeated polling/telemetry outages are deduplicated. Info-level events cover
  command start/success and recovery. Progress adds an unrecorded `stage` field.
- New logging tests attach the actual HA `system_log` component, check useful
  user-visible error details, prevent repeated outage warnings and verify that
  deliberately sensitive synthetic exception contents never reach logs.
  `services.py` documents its awaited contract; DE/EN action/option descriptions
  explain automation use. README, architecture, controls, source references and
  the new [automation guide](AUTOMATIONS.md) document completion and error handling.
- Focused development run:
  `.venv/bin/pytest -q tests/test_automation_wait.py tests/test_logging.py tests/test_batch_reference.py tests/test_telemetry.py --tb=short --show-capture=no --timeout=30`:
  **109 passed, 1 failed in 17.35 seconds**. The sole failure expected the wrong
  wording for HA's built-in recovery message; the assertion was corrected to the
  actual `recovered` message before the complete successful run below.
- Complete final run:
  `.venv/bin/pytest -q --disable-socket --allow-unix-socket --tb=short --show-capture=no --timeout=30 --cov=custom_components.ecoflow_smart_home_panel_v1 --cov-report=term-missing`:
  **533 passed in 49.40 seconds**, **99% coverage** (1,258 statements, 8 uncovered).
  Controls, service handlers, telemetry and the failure classifier have **100%
  line coverage**. All device I/O is mocked; internet sockets are blocked.
  This includes the existing 36 exact reference trace comparisons and all
  quota, Recorder, configuration, lifecycle, reauth and opt-in regressions.
- `.venv/bin/ruff check custom_components tests scripts`,
  `.venv/bin/ruff format --check custom_components tests scripts` (**43 files**),
  `.venv/bin/python scripts/sync_catalog.py --check`,
  `.venv/bin/python -m compileall -q custom_components`, `git diff --check`: **passed**.
- `docker run --rm --network none -v /home/nick/dev/ecoflow_smart_home_panel_v1:/github/workspace:ro ghcr.io/home-assistant/hassfest:latest`:
  **1 integration, 0 invalid**, using the previously recorded cached image.
  No GitHub workflow, HACS validation run or release was triggered.
- Quota coverage remains **245/245 synthetic scalar leaves**, **44 enabled /
  201 disabled**. Defaults: grid availability, panel battery percentage, ten
  source states, nominal grid voltage/frequency, two daily counters, ten circuit
  powers, ten control modes and eight storage readings (battery/input/output/
  temperature for each of two entries). Up to 25 separately opted-in controls.
  No field metadata, polling interval, command payload or reference timing changed.
- Remaining: owner hardware acceptance of native batch/mode controls and M4/HACS
  installation/upgrade acceptance. A failed device/cloud confirmation remains a
  failure, never a guarantee of successful switching. No live commands, DEV
  restart, production installation or reference-repository changes occurred.

Manual verification without switching: after the normal update, inspect the
revised integration options and the `set_all_sources` action in the automation
editor. Choose the panel entry, check the target/confirmation fields and place
the next action after it, with “continue on error” disabled. Save/inspect the
automation without executing it. No hardware action is required for this check.
