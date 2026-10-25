"""Offline command transactions and adversarial status parsing; never real writes."""

import asyncio
from copy import deepcopy
from unittest.mock import patch

import pytest
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from custom_components.ecoflow_smart_home_panel_v1.api import (
    AuthenticationError,
    EcoFlowError,
    RateLimitError,
)
from custom_components.ecoflow_smart_home_panel_v1.const import (
    CONF_BATCH_CONTROLS,
    CONF_CHARGE_CONTROLS,
    CONF_SOURCE_CONTROLS,
    DOMAIN,
)
from custom_components.ecoflow_smart_home_panel_v1.controls import (
    CIRCUIT_ORDER,
    read_control_states,
)

ALL_OPTIONS = {CONF_SOURCE_CONTROLS: True, CONF_CHARGE_CONTROLS: True, CONF_BATCH_CONTROLS: True}


@pytest.mark.parametrize("nested", [False, True])
def test_control_states(quota, nested):
    data = (
        {"heartbeat": {k.removeprefix("heartbeat."): v for k, v in quota.items()}}
        if nested
        else quota
    )
    states = read_control_states(data)
    assert states["source"] == tuple("grid" if i % 2 == 0 else "battery" for i in range(10))
    assert states["charge"] == (False, True)


@pytest.mark.parametrize("bad", [True, False, 0.0, 1.0, "0", "1", "2", None, {}, [], 3, -1])
def test_invalid_codes_never_confirm(quota, bad):
    quota["heartbeat.loadCmdChCtrlInfos"][0]["ctrlSta"] = bad
    quota["heartbeat.backupCmdChCtrlInfos"][0]["ctrlSta"] = bad
    states = read_control_states(quota)
    assert states["source"][0] is None
    assert states["charge"][0] is None


@pytest.mark.parametrize(
    "kind,array,size", [("source", "loadCmdChCtrlInfos", 10), ("charge", "backupCmdChCtrlInfos", 2)]
)
@pytest.mark.parametrize(
    "damage",
    [
        "missing",
        "short",
        "long",
        "empty_item",
        "ambiguous",
        "null",
        "wrong_ch",
        "bool_ch",
        "fake_bracket_key",
    ],
)
def test_incomplete_and_ambiguous_array_never_confirms(quota, kind, array, size, damage):
    key = f"heartbeat.{array}"
    if damage == "missing":
        del quota[key]
    elif damage == "short":
        quota[key].pop()
    elif damage == "long":
        quota[key].append({"ctrlSta": 0})
    elif damage == "empty_item":
        quota[key][-1] = {}
    elif damage == "ambiguous":
        quota["heartbeat"] = {array: []}
    elif damage == "null":
        quota[key] = None
    elif damage == "wrong_ch":
        quota[key][0]["ch"] = 9
    elif damage == "bool_ch":
        quota[key][0]["ch"] = False
    else:
        quota = {f"{key}[0].ctrlSta": 0}
    assert read_control_states(quota)[kind] == (None,) * size


def test_sta_fallback_does_not_override_invalid_ctrlsta(quota):
    item = quota["heartbeat.loadCmdChCtrlInfos"][0]
    item["sta"] = item.pop("ctrlSta")
    assert read_control_states(quota)["source"][0] == "grid"
    item["ctrlSta"] = None
    assert read_control_states(quota)["source"][0] is None


async def test_no_writes_on_setup_poll_reload_even_opted_in(hass, entry, control_env):
    controls, put, _ = control_env
    await entry.runtime_data.async_refresh()
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids("select")) == 20
    assert len(hass.states.async_entity_ids("switch")) == 2
    put.assert_not_awaited()
    assert controls._closed


@pytest.mark.parametrize(
    "kind,index,target,old,new,expected",
    [
        ("source", 0, "battery", 0, 1, {"cmdSet": 11, "id": 16, "ch": 0, "ctrlMode": 1, "sta": 1}),
        ("source", 9, "grid", 1, 0, {"cmdSet": 11, "id": 16, "ch": 9, "ctrlMode": 0, "sta": 0}),
        ("charge", 0, True, 0, 2, {"cmdSet": 11, "id": 17, "ch": 10, "ctrlMode": 1, "sta": 2}),
        ("charge", 1, False, 2, 0, {"cmdSet": 11, "id": 17, "ch": 11, "ctrlMode": 0, "sta": 0}),
    ],
)
async def test_exact_payload_and_fresh_verification(
    control_env, mock_quota, quota, kind, index, target, old, new, expected
):
    controls, put, sleep = control_env
    key = "heartbeat." + ("loadCmdChCtrlInfos" if kind == "source" else "backupCmdChCtrlInfos")
    before = deepcopy(quota)
    before[key][index]["ctrlSta"] = old
    after = deepcopy(before)
    after[key][index]["ctrlSta"] = new
    mock_quota.side_effect = [before, after]
    await (
        controls.async_set_source(index, target)
        if kind == "source"
        else controls.async_set_charge(index, target)
    )
    put.assert_awaited_once_with(expected)
    sleep.assert_awaited_once_with(10 if kind == "source" else 2)
    assert mock_quota.await_count == 2
    assert controls.status["state"] == "succeeded"
    assert controls.coordinator.last_update_success


async def test_fresh_already_target_skips_write(control_env, mock_quota):
    controls, put, sleep = control_env
    await controls.async_set_source(0, "grid")
    assert mock_quota.await_count == 1
    put.assert_not_awaited()
    sleep.assert_not_awaited()


async def test_stale_target_is_not_confirmation(control_env, mock_quota, quota):
    controls, put, sleep = control_env
    assert controls.coordinator.data.control_states["source"][0] == "grid"
    before = deepcopy(quota)
    before["heartbeat.loadCmdChCtrlInfos"][0]["ctrlSta"] = 1
    mock_quota.side_effect = [before, quota]
    await controls.async_set_source(0, "grid")
    put.assert_awaited_once()
    assert mock_quota.await_count == 2


@pytest.mark.parametrize("partial", [True, False])
async def test_retries_eight_times_then_unavailable(control_env, mock_quota, partial):
    controls, put, sleep = control_env
    if partial:
        mock_quota.return_value = {}
    with pytest.raises(HomeAssistantError, match="not confirmed"):
        await controls.async_set_source(0, "battery")
    assert put.await_count == 8
    assert mock_quota.await_count == 16
    assert [c.args[0] for c in sleep.await_args_list] == [10, 15] * 7 + [10]
    assert controls.status["state"] == "failed"
    assert not controls.coordinator.last_update_success


async def test_partial_then_retry_confirmation(control_env, mock_quota, quota):
    controls, put, _ = control_env
    after = deepcopy(quota)
    after["heartbeat.loadCmdChCtrlInfos"][0]["ctrlSta"] = 1
    mock_quota.side_effect = [quota, {}, quota, after]
    await controls.async_set_source(0, "battery")
    assert put.await_count == 2
    assert controls.status["attempt"] == 2


@pytest.mark.parametrize(
    "error", [EcoFlowError("failed"), AuthenticationError("denied"), RateLimitError(180)]
)
async def test_put_failure_stops_redacts_and_invalidates(control_env, mock_quota, error, caplog):
    controls, put, sleep = control_env
    put.side_effect = error
    with patch.object(controls.coordinator.config_entry, "async_start_reauth") as reauth:
        with pytest.raises(HomeAssistantError):
            await controls.async_set_source(0, "battery")
        assert reauth.call_count == isinstance(error, AuthenticationError)
    put.assert_awaited_once()
    sleep.assert_not_awaited()
    assert controls.status["state"] == "failed"
    assert not controls.coordinator.last_update_success
    if isinstance(error, RateLimitError):
        assert controls.coordinator.update_interval.total_seconds() == 180
    assert "test-secret" not in caplog.text and "SHP-TEST" not in caplog.text


@pytest.mark.parametrize("stage", ["before", "after"])
async def test_refresh_failure_is_never_success(control_env, mock_quota, quota, stage):
    controls, put, _ = control_env
    mock_quota.side_effect = (
        [EcoFlowError("failure")] if stage == "before" else [quota, EcoFlowError("failure")]
    )
    with pytest.raises(HomeAssistantError):
        await controls.async_set_source(0, "battery")
    assert put.await_count == (stage == "after")
    assert not controls.coordinator.last_update_success


async def test_auth_refresh_starts_reauth(control_env, mock_quota):
    controls, _, _ = control_env
    mock_quota.side_effect = AuthenticationError("denied")
    with patch.object(controls.coordinator.config_entry, "async_start_reauth") as reauth:
        with pytest.raises(HomeAssistantError):
            await controls.async_set_source(0, "battery")
        reauth.assert_called_once()


@pytest.mark.parametrize(
    "kind,index,target",
    [
        ("source", True, "grid"),
        ("source", -1, "grid"),
        ("source", 10, "grid"),
        ("source", 0, "off"),
        ("charge", 2, True),
        ("charge", 0, 1),
    ],
)
async def test_invalid_commands_never_reach_api(control_env, kind, index, target):
    controls, put, _ = control_env
    with pytest.raises(ServiceValidationError):
        await (
            controls.async_set_source(index, target)
            if kind == "source"
            else controls.async_set_charge(index, target)
        )
    put.assert_not_awaited()


async def test_cross_platform_concurrency_is_serialized(control_env, mock_quota, quota):
    controls, put, sleep = control_env
    sleeping = asyncio.Event()
    release = asyncio.Event()

    async def settle(seconds):
        sleeping.set()
        await release.wait()

    sleep.side_effect = settle
    after = deepcopy(quota)
    after["heartbeat.loadCmdChCtrlInfos"][0]["ctrlSta"] = 1
    charged = deepcopy(after)
    charged["heartbeat.backupCmdChCtrlInfos"][0]["ctrlSta"] = 2
    mock_quota.side_effect = [quota, after, after, charged]
    first = asyncio.create_task(controls.async_set_source(0, "battery"))
    await sleeping.wait()
    second = asyncio.create_task(controls.async_set_charge(0, True))
    await asyncio.sleep(0)
    assert put.await_count == 1
    # The in-flight target is never shown optimistically.
    assert controls.coordinator.data.control_states["source"][0] == "grid"
    release.set()
    await asyncio.gather(first, second)
    assert [c.args[0]["id"] for c in put.await_args_list] == [16, 17]


@pytest.mark.parametrize("unload", [False, True])
async def test_cancel_active_and_queued_no_more_writes(hass, entry, control_env, unload):
    controls, put, sleep = control_env
    sleeping = asyncio.Event()

    async def settle(seconds):
        sleeping.set()
        await asyncio.Event().wait()

    sleep.side_effect = settle
    first = asyncio.create_task(controls.async_set_source(0, "battery"))
    await sleeping.wait()
    second = asyncio.create_task(controls.async_set_charge(0, True))
    await asyncio.sleep(0)
    if unload:
        assert await hass.config_entries.async_unload(entry.entry_id)
    else:
        await hass.services.async_call(
            DOMAIN, "cancel_commands", {"config_entry_id": entry.entry_id}, blocking=True
        )
    assert first.cancelled() and second.cancelled()
    assert controls.status["state"] == "cancelled"
    assert not controls._tasks
    put.assert_awaited_once()


async def test_ordered_batch_updates_progress(control_env, mock_quota, quota):
    controls, put, sleep = control_env
    current = deepcopy(quota)
    for item in current["heartbeat.loadCmdChCtrlInfos"]:
        item["ctrlSta"] = 0
    mock_quota.side_effect = lambda: deepcopy(current)

    async def write(params):
        current["heartbeat.loadCmdChCtrlInfos"][params["ch"]]["ctrlSta"] = params["sta"]

    put.side_effect = write
    result = await controls.async_set_all_sources("battery")
    assert [c.args[0]["ch"] + 1 for c in put.await_args_list] == list(CIRCUIT_ORDER)
    assert result["completed"] == list(CIRCUIT_ORDER)
    assert result["state"] == "succeeded"
    assert sleep.await_count == 20


async def test_batch_continues_after_failure_no_rollback(control_env, mock_quota, quota):
    controls, put, sleep = control_env
    current = deepcopy(quota)
    for item in current["heartbeat.loadCmdChCtrlInfos"]:
        item["ctrlSta"] = 0
    mock_quota.side_effect = lambda: deepcopy(current)

    async def write(params):
        if params["ch"] == 5:
            raise EcoFlowError("failed")
        current["heartbeat.loadCmdChCtrlInfos"][params["ch"]]["ctrlSta"] = 1

    put.side_effect = write
    with pytest.raises(HomeAssistantError):
        await controls.async_set_all_sources("battery")
    assert [c.args[0]["ch"] + 1 for c in put.await_args_list] == list(CIRCUIT_ORDER)
    assert controls.status["completed"] == [7, 3, 1, 2, 4, 5, 8, 9, 10]
    assert controls.status["failed"] == [6]
    assert [call.args[0] for call in sleep.await_args_list] == [10] * 19
    assert controls.status["state"] == "failed"


async def test_queued_cancellation_does_not_change_active_result(control_env, mock_quota, quota):
    controls, put, sleep = control_env
    sleeping = asyncio.Event()
    release = asyncio.Event()

    async def settle(seconds):
        sleeping.set()
        await release.wait()

    sleep.side_effect = settle
    after = deepcopy(quota)
    after["heartbeat.loadCmdChCtrlInfos"][0]["ctrlSta"] = 1
    mock_quota.side_effect = [quota, after]
    active = asyncio.create_task(controls.async_set_source(0, "battery"))
    await sleeping.wait()
    queued = asyncio.create_task(controls.async_set_charge(0, True))
    await asyncio.sleep(0)
    queued.cancel()
    with pytest.raises(asyncio.CancelledError):
        await queued
    assert controls.status["state"] == "running"
    release.set()
    await active
    assert controls.status["state"] == "succeeded"
    put.assert_awaited_once()


async def test_batch_requires_source_and_batch_flags(hass, entry, control_env):
    controls, put, _ = control_env
    with pytest.raises(ServiceValidationError):
        await controls.async_set_all_sources("off")
    hass.config_entries.async_update_entry(entry, options={"enable_source_controls": True})
    with pytest.raises(ServiceValidationError):
        await controls.async_set_all_sources("grid")
    await hass.async_block_till_done()
    put.assert_not_awaited()


def test_null_nested_duplicate_never_confirms(quota):
    quota["heartbeat"] = {"loadCmdChCtrlInfos": None}
    assert read_control_states(quota)["source"] == (None,) * 10
