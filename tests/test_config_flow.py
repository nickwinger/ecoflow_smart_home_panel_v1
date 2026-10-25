"""Exercise the actual Home Assistant flow manager."""

from unittest.mock import patch

import pytest
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_RECONFIGURE, SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType, InvalidData

from custom_components.ecoflow_smart_home_panel_v1.api import (
    AuthenticationError,
    EcoFlowError,
    InvalidResponseError,
    RateLimitError,
)
from custom_components.ecoflow_smart_home_panel_v1.const import DOMAIN

from .conftest import DATA


async def test_create_and_duplicate(hass, mock_quota):
    with patch(
        "custom_components.ecoflow_smart_home_panel_v1.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
        assert result["type"] is FlowResultType.FORM
        assert {str(key) for key in result["data_schema"].schema} == {
            "access_key",
            "secret_key",
            "serial",
            "region",
        }
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {**DATA, "serial": " shp-test-0001 "}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"]["serial"] == DATA["serial"]
        assert "confirm_v1" not in result["data"]
        assert "SHP-TEST" not in result["title"]
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=DATA
        )
        assert result["reason"] == "already_configured"
        assert mock_quota.call_count == 1


@pytest.mark.parametrize(
    "error,expected",
    [
        (AuthenticationError(), "invalid_auth"),
        (EcoFlowError(), "cannot_connect"),
        (RateLimitError(), "rate_limited"),
        (InvalidResponseError(), "invalid_response"),
    ],
)
async def test_errors(hass, mock_quota, error, expected):
    mock_quota.side_effect = error
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=DATA
    )
    assert result["errors"] == {"base": expected}


async def test_partial_onboarding(hass, mock_quota):
    mock_quota.return_value = {"heartbeat.gridSta": 1}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=DATA
    )
    assert result["errors"] == {"base": "unsupported_device"}


@pytest.mark.parametrize(
    "change,expected",
    [({"access_key": " "}, "invalid_input")],
)
async def test_input_validation(hass, mock_quota, change, expected):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data={**DATA, **change}
    )
    assert result["errors"] == {"base": expected}
    mock_quota.assert_not_called()


@pytest.mark.parametrize("source", [SOURCE_REAUTH, SOURCE_RECONFIGURE])
@pytest.mark.parametrize("legacy_confirmation", [None, False, True])
async def test_credentials_replaced(hass, entry, mock_quota, source, legacy_confirmation):
    if legacy_confirmation is not None:
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, "confirm_v1": legacy_confirmation}
        )
    with patch.object(hass.config_entries, "async_reload", return_value=True) as reload:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": source, "entry_id": entry.entry_id},
            data=entry.data if source == SOURCE_REAUTH else None,
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"access_key": "new-test-access", "secret_key": "new-test-secret"}
        )
        assert result["type"] is FlowResultType.ABORT
        assert entry.data["secret_key"] == "new-test-secret"
        assert entry.unique_id == DATA["serial"]
        reload.assert_awaited_once()


@pytest.mark.parametrize("interval", [1, 5, 120, 600])
async def test_options(hass, entry, interval):
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"poll_interval": interval}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {
        "poll_interval": interval,
        "enable_source_controls": False,
        "enable_charge_controls": False,
        "enable_batch_controls": False,
    }


@pytest.mark.parametrize("interval", [0, -1, 601, 5.5, "5", None])
async def test_options_reject_invalid_intervals(hass, entry, interval):
    result = await hass.config_entries.options.async_init(entry.entry_id)
    with pytest.raises(InvalidData):
        await hass.config_entries.options.async_configure(
            result["flow_id"], {"poll_interval": interval}
        )
    assert entry.options == {}


async def test_options_reject_boolean_interval(hass, entry):
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"poll_interval": True}
    )
    assert result["errors"] == {"base": "invalid_poll_interval"}
    assert entry.options == {}


@pytest.mark.parametrize("configured", [None, 60])
async def test_options_default_and_existing_selection(hass, entry, configured):
    if configured is not None:
        hass.config_entries.async_update_entry(entry, options={"poll_interval": configured})
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["data_schema"]({}) == {
        "poll_interval": 5 if configured is None else configured,
        "enable_source_controls": False,
        "enable_charge_controls": False,
        "enable_batch_controls": False,
    }


@pytest.mark.parametrize(
    "change", [{"access_key": "a\nb"}, {"serial": "not/a/serial"}, {"region": "unknown"}]
)
async def test_invalid_credentials_do_not_call_cloud(hass, mock_quota, change):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data={**DATA, **change}
    )
    assert result["errors"] == {"base": "invalid_input"}
    mock_quota.assert_not_called()


async def test_control_options_independent_and_batch_dependency(hass, entry):
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "poll_interval": 5,
            "enable_batch_controls": True,
        },
    )
    assert result["errors"] == {"base": "batch_requires_source"}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "poll_interval": 5,
            "enable_source_controls": True,
            "enable_batch_controls": True,
            "enable_charge_controls": False,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["enable_source_controls"] is True
    assert entry.options["enable_batch_controls"] is True
    assert entry.options["enable_charge_controls"] is False
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["data_schema"]({}) == dict(entry.options)


@pytest.mark.parametrize("value", ["true", 1, None])
async def test_controls_require_boolean_options(hass, entry, value):
    result = await hass.config_entries.options.async_init(entry.entry_id)
    with pytest.raises(InvalidData):
        await hass.config_entries.options.async_configure(
            result["flow_id"], {"poll_interval": 5, "enable_source_controls": value}
        )
    assert entry.options == {}
