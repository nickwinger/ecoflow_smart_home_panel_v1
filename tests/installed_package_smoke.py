"""Executed only from the temporary HACS-installed directory in a fresh process."""

import asyncio
import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

DOMAIN = "ecoflow_smart_home_panel_v1"
DATA = {
    "access_key": "test-access",
    "secret_key": "test-secret",
    "serial": "SHP-TEST-0001",
    "region": "eu",
}


@pytest.fixture
def hass_config_dir():
    """Load only the actual directory produced by the HACS installer."""
    return str(Path.cwd())


async def test_installed_package_lifecycle(hass, enable_custom_integrations):
    import custom_components.ecoflow_smart_home_panel_v1 as integration

    installed_path = await asyncio.to_thread(Path(integration.__file__).resolve)
    assert installed_path.is_relative_to(Path.cwd())
    quota = {
        "heartbeat.gridSta": 1,
        "heartbeat.backupBatPer": 61,
        "heartbeat.loadCmdChCtrlInfos": [{"ctrlSta": 0, "ctrlMode": 0} for _ in range(10)],
        "heartbeat.backupCmdChCtrlInfos": [{"ctrlSta": 0}, {"ctrlSta": 2}],
    }
    with (
        patch(
            f"custom_components.{DOMAIN}.api.EcoFlowClient.get_quota_all",
            AsyncMock(return_value=quota),
        ),
        patch(f"custom_components.{DOMAIN}.api.EcoFlowClient.put_quota", AsyncMock()) as put,
        patch(f"custom_components.{DOMAIN}.telemetry.PowerTelemetry.start"),
    ):
        upgraded = os.environ["ECOFLOW_INSTALL_UPGRADE"] == "1"
        if upgraded:
            entry = MockConfigEntry(
                domain=DOMAIN,
                version=1,
                minor_version=2,
                data=DATA,
                unique_id=DATA["serial"],
                options={
                    "poll_interval": 27,
                    "enable_source_controls": True,
                    "enable_charge_controls": True,
                    "enable_batch_controls": True,
                },
            )
            entry.add_to_hass(hass)
            registry = er.async_get(hass)
            prior = registry.async_get_or_create(
                "sensor",
                DOMAIN,
                f'{DATA["serial"]}:quota:["heartbeat.backupBatPer"]',
                config_entry=entry,
                suggested_object_id="existing_battery",
                disabled_by=er.RegistryEntryDisabler.USER,
            )
            registry.async_update_entity(prior.entity_id, name="My battery")
            assert await hass.config_entries.async_setup(entry.entry_id)
        else:
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": "user"}, data=DATA
            )
            entry = result["result"]
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED
        assert entry.data == DATA
        assert entry.runtime_data.poll_interval == (27 if upgraded else 5)
        assert not entry.options.get("notify_batch_failures", False)
        if upgraded:
            preserved = registry.async_get(prior.entity_id)
            assert preserved.name == "My battery"
            assert preserved.disabled_by is er.RegistryEntryDisabler.USER
            assert entry.options["enable_batch_controls"] is True
        else:
            assert not any(
                state.domain in {"select", "switch", "button"} for state in hass.states.async_all()
            )
        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert "notify_batch_failures" in {str(key) for key in result["data_schema"].schema}
        assert await hass.config_entries.async_reload(entry.entry_id)
        assert await hass.config_entries.async_unload(entry.entry_id)
        assert await hass.config_entries.async_remove(entry.entry_id)
        put.assert_not_awaited()
    manifest = json.loads((Path(integration.__file__).parent / "manifest.json").read_text())
    assert manifest["version"] == "0.4.0"
