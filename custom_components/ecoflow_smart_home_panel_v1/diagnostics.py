"""Safe aggregate diagnostics: no credentials, raw paths, names or readings."""

from homeassistant.core import HomeAssistant

from . import EcoFlowConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: EcoFlowConfigEntry
) -> dict:
    coordinator = entry.runtime_data
    return {
        "last_update_success": coordinator.last_update_success,
        "poll_interval_seconds": coordinator.poll_interval,
        "discovered_entities": len(coordinator.known_paths),
        "current_safe_leaves": len(coordinator.data.leaves),
        "excluded_subtrees_or_values": coordinator.data.excluded,
        "registry_limit_reached": coordinator.registry_limit_reached,
        "catalog_patterns": len(coordinator.catalog.fields),
        "controls_implemented": True,
        "source_controls_enabled": coordinator.controls.enabled("source"),
        "charge_controls_enabled": coordinator.controls.enabled("charge"),
        "control_operation": dict(coordinator.controls.status),
    }
