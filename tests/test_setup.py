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
    assert entry.runtime_data.poll_interval == 5
    assert entry.runtime_data.update_interval == timedelta(seconds=5)
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
    mock_quota.side_effect = EcoFlowError("Offline")
    await coordinator.async_refresh()
    assert coordinator.update_interval == timedelta(seconds=10)
    mock_quota.side_effect = RateLimitError(300)
    await coordinator.async_refresh()
    assert not coordinator.last_update_success
    assert coordinator.update_interval == timedelta(seconds=300)
    mock_quota.side_effect = None
    mock_quota.return_value = {"heartbeat.gridSta": 0}
    await coordinator.async_refresh()
    assert coordinator.last_update_success
    assert coordinator.data.leaves == {("heartbeat.gridSta",): 0}
    assert coordinator.update_interval == timedelta(seconds=5)
    await hass.config_entries.async_unload(entry.entry_id)


async def test_scheduled_poll_and_unload(hass, entry, mock_quota):
    from homeassistant.util import dt as dt_util
    from pytest_homeassistant_custom_component.common import async_fire_time_changed

    await hass.config_entries.async_setup(entry.entry_id)
    now = dt_util.utcnow()
    async_fire_time_changed(hass, now + timedelta(seconds=3))
    await hass.async_block_till_done()
    assert mock_quota.await_count == 1
    async_fire_time_changed(hass, now + timedelta(seconds=6))
    await hass.async_block_till_done()
    assert mock_quota.await_count == 2
    await hass.config_entries.async_unload(entry.entry_id)
    async_fire_time_changed(hass, now + timedelta(seconds=12))
    await hass.async_block_till_done()
    assert mock_quota.await_count == 2


async def test_options_reload_preserves_identity(hass, entry, mock_quota):
    await hass.config_entries.async_setup(entry.entry_id)
    previous = entry.runtime_data
    hass.config_entries.async_update_entry(entry, options={"poll_interval": 90})
    await hass.async_block_till_done()
    assert entry.runtime_data is not previous
    assert entry.runtime_data.poll_interval == 90
    assert entry.unique_id == DATA["serial"]
    await hass.config_entries.async_unload(entry.entry_id)


async def test_runtime_auth_triggers_reauth(hass, entry, mock_quota):
    await hass.config_entries.async_setup(entry.entry_id)
    mock_quota.side_effect = AuthenticationError("Cloud authentication rejected")
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    flows = hass.config_entries.flow.async_progress()
    assert any(flow["context"].get("source") == "reauth" for flow in flows)
    assert not entry.runtime_data.last_update_success
    await hass.config_entries.async_unload(entry.entry_id)


async def test_identical_channel_power_reports_each_poll_without_fake_change(
    hass, entry, mock_quota, quota, freezer
):
    from homeassistant.helpers import entity_registry as er
    from homeassistant.util import dt as dt_util
    from pytest_homeassistant_custom_component.common import async_fire_time_changed

    mock_quota.return_value = {
        **quota,
        "channelPower.infoList": [{"chWatt": 123} for _ in range(10)],
    }
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    coordinator = entry.runtime_data
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, coordinator.unique_id(("channelPower.infoList", 6, "chWatt"))
    )
    initial = hass.states.get(entity_id)
    changed = initial.last_changed
    updated = initial.last_updated
    reported = initial.last_reported
    start = dt_util.utcnow()
    for cycle in range(1, 4):
        now = start + timedelta(seconds=6 * cycle)
        freezer.move_to(now)
        async_fire_time_changed(hass, now)
        await hass.async_block_till_done()
        state = hass.states.get(entity_id)
        assert mock_quota.await_count == cycle + 1
        assert coordinator.successful_quota_refreshes == cycle + 1
        assert state.last_reported > reported
        assert state.last_changed == changed
        assert state.last_updated == updated
        assert state.state == "123"
        reported = state.last_reported
    mock_quota.return_value["channelPower.infoList"][6]["chWatt"] = 321
    now = start + timedelta(seconds=24)
    freezer.move_to(now)
    async_fire_time_changed(hass, now)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == "321"
    assert state.last_changed > changed
    assert coordinator.successful_quota_refreshes == 5
    await hass.config_entries.async_unload(entry.entry_id)


async def test_poll_diagnostics_distinguish_success_and_backoff(hass, entry, mock_quota):
    from custom_components.ecoflow_smart_home_panel_v1.diagnostics import (
        async_get_config_entry_diagnostics,
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    before = await async_get_config_entry_diagnostics(hass, entry)
    assert before["successful_quota_refreshes"] == 1
    assert before["last_successful_quota_refresh"] is not None
    assert before["effective_poll_interval_seconds"] == 5
    assert before["polling_disabled"] is False
    mock_quota.side_effect = RateLimitError(180)
    await entry.runtime_data.async_refresh()
    failed = await async_get_config_entry_diagnostics(hass, entry)
    assert failed["successful_quota_refreshes"] == 1
    assert failed["last_successful_quota_refresh"] == before["last_successful_quota_refresh"]
    assert failed["last_update_success"] is False
    assert failed["consecutive_poll_failures"] == 1
    assert failed["effective_poll_interval_seconds"] == 180
    mock_quota.side_effect = None
    await entry.runtime_data.async_refresh()
    recovered = await async_get_config_entry_diagnostics(hass, entry)
    assert recovered["successful_quota_refreshes"] == 2
    assert recovered["last_update_success"] is True
    assert recovered["consecutive_poll_failures"] == 0
    assert recovered["effective_poll_interval_seconds"] == 5
    await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize("interval", [1, 600])
async def test_scheduled_poll_at_supported_bounds(hass, entry, mock_quota, interval):
    from homeassistant.util import dt as dt_util
    from pytest_homeassistant_custom_component.common import async_fire_time_changed

    hass.config_entries.async_update_entry(entry, options={"poll_interval": interval})
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    now = dt_util.utcnow()
    async_fire_time_changed(hass, now + timedelta(seconds=interval + 1))
    await hass.async_block_till_done()
    assert mock_quota.await_count == 2
    assert entry.runtime_data.update_interval == timedelta(seconds=interval)
    await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize("saved,expected", [(900, 600), (0, 1), (True, 5), ("5", 5)])
async def test_legacy_interval_normalization(hass, entry, mock_quota, saved, expected):
    hass.config_entries.async_update_entry(entry, options={"poll_interval": saved})
    assert await hass.config_entries.async_setup(entry.entry_id)
    assert entry.runtime_data.poll_interval == expected
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["data_schema"]({})["poll_interval"] == expected
