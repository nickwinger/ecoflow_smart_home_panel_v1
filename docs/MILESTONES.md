# Development milestones

Milestone status below distinguishes repository scaffolding from functioning Home Assistant functionality.

## M0 — project bootstrap [DONE]

- [x] Public dedicated SHP v1 repository and HACS-compatible directory layout.
- [x] README, license, AGENTS.md, CODEX_TASK.md, source map, entity/history contract.
- [x] Quota metadata catalog seed with German labels and evidenced explanations.
- [x] Minimal HA manifest/module placeholders and GitHub Actions starting points.

Acceptance: files present in GitHub. **No claim of a working integration at this milestone.**

## M1 — UI configuration, API and polling [TODO]

- [ ] Asynchronous signed EcoFlow Cloud client, credentials via HA config flow, unique config entries by panel serial.
- [ ] Connection and version checks (SHP v1 only), reauth and meaningful errors.
- [ ] One DataUpdateCoordinator with shared timed fetch and appropriate rate/error handling.
- [ ] Test config setup/unload/reload and cloud responses offline.

Acceptance: read-only HA integration loads in test instance and fetches valid SHP v1 quota.

## M2 — complete selectable entity model [TODO]

- [ ] Generic raw quota leaf coverage incl. dotted keys, nested dicts and indexed lists.
- [ ] All 81 catalog descriptions/patterns integrated, plus truthful fallback for unknown paths.
- [ ] Stable unique IDs, friendly de/en names, path, description, confidence, verified states/units.
- [ ] Essential sensors enabled, diagnostics disabled; no independent historical storage.
- [ ] Valid state classes/long-term statistics for supported numeric readings.
- [ ] Unit tests comparing fixture leaves to entity catalog, missing fields and enablement defaults.

Acceptance: each quota scalar leaf can be made an entity; enabling records via HA Recorder; disabled ones don't.

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
