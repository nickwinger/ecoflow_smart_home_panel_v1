# EcoFlow Smart Home Panel v1 — Home Assistant integration

> **Status: M1 read-only core implemented and tested offline; M2 entity work follows.** Not hardware-validated or release-ready. No device controls are exposed.

A developing HACS-installable, native Home Assistant integration for **EcoFlow Smart Home Panel, first generation (v1)**. This repository deliberately **does not target Smart Home Panel 2 or newer generations**.

## Goals

- Reuse the *existing, already working* EcoFlow Open API and control logic from [nickwinger/homeassistant_config/ecoflow](https://github.com/nickwinger/homeassistant_config/tree/main/ecoflow), without touching that deployment.
- Configure access key, secret key and device serial through Home Assistant's UI; do not require external Python jobs or input helpers.
- Expose useful readings and explicit controls as native Home Assistant entities.
- Expose **every scalar leaf** of successful quota responses as a discoverable entity, including fields in arrays; additional/unknown diagnostic entities start **disabled by default**.
- Give entities **friendly, translatable names and meaningful explanations**, backed by an evidence-graded quota field catalog. Keep the original quota property path discoverable.
- **History exclusively through Home Assistant Recorder for enabled entities.** No separate full-JSON archive, SQLite/CSV recorder, or shadow historical store. Disabled entities must not generate new history.
- Implement safe, verified, opt-in channel/source switching and battery charge control without changing startup power routing.
- Support HACS custom repository installation first; pursue broader HACS listing after quality, tests and branding checks.

## Development

Read [CODEX_TASK.md](CODEX_TASK.md), [AGENTS.md](AGENTS.md), [docs/MILESTONES.md](docs/MILESTONES.md), and [docs/ENTITY_CATALOG.md](docs/ENTITY_CATALOG.md) before coding. The reference source repository is not this integration: it is read-only input.

The core supports UI setup, duplicate-serial prevention, credential replacement/reauthentication, a shared async client, polling every 60 seconds (30–900 configurable), bounded failure backoff, rate-limit delays and clean unload. The initial device check requires explicit SHP v1 confirmation and the v1 control-array topology; it is not authoritative model identification. HTTP 401/403 triggers reauth; undocumented application errors remain generic failures. Development uses Home Assistant 2026.10.3 and Python 3.14 in an isolated test environment.

## Quota name examples

| Quota path | German-friendly name | Interpretation |
| --- | --- | --- |
| `heartbeat.gridSta` | Netzstatus | Grid availability, documented 0/1 |
| `heartbeat.backupBatPer` | Batteriestand Backup | Percent, validate bounds; never silently guess scaling |
| `channelPower.infoList[6].chWatt` | Stromkreis 7 – Leistung | Raw numeric power with documented/inferred confidence |
| `heartbeat.loadCmdChCtrlInfos[6].ctrlSta` | Stromkreis 7 – Versorgungsquelle | 0 grid, 1 battery, other values unknown |
| `selfCheck.result` | Selbsttest – Ergebniscode | Raw code, unknown enum meaning; diagnostic and disabled by default |

Detailed names, descriptions, enum mappings, confidence and raw paths: [docs/quota-field-guide.json](docs/quota-field-guide.json). Some values are documented only by inference: no fabricated units or enums.

## Privacy and safety

Never commit API keys, tokens, device serials, production cache files, logs or identifying example payloads. Energy routing and charging are safety-relevant: commands should be user initiated, explicitly enabled, serialized and verified against fresh responses, never optimistic.

## License

MIT, see [LICENSE](LICENSE). This project is independently maintained and is not affiliated with EcoFlow or Home Assistant.

Official EcoFlow reference: [Smart Home Panel v1 API](https://developer-eu.ecoflow.com/us/document/PP4?id=2058837749501956098). Local manufacturer copies are listed in [reference sources](docs/REFERENCE_SOURCES.md).
