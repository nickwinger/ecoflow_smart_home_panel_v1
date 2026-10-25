# ⚡ EcoFlow Smart Home Panel v1

<img src="custom_components/ecoflow_smart_home_panel_v1/brand/icon.png" width="128" alt="EcoFlow Smart Home Panel v1 icon" />

**Bring your first-generation EcoFlow Smart Home Panel into Home Assistant.** Monitor grid power, backup batteries, circuit status and detailed device diagnostics — with native entities and Home Assistant history.

![Home Assistant 2026.10+](https://img.shields.io/badge/Home%20Assistant-2026.10%2B-41BDF5)
![Version 0.3.0](https://img.shields.io/badge/version-0.3.0-blue)
![Opt-in controls](https://img.shields.io/badge/controls-opt--in-orange)
[![MIT License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

> [!IMPORTANT]
> **Early preview (v0.3.0) · Read-only by default.** Supports the **original Smart Home Panel (v1)**, not SHP2 or newer models. Source switching and charging controls require separate opt-in. Source switching and charging have been confirmed by the owner; the new mode/batch controls still need hardware acceptance. Test in an isolated Home Assistant instance before production use.

## ✨ Features

- ⚡ **Live monitoring** — grid availability, backup battery level, circuit power-source status and energy readings.
- 📊 **Detailed diagnostics** — discover individual values exposed by EcoFlow's Quota API, including per-circuit and per-battery data.
- 🏷️ **Understandable entities** — English/German names, descriptions and original quota paths.
- 🕘 **Selective history** — Home Assistant Recorder stores enabled entities; most advanced diagnostics start disabled to save space.
- 🎛️ **Optional controls** — ten grid/battery selects, ten automatic/manual selects, two charging switches and three separately enabled batch buttons.
- ☁️ **Cloud connection** — authenticated EcoFlow API polling, configurable update interval and error handling.

## 📦 Installation

**Requirements:** Home Assistant **2026.10+**, an **EcoFlow Smart Home Panel v1**, and EcoFlow Developer **Access Key**, **Secret Key** and panel **serial number**.

### Option A: HACS (recommended)

This integration is available as a **custom HACS repository**. It is **not yet listed in the default HACS catalog**.

1. Open **HACS** in Home Assistant.
2. Open the **⋮ menu → Custom repositories**.
3. Add `https://github.com/nickwinger/ecoflow_smart_home_panel_v1` and select **Integration**.
4. Find **EcoFlow Smart Home Panel v1** in HACS and select **Download**.
5. **Restart Home Assistant**, then follow [Configuration](#-configuration).

[HACS help: Custom repositories](https://www.hacs.dev/docs/faq/custom_repositories/)

### Option B: Manual installation

1. Download this repository as a ZIP file.
2. Copy the directory `custom_components/ecoflow_smart_home_panel_v1` to `<config>/custom_components/` in Home Assistant.
3. **Restart Home Assistant** and follow [Configuration](#-configuration).

Your resulting path should be:

```text
<config>/custom_components/ecoflow_smart_home_panel_v1/manifest.json
```

## 🔑 Configuration

1. Go to **Settings → Devices & services → Add integration**.
2. Search for **EcoFlow Smart Home Panel v1**.
3. Enter your **Access Key**, **Secret Key** and **panel serial number**.
4. Select the correct API region (**EU** or **Global**). The integration checks the supported v1 quota layout automatically.

That's it! Your panel and available entities will appear under **Devices & services**. You can adjust polling in the integration **Options** (default: **5 seconds**, configurable from **1–600 seconds**). Entries without a saved interval adopt this default after restart; valid saved custom intervals are preserved; older values outside the range are clamped.

> The integration uses the EcoFlow Developer API over the internet; it does not connect directly to the panel on your local network.

## 🎛️ Optional control

In **Options**, independently enable circuit controls (source and automatic/manual mode) or charging controls. The controls appear on the panel’s device page. No Home Assistant helpers are required. Enabling them sends no commands; only an explicit action changes the panel. Each write is followed by fresh status verification, with bounded retries and serialization. Startup and polling never switch anything.

Enabling batch controls adds **All circuits to grid**, **All circuits to battery** and **Cancel switching** buttons to the device page. A button press starts the chosen sequence; enabling the option alone does nothing. Batches stop on the first failure. The existing confirmed action remains available for automations. See [control behavior and checks](docs/CONTROLS.md).

Automatic mode returns supply control to the panel. Manual mode holds the currently reported supply source. The diagnostic “Control mode” sensor remains a separate status display.

The integration keeps a read-only connection to EcoFlow open so circuit power continues updating with the phone app closed. No extra login, MQTT broker or helper is needed. If that connection loses fresh power reports, circuit power becomes unavailable until reports resume. See [live-data diagnosis](docs/LIVE_DATA.md).

## 📈 Entities & history

| Example | What it tells you |
| --- | --- |
| Grid availability | Whether utility grid power is available |
| Backup battery level | Backup system charge percentage (when valid) |
| Circuit 1–10 power source | Grid, battery or off/unknown |
| Grid voltage & frequency | Reported nominal grid settings |
| Daily grid/backup energy | Raw daily readings (not yet Energy Dashboard totals) |
| Circuit diagnostics | Power and control mode for all ten circuits, enabled by default |
| Storage diagnostics | Battery level, input/output power and temperature for both entries, enabled by default |
| Other diagnostics | Additional available quota fields, mostly disabled by default |

The synthetic test fixture covers **245/245 scalar leaves: 44 enabled, 201 disabled**. Opt-in controls add up to 25 entities. Circuits always use **Circuit N** / **Stromkreis N**, according to Home Assistant’s system language; EcoFlow app names do not replace them. Explicit names you set in HA are preserved.

**Want more data?** Open the panel's **Entities** list, show disabled entities and enable only the diagnostics you need. The complete list depends on your device's responses.

- **Enabled entities:** normal Home Assistant history, subject to your Recorder settings.
- **Disabled entities:** no new recorded history.
- **Long-term statistics:** only for measurements with verified types, units and state classes. Not every numeric quota field qualifies.

For full field descriptions and technical details, see the [entity catalog](docs/ENTITY_CATALOG.md). For polling versus actual value changes, see [update timestamps](docs/ARCHITECTURE.md#polling-and-value-change-timestamps).

## 🛠️ Troubleshooting

| Problem | Try this |
| --- | --- |
| Integration not found | Restart Home Assistant and refresh your browser after installation |
| Setup fails | Verify the keys, serial number and EU/Global region; retry if EcoFlow returns an incomplete response |
| A value is unavailable or unknown | The API may have omitted it or returned an unrecognized code; the integration deliberately avoids guessing |
| Channel power says “seconds ago” despite 5-second polling | Check both quota polling and `power_telemetry_connected` / `power_telemetry_age_seconds` in diagnostics. Successful HTTP polling alone can return frozen cloud values; the read-only MQTT connection keeps updates flowing |
| Too many entities | Most raw diagnostic entities are disabled by default; enable only what you need |

[Report an issue](https://github.com/nickwinger/ecoflow_smart_home_panel_v1/issues)

## 💻 Development

Develop and test against a **separate, disposable Home Assistant instance** — never your production configuration.

- [Local VS Code / WSL Dev Container guide](docs/LOCAL_LIVE_TEST.md)
- [Developer scripts and complete HA DEV reinstall](scripts.md)
- [Technical architecture](docs/ARCHITECTURE.md)
- [Migration from existing helper scripts](docs/MIGRATION.md)
- [API references and data provenance](docs/REFERENCE_SOURCES.md), including all three supplied HTML references
- [Official EcoFlow SHP v1 API](https://developer-eu.ecoflow.com/us/document/PP4?id=2058837749501956098)

## 📄 License & disclaimer

Licensed under [MIT](LICENSE). Unofficial community project — **not affiliated with or endorsed by EcoFlow or Home Assistant**. EcoFlow and Smart Home Panel are trademarks of their respective owners.
