"""EcoFlow Smart Home Panel v1 native, read-only cloud integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import async_get as async_get_device_registry

from .api import EcoFlowClient
from .const import CONF_ACCESS_KEY, CONF_REGION, CONF_SECRET_KEY, CONF_SERIAL, DOMAIN, NAME
from .coordinator import EcoFlowCoordinator

type EcoFlowConfigEntry = ConfigEntry[EcoFlowCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: EcoFlowConfigEntry) -> bool:
    """Set up a shared client without any device writes."""
    client = EcoFlowClient(
        async_get_clientsession(hass),
        entry.data[CONF_ACCESS_KEY],
        entry.data[CONF_SECRET_KEY],
        entry.data[CONF_SERIAL],
        entry.data[CONF_REGION],
    )
    coordinator = EcoFlowCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    entry.async_on_unload(coordinator.async_add_listener(lambda: None))
    async_get_device_registry(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.data[CONF_SERIAL])},
        manufacturer="EcoFlow",
        model="Smart Home Panel v1",
        name=NAME,
    )
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EcoFlowConfigEntry) -> bool:
    """Stop polling; the HTTP session is owned by Home Assistant."""
    await entry.runtime_data.async_shutdown()
    return True


async def async_reload_entry(hass: HomeAssistant, entry: EcoFlowConfigEntry) -> None:
    """Apply changed polling options."""
    await hass.config_entries.async_reload(entry.entry_id)
