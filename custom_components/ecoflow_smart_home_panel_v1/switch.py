"""Two opt-in charging-mode switches following the proven helper semantics."""

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import EcoFlowConfigEntry
from .control_entity import ControlEntity
from .controls import control_state

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: EcoFlowConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    if coordinator.controls.enabled("charge"):
        async_add_entities(ChargeSwitch(coordinator, "charge", i) for i in range(2))


class ChargeSwitch(ControlEntity, SwitchEntity):
    @property
    def is_on(self) -> bool | None:
        return control_state(self.coordinator.data, "charge", self.index)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.controls.async_set_charge(self.index, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.controls.async_set_charge(self.index, False)
