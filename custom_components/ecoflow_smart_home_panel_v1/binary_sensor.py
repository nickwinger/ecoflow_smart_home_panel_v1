"""Only documented binary semantics become binary sensors."""

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import EcoFlowConfigEntry
from .entity import QuotaEntity, async_discover


async def async_setup_entry(
    hass: HomeAssistant, entry: EcoFlowConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_discover(entry.runtime_data, async_add_entities, QuotaBinarySensor, binary=True)


class QuotaBinarySensor(QuotaEntity, BinarySensorEntity):
    """Unknown codes stay unknown, never a fabricated false state."""

    @property
    def is_on(self) -> bool | None:
        return self.field.value(self.raw_value)
