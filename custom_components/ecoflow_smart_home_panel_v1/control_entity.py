"""State-backed control presentation; no target restoration or optimistic states."""

from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME
from .coordinator import EcoFlowCoordinator
from .entity import channel_label


class ControlEntity(CoordinatorEntity[EcoFlowCoordinator]):
    _attr_has_entity_name = True
    _unrecorded_attributes = frozenset({"description", "quota_path", "control_operation"})

    def __init__(self, coordinator: EcoFlowCoordinator, kind: str, index: int) -> None:
        super().__init__(coordinator)
        self.kind = kind
        self.index = index
        self.language = "de" if coordinator.hass.config.language == "de" else "en"
        self._attr_translation_key = kind
        self._attr_unique_id = f"{coordinator.serial}:control:{kind}:{index}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, coordinator.serial)}, name=NAME)
        self._attr_translation_placeholders = self._placeholders()

    def _placeholders(self) -> dict[str, str]:
        if self.kind == "source":
            label = channel_label(self.coordinator.data.leaves, self.index)
            generic = "Stromkreis" if self.language == "de" else "Circuit"
        else:
            label = ""
            generic = "Backup-Eintrag" if self.language == "de" else "Backup entry"
        return {"channel": label or f"{generic} {self.index + 1}"}

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.controls.enabled(self.kind)

    @property
    def extra_state_attributes(self) -> dict:
        if self.kind == "source":
            array = "loadCmdChCtrlInfos"
            description = (
                "Versorgungsquelle gezielt umschalten; Erfolg erst nach frischer Quota-Bestätigung."
                if self.language == "de"
                else "Intentionally change supply source; success requires fresh quota confirmation."
            )
        else:
            array = "backupCmdChCtrlInfos"
            description = (
                "Lademodus laut funktionierendem Helper: 2=ein, 0/1=aus; Herstellerangabe widersprüchlich. Kein Nachweis tatsächlicher Ladeleistung oder physischer Speicherzuordnung."
                if self.language == "de"
                else "Charge mode per working helper: 2=on, 0/1=off; vendor table conflicts. Does not prove actual charging power or physical storage assignment."
            )
        return {
            "description": description,
            "quota_path": f"data.heartbeat.{array}[{self.index}].ctrlSta",
            "control_operation": dict(self.coordinator.controls.status),
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        self._attr_translation_placeholders = self._placeholders()
        self.__dict__.pop("name", None)
        super()._handle_coordinator_update()
