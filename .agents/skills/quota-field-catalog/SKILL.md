---
name: quota-field-catalog
description: Use when implementing or reviewing EcoFlow SHP v1 get_quota_all field extraction, entity coverage, friendly German/English names, explanations, validity/units, disabled-by-default diagnostics and Recorder behavior.
---

# Quota coverage and naming review

1. Read `docs/quota-field-guide.json`, `docs/ENTITY_CATALOG.md`, `docs/ARCHITECTURE.md` and the read-only reference `ecoflow_api.py` and `ecoflow_values.py` from `nickwinger/homeassistant_config`.
2. For each catalog path, retain raw path, friendly German/English label, actual *explanation*, units and enum where verified, and a confidence flag. Never turn unknown or inferred information into documented fact.
3. Handle catalog patterns `[]` against concrete paths such as `heartbeat.loadCmdChCtrlInfos[6].ctrlSta`; do not lose the 1-based human circuit number.
4. Flatten `quota["data"]` generically including literal dotted keys, nested dicts, lists, booleans, strings and numeric leaf values. Use bounded recursion and stable indexing. Do not treat `None` as zero.
5. Every safe scalar leaf is a discoverable entity, including unknown properties. Known high-value measurements may default enabled, raw diagnostic leaves default disabled.
6. Add German/English translated friendly names; expose explanatory metadata so that a user can learn what a quota property actually means. Unknown semantics should be clearly described as such. Avoid verbose full raw JSON extra attributes.
7. Test that the discovered set of source paths equals the safe fixture leaves, unknown paths are covered, metadata resolves correctly, and missing partial fields report unavailable/unknown.
8. Assert disabled entities produce no new Recorder history and no other logging/archiving stores quota snapshots. Valid numeric measurements only get state classes.
9. Update catalog documentation and tests whenever decoding facts change. Never silently guess unknown scaling, codes, channel offsets or reset behavior.
