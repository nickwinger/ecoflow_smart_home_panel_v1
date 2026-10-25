"""Seed and supplementary patterns have usable, evidence-graded metadata."""

import json
import re
from pathlib import Path

import pytest

from custom_components.ecoflow_smart_home_panel_v1.catalog import load_catalog

GUIDE = json.loads(Path("docs/quota-field-guide.json").read_text())
CATALOG = load_catalog()


def concrete(pattern):
    parts = []
    for token in re.split(r"(\[\])", pattern):
        if token == "[]":
            parts.append(0)
        elif token:
            parts.extend(token.strip(".").split("."))
    return tuple(parts)


@pytest.mark.parametrize("source", GUIDE["fields"], ids=lambda f: f["path"])
def test_every_catalog_pattern(source):
    field = CATALOG.resolve(concrete(source["path"]))
    assert field.source == source
    assert field.exact
    for lang in ("de", "en"):
        assert len(field.description(lang)) > 15
        assert len(source[f"friendly_name_{lang}"]) > 3
        translations = json.loads(
            Path(
                f"custom_components/ecoflow_smart_home_panel_v1/translations/{lang}.json"
            ).read_text()
        )
        assert field.key in translations["entity"]["sensor"]
    assert field.source["confidence"] in (
        "documented",
        "inferred",
        "community",
        "unknown",
        "local_implementation",
    )
    if source["confidence"] not in ("documented", "community"):
        assert field.unit is None
        assert field.enum is None
        assert not field.measurement
        assert not field.enabled
    if source["confidence"] == "community":
        assert not field.measurement
        assert not field.enabled


@pytest.mark.parametrize(
    "pattern,raw,expected",
    [
        ("heartbeat.backupBatPer", 0, 0),
        ("heartbeat.backupBatPer", 100, 100),
        ("heartbeat.backupBatPer", 101, None),
        ("heartbeat.backupBatPer", -1, None),
        ("heartbeat.backupBatPer", "62", None),
        ("heartbeat.backupBatPer", True, None),
        ("heartbeat.gridSta", 1, True),
        ("heartbeat.gridSta", 0, False),
        ("heartbeat.gridSta", 2, None),
        ("heartbeat.gridSta", "1", None),
        ("heartbeat.loadCmdChCtrlInfos[].ctrlSta", 0, "grid"),
        ("heartbeat.loadCmdChCtrlInfos[].ctrlSta", 1, "battery"),
        ("heartbeat.loadCmdChCtrlInfos[].ctrlSta", 2, "off"),
        ("heartbeat.loadCmdChCtrlInfos[].ctrlSta", 99, None),
        ("heartbeat.loadCmdChCtrlInfos[].ctrlSta", True, None),
        ("heartbeat.backupCmdChCtrlInfos[].ctrlSta", 2, 2),
        ("gridInfo.gridVol", 99, None),
        ("gridInfo.gridVol", 230, 230),
        ("gridInfo.gridFreq", 55, None),
        ("channelPower.infoList[].powType", 17, 17),
        ("channelPower.infoList[].chWatt", 123, 123),
    ],
)
def test_strict_value_semantics(pattern, raw, expected):
    assert CATALOG.resolve(concrete(pattern)).value(raw) == expected


def test_statistics_and_daily_counter_policy():
    assert CATALOG.resolve(("heartbeat.backupBatPer",)).measurement
    for path in (
        "heartbeat.gridDayWatth",
        "heartbeat.backupDayWatth",
        "gridInfo.gridVol",
        "gridInfo.gridFreq",
        "heartbeat.workTime",
    ):
        assert not CATALOG.resolve((path,)).measurement
    for path in ("heartbeat.gridDayWatth", "heartbeat.backupDayWatth"):
        field = CATALOG.resolve((path,))
        assert field.unit == "Wh"
        assert field.source["unit_confidence"] == "community"
    assert CATALOG.resolve(("heartbeat.workTime",)).unit == "min"


def test_container_arrays_unknowns_and_numbering():
    field = CATALOG.resolve(("mainsLoadWatt.watth", 1, 3))
    assert field.source["path"] == "mainsLoadWatt.watth[][]"
    assert field.unit is None
    unknown = CATALOG.resolve(("new", 0, "raw"))
    assert unknown.source is None
    assert "unknown" in unknown.description("en")
    assert not unknown.enabled
    assert not CATALOG.resolve(("heartbeat.loadCmdChCtrlInfos", 10, "ctrlSta")).enabled


@pytest.mark.parametrize(
    "pattern,unit,raw,expected",
    [
        ("loadChCurInfo.cur[]", "A", 15, 15),
        ("channelPower.infoList[].chWatt", "W", -123.5, -123.5),
        ("heartbeat.energyInfos[].lcdInputWatts", "W", 321, 321),
        ("heartbeat.energyInfos[].outputPower", "W", 0, 0),
        ("heartbeat.energyInfos[].emsBatTemp", "°C", -8, -8),
        ("heartbeat.energyInfos[].batteryPercentage", "%", 101, None),
        ("heartbeat.energyInfos[].batteryPercentage", "%", "50", None),
        ("heartbeat.energyInfos[].batteryPercentage", "%", 50, 50),
    ],
)
def test_community_units_without_scaling_or_statistics(pattern, unit, raw, expected):
    field = CATALOG.resolve(concrete(pattern))
    assert field.unit == unit
    assert field.value(raw) == expected
    assert not field.measurement
    assert not field.enabled
    assert field.source["evidence"]["sources"]
    assert field.source["unit_confidence"] == "community"


@pytest.mark.parametrize(
    "pattern",
    [
        "heartbeat.backupChaTime",
        "heartbeat.energyInfos[].chargeTime",
        "heartbeat.energyInfos[].dischargeTime",
        "heartbeat.backupFullCap",
        "heartbeat.energyInfos[].fullCap",
    ],
)
def test_unresolved_capacity_and_time_sentinels_remain_raw(pattern):
    field = CATALOG.resolve(concrete(pattern))
    assert field.value(4294967295) == 4294967295
    assert field.value(None) is None
    assert field.unit is None
    assert not field.measurement


def test_all_28_supplementary_sections_have_catalog_evidence():
    refs = {f["evidence"]["review"].split("#")[-1] for f in GUIDE["fields"] if "evidence" in f}
    assert refs == {f"property-{i:02d}" for i in range(1, 29)}
    assert GUIDE["field_count"] == len(GUIDE["fields"]) == 92
