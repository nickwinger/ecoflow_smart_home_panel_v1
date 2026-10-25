"""User-visible HA logs contain useful context, no payloads and no outage floods."""

import logging
from unittest.mock import Mock

import pytest
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    HomeAssistantError,
    ServiceValidationError,
)
from homeassistant.setup import async_setup_component

from custom_components.ecoflow_smart_home_panel_v1.api import (
    AuthenticationError,
    EcoFlowError,
    InvalidResponseError,
    RateLimitError,
    UnsupportedDeviceError,
)
from custom_components.ecoflow_smart_home_panel_v1.const import DOMAIN
from custom_components.ecoflow_smart_home_panel_v1.logging_utils import failure_reason
from custom_components.ecoflow_smart_home_panel_v1.quota import QuotaLimitError

from .test_batch_reference import Scenario

LOGGER = f"custom_components.{DOMAIN}"
PRIVATE = "test-access test-secret SHP-TEST-0001 https://private.invalid/raw?token=secret"


@pytest.mark.parametrize(
    "error,expected",
    [
        (AuthenticationError(PRIVATE), "authentication rejected"),
        (ConfigEntryAuthFailed(PRIVATE), "authentication rejected"),
        (RateLimitError(90), "rate limit"),
        (InvalidResponseError(PRIVATE), "invalid or rejected"),
        (UnsupportedDeviceError(PRIVATE), "layout"),
        (QuotaLimitError(PRIVATE), "limits"),
        (EcoFlowError(PRIVATE), "request failed"),
        (ServiceValidationError(PRIVATE), "invalid or no longer enabled"),
        (HomeAssistantError(PRIVATE), "not be confirmed"),
        (OSError(PRIVATE), "connection failed"),
        (TimeoutError(PRIVATE), "connection failed"),
        (RuntimeError(PRIVATE), "unexpected internal error"),
    ],
)
def test_allowlisted_failure_reasons(error, expected):
    reason = failure_reason(error)
    assert expected in reason and PRIVATE not in reason


async def test_batch_errors_reach_home_assistant_system_log(
    hass, entry, control_env, mock_quota, caplog
):
    assert await async_setup_component(hass, "system_log", {})
    controls, put, _ = control_env
    panel = Scenario("success", "battery")
    mock_quota.side_effect = panel.read

    def write(params):
        if params["ch"] == 5:
            raise EcoFlowError(PRIVATE)
        return panel.write(params)

    put.side_effect = write
    with pytest.raises(HomeAssistantError):
        await controls.async_set_all_sources("battery")
    await hass.async_block_till_done()
    records = hass.data["system_log"].records.to_list()
    messages = "\n".join(
        message
        for record in records
        if record["name"].startswith(LOGGER)
        for message in record["message"]
    )
    assert "circuit source 6 -> battery failed during write (attempt 1/8)" in messages
    assert "Continuing with remaining circuits" in messages
    assert "unconfirmed circuits=[6]" in messages
    assert "confirmed circuits=[7, 3, 1, 2, 4, 5, 8, 9, 10]" in messages
    for private in PRIVATE.split():
        assert private not in messages + caplog.text


async def test_retry_warning_is_bounded_and_final_error_explains_failure(
    control_env, mock_quota, caplog
):
    controls, _, _ = control_env
    mock_quota.return_value = {}
    with pytest.raises(HomeAssistantError):
        await controls.async_set_source(0, "battery")
    records = [r for r in caplog.records if r.name == LOGGER + ".controls"]
    assert sum(r.levelno == logging.WARNING for r in records) == 1
    assert sum(r.levelno == logging.ERROR for r in records) == 1
    assert "attempt 8/8" in records[-1].getMessage()


async def test_polling_logs_once_per_outage_and_recovers(hass, entry, mock_quota, quota, caplog):
    assert await hass.config_entries.async_setup(entry.entry_id)
    coordinator = entry.runtime_data
    caplog.clear()
    caplog.set_level(logging.INFO, logger=LOGGER)
    mock_quota.side_effect = EcoFlowError(PRIVATE)
    for _ in range(3):
        await coordinator.async_refresh()
    errors = [
        r
        for r in caplog.records
        if r.name == LOGGER + ".coordinator" and r.levelno == logging.ERROR
    ]
    assert len(errors) == 1
    assert "next poll in 10 seconds" in errors[0].getMessage()
    for private in PRIVATE.split():
        assert private not in caplog.text
    mock_quota.side_effect = None
    mock_quota.return_value = quota
    await coordinator.async_refresh()
    assert any("recovered" in r.getMessage() for r in caplog.records if r.levelno == logging.INFO)


async def test_mqtt_logs_one_warning_until_fresh_reports_recover(hass, entry, mock_quota, caplog):
    assert await hass.config_entries.async_setup(entry.entry_id)
    stream = entry.runtime_data.telemetry
    stream.enabled = True
    stream._client = transport = Mock()
    stream.connected = True
    stream._accept_power(transport, {})
    stream.last_power_at -= 31
    caplog.clear()
    caplog.set_level(logging.INFO, logger=LOGGER)
    for _ in range(5):
        stream.apply(entry.runtime_data.data.leaves)
        stream._accept_disconnect(transport)
    records = [r for r in caplog.records if r.name == LOGGER + ".telemetry"]
    assert len(records) == 1 and records[0].levelno == logging.WARNING
    stream._accept_connection(transport, True)
    assert len([r for r in caplog.records if r.name == LOGGER + ".telemetry"]) == 1
    stream._accept_power(transport, {})
    assert "fresh reports are arriving" in caplog.text
    stream._accept_disconnect(transport)
    assert (
        len(
            [
                r
                for r in caplog.records
                if r.name == LOGGER + ".telemetry" and r.levelno == logging.WARNING
            ]
        )
        == 2
    )
    stream._client = None


async def test_unexpected_command_error_is_logged_without_traceback(control_env, caplog):
    controls, put, _ = control_env
    put.side_effect = RuntimeError(PRIVATE)
    with pytest.raises(HomeAssistantError):
        await controls.async_set_source(0, "battery")
    records = [r for r in caplog.records if r.name == LOGGER + ".controls"]
    assert "unexpected internal error" in records[-1].getMessage()
    assert all(r.exc_info is None for r in records)
    for private in PRIVATE.split():
        assert private not in caplog.text
