"""Native scalar and enum quota sensors."""

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import EcoFlowConfigEntry
from .catalog import Field
from .coordinator import EcoFlowCoordinator
from .entity import QuotaEntity, async_discover
from .quota import Scalar


async def async_setup_entry(
    hass: HomeAssistant, entry: EcoFlowConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_discover(entry.runtime_data, async_add_entities, QuotaSensor, binary=False)


class QuotaSensor(QuotaEntity, SensorEntity):
    """Unit and statistics eligibility are fixed by evidence, never by magnitude."""

    def __init__(self, coordinator: EcoFlowCoordinator, field: Field) -> None:
        super().__init__(coordinator, field)
        self._attr_native_unit_of_measurement = field.unit
        self._attr_state_class = SensorStateClass.MEASUREMENT if field.measurement else None
        if field.enum:
            self._attr_device_class = SensorDeviceClass.ENUM
            self._attr_options = list(field.enum.values())
        elif field.unit == "%":
            self._attr_device_class = SensorDeviceClass.BATTERY
        elif field.unit == "V":
            self._attr_device_class = SensorDeviceClass.VOLTAGE
        elif field.unit == "Hz":
            self._attr_device_class = SensorDeviceClass.FREQUENCY
        elif field.unit == "A":
            self._attr_device_class = SensorDeviceClass.CURRENT
        elif field.unit == "W":
            self._attr_device_class = SensorDeviceClass.POWER
        elif field.unit == "Wh":
            self._attr_device_class = SensorDeviceClass.ENERGY
        elif field.unit == "°C":
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
        elif field.unit == "min":
            self._attr_device_class = SensorDeviceClass.DURATION

    @property
    def native_value(self) -> Scalar:
        return self.field.value(self.raw_value)
