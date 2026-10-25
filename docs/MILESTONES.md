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

Validation: `pytest -q --tb=short --show-capture=no --timeout=30` (40 tests), `ruff check custom_components tests`, `ruff format --check custom_components tests`. Commit: [`34f6aba`](https://github.com/nickwinger/ecoflow_smart_home_panel_v1/commit/34f6aba) (`feat: implement M1 signed read-only cloud core`). M2 entities are still pending at this commit.

## M2 — complete selectable entity model [IMPLEMENTED / OFFLINE VERIFIED]

- [x] Generic raw quota leaf coverage incl. dotted keys, nested dicts and indexed lists.
- [x] All 81 catalog descriptions/patterns integrated, plus truthful fallback for unknown paths.
- [x] Stable unique IDs, friendly de/en names, path, description, confidence, verified states/units.
- [x] Essential sensors enabled, diagnostics disabled; no independent historical storage.
- [x] Valid state classes/long-term statistics for supported numeric readings.
- [x] Unit tests comparing fixture leaves to entity catalog, missing fields and enablement defaults.

Acceptance verified in isolated HA: all 243 synthetic scalar leaves register, all can be enabled; 16 enabled and 227 disabled by default. A real in-memory Recorder test proves disabled entities have no rows, static metadata is omitted and prior history survives disabling. No shadow store. All 81 patterns have German/English metadata and truthful fallbacks.

Default-enabled: grid availability (1), panel battery percentage (1), ten load supply states (10), nominal grid settings (2), raw daily energy counters (2). Inferred power/storage/temperature readings remain raw diagnostics without units/statistics. Only the valid documented panel battery percentage has measurement statistics.

M2 commit: `feat: expose complete bounded quota entities with selective history`; exact SHA will be linked by the validation-results commit. Current local checks: Ruff, formatter, catalog regeneration check, compileall, and the full offline pytest suite. See the verification record below for the final count and CI results.

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
- [ ] Optional HACS default listing and Home Assistant brands contribution.
- [ ] First release only after user confirms real-hardware acceptance.

Acceptance: repeatable install with no unrelated HA changes or data loss.

Each completed milestone must include commit link, test commands/outcomes and remaining risks. Never mark an untested milestone complete.

## Verification record (2026-10-25)

- Python 3.14.4, Home Assistant 2026.10.3; no real EcoFlow requests or hardware writes.
- `ruff check custom_components tests scripts` and `ruff format --check custom_components tests scripts`: **passed** (22 Python files).
- `python scripts/sync_catalog.py --check` and `python -m compileall -q custom_components`: **passed**.
- `pytest -q --tb=short --show-capture=no --timeout=30 --cov=custom_components.ecoflow_smart_home_panel_v1 --cov-report=term-missing`: **186 passed**, 98% line coverage (573 statements, 9 uncovered), 8.58 seconds.
- Official hassfest and HACS run in GitHub Actions after push; Docker is unavailable in this WSL environment. HACS skips only `brands`, explicitly deferred to M4.
- Remaining: user hardware read validation, actual HACS installation/upgrade acceptance, authoritative model/error metadata, inferred units/scales and daily counter reset semantics. M3 controls and M4 release approval remain open.
