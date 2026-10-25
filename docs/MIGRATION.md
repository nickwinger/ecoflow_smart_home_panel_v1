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
   incomplete. This version offers no write-capable entities/services.
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
   delete helpers, or enable future M3 controls during this read-only acceptance.

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

Verify that each named circuit displays only its EcoFlow channel name plus the
reading name. Unnamed circuits use `Stromkreis <number>` or `Circuit <number>`
according to the HA system language. An explicit custom HA entity name still
wins; clear that override manually if you want the generated name instead.

The expanded synthetic fixture has 245 leaves, 44 enabled and 201 disabled.
The extra 28 enabled readings remain under Diagnostics. Their state history starts
when enabled (unless excluded by Recorder); their community evidence does not
create new long-term statistics. This upgrade changes no physical device setting.
