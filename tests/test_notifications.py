"""Optional HA notifications never change batch execution or error propagation."""

import asyncio
from unittest.mock import patch

import pytest
from homeassistant.components import persistent_notification
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ecoflow_smart_home_panel_v1.const import CONF_BATCH_NOTIFICATIONS, DOMAIN
from custom_components.ecoflow_smart_home_panel_v1.notifications import (
    async_batch_failed,
    async_batch_succeeded,
    notification_id,
)

from .conftest import DATA
from .test_batch_reference import Scenario


def messages(hass):
    return persistent_notification._async_get_or_create_notifications(hass)


async def enable(hass, entry, controls):
    # Notification opt-in has no effect on commands, so avoid a reload of test mocks.
    with patch.object(hass.config_entries, "async_reload", return_value=True):
        hass.config_entries.async_update_entry(
            entry, options={**entry.options, CONF_BATCH_NOTIFICATIONS: True}
        )
        await hass.async_block_till_done()
    assert entry.runtime_data.controls is controls


@pytest.mark.parametrize("language", ["de", "en"])
@pytest.mark.parametrize("target", ["grid", "battery"])
async def test_batch_failure_notification_then_matching_success(
    hass, entry, control_env, mock_quota, language, target
):
    controls, put, _ = control_env
    hass.config.language = language
    await enable(hass, entry, controls)
    panel = Scenario("put_error", target)
    mock_quota.side_effect = panel.read
    put.side_effect = panel.write
    identifier = notification_id(entry, target)
    for _ in range(2):
        with pytest.raises(HomeAssistantError):
            await controls.async_set_all_sources(target)
        assert controls.status["failed"] == [6]
        assert len(controls.status["completed"]) == 9
        notification = messages(hass)[identifier]
        assert ("Stromkreise: 6" if language == "de" else "circuits: 6") in notification["message"]
        assert ("fehlgeschlagen" if language == "de" else "failed") in notification["title"]
        for value in DATA.values():
            if value != "eu":
                assert value not in str(notification)
    assert sum(key.startswith(DOMAIN) for key in messages(hass)) == 1
    other_target = "grid" if target == "battery" else "battery"
    async_batch_succeeded(hass, entry, other_target)
    assert identifier in messages(hass)
    panel = Scenario("success", target)
    mock_quota.side_effect = panel.read
    put.side_effect = panel.write
    await controls.async_set_all_sources(target)
    assert identifier not in messages(hass)


async def test_default_off_and_single_command_failure_do_not_notify(
    hass, entry, control_env, mock_quota
):
    controls, put, _ = control_env
    panel = Scenario("put_error", "battery")
    mock_quota.side_effect = panel.read
    put.side_effect = panel.write
    with pytest.raises(HomeAssistantError):
        await controls.async_set_all_sources("battery")
    assert notification_id(entry, "battery") not in messages(hass)
    await enable(hass, entry, controls)
    with pytest.raises(HomeAssistantError):
        await controls.async_set_source(5, "battery")
    assert not any(key.startswith(DOMAIN) for key in messages(hass))


async def test_cancellation_does_not_create_or_clear_failure(hass, entry, control_env):
    controls, _, pause = control_env
    await enable(hass, entry, controls)
    async_batch_failed(hass, entry, "grid", [])
    started = asyncio.Event()

    async def wait(_seconds):
        started.set()
        await asyncio.Event().wait()

    pause.side_effect = wait
    task = asyncio.create_task(controls.async_set_all_sources("battery"))
    async with asyncio.timeout(2):
        await started.wait()
    await controls.async_cancel()
    await asyncio.gather(task, return_exceptions=True)
    assert notification_id(entry, "grid") in messages(hass)
    assert notification_id(entry, "battery") not in messages(hass)


async def test_notification_is_only_created_after_final_pause(hass, entry, control_env, mock_quota):
    controls, put, pause = control_env
    await enable(hass, entry, controls)
    panel = Scenario("put_error", "battery")
    mock_quota.side_effect = panel.read
    put.side_effect = panel.write
    last_pause = asyncio.Event()
    release = asyncio.Event()

    async def wait(_seconds):
        if controls.status["channel"] == 10 and controls.status["stage"] == "channel pause":
            last_pause.set()
            await release.wait()

    pause.side_effect = wait
    task = asyncio.create_task(controls.async_set_all_sources("battery"))
    async with asyncio.timeout(2):
        await last_pause.wait()
    assert notification_id(entry, "battery") not in messages(hass)
    release.set()
    with pytest.raises(HomeAssistantError):
        await task
    assert notification_id(entry, "battery") in messages(hass)


@pytest.mark.parametrize("cleanup", ["disable", "remove", "disabled_setup"])
async def test_cleanup_preserves_other_panels_and_unrelated_notifications(
    hass, entry, control_env, cleanup
):
    controls, put, _ = control_env
    await enable(hass, entry, controls)
    other = MockConfigEntry(
        domain=DOMAIN,
        data={**DATA, "serial": "SHP-TEST-0002"},
        options={CONF_BATCH_NOTIFICATIONS: True},
    )
    for target in ("grid", "battery"):
        async_batch_failed(hass, entry, target, [])
        async_batch_failed(hass, other, target, [])
    persistent_notification.async_create(hass, "Unrelated", notification_id="other-integration")
    if cleanup == "disable":
        result = await hass.config_entries.options.async_init(entry.entry_id)
        await hass.config_entries.options.async_configure(
            result["flow_id"],
            {**entry.options, "poll_interval": 5, CONF_BATCH_NOTIFICATIONS: False},
        )
        await hass.async_block_till_done()
    elif cleanup == "remove":
        assert await hass.config_entries.async_remove(entry.entry_id)
    else:
        await hass.config_entries.async_unload(entry.entry_id)
        hass.config_entries.async_update_entry(entry, options={})
        assert await hass.config_entries.async_setup(entry.entry_id)
    for target in ("grid", "battery"):
        assert notification_id(entry, target) not in messages(hass)
        assert notification_id(other, target) in messages(hass)
    assert "other-integration" in messages(hass)
    put.assert_not_awaited()


async def test_reload_and_manual_dismiss_do_not_switch(hass, entry, control_env):
    controls, put, _ = control_env
    await enable(hass, entry, controls)
    async_batch_failed(hass, entry, "grid", [])
    await hass.config_entries.async_reload(entry.entry_id)
    identifier = notification_id(entry, "grid")
    assert identifier in messages(hass)
    await hass.services.async_call(
        "persistent_notification", "dismiss", {"notification_id": identifier}, blocking=True
    )
    assert identifier not in messages(hass)
    put.assert_not_awaited()


async def test_option_without_controls_is_allowed_and_defaults_off(hass, entry):
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["data_schema"]({})[CONF_BATCH_NOTIFICATIONS] is False
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"poll_interval": 5, CONF_BATCH_NOTIFICATIONS: True}
    )
    assert entry.options[CONF_BATCH_NOTIFICATIONS] is True
    assert entry.options["enable_source_controls"] is False
    assert entry.options["enable_batch_controls"] is False
