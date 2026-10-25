# Migration approach (future / not executable yet)

There is currently a working external Python HTTP-to-Home-Assistant helper setup. It must not be removed merely because the new integration can be installed.

1. Implement and test read-only integration in parallel, without adding any write-capable automation or services to the running system.
2. Compare measured values, source/state semantics, channel numbering, battery data and field availability over multiple API cycles.
3. Enable only desired native entities. Understand that their HA Recorder history starts from first enabled state; historical helper records do not automatically move with them.
4. Verify sensible state classes and the HA statistics page; take a recorder/database backup before changing existing helpers, entity IDs or settings.
5. Only after explicit user approval, disable the old helper write jobs, remap dashboards/automations to new native entity IDs and test control paths on real hardware under supervision.
6. Preserve old history unless there is an explicit independent request to migrate or delete it. Disable old helpers only when no automations reference them.
7. Keep a rollback path to prior Python integration (never run conflicting polling/command writers inadvertently).

No automatic migration, automatic device switching, import of old JSON histories or deletion of helper data belongs in the initial installation.
