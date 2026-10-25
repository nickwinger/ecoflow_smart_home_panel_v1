"""Offline HA fixtures. All identifiers and readings are invented."""

from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ecoflow_smart_home_panel_v1.const import DOMAIN

DATA = {
    "access_key": "test-access",
    "secret_key": "test-secret",
    "serial": "SHP-TEST-0001",
    "region": "eu",
    "confirm_v1": True,
}


@pytest.fixture(autouse=True)
def custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
def quota():
    return {
        "heartbeat.gridSta": 1,
        "heartbeat.backupBatPer": 61,
        "heartbeat.loadCmdChCtrlInfos": [{"ctrlSta": i % 2} for i in range(10)],
        "heartbeat.backupCmdChCtrlInfos": [{"ctrlSta": 0}, {"ctrlSta": 2}],
    }


@pytest.fixture
def entry(hass):
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DATA["serial"], data=DATA, title="Test panel")
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def mock_quota(quota):
    with patch(
        "custom_components.ecoflow_smart_home_panel_v1.api.EcoFlowClient.get_quota_all",
        new_callable=AsyncMock,
        return_value=quota,
    ) as mock:
        yield mock
