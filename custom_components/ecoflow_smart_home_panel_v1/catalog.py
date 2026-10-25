"""Evidence-based metadata resolution; the catalog never limits discovery."""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .quota import RawPath, Scalar, display_path

_ARRAY_INDEX = re.compile(r"\[(\d+)\]")
_ENUMS = {
    "heartbeat.loadCmdChCtrlInfos[].ctrlSta": {0: "grid", 1: "battery", 2: "off"},
    "heartbeat.loadCmdChCtrlInfos[].ctrlMode": {0: "automatic", 1: "manual"},
    "heartbeat.backupCmdChCtrlInfos[].ctrlMode": {0: "automatic", 1: "manual"},
    "timeTask[].cfg.comCfg.type": {1: "charge", 2: "discharge"},
    "timeTask[].cfg.comCfg.timeRange.timeMode": {0: "daily", 1: "weekly", 2: "monthly", 3: "date"},
}
_BINARY = {
    "heartbeat.gridSta",
    "epsModeInfo.eps",
    "splitPhaseInfo.cfgList[].linkMark",
    "chUseInfo.isEnable[]",
    "emergencyStrategy.chSta[].isEnable",
    "timeTask[].cfg.comCfg.isCfg",
    "timeTask[].cfg.comCfg.isEnable",
    "timeTask[].cfg.comCfg.timeRange.isEnable",
    "cfgSta.sta",
    "timeTask[].cfg.param.chSta[]",
}
_ENABLED = {
    "heartbeat.gridSta",
    "heartbeat.backupBatPer",
    "heartbeat.gridDayWatth",
    "heartbeat.backupDayWatth",
    "heartbeat.loadCmdChCtrlInfos[].ctrlSta",
    "gridInfo.gridVol",
    "gridInfo.gridFreq",
}
_UNITS = {
    "heartbeat.backupBatPer": "%",
    "gridInfo.gridVol": "V",
    "gridInfo.gridFreq": "Hz",
    "timeTask[].cfg.param.hightBattery": "%",
    "timeTask[].cfg.param.lowBattery": "%",
    "backupChaDiscCfg.forceChargeHigh": "%",
    "backupChaDiscCfg.discLower": "%",
    "heartbeat.workTime": "min",
    # Explicitly sourced community units. No scaling or statistics implied.
    "loadChCurInfo.cur[]": "A",
    "channelPower.infoList[].chWatt": "W",
    "heartbeat.energyInfos[].batteryPercentage": "%",
    "heartbeat.energyInfos[].lcdInputWatts": "W",
    "heartbeat.energyInfos[].outputPower": "W",
    "heartbeat.energyInfos[].emsBatTemp": "°C",
    "heartbeat.gridDayWatth": "Wh",
    "heartbeat.backupDayWatth": "Wh",
}


def translation_key(pattern: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", pattern.lower()).strip("_")


@dataclass(frozen=True)
class Field:
    """Resolved static metadata, independent of the most recent value."""

    path: RawPath
    pattern: str
    source: dict[str, Any] | None
    exact: bool

    @property
    def key(self) -> str:
        return translation_key(self.source["path"]) if self.source else "unknown_quota"

    @property
    def confidence(self) -> str:
        if not self.source:
            return "unknown"
        # A container describes its scalar array entries, not arbitrary newly
        # discovered child properties. Do not transfer certainty to those.
        suffix = self.pattern[len(self.source["path"]) :]
        if self.exact or (suffix and re.fullmatch(r"(?:\[\])+", suffix)):
            return self.source["confidence"]
        return "unknown"

    @property
    def binary(self) -> bool:
        return self.pattern in _BINARY

    @property
    def enabled(self) -> bool:
        if self.pattern == "heartbeat.loadCmdChCtrlInfos[].ctrlSta":
            indexes = _ARRAY_INDEX.findall(display_path(self.path))
            return bool(indexes) and int(indexes[0]) < 10
        return self.pattern in _ENABLED

    @property
    def unit(self) -> str | None:
        return _UNITS.get(self.pattern)

    @property
    def measurement(self) -> bool:
        return self.pattern == "heartbeat.backupBatPer"

    @property
    def enum(self) -> dict[int, str] | None:
        return _ENUMS.get(self.pattern)

    def value(self, raw: Scalar) -> Scalar:
        """Strict validity: no string/boolean-to-number coercion or scaling."""
        if self.binary:
            return bool(raw) if type(raw) in (int, bool) and raw in (0, 1) else None
        if self.enum:
            return self.enum.get(raw) if type(raw) is int else None
        if self.unit:
            if type(raw) not in (int, float):
                return None
            if self.unit == "%" and not 0 <= raw <= 100:
                return None
            if self.unit == "V" and not 100 <= raw <= 250:
                return None
            if self.unit == "Hz" and raw not in (50, 60):
                return None
        if self.source and self.exact:
            expected = self.source["value_type"]
            if expected in ("integer", "number") and type(raw) not in (int, float):
                return None
            if expected == "integer" and type(raw) is not int:
                return None
            if expected == "string" and not isinstance(raw, str):
                return None
        return raw

    def description(self, language: str) -> str:
        if not self.source:
            return (
                "Bedeutung, Einheit und Codes dieses Quota-Feldes sind unbekannt. Unveränderter Rohwert."
                if language == "de"
                else "Meaning, unit and codes of this quota field are unknown. Unscaled raw value."
            )
        if language == "de":
            result = (
                ". ".join(
                    str(self.source[k]).rstrip(".")
                    for k in ("meaning_de", "notes", "implementation_notes_de")
                    if self.source.get(k)
                )
                + "."
            )
        else:
            result = self.source["meaning_en"]
        if not self.exact:
            result += (
                " Untereintrag; zusätzliche Unterfelder haben keine gesicherte eigene Bedeutung."
                if language == "de"
                else " Subentry; additional child fields have no verified individual semantics."
            )
        if _ARRAY_INDEX.search(display_path(self.path)):
            result += (
                " Arrayindizes beginnen bei 0; Anzeigenummern bei 1. Lastkanäle 0–9 entsprechen Stromkreisen 1–10. Speicher/Backup folgt der Arrayreihenfolge; physische Zuordnung unbestätigt."
                if language == "de"
                else " Array indices start at 0; display numbers at 1. Load indices 0–9 are circuits 1–10. Storage/backup follows array order; physical assignment is unverified."
            )
        return result


class Catalog:
    """Resolve exact patterns and descriptive container fallbacks."""

    def __init__(self, fields: list[dict[str, Any]]) -> None:
        self.fields = {field["path"]: field for field in fields}
        self.containers = sorted(
            (
                key
                for key, field in self.fields.items()
                if field["value_type"] in ("array", "object")
            ),
            key=len,
            reverse=True,
        )

    def resolve(self, path: RawPath) -> Field:
        pattern = _ARRAY_INDEX.sub("[]", display_path(path))
        if source := self.fields.get(pattern):
            return Field(path, pattern, source, True)
        for container in self.containers:
            if pattern.startswith(container + "[]") or pattern.startswith(container + "."):
                return Field(path, pattern, self.fields[container], False)
        return Field(path, pattern, None, False)


def load_catalog() -> Catalog:
    """Read the installed resource in HA's executor, never the source docs."""
    return Catalog(json.loads(Path(__file__).with_name("catalog.json").read_text())["fields"])
