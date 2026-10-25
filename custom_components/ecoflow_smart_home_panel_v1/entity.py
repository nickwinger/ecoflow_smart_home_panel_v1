"""Shared discovery and metadata for individually selectable quota leaves."""

import re
import unicodedata
from collections.abc import Callable
from typing import Any

from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .catalog import Field
from .const import DOMAIN, NAME
from .coordinator import EcoFlowCoordinator
from .quota import RawPath, Scalar, display_path, identity


def safe_label(value: Scalar) -> str:
    """Bound labels; remove control, bidi and formatting characters."""
    if not isinstance(value, str):
        return ""
    return " ".join(
        "".join(c for c in value if not unicodedata.category(c).startswith("C")).split()
    )[:48]


def channel_label(leaves: dict[RawPath, Scalar], index: int) -> str:
    """Resolve one unambiguous string or contiguous, zero-padded UTF-8 name."""
    target = f"loadChInfo.info[{index}].chName"
    strings = []
    byte_groups: dict[RawPath, dict[int, Scalar]] = {}
    for path, value in leaves.items():
        if display_path(path) == target:
            strings.append(value)
        elif type(path[-1]) is int and display_path(path[:-1]) == target:
            byte_groups.setdefault(path[:-1], {})[path[-1]] = value
    if len(strings) + len(byte_groups) != 1:
        return ""
    if strings:
        return safe_label(strings[0])
    values = next(iter(byte_groups.values()))
    if set(values) != set(range(len(values))) or any(
        type(v) is not int or not 0 <= v <= 255 for v in values.values()
    ):
        return ""
    raw = bytes(values[i] for i in range(len(values))).rstrip(b"\x00")
    if b"\x00" in raw:
        return ""
    try:
        return safe_label(raw.decode("utf-8"))
    except UnicodeDecodeError:
        return ""


@callback
def async_discover(
    coordinator: EcoFlowCoordinator,
    async_add_entities: AddEntitiesCallback,
    factory: Callable,
    *,
    binary: bool,
) -> None:
    """Register disabled leaves too; HA only adds enabled entities to its loop."""
    added: set[RawPath] = set()

    @callback
    def discover() -> None:
        entities = []
        for path in sorted(coordinator.known_paths - added, key=identity):
            field = coordinator.catalog.resolve(path)
            if field.binary == binary:
                entities.append(factory(coordinator, field))
                added.add(path)
        if entities:
            async_add_entities(entities)

    discover()
    # Keep shared discovery alive even if every entity is disabled. It performs
    # one quota request, never one request or state update per disabled entity.
    coordinator.config_entry.async_on_unload(coordinator.async_add_listener(discover))


class QuotaEntity(CoordinatorEntity[EcoFlowCoordinator]):
    """No full payload attributes, storage helper or optimistic state."""

    _attr_has_entity_name = True
    _unrecorded_attributes = frozenset(
        {
            "description",
            "quota_path",
            "quota_access_path",
            "confidence",
            "documented_unit",
            "documented_enum",
            "channel_label",
            "unit_confidence",
            "evidence_reference",
        }
    )

    def __init__(self, coordinator: EcoFlowCoordinator, field: Field) -> None:
        super().__init__(coordinator, context=identity(field.path))
        self.field = field
        self.language = "de" if coordinator.hass.config.language == "de" else "en"
        self._attr_unique_id = coordinator.unique_id(field.path)
        self._attr_translation_key = field.key
        self._attr_entity_registry_enabled_default = field.enabled
        self._attr_entity_category = EntityCategory.DIAGNOSTIC if field.diagnostic else None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.serial)},
            manufacturer="EcoFlow",
            model="Smart Home Panel v1",
            name=NAME,
        )
        self._attr_translation_placeholders = self._placeholders()

    def _channel_label(self) -> str:
        path = display_path(self.field.path)
        match = re.search(r"\[(\d+)\]", path)
        if not match or not path.startswith(
            (
                "heartbeat.loadCmdChCtrlInfos",
                "channelPower.infoList",
                "loadChInfo.info",
                "chUseInfo.isEnable",
                "loadChCurInfo.cur",
                "emergencyStrategy.chSta",
                "splitPhaseInfo.cfgList",
            )
        ):
            return ""
        index = int(match[1])
        if index >= 10:
            return ""
        return channel_label(self.coordinator.data.leaves, index)

    def _placeholders(self) -> dict[str, str]:
        path = display_path(self.field.path)
        if not self.field.source:
            return {"path": path[:160]}
        indexes = re.findall(r"\[(\d+)\]", path)
        context = ""
        if indexes:
            index = int(indexes[0])
            if path.startswith("timeTask"):
                label = "Aufgabe" if self.language == "de" else "Task"
            elif path.startswith("heartbeat.energyInfos"):
                label = "Speichereintrag" if self.language == "de" else "Storage entry"
            elif path.startswith("heartbeat.backupCmdChCtrlInfos"):
                label = "Backup-Eintrag" if self.language == "de" else "Backup entry"
            elif (
                path.startswith(
                    (
                        "heartbeat.loadCmdChCtrlInfos",
                        "channelPower.infoList",
                        "loadChInfo.info",
                        "chUseInfo.isEnable",
                        "loadChCurInfo.cur",
                        "emergencyStrategy.chSta",
                        "splitPhaseInfo.cfgList",
                    )
                )
                and index < 10
            ):
                label = "Stromkreis" if self.language == "de" else "Circuit"
            else:
                label = "Eintrag" if self.language == "de" else "Entry"
            context = f"{label} {index + 1} – "
        detail = ""
        if not self.field.exact or len(indexes) > 1:
            # Source suffix disambiguates unnamed array scalars/unknown children.
            detail = f" ({path[:120]})"
        return {"context": context, "detail": detail}

    @property
    def available(self) -> bool:
        return super().available and self.field.path in self.coordinator.data.leaves

    @property
    def raw_value(self) -> Scalar:
        return self.coordinator.data.leaves.get(self.field.path)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        source = self.field.source
        result = {
            "description": self.field.description(self.language),
            "quota_path": "data." + display_path(self.field.path),
            "quota_access_path": list(self.field.path),
            "confidence": self.field.confidence,
        }
        if source:
            result["documented_unit"] = source["unit"]
            result["documented_enum"] = (
                source.get("enum_en") if self.language == "en" else source["enum"]
            )
            if evidence := source.get("evidence"):
                result["evidence_reference"] = evidence["review"]
            if unit_confidence := source.get("unit_confidence"):
                result["unit_confidence"] = unit_confidence
        if label := self._channel_label():
            result["channel_label"] = label
        # Keep unknown enums/invalid percentages inspectable without pretending
        # that their normalized state is valid. This small scalar is recordable.
        if self.field.value(self.raw_value) != self.raw_value:
            result["raw_value"] = self.raw_value
        return result

    @callback
    def _handle_coordinator_update(self) -> None:
        self._attr_translation_placeholders = self._placeholders()
        # HA caches names. Refresh the presentation after device label changes;
        # registry unique IDs and user-chosen entity IDs remain untouched.
        self.__dict__.pop("name", None)
        super()._handle_coordinator_update()
