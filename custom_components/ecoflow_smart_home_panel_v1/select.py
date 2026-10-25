"""Ten source selectors, created only after explicit source-control opt-in."""

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import EcoFlowConfigEntry
from .control_entity import ControlEntity
from .controls import control_state

PARALLEL_UPDATES = 0  # The controller serializes whole transactions across platforms.


async def async_setup_entry(
    hass: HomeAssistant, entry: EcoFlowConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    if coordinator.controls.enabled("source"):
        async_add_entities(SourceSelect(coordinator, "source", i) for i in range(10))
        async_add_entities(ControlModeSelect(coordinator, "mode", i) for i in range(10))


class SourceSelect(ControlEntity, SelectEntity):
    _attr_options = ["grid", "battery"]

    @property
    def current_option(self) -> str | None:
        return control_state(self.coordinator.data, "source", self.index)

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.controls.async_set_source(self.index, option)


class ControlModeSelect(ControlEntity, SelectEntity):
    _attr_options = ["automatic", "manual"]

    @property
    def current_option(self) -> str | None:
        return control_state(self.coordinator.data, "mode", self.index)

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.controls.async_set_mode(self.index, option)
