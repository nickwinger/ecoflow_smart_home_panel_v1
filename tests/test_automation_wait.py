"""Real HA action sequences await confirmation, and stop on failure/cancellation."""

import asyncio
from unittest.mock import AsyncMock

import pytest
from homeassistant.core import Context
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.script import Script

from custom_components.ecoflow_smart_home_panel_v1.const import DOMAIN
from custom_components.ecoflow_smart_home_panel_v1.controls import CIRCUIT_ORDER

from .test_batch_reference import Scenario
from .test_control_mode import button_id


def sequence(hass, entry, after, *, button=False, entry_id=None):
    hass.services.async_register("batch_test", "after", after)
    action = (
        {"action": "button.press", "target": {"entity_id": button_id(hass, entry, "battery")}}
        if button
        else {
            "action": f"{DOMAIN}.set_all_sources",
            "data": {
                "config_entry_id": entry_id or entry.entry_id,
                "source": "battery",
                "confirm": True,
            },
            "response_variable": "batch_result",
        }
    )
    following = {"action": "batch_test.after"}
    if not button:
        following["data"] = {"completed": "{{ batch_result.completed }}"}
    return Script(hass, cv.SCRIPT_SCHEMA([action, following]), "Batch wait test", "automation")


@pytest.mark.parametrize("outcome", ["success", "failure", "cancel"])
async def test_automation_waits_until_entire_batch_finishes(
    hass, entry, control_env, mock_quota, outcome
):
    controls, put, sleep = control_env
    panel = Scenario("put_error" if outcome == "failure" else "success", "battery")
    mock_quota.side_effect = panel.read
    put.side_effect = panel.write
    first = asyncio.Event()
    last = asyncio.Event()
    release_first = asyncio.Event()
    release_last = asyncio.Event()

    async def pause(seconds):
        if not first.is_set():
            first.set()
            await release_first.wait()
        if controls.status["stage"] == "channel pause" and controls.status["channel"] == 10:
            last.set()
            await release_last.wait()

    sleep.side_effect = pause
    after = AsyncMock()
    script = sequence(hass, entry, after)
    task = asyncio.create_task(script.async_run({}, Context()))
    async with asyncio.timeout(2):
        await first.wait()
    assert not task.done() and script.is_running
    after.assert_not_awaited()
    if outcome == "cancel":
        await controls.async_cancel()
        await asyncio.gather(task, return_exceptions=True)
        assert controls.status["state"] == "cancelled"
        after.assert_not_awaited()
        return
    release_first.set()
    async with asyncio.timeout(2):
        await last.wait()
    assert not task.done() and script.is_running
    after.assert_not_awaited()  # Even the last reference pause is awaited.
    assert len(controls.status["completed"]) + len(controls.status["failed"]) == 10
    release_last.set()
    if outcome == "failure":
        with pytest.raises(HomeAssistantError):
            await task
        after.assert_not_awaited()
    else:
        await task
        after.assert_awaited_once()
        assert after.call_args.args[0].data["completed"] == list(CIRCUIT_ORDER)
    assert not script.is_running


async def test_invalid_service_target_stops_following_actions(hass, entry, control_env):
    after = AsyncMock()
    script = sequence(hass, entry, after, entry_id="missing-entry")
    with pytest.raises(HomeAssistantError):
        await script.async_run({}, Context())
    after.assert_not_awaited()


async def test_unavailable_button_can_be_skipped_but_direct_action_recovers(
    hass, entry, control_env, mock_quota
):
    """An entity action may be skipped by HA; use the strict entry-scoped action."""
    controls, put, _ = control_env
    controls.coordinator.async_control_error(HomeAssistantError("synthetic outage"))
    assert hass.states.get(button_id(hass, entry, "battery")).state == "unavailable"
    after = AsyncMock()
    await sequence(hass, entry, after, button=True).async_run({}, Context())
    after.assert_awaited_once()
    put.assert_not_awaited()
    panel = Scenario("success", "battery")
    mock_quota.side_effect = panel.read
    put.side_effect = panel.write
    after.reset_mock()
    await sequence(hass, entry, after).async_run({}, Context())
    assert controls.status["completed"] == list(CIRCUIT_ORDER)
    after.assert_awaited_once()
