"""Explicit, entry-scoped batch and cancellation actions."""

import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN


@callback
def async_register_services(hass: HomeAssistant) -> None:
    """Register at integration setup; handlers always check current entry options."""

    def coordinator(call: ServiceCall):
        entry = hass.config_entries.async_get_entry(call.data["config_entry_id"])
        if entry is None or entry.domain != DOMAIN or entry.state is not ConfigEntryState.LOADED:
            raise ServiceValidationError("Select a loaded EcoFlow Smart Home Panel v1 entry")
        return entry.runtime_data

    async def set_all_sources(call: ServiceCall) -> dict:
        """Await all confirmations and pauses; never detach from the calling automation."""
        return await coordinator(call).controls.async_set_all_sources(call.data["source"])

    async def cancel_commands(call: ServiceCall) -> None:
        await coordinator(call).controls.async_cancel()

    hass.services.async_register(
        DOMAIN,
        "set_all_sources",
        set_all_sources,
        schema=vol.Schema(
            {
                vol.Required("config_entry_id"): cv.string,
                vol.Required("source"): vol.In(("grid", "battery")),
                vol.Required("confirm"): vol.All(bool, vol.Equal(True)),
            }
        ),
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        "cancel_commands",
        cancel_commands,
        schema=vol.Schema({vol.Required("config_entry_id"): cv.string}),
    )
