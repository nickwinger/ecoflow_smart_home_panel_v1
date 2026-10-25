"""Mode changes preserve fresh source state; no physical device is contacted."""

from copy import deepcopy

import pytest
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from custom_components.ecoflow_smart_home_panel_v1.const import DOMAIN
from custom_components.ecoflow_smart_home_panel_v1.controls import read_control_states

from .test_control_entities import entity_id


def with_mode(quota, mode=0, source=0):
    result = deepcopy(quota)
    for item in result["heartbeat.loadCmdChCtrlInfos"]:
        item.update(ctrlMode=mode, ctrlSta=source)
    return result


@pytest.mark.parametrize("nested", [False, True])
@pytest.mark.parametrize(
    "value,expected",
    [
        (0, "automatic"),
        (1, "manual"),
        (2, None),
        (True, None),
        (1.0, None),
        ("1", None),
        (None, None),
    ],
)
def test_mode_decoding(quota, nested, value, expected):
    data = with_mode(quota, value)
    if nested:
        data = {"heartbeat": {"loadCmdChCtrlInfos": data["heartbeat.loadCmdChCtrlInfos"]}}
    assert read_control_states(data)["mode"] == (expected,) * 10


@pytest.mark.parametrize("damage", ["missing", "partial", "ambiguous", "wrong_index"])
def test_mode_requires_complete_unambiguous_array(quota, damage):
    data = with_mode(quota)
    if damage == "missing":
        del data["heartbeat.loadCmdChCtrlInfos"][-1]["ctrlMode"]
    elif damage == "partial":
        data["heartbeat.loadCmdChCtrlInfos"].pop()
    elif damage == "ambiguous":
        data["heartbeat"] = {"loadCmdChCtrlInfos": None}
    else:
        data["heartbeat.loadCmdChCtrlInfos"][0]["ch"] = 3
    assert read_control_states(data)["mode"] == (None,) * 10


@pytest.mark.parametrize("target,old,new", [("manual", 0, 1), ("automatic", 1, 0)])
@pytest.mark.parametrize("source", [0, 1, 2])
async def test_mode_exact_payload_preserves_fresh_source(
    hass, entry, control_env, mock_quota, quota, target, old, new, source
):
    controls, put, sleep = control_env
    # Previously held source must not be used to build the command.
    mock_quota.side_effect = [with_mode(quota, old, source), with_mode(quota, new, source)]
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": entity_id(hass, entry, "mode", 6), "option": target},
        blocking=True,
    )
    put.assert_awaited_once_with(
        {
            "cmdSet": 11,
            "id": 16,
            "ch": 6,
            "ctrlMode": new,
            "sta": source if target == "manual" else 0,
        }
    )
    sleep.assert_awaited_once_with(10)
    assert hass.states.get(entity_id(hass, entry, "mode", 6)).state == target
    assert controls.status["state"] == "succeeded"


async def test_mode_target_already_current_sends_no_command(control_env, mock_quota, quota):
    controls, put, sleep = control_env
    mock_quota.return_value = with_mode(quota, 1)
    await controls.async_set_mode(0, "manual")
    put.assert_not_awaited()
    sleep.assert_not_awaited()


@pytest.mark.parametrize("source", [None, True, 1.0, "0", 3])
async def test_mode_never_guesses_missing_source(control_env, mock_quota, quota, source):
    controls, put, _ = control_env
    mock_quota.return_value = with_mode(quota, 0, source)
    with pytest.raises(HomeAssistantError):
        await controls.async_set_mode(0, "manual")
    put.assert_not_awaited()


async def test_mode_retries_use_new_source_and_require_actual_confirmation(
    control_env, mock_quota, quota
):
    controls, put, sleep = control_env
    mock_quota.side_effect = [
        with_mode(quota, 0, 0),
        with_mode(quota, 0, 0),
        with_mode(quota, 0, 1),
        with_mode(quota, 1, 1),
    ]
    await controls.async_set_mode(0, "manual")
    assert [call.args[0]["sta"] for call in put.await_args_list] == [0, 1]
    assert [call.args[0] for call in sleep.await_args_list] == [10, 15, 10]


async def test_mode_unknown_confirmation_exhausts_bounded_retries(control_env, mock_quota, quota):
    controls, put, sleep = control_env
    mock_quota.side_effect = [with_mode(quota, 0), with_mode(quota, None)] * 8
    with pytest.raises(HomeAssistantError):
        await controls.async_set_mode(0, "manual")
    assert put.await_count == 8
    assert sleep.await_count == 15
    assert controls.status["state"] == "failed"


@pytest.mark.parametrize(
    "index,target", [(True, "manual"), (-1, "manual"), (10, "manual"), (0, "off"), (0, True)]
)
async def test_invalid_mode_requests(control_env, index, target):
    controls, put, _ = control_env
    with pytest.raises(ServiceValidationError):
        await controls.async_set_mode(index, target)
    put.assert_not_awaited()


def button_id(hass, entry, action):
    return er.async_get(hass).async_get_entity_id(
        "button", DOMAIN, f"{entry.data['serial']}:control:batch:{action}"
    )


async def test_batch_buttons_hidden_and_action_blocked_after_fi_trip(
    hass, entry, control_env
):
    controls, put, sleep = control_env
    assert hass.states.async_entity_ids("button") == []
    assert not controls.batch_enabled()
    with pytest.raises(ServiceValidationError, match="suspended"):
        await controls.async_set_all_sources("battery")
    put.assert_not_awaited()
    sleep.assert_not_awaited()

@pytest.mark.parametrize(
    "options", [{}, {"enable_source_controls": True}, {"enable_batch_controls": True}]
)
async def test_batch_buttons_require_both_options(hass, entry, mock_quota, options):
    hass.config_entries.async_update_entry(entry, options=options)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.async_entity_ids("button") == []
