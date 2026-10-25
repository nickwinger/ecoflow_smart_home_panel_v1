"""Native entity lifecycle, registry defaults, translations and fresh state."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ecoflow_smart_home_panel_v1.const import DOMAIN
from custom_components.ecoflow_smart_home_panel_v1.diagnostics import (
    async_get_config_entry_diagnostics,
)
from custom_components.ecoflow_smart_home_panel_v1.entity import channel_label
from custom_components.ecoflow_smart_home_panel_v1.quota import identity

from .test_quota import independent_leaves


@pytest.fixture
def quota():
    return json.loads(Path("tests/fixtures/quota.json").read_text())["data"]


def registry_entries(hass, entry):
    return er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)


def entity_for(hass, entry, path):
    return next(
        e
        for e in registry_entries(hass, entry)
        if e.unique_id == entry.runtime_data.unique_id(path)
    )


async def setup(hass, entry):
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_complete_registry_and_defaults(hass, entry, mock_quota, quota):
    await setup(hass, entry)
    entities = registry_entries(hass, entry)
    assert len(entities) == len(independent_leaves(quota))
    represented = {e.unique_id.removeprefix(entry.runtime_data.unique_prefix) for e in entities}
    assert represented == {identity(p) for p in independent_leaves(quota)}
    enabled = [e for e in entities if e.disabled_by is None]
    assert len(entities) == 245
    assert len(enabled) == 44
    assert sum(e.entity_category is None for e in enabled) == 16
    assert sum(e.entity_category is not None for e in enabled) == 28
    assert len([e for e in entities if hass.states.get(e.entity_id)]) == 44
    for e in entities:
        if e.disabled_by:
            assert e.disabled_by is er.RegistryEntryDisabler.INTEGRATION
            assert e.entity_category.value == "diagnostic"
            assert hass.states.get(e.entity_id) is None
        else:
            state = hass.states.get(e.entity_id)
            assert state.attributes["description"]
            assert state.attributes["quota_access_path"]
            assert "SHP-TEST" not in state.attributes["friendly_name"]
    assert mock_quota.await_count == 1
    assert len(entry.runtime_data._listeners) == 46  # two discovery + 44 enabled


async def test_partial_unknowns_recovery_and_new_fields(hass, entry, mock_quota, quota):
    await setup(hass, entry)
    source = entity_for(hass, entry, ("heartbeat.loadCmdChCtrlInfos", 0, "ctrlSta"))
    grid = entity_for(hass, entry, ("heartbeat.gridSta",))
    battery = entity_for(hass, entry, ("heartbeat.backupBatPer",))
    mock_quota.return_value = {
        "heartbeat.loadCmdChCtrlInfos": [{"ctrlSta": 97}],
        "heartbeat.backupBatPer": 610,
        "brandNew": {"raw": 42},
    }
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(source.entity_id).state == "unknown"
    assert hass.states.get(source.entity_id).attributes["raw_value"] == 97
    assert hass.states.get(grid.entity_id).state == "unavailable"
    assert hass.states.get(battery.entity_id).state == "unknown"
    assert hass.states.get(battery.entity_id).attributes["raw_value"] == 610
    new = entity_for(hass, entry, ("brandNew", "raw"))
    assert new.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    mock_quota.return_value = quota
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(grid.entity_id).state == "on"
    assert hass.states.get(battery.entity_id).state == "62"


async def test_enable_reload_missing_and_disable(hass, entry, mock_quota):
    await setup(hass, entry)
    diagnostic = entity_for(hass, entry, ("selfCheck.result",))
    registry = er.async_get(hass)
    registry.async_update_entity(diagnostic.entity_id, disabled_by=None)
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(diagnostic.entity_id).state == "13"
    mock_quota.return_value = {}
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(diagnostic.entity_id).state == "unavailable"
    registry.async_update_entity(diagnostic.entity_id, disabled_by=er.RegistryEntryDisabler.USER)
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(diagnostic.entity_id) is None
    # Registration survives even an empty initial snapshot; no cached state is restored.
    assert (
        entity_for(hass, entry, ("selfCheck.result",)).disabled_by is er.RegistryEntryDisabler.USER
    )


@pytest.mark.parametrize(
    "language,expected",
    [("en", "Circuit 1 – Supply source"), ("de", "Stromkreis 1 – Versorgungsquelle")],
)
async def test_translated_names_and_safe_rename(hass, entry, mock_quota, quota, language, expected):
    hass.config.language = language
    await setup(hass, entry)
    entity = entity_for(hass, entry, ("heartbeat.loadCmdChCtrlInfos", 0, "ctrlSta"))
    before = hass.states.get(entity.entity_id)
    assert before.name.endswith(expected)
    assert "(" not in before.name
    assert before.attributes["channel_label"] == "Test circuit 1"
    quota["loadChInfo"]["info"][0]["chName"] = "New\x00 name\u202e"
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    after = hass.states.get(entity.entity_id)
    assert after.name == before.name
    assert "(" not in after.name
    assert after.attributes["channel_label"] == "New name"
    assert "\u202e" not in after.name
    assert (
        entity_for(hass, entry, ("heartbeat.loadCmdChCtrlInfos", 0, "ctrlSta")).unique_id
        == entity.unique_id
    )
    assert len(registry_entries(hass, entry)) == len(independent_leaves(quota))


async def test_collision_type_changes_and_two_panels(hass, entry, mock_quota, quota):
    await setup(hass, entry)
    first = entity_for(hass, entry, ("collision.value",))
    second = entity_for(hass, entry, ("collision", "value"))
    assert first.unique_id != second.unique_id
    assert first.entity_id != second.entity_id
    other = MockConfigEntry(
        domain=DOMAIN, unique_id="SHP-TEST-0002", data={**entry.data, "serial": "SHP-TEST-0002"}
    )
    other.add_to_hass(hass)
    await setup(hass, other)
    assert {e.unique_id for e in registry_entries(hass, entry)}.isdisjoint(
        e.unique_id for e in registry_entries(hass, other)
    )
    quota["future"]["flag"] = "changed type"
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert len(registry_entries(hass, entry)) == len(independent_leaves(quota))


async def test_registry_budget_survives_reload(hass, entry, mock_quota):
    mock_quota.return_value = {"one": 1, "two": 2}
    with patch("custom_components.ecoflow_smart_home_panel_v1.coordinator.MAX_ENTITIES", 3):
        await setup(hass, entry)
        mock_quota.return_value = {"three": 3, "four": 4}
        await entry.runtime_data.async_refresh()
        await hass.async_block_till_done()
        assert len(registry_entries(hass, entry)) == 3
        assert entry.runtime_data.registry_limit_reached
        mock_quota.return_value = {"five": 5}
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
        assert len(registry_entries(hass, entry)) == 3
        assert entry.runtime_data.registry_limit_reached


async def test_diagnostics_privacy_and_no_legacy_mutation(hass, entry, mock_quota, quota):
    hass.states.async_set("input_number.legacy_test", 42)
    quota.update(
        {"accessKey": "test-access", "heartbeat.mm100Sn": [83, 78], "extra": "test-secret"}
    )
    await setup(hass, entry)
    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    text = json.dumps(diagnostics)
    for private in (
        "test-secret",
        "test-access",
        "SHP-TEST",
        "Test circuit",
        "heartbeat",
        "quota_path",
    ):
        assert private not in text
    assert diagnostics["excluded_subtrees_or_values"] == 3
    assert diagnostics["controls_implemented"] is True
    assert diagnostics["source_controls_enabled"] is False
    assert diagnostics["charge_controls_enabled"] is False
    assert hass.states.get("input_number.legacy_test").state == "42"
    assert not hass.services.has_service(DOMAIN, "set_source")
    assert not hass.services.has_service(DOMAIN, "set_charge")


async def test_failed_poll_makes_enabled_entities_unavailable(hass, entry, mock_quota):
    from custom_components.ecoflow_smart_home_panel_v1.api import EcoFlowError

    await setup(hass, entry)
    mock_quota.side_effect = EcoFlowError("Cloud unavailable")
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    for e in registry_entries(hass, entry):
        state = hass.states.get(e.entity_id)
        if not e.disabled_by:
            assert state.state == "unavailable"
        else:
            assert state is None


async def test_enable_every_leaf_and_unknown_null(hass, entry, mock_quota, quota):
    await setup(hass, entry)
    registry = er.async_get(hass)
    for entity in registry_entries(hass, entry):
        if entity.disabled_by:
            registry.async_update_entity(entity.entity_id, disabled_by=None)
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    for entity in registry_entries(hass, entry):
        state = hass.states.get(entity.entity_id)
        assert state is not None
        assert state.attributes["description"]
    null = entity_for(hass, entry, ("future", "null"))
    assert hass.states.get(null.entity_id).state == "unknown"
    assert mock_quota.await_count == 2


@pytest.mark.parametrize(
    "values,expected",
    [
        ([75, 195, 188, 99, 104, 101, 0, 0], "Küche"),
        ([65, 0, 66], ""),
        ([255], ""),
        ([256], ""),
        ([True], ""),
        ([None], ""),
        ([0, 0], ""),
    ],
)
def test_utf8_channel_names_are_strict_and_preserve_raw_bytes(values, expected):
    leaves = {("loadChInfo", "info", 0, "chName", i): v for i, v in enumerate(values)}
    before = dict(leaves)
    assert channel_label(leaves, 0) == expected
    assert leaves == before


def test_ambiguous_or_partial_name_is_not_displayed():
    leaves = {("loadChInfo", "info", 0, "chName", 1): 65}
    assert channel_label(leaves, 0) == ""
    leaves = {
        ("loadChInfo", "info", 0, "chName"): "one",
        ("loadChInfo.info", 0, "chName"): "two",
    }
    assert channel_label(leaves, 0) == ""


async def test_byte_names_update_presentation_without_changing_circuit_identity(
    hass, entry, mock_quota, quota
):
    await setup(hass, entry)
    circuit = entity_for(hass, entry, ("heartbeat.loadCmdChCtrlInfos", 0, "ctrlSta"))
    quota["loadChInfo"]["info"][0]["chName"] = [75, 195, 188, 99, 104, 101, 0]
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert "Circuit 1 – " in hass.states.get(circuit.entity_id).name
    assert "(" not in hass.states.get(circuit.entity_id).name
    assert hass.states.get(circuit.entity_id).attributes["channel_label"] == "Küche"
    assert (
        circuit.unique_id
        == entity_for(hass, entry, ("heartbeat.loadCmdChCtrlInfos", 0, "ctrlSta")).unique_id
    )
    for index in range(7):
        byte = entity_for(hass, entry, ("loadChInfo", "info", 0, "chName", index))
        assert byte.disabled_by is er.RegistryEntryDisabler.INTEGRATION
        assert hass.states.get(byte.entity_id) is None


async def test_community_metadata_and_units_in_native_ha_states(hass, entry, mock_quota, quota):
    quota["heartbeat.energyInfos"][0].update(
        {"lcdInputWatts": 234, "chargeTime": 4294967295, "dischargeTime": 0}
    )
    await setup(hass, entry)
    registry = er.async_get(hass)
    paths = {
        ("heartbeat.energyInfos", 0, "lcdInputWatts"): ("W", "power"),
        ("heartbeat.energyInfos", 0, "emsBatTemp"): ("°C", "temperature"),
        ("loadChCurInfo.cur", 0): ("A", "current"),
        ("heartbeat.workTime",): ("min", "duration"),
        ("heartbeat.gridDayWatth",): ("Wh", "energy"),
    }
    for path in paths:
        registry.async_update_entity(entity_for(hass, entry, path).entity_id, disabled_by=None)
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    for path, (unit, device_class) in paths.items():
        state = hass.states.get(entity_for(hass, entry, path).entity_id)
        assert state.attributes["unit_of_measurement"] == unit
        assert state.attributes["device_class"] == device_class
        assert "state_class" not in state.attributes
        assert "property-" in state.attributes["evidence_reference"]


@pytest.mark.parametrize("language,prefix", [("de", "Stromkreis 1"), ("en", "Circuit 1")])
@pytest.mark.parametrize(
    "label", [None, "", " \x00 ", [255], [0, 0], "Kitchen", [75, 195, 188, 99, 104, 101, 0]]
)
async def test_fixed_localized_circuit_names_ignore_cloud_names(
    hass, entry, mock_quota, quota, language, prefix, label
):
    hass.config.language = language
    quota["loadChInfo"]["info"][0]["chName"] = label
    await setup(hass, entry)
    for path in (
        ("heartbeat.loadCmdChCtrlInfos", 0, "ctrlSta"),
        ("heartbeat.loadCmdChCtrlInfos", 0, "ctrlMode"),
        ("channelPower.infoList", 0, "chWatt"),
    ):
        state = hass.states.get(entity_for(hass, entry, path).entity_id)
        assert f"{prefix} – " in state.name
        assert "(" not in state.name
        assert ("Circuit" if language == "de" else "Stromkreis") not in state.name
