"""Visible, explicitly pressed all-circuit controls; never run during setup."""

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import EcoFlowConfigEntry
from .const import DOMAIN, NAME
from .coordinator import EcoFlowCoordinator

PARALLEL_UPDATES = 0  # Cancellation must remain usable while a batch is running.


async def async_setup_entry(
    hass: HomeAssistant, entry: EcoFlowConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    if entry.runtime_data.controls.batch_enabled():
        async_add_entities(
            BatchButton(entry.runtime_data, action) for action in ("grid", "battery", "cancel")
        )


class BatchButton(CoordinatorEntity[EcoFlowCoordinator], ButtonEntity):
    _attr_has_entity_name = True
    _unrecorded_attributes = frozenset({"control_operation"})

    def __init__(self, coordinator: EcoFlowCoordinator, action: str) -> None:
        super().__init__(coordinator)
        self.action = action
        self._attr_translation_key = f"batch_{action}"
        self._attr_unique_id = f"{coordinator.serial}:control:batch:{action}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, coordinator.serial)}, name=NAME)

    @property
    def available(self) -> bool:
        controls = self.coordinator.controls
        return controls.batch_enabled() and (
            self.action == "cancel" or (super().available and controls.status["state"] != "running")
        )

    @property
    def extra_state_attributes(self) -> dict:
        return {"control_operation": dict(self.coordinator.controls.status)}

    async def async_press(self) -> None:
        if self.action == "cancel":
            await self.coordinator.controls.async_cancel()
        else:
            await self.coordinator.controls.async_set_all_sources(self.action)
