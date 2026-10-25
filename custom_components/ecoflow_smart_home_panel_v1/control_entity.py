"""State-backed control presentation; no target restoration or optimistic states."""

from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME
from .coordinator import EcoFlowCoordinator


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
        if self.kind in ("source", "mode"):
            generic = "Stromkreis" if self.language == "de" else "Circuit"
        else:
            generic = "Backup-Eintrag" if self.language == "de" else "Backup entry"
        return {"channel": f"{generic} {self.index + 1}"}

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.controls.enabled(self.kind)

    @property
    def extra_state_attributes(self) -> dict:
        field = "ctrlSta"
        if self.kind == "mode":
            array = "loadCmdChCtrlInfos"
            field = "ctrlMode"
            description = (
                "Automatisch: Das Panel steuert die Versorgung. Manuell: Die aktuelle Versorgungsquelle wird zur manuellen Vorgabe."
                if self.language == "de"
                else "Automatic: the panel controls the supply. Manual: the current supply source becomes the manual setting."
            )
        elif self.kind == "source":
            array = "loadCmdChCtrlInfos"
            description = (
                "Zwischen Netzstrom und Batterie umschalten. Der angezeigte Zustand wird vom Panel bestätigt."
                if self.language == "de"
                else "Switch between grid and battery. The displayed state is confirmed by the panel."
            )
        else:
            array = "backupCmdChCtrlInfos"
            description = (
                "Laden für diesen Backup-Anschluss ein- oder ausschalten. Die tatsächliche Ladeleistung zeigen die Leistungssensoren."
                if self.language == "de"
                else "Turn charging for this backup connection on or off. Power sensors show the actual charging power."
            )
        return {
            "description": description,
            "quota_path": f"data.heartbeat.{array}[{self.index}].{field}",
            "control_operation": dict(self.coordinator.controls.status),
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        self._attr_translation_placeholders = self._placeholders()
        self.__dict__.pop("name", None)
        super()._handle_coordinator_update()
