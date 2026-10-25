"""One-time adoption of requested defaults in existing HA entity registries."""

import pytest
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ecoflow_smart_home_panel_v1 import async_migrate_entry
from custom_components.ecoflow_smart_home_panel_v1.const import DOMAIN
from custom_components.ecoflow_smart_home_panel_v1.quota import identity

from .test_entities import entity_for, setup


async def test_upgrade_enables_old_defaults_without_overwriting_user_choices(
    hass, entry, mock_quota
):
    registry = er.async_get(hass)
    auto_paths = [
        ("channelPower.infoList", 0, "chWatt"),
        ("heartbeat.loadCmdChCtrlInfos", 9, "ctrlMode"),
        *[
            ("heartbeat.energyInfos", 1, name)
            for name in ("batteryPercentage", "lcdInputWatts", "outputPower", "emsBatTemp")
        ],
    ]
    preserved = {
        ("channelPower.infoList", 1, "chWatt"): er.RegistryEntryDisabler.USER,
        ("channelPower.infoList", 10, "chWatt"): er.RegistryEntryDisabler.INTEGRATION,
        ("heartbeat.energyInfos", 2, "outputPower"): er.RegistryEntryDisabler.INTEGRATION,
        ("heartbeat.energyInfos", 0, "fullCap"): er.RegistryEntryDisabler.INTEGRATION,
        ("heartbeat.loadCmdChCtrlInfos", 1, "ctrlMode"): er.RegistryEntryDisabler.DEVICE,
    }
    original = {}
    for path in [*auto_paths, *preserved]:
        original[path] = registry.async_get_or_create(
            "sensor",
            DOMAIN,
            f"{entry.data['serial']}:quota:{identity(path)}",
            config_entry=entry,
            disabled_by=preserved.get(path, er.RegistryEntryDisabler.INTEGRATION),
            suggested_object_id=f"legacy_{len(original)}",
        )
    customized = original[auto_paths[0]]
    registry.async_update_entity(customized.entity_id, name="My custom name")
    assert entry.minor_version == 1
    await setup(hass, entry)
    assert entry.minor_version == 2
    for path in auto_paths:
        current = entity_for(hass, entry, path)
        assert current.entity_id == original[path].entity_id
        assert current.unique_id == original[path].unique_id
        assert current.disabled_by is None
        assert current.entity_category.value == "diagnostic"
        assert hass.states.get(current.entity_id) is not None
    assert hass.states.get(customized.entity_id).name == "My custom name"
    for path, disabler in preserved.items():
        current = entity_for(hass, entry, path)
        assert current.disabled_by is disabler
        assert hass.states.get(current.entity_id) is None
    # Subsequent user choices survive reloads; migration never repeats.
    registry.async_update_entity(customized.entity_id, disabled_by=er.RegistryEntryDisabler.USER)
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert registry.async_get(customized.entity_id).disabled_by is er.RegistryEntryDisabler.USER
    assert hass.states.get(customized.entity_id) is None


@pytest.mark.parametrize("raw", ["broken", "null", "{}", "[]", "[{}]"])
async def test_migration_ignores_invalid_registry_identities(hass, entry, raw):
    registry = er.async_get(hass)
    entity = registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{entry.data['serial']}:quota:{raw}",
        config_entry=entry,
        disabled_by=er.RegistryEntryDisabler.INTEGRATION,
    )
    assert await async_migrate_entry(hass, entry)
    assert registry.async_get(entity.entity_id).disabled_by is er.RegistryEntryDisabler.INTEGRATION


async def test_migration_is_scoped_to_panel_and_platform(hass, entry):
    registry = er.async_get(hass)
    other = MockConfigEntry(domain=DOMAIN, data={**entry.data, "serial": "SHP-OTHER"})
    other.add_to_hass(hass)
    path = identity(("channelPower.infoList", 0, "chWatt"))
    entries = [
        registry.async_get_or_create(
            "sensor",
            DOMAIN,
            f"SHP-OTHER:quota:{path}",
            config_entry=other,
            disabled_by=er.RegistryEntryDisabler.INTEGRATION,
        ),
        registry.async_get_or_create(
            "sensor",
            DOMAIN,
            f"wrong-prefix:{path}",
            config_entry=entry,
            disabled_by=er.RegistryEntryDisabler.INTEGRATION,
        ),
        registry.async_get_or_create(
            "binary_sensor",
            DOMAIN,
            f"{entry.data['serial']}:quota:{path}",
            config_entry=entry,
            disabled_by=er.RegistryEntryDisabler.INTEGRATION,
        ),
    ]
    assert await async_migrate_entry(hass, entry)
    assert other.minor_version == 1
    assert all(
        registry.async_get(e.entity_id).disabled_by is er.RegistryEntryDisabler.INTEGRATION
        for e in entries
    )


async def test_migration_rejects_future_major_and_preserves_future_minor(hass, entry):
    hass.config_entries.async_update_entry(entry, version=2)
    assert not await async_migrate_entry(hass, entry)
    hass.config_entries.async_update_entry(entry, version=1, minor_version=3)
    assert await async_migrate_entry(hass, entry)
    assert entry.minor_version == 3
