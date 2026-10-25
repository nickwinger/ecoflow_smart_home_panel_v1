# Migration and manual read-only validation

There is currently a working external Python HTTP-to-Home-Assistant helper setup. It must not be removed merely because the new integration can be installed.

1. The M1/M2 read-only integration is offline-tested; validate it in an isolated HA instance in parallel, without adding any write-capable automation or services to the running system.
2. Compare measured values, source/state semantics, channel numbering, battery data and field availability over multiple API cycles.
3. Enable only desired native entities. Understand that their HA Recorder history starts from first enabled state; historical helper records do not automatically move with them.
4. Verify sensible state classes and the HA statistics page; take a recorder/database backup before changing existing helpers, entity IDs or settings.
5. Only after explicit user approval, disable the old helper write jobs, remap dashboards/automations to new native entity IDs and test control paths on real hardware under supervision.
6. Preserve old history unless there is an explicit independent request to migrate or delete it. Disable old helpers only when no automations reference them.
7. Keep a rollback path to prior Python integration (never run conflicting polling/command writers inadvertently).

No automatic legacy-helper migration, automatic device switching, import of old JSON histories or deletion of helper data belongs in the initial installation.

## Manual acceptance checklist (not performed by development)

1. Install via a HACS custom repository in an isolated HA 2026.10+ instance and
   configure the confirmed first-generation panel. Retry if initial topology is
   incomplete. Leave the source, charge and batch control options off; M3 defaults to read-only.
2. Compare grid status, battery percentage and circuit numbering with the existing
   display over several shared polls. Treat inferred/raw values accordingly.
3. Inspect disabled entities, enable one diagnostic and confirm it gains state
   history. Disable it and confirm polling no longer creates history for it;
   existing historical rows remain until normal retention or explicit deletion.
4. Review entity descriptions in German/English, rename a channel in the existing
   source UI if desired, then verify native unique IDs/history remain stable.
5. Reload, restart and change polling options. Existing registry choices should
   persist; a missing cloud field must show unavailable, never a cached healthy state.
6. Check HA's statistics diagnostics: only the validated panel battery percentage
   is a measurement statistic. Daily counters are not Energy Dashboard totals.
7. Leave existing helper jobs and automations operational. Do not migrate histories,
   delete helpers, or enable M3 controls during this read-only acceptance.

The scaffold had no persisted config-entry schema to migrate. This implementation
starts at config-entry version 1. No legacy helper import or automatic cutover is
performed; native entities start their own history when enabled.

## Upgrade to 0.1.1: names and requested diagnostic defaults

After updating the integration files, restart the isolated HA instance. The config
entry moves from schema 1.1 to 1.2. Existing circuit channel power/control mode and
storage battery level/input power/output power/temperature entities that were
previously disabled by the integration become enabled once. User-disabled or
device-disabled entities stay disabled; these may be enabled manually if desired.
Existing entity IDs, custom HA names and Recorder history are preserved.

Circuits now always show **Stromkreis N** / **Circuit N** according to HA’s system
language, regardless of EcoFlow app labels. HA custom names, unique IDs and history
are preserved. The optional cloud label remains diagnostic metadata.

The expanded synthetic fixture has 245 leaves, 44 enabled and 201 disabled.
The extra 28 enabled readings remain under Diagnostics. Their state history starts
when enabled (unless excluded by Recorder); their community evidence does not
create new long-term statistics. This upgrade changes no physical device setting.

## Upgrade to 0.2.0: controls remain opt-in

Config-entry schema remains 1.2. Existing polling intervals, entity IDs, names,
disable choices and history are preserved. The three new control options default
to false on both new and upgraded entries; no migration turns them on. Controls
are never restored as commands. An explicit option opt-in adds ten source selects
and/or two charging-mode switches. Batch switching needs a separate option.

Follow [the M3 read-only acceptance checklist](CONTROLS.md#manuelle-abnahme-ohne-schalten).
Removing an option cancels commands during reload and removes its live control
entities, while HA retains registry entries/history (possibly unavailable
placeholders). Re-enabling preserves explicit user entity disables. Do not connect
existing write automations to these entities or run competing writers until the
owner has approved a separate supervised hardware validation and cutover.

## Upgrade to 0.2.1: simpler setup and polling diagnostics

The v1 confirmation checkbox is removed. Existing entries continue working;
legacy confirmation data is ignored, and the quota-topology check remains.
Polling defaults, saved options, entity IDs and enablement choices are unchanged.
New aggregate diagnostics distinguish the last successful retrieval from a
changed power value. See [update timestamps](ARCHITECTURE.md#polling-and-value-change-timestamps).
In HA DEV, restart the existing service and reopen the configuration dialog;
no volume reset or recreation of the integration is necessary.

For 0.3.0, existing source-control opt-ins also expose ten mode selects. An existing
batch opt-in exposes three buttons; none runs automatically. Allow outbound TLS
8883 to EcoFlow for continuous power updates with the app closed. Credentials are
obtained from the existing shared API client; no local MQTT broker or new login.
Polling defaults to 5 seconds with 1–600 allowed; old larger intervals become 600.
