# Distribution and release acceptance

## Current distribution

Version 0.4.0 is installable from the default branch through HACS **Custom
repositories → Integration**. This path does not require a GitHub release.
All runtime modules, catalog data, translations, service descriptions and local
brand assets reside inside the single integration directory. No DEV configuration,
test source, reference documents or credentials are installed.

Source switching and charging have owner confirmation. Native mode/batch hardware
acceptance remains to be recorded by the owner. Installation performs no automatic
production migration. Offline simulation is not actual device acceptance.

## Before a tagged GitHub release

1. Record owner verification of monitoring with the app closed, individual
   source/charge operation and native mode/batch controls. Development/CI never
   sends these commands. Record aggregate results, not production payloads.
2. Record HACS installation/upgrade on the owner's instance, preserved entity
   names/options/history, and reauthentication if keys are replaced.
3. Run the complete [offline/HACS checks](../CONTRIBUTING.md), official hassfest
   and catalog synchronization on the exact candidate commit.
4. Align `manifest.json`, README and changelog version. Review upgrade notes,
   supported HA version, dependency changes and rollback instructions.
5. After explicit owner release approval, create a matching version tag and
   GitHub release with changelog and validation links. A separate ZIP asset is
   unnecessary for this layout; HACS can download the tagged source.
   No release, deployment or hardware action is triggered by CI.

## HACS catalog metadata

Custom repositories are the supported distribution. Default-catalog submission
is optional and not needed to install. Local brand files are validated.
Repository topics still need maintainer administration access if catalog
inclusion is desired; this is the only ignored HACS check. The optional category
is omitted because the available official hassfest image rejects that key;
HACS reports a non-failing warning.

## Reproducibility and limits

The M4 harness pins official HACS source
`a15e87ec0d1c82e58f1ddbaf17669d3eaa261eb8`, checks its revision and executes its
validators/install routines with local archives and recorded public metadata.
Fresh and upgrade installations are loaded in separate HA test processes.
This verifies distribution without contacting EcoFlow or modifying running HA.
It does not exercise GitHub login or clicks in the HACS frontend.

The [milestone record](MILESTONES.md) records versions, validator image, commands,
results and remaining owner checks. Older CI runs do not validate a newer commit.
