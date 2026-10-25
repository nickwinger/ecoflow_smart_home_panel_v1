"""Real HA platforms, services, translated naming, option gates and lifecycle."""

from copy import deepcopy
from unittest.mock import AsyncMock, patch

import pytest
import voluptuous as vol
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ecoflow_smart_home_panel_v1.const import DOMAIN

from .test_controls import ALL_OPTIONS


def entity_id(hass, entry, kind, index=0):
    return er.async_get(hass).async_get_entity_id(
        "select" if kind in ("source", "mode") else "switch",
        DOMAIN,
        f"{entry.data['serial']}:control:{kind}:{index}",
    )


@pytest.mark.parametrize(
    "options,selects,switches",
    [
        ({}, 0, 0),
        ({"enable_source_controls": True}, 20, 0),
        ({"enable_charge_controls": True}, 0, 2),
        ({"enable_source_controls": "true", "enable_charge_controls": 1}, 0, 0),
    ],
)
async def test_independent_opt_in_and_no_side_effects(
    hass, entry, mock_quota, options, selects, switches
):
    hass.config_entries.async_update_entry(entry, options=options)
    with patch(
        "custom_components.ecoflow_smart_home_panel_v1.api.EcoFlowClient.put_quota",
        new_callable=AsyncMock,
    ) as put:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert len(hass.states.async_entity_ids("select")) == selects
        assert len(hass.states.async_entity_ids("switch")) == switches
        put.assert_not_awaited()
        if not selects:
            with pytest.raises(ServiceValidationError):
                await entry.runtime_data.controls.async_set_source(0, "grid")
        if not switches:
            with pytest.raises(ServiceValidationError):
                await entry.runtime_data.controls.async_set_charge(0, False)


@pytest.mark.parametrize("language,prefix", [("de", "Stromkreis"), ("en", "Circuit")])
async def test_names_and_rename_keep_ids(hass, entry, mock_quota, quota, language, prefix):
    hass.config.language = language
    hass.config_entries.async_update_entry(entry, options=ALL_OPTIONS)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    eid = entity_id(hass, entry, "source")
    assert prefix + " 1" in hass.states.get(eid).name
    data = deepcopy(quota)
    data["loadChInfo.info"] = [{"chName": "Test Kitchen"}]
    mock_quota.return_value = data
    await entry.runtime_data.async_refresh()
    assert "Test Kitchen" not in hass.states.get(eid).name
    assert prefix + " 1" in hass.states.get(eid).name
    assert entity_id(hass, entry, "source") == eid
    mock_quota.return_value = quota
    await entry.runtime_data.async_refresh()
    assert prefix + " 1" in hass.states.get(eid).name


async def test_real_ha_select_and_switch_services(hass, entry, control_env, mock_quota, quota):
    controls, put, _ = control_env
    current = deepcopy(quota)
    mock_quota.side_effect = lambda: deepcopy(current)

    async def write(params):
        key = (
            "heartbeat.loadCmdChCtrlInfos"
            if params["id"] == 16
            else "heartbeat.backupCmdChCtrlInfos"
        )
        index = params["ch"] if params["id"] == 16 else params["ch"] - 10
        current[key][index]["ctrlSta"] = params["sta"]

    put.side_effect = write
    source = entity_id(hass, entry, "source")
    charge = entity_id(hass, entry, "charge")
    await hass.services.async_call(
        "select", "select_option", {"entity_id": source, "option": "battery"}, blocking=True
    )
    assert hass.states.get(source).state == "battery"
    await hass.services.async_call("switch", "turn_on", {"entity_id": charge}, blocking=True)
    assert hass.states.get(charge).state == "on"
    await hass.services.async_call("switch", "turn_off", {"entity_id": charge}, blocking=True)
    assert hass.states.get(charge).state == "off"
    assert len(put.await_args_list) == 3
    assert hass.states.get(charge).attributes["control_operation"]["state"] == "succeeded"


async def test_unknown_status_failure_and_recovery(hass, entry, control_env, mock_quota, quota):
    controls, put, _ = control_env
    mock_quota.return_value = {}
    await entry.runtime_data.async_refresh()
    source = entity_id(hass, entry, "source")
    charge = entity_id(hass, entry, "charge")
    assert hass.states.get(source).state == "unknown"
    assert hass.states.get(charge).state == "unknown"
    put.side_effect = HomeAssistantError("failed")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "select", "select_option", {"entity_id": source, "option": "battery"}, blocking=True
        )
    assert hass.states.get(source).state == "unavailable"
    assert hass.states.get(charge).state == "unavailable"
    mock_quota.return_value = quota
    await entry.runtime_data.async_refresh()
    assert hass.states.get(source).state == "grid"
    assert hass.states.get(charge).state == "off"


@pytest.mark.parametrize(
    "extra", [{}, {"confirm": False}, {"confirm": 1}, {"confirm": True, "source": "off"}]
)
async def test_batch_requires_explicit_valid_confirmation(hass, entry, control_env, extra):
    _, put, _ = control_env
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            "set_all_sources",
            {"config_entry_id": entry.entry_id, "source": "grid", **extra},
            blocking=True,
        )
    put.assert_not_awaited()


async def test_batch_gate_and_entry_scope(hass, entry, mock_quota):
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    for eid in [entry.entry_id, "missing"]:
        with pytest.raises(ServiceValidationError):
            await hass.services.async_call(
                DOMAIN,
                "set_all_sources",
                {"config_entry_id": eid, "source": "grid", "confirm": True},
                blocking=True,
            )
    other = MockConfigEntry(domain="other", data={})
    other.add_to_hass(hass)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "cancel_commands", {"config_entry_id": other.entry_id}, blocking=True
        )
    assert await hass.config_entries.async_unload(entry.entry_id)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "set_all_sources",
            {"config_entry_id": entry.entry_id, "source": "grid", "confirm": True},
            blocking=True,
        )


async def test_batch_action_response(hass, entry, control_env, mock_quota, quota):
    _, put, _ = control_env
    data = deepcopy(quota)
    for item in data["heartbeat.loadCmdChCtrlInfos"]:
        item["ctrlSta"] = 0
    mock_quota.return_value = data
    response = await hass.services.async_call(
        DOMAIN,
        "set_all_sources",
        {"config_entry_id": entry.entry_id, "source": "grid", "confirm": True},
        blocking=True,
        return_response=True,
    )
    assert response["state"] == "succeeded"
    assert response["completed"] == [7, 6, 3, 1, 2, 4, 5, 8, 9, 10]
    put.assert_not_awaited()


async def test_options_revoke_controls_and_preserve_user_disable(
    hass, entry, control_env, mock_quota
):
    old_controls, put, _ = control_env
    source = entity_id(hass, entry, "source")
    er.async_get(hass).async_update_entity(source, disabled_by=er.RegistryEntryDisabler.USER)
    hass.config_entries.async_update_entry(entry, options={})
    await hass.async_block_till_done()
    assert old_controls._closed
    assert all(
        hass.states.get(eid).state == "unavailable"
        for eid in hass.states.async_entity_ids("select")
    )
    with pytest.raises(ServiceValidationError):
        await old_controls.async_set_source(0, "battery")
    hass.config_entries.async_update_entry(entry, options=ALL_OPTIONS)
    await hass.async_block_till_done()
    assert er.async_get(hass).async_get(source).disabled_by is er.RegistryEntryDisabler.USER
    assert hass.states.get(source) is None
    put.assert_not_awaited()
