"""EcoFlow Smart Home Panel v1 with read-only defaults and opt-in controls."""

import json

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import async_get as async_get_device_registry

from .api import EcoFlowClient
from .catalog import load_catalog
from .const import (
    CONF_ACCESS_KEY,
    CONF_BATCH_NOTIFICATIONS,
    CONF_REGION,
    CONF_SECRET_KEY,
    CONF_SERIAL,
    DOMAIN,
    NAME,
)
from .coordinator import EcoFlowCoordinator
from .notifications import async_clear_notifications
from .services import async_register_services

PLATFORMS = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SELECT,
    Platform.SWITCH,
    Platform.BUTTON,
]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type EcoFlowConfigEntry = ConfigEntry[EcoFlowCoordinator]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register explicit actions without creating or executing commands."""
    async_register_services(hass)
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: EcoFlowConfigEntry) -> bool:
    """Apply requested diagnostic defaults once, preserving explicit user choices."""
    if entry.version > 1:
        return False
    if entry.minor_version < 2:
        catalog = await hass.async_add_executor_job(load_catalog)
        registry = er.async_get(hass)
        prefix = f"{entry.data[CONF_SERIAL]}:quota:"
        for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
            if (
                entity.platform != DOMAIN
                or entity.domain != "sensor"
                or entity.disabled_by is not er.RegistryEntryDisabler.INTEGRATION
                or not entity.unique_id.startswith(prefix)
            ):
                continue
            try:
                path = json.loads(entity.unique_id[len(prefix) :])
            except ValueError:
                continue
            if (
                isinstance(path, list)
                and path
                and all(type(part) in (str, int) for part in path)
                and catalog.resolve(tuple(path)).enabled_diagnostic
            ):
                registry.async_update_entity(entity.entity_id, disabled_by=None)
        hass.config_entries.async_update_entry(entry, minor_version=2)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: EcoFlowConfigEntry) -> bool:
    """Set up a shared client without any device writes."""
    if entry.options.get(CONF_BATCH_NOTIFICATIONS) is not True:
        async_clear_notifications(hass, entry)
    client = EcoFlowClient(
        async_get_clientsession(hass),
        entry.data[CONF_ACCESS_KEY],
        entry.data[CONF_SECRET_KEY],
        entry.data[CONF_SERIAL],
        entry.data[CONF_REGION],
    )
    catalog = await hass.async_add_executor_job(load_catalog)
    coordinator = EcoFlowCoordinator(hass, entry, client, catalog)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    async_get_device_registry(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.data[CONF_SERIAL])},
        manufacturer="EcoFlow",
        model="Smart Home Panel v1",
        name=NAME,
    )
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    coordinator.telemetry.start()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EcoFlowConfigEntry) -> bool:
    """Stop polling; the HTTP session is owned by Home Assistant."""
    await entry.runtime_data.controls.async_cancel(shutdown=True)
    await entry.runtime_data.telemetry.async_stop()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(hass: HomeAssistant, entry: EcoFlowConfigEntry) -> None:
    """Apply changed polling/control options without restoring previous targets."""
    if entry.options.get(CONF_BATCH_NOTIFICATIONS) is not True:
        async_clear_notifications(hass, entry)
    await hass.config_entries.async_reload(entry.entry_id)


async def async_remove_entry(hass: HomeAssistant, entry: EcoFlowConfigEntry) -> None:
    """Remove only this entry's notifications; never operate the panel."""
    async_clear_notifications(hass, entry)
