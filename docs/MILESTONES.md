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

Acceptance: read-only HA integration loads in isolated HA 2026.10.3 tests and fetches synthetic SHP v1 quota. Device identity is checked conservatively by user confirmation plus topology; the manufacturer list API has no model field. No hardware claim.

Validation: `pytest -q --tb=short --show-capture=no --timeout=30` (40 tests), `ruff check custom_components tests`, `ruff format --check custom_components tests`. Commit: [`223d1f7`](https://github.com/nickwinger/ecoflow_smart_home_panel_v1/commit/223d1f7d24d4fa5fcff6bf4d9ac65607b7f7d67b) (`feat: implement M1 signed read-only cloud core`). M2 entities are still pending at this commit.

## M2 — complete selectable entity model [IMPLEMENTED / OFFLINE VERIFIED]

- [x] Generic raw quota leaf coverage incl. dotted keys, nested dicts and indexed lists.
- [x] All 81 seed descriptions plus 11 supplementary patterns integrated (92 total), plus truthful fallback for unknown paths.
- [x] Stable unique IDs, friendly de/en names, path, description, confidence, verified states/units.
- [x] Essential sensors enabled, diagnostics disabled; no independent historical storage.
- [x] Valid state classes/long-term statistics for supported numeric readings.
- [x] Unit tests comparing fixture leaves to entity catalog, missing fields and enablement defaults.

Acceptance verified in isolated HA: all 243 synthetic scalar leaves register, all can be enabled; 16 enabled and 227 disabled by default. A real in-memory Recorder test proves disabled entities have no rows, static metadata is omitted and prior history survives disabling. No shadow store. All 92 patterns have German/English metadata and truthful fallbacks.

Default-enabled: grid availability (1), panel battery percentage (1), ten load supply states (10), nominal grid settings (2), daily energy counters with community Wh units (2). Power/storage/temperature readings have attributed community units but remain disabled diagnostics without statistics. Only the valid documented panel battery percentage has measurement statistics.

M2 commit: [`544287c`](https://github.com/nickwinger/ecoflow_smart_home_panel_v1/commit/544287cf29a868aaf29b4ad0b645a7be080bca9e), `feat: expose complete bounded quota entities with selective history`. Current local checks: Ruff, formatter, catalog regeneration check, compileall, and the full offline pytest suite. See the verification record below for the final count and CI results.

## M3 — verified, explicit source/charge control [TODO]

- [ ] Native select/switch or appropriate controls, opt-in and no startup switching.
- [ ] Exact proven write payloads, retries, post-write fresh confirmation, unknown-safe handling.
- [ ] Optional ordered batch services, serialized access and no optimistic success.
- [ ] Offline command/state/error tests and documented manual hardware QA.

Acceptance: side-effect-free CI; controlled real-device verification happens only with user approval.

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
