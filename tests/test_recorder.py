"""Real HA Recorder SQL tests against an isolated in-memory database."""

import json
from pathlib import Path

import pytest
from homeassistant.components.recorder.db_schema import StateAttributes, States, StatesMeta
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.recorder import session_scope
from pytest_homeassistant_custom_component.components.recorder.common import (
    async_wait_recording_done,
)
from sqlalchemy import select

from .test_entities import entity_for, registry_entries, setup


@pytest.fixture
def quota():
    return json.loads(Path("tests/fixtures/quota.json").read_text())["data"]


@pytest.fixture
def mock_recorder_before_hass(recorder_db_url):
    """Initialize recorder database fixtures before the autouse HA fixture."""


def recorded_rows(hass):
    with session_scope(hass=hass, read_only=True) as session:
        rows = session.execute(
            select(StatesMeta.entity_id, States.state, StateAttributes.shared_attrs)
            .join(States, States.metadata_id == StatesMeta.metadata_id)
            .outerjoin(StateAttributes, States.attributes_id == StateAttributes.attributes_id)
        ).all()
        return [
            (entity_id, state, json.loads(attrs) if attrs else {})
            for entity_id, state, attrs in rows
        ]


async def test_only_enabled_entities_record_and_static_metadata_is_omitted(
    recorder_mock, hass, entry, mock_quota, quota
):
    await hass.async_start()
    await setup(hass, entry)
    await async_wait_recording_done(hass)
    rows = await hass.async_add_executor_job(recorded_rows, hass)
    recorded = {row[0] for row in rows}
    for entity in registry_entries(hass, entry):
        assert (entity.entity_id in recorded) == (entity.disabled_by is None)
    for _entity_id, _state, attrs in rows:
        assert "description" not in attrs
        assert "quota_path" not in attrs
        assert "quota_access_path" not in attrs
        assert "confidence" not in attrs
        assert "documented_enum" not in attrs
        assert "unit_confidence" not in attrs
        assert "evidence_reference" not in attrs
    battery = entity_for(hass, entry, ("heartbeat.backupBatPer",))
    assert any(
        row[0] == battery.entity_id and row[2].get("state_class") == "measurement" for row in rows
    )
    for path in (
        ("channelPower.infoList", 0, "chWatt"),
        ("heartbeat.loadCmdChCtrlInfos", 0, "ctrlMode"),
        ("heartbeat.energyInfos", 0, "lcdInputWatts"),
    ):
        diagnostic = entity_for(hass, entry, path)
        assert diagnostic.entity_category.value == "diagnostic"
        assert diagnostic.disabled_by is None
        assert any(row[0] == diagnostic.entity_id and "state_class" not in row[2] for row in rows)
    diagnostic = entity_for(hass, entry, ("heartbeat.backupCmdChCtrlInfos", 0, "ctrlSta"))
    registry = er.async_get(hass)
    registry.async_update_entity(diagnostic.entity_id, disabled_by=None)
    await hass.config_entries.async_reload(entry.entry_id)
    await async_wait_recording_done(hass)
    rows = await hass.async_add_executor_job(recorded_rows, hass)
    assert any(row[0] == diagnostic.entity_id and row[1] == "0" for row in rows)
    registry.async_update_entity(diagnostic.entity_id, disabled_by=er.RegistryEntryDisabler.USER)
    await hass.config_entries.async_reload(entry.entry_id)
    await async_wait_recording_done(hass)
    before = await hass.async_add_executor_job(recorded_rows, hass)
    quota["heartbeat.backupCmdChCtrlInfos"][0]["ctrlSta"] = 91
    quota["heartbeat.backupBatPer"] = 63
    await entry.runtime_data.async_refresh()
    await async_wait_recording_done(hass)
    after = await hass.async_add_executor_job(recorded_rows, hass)
    assert [r for r in after if r[0] == diagnostic.entity_id] == [
        r for r in before if r[0] == diagnostic.entity_id
    ]
    assert any(r[0] == diagnostic.entity_id and r[1] == "0" for r in after)  # old history remains
    assert any(r[0] == battery.entity_id and r[1] == "63" for r in after)
    await hass.config_entries.async_unload(entry.entry_id)


async def test_opt_in_controls_record_states_without_progress_payloads(
    recorder_mock, hass, entry, mock_quota
):
    await hass.async_start()
    hass.config_entries.async_update_entry(
        entry, options={"enable_source_controls": True, "enable_charge_controls": True}
    )
    await setup(hass, entry)
    await async_wait_recording_done(hass)
    rows = await hass.async_add_executor_job(recorded_rows, hass)
    controls = [row for row in rows if row[0].startswith(("select.", "switch."))]
    assert len({row[0] for row in controls}) == 12
    assert all(
        "control_operation" not in row[2]
        and "description" not in row[2]
        and "quota_path" not in row[2]
        for row in controls
    )
    disabled = [e.entity_id for e in registry_entries(hass, entry) if e.disabled_by]
    assert not any(row[0] in disabled for row in rows)
    await hass.config_entries.async_unload(entry.entry_id)
