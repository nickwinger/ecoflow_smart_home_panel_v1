# Changelog

## 0.4.0 — 2026-10-25 (available from main)

- Optional German/English persistent HA notification after failed all-circuit
  switching. Off by default; repeated failures update the same entry/target
  message. Full success to the same target, option removal or entry removal
  clears it. No changes to switching order, retries, timing or automation errors.
- HACS distribution checks using pinned official validators and installation
  code, including clean installation, upgrade from 0.3.2 and loading the installed
  files in a separate HA test process. Local brand validation enabled in CI.
- Installation, upgrade, rollback, helper migration, security, credits and
  release acceptance documented. CI stays manual-only.
- Config-entry schema 1.2, existing identities/options and 245-leaf coverage
  unchanged. No automatic control opt-in or history migration.

No GitHub release has been published. HACS custom repositories can install main;
native batch/mode hardware acceptance is still separate from offline validation.

## 0.3.2

- Sanitized HA error logging and real automation-sequence tests for completion,
  failure, cancellation and unavailable-button behavior. 533 offline tests passed.

## 0.3.1

- Restore the complete `ecoflow/shp_mode.py` batch sequence, including continuing
  after individual failures and all final pauses. Differential trace tests.

## 0.3.0

- Passive TLS MQTT connection for circuit-power updates with the phone app closed.
- Automatic/manual selects and batch/cancel buttons; polling range 1–600 seconds.

## 0.2.x

- Opt-in source and charging controls; simpler v1-only setup and polling diagnostics.

## 0.1.x

- Native configuration, signed async API, full bounded quota discovery,
  German/English descriptions, selective Recorder history and requested defaults.
