# Security and data handling

The maintained code is on `main` (currently 0.4.x). Review the changelog before
upgrading; this is an independent custom integration, not a Home Assistant Core
or EcoFlow-certified product.

- Keys and panel serials reside in HA-managed config entries. Protect HA backups
  and filesystem access: config-entry storage is not a separate secrets vault.
- HTTPS requests and MQTT use certificate verification. No inbound listener,
  user-supplied endpoint, MQTT publishing or actuator write during setup/polling.
- Every explicit control transaction is serialized and verified from fresh HTTP
  quota. Rate limits, timeouts and incomplete responses cannot prove success.
- Responses, traversal and entity discovery are bounded. Unknown diagnostics are
  disabled by default. No custom quota archive or external history database.
- Logs, notification messages and downloaded integration diagnostics exclude
  credentials, serials and raw payloads. Entity unique IDs internally include
  the serial for stable identity; do not publish a raw HA entity/config registry.
- A successful cloud confirmation is not an electrical interlock. The integration
  does not control other applications or external writers to the panel.

For ordinary bugs, use the repository issue tracker with version, symptom and
redacted integration diagnostics. Never upload credentials, HA tokens, complete
backups, `.storage` files or production quota responses. If a credential was
exposed, revoke/replace it in EcoFlow and reconfigure the integration.
For a vulnerability, use GitHub's private vulnerability reporting if offered by
the repository; otherwise contact the maintainer privately before posting exploit
details. No external reporting service or automatic telemetry is configured.
