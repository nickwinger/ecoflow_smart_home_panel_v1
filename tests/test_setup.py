"""Setup lifecycle and failure handling using real HA config entries."""

from datetime import timedelta

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import device_registry as dr

from custom_components.ecoflow_smart_home_panel_v1.api import (
    AuthenticationError,
    EcoFlowError,
    RateLimitError,
)
from custom_components.ecoflow_smart_home_panel_v1.const import DOMAIN

from .conftest import DATA


async def test_lifecycle(hass, entry, mock_quota):
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    device = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)[0]
    assert (DOMAIN, DATA["serial"]) in device.identifiers
    assert device and "SHP-TEST" not in device.name
    assert await hass.config_entries.async_reload(entry.entry_id)
    assert mock_quota.await_count == 2
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert await hass.config_entries.async_remove(entry.entry_id)


@pytest.mark.parametrize(
    "error,state",
    [
        (EcoFlowError("Offline"), ConfigEntryState.SETUP_RETRY),
        (AuthenticationError(), ConfigEntryState.SETUP_ERROR),
    ],
)
async def test_setup_failure(hass, entry, mock_quota, error, state):
    mock_quota.side_effect = error
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is state


async def test_backoff_and_recovery(hass, entry, mock_quota, quota):
    await hass.config_entries.async_setup(entry.entry_id)
    coordinator = entry.runtime_data
    mock_quota.side_effect = RateLimitError(300)
    await coordinator.async_refresh()
    assert not coordinator.last_update_success
    assert coordinator.update_interval == timedelta(seconds=300)
    mock_quota.side_effect = None
    mock_quota.return_value = {"heartbeat.gridSta": 0}
    await coordinator.async_refresh()
    assert coordinator.last_update_success
    assert coordinator.data == {"heartbeat.gridSta": 0}
    assert coordinator.update_interval == timedelta(seconds=60)
    await hass.config_entries.async_unload(entry.entry_id)


async def test_scheduled_poll_and_unload(hass, entry, mock_quota):
    from homeassistant.util import dt as dt_util
    from pytest_homeassistant_custom_component.common import async_fire_time_changed

    await hass.config_entries.async_setup(entry.entry_id)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=65))
    await hass.async_block_till_done()
    assert mock_quota.await_count == 2
    await hass.config_entries.async_unload(entry.entry_id)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=140))
    await hass.async_block_till_done()
    assert mock_quota.await_count == 2
