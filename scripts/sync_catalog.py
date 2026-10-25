"""Generate HACS-contained metadata and entity translations from the field guide."""

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components/ecoflow_smart_home_panel_v1"


def generated():
    source = json.loads((ROOT / "docs/quota-field-guide.json").read_text())
    outputs = {INTEGRATION / "catalog.json": source}
    states = {
        "grid": ("Grid", "Netzstrom"),
        "battery": ("Battery", "Batteriespeicher"),
        "off": ("Off", "Aus"),
        "automatic": ("Automatic", "Automatisch"),
        "manual": ("Manual", "Manuell"),
        "charge": ("Charge", "Laden"),
        "discharge": ("Discharge", "Entladen"),
        "daily": ("Daily", "Täglich"),
        "weekly": ("Weekly", "Wöchentlich"),
        "monthly": ("Monthly", "Monatlich"),
        "date": ("Specific date", "Konkretes Datum"),
    }
    for lang in ("en", "de"):
        file = INTEGRATION / "translations" / f"{lang}.json"
        content = json.loads(file.read_text())
        entities = {}
        for field in source["fields"]:
            key = re.sub("[^a-z0-9]+", "_", field["path"].lower()).strip("_")
            entities[key] = {"name": "{context}" + field[f"friendly_name_{lang}"] + "{detail}"}
            enum = field.get("enum")
            if enum and field["path"] in (
                "heartbeat.loadCmdChCtrlInfos[].ctrlSta",
                "heartbeat.loadCmdChCtrlInfos[].ctrlMode",
                "heartbeat.backupCmdChCtrlInfos[].ctrlMode",
                "timeTask[].cfg.comCfg.type",
                "timeTask[].cfg.comCfg.timeRange.timeMode",
            ):
                ids = {
                    "heartbeat.loadCmdChCtrlInfos[].ctrlSta": ["grid", "battery", "off"],
                    "heartbeat.loadCmdChCtrlInfos[].ctrlMode": ["automatic", "manual"],
                    "heartbeat.backupCmdChCtrlInfos[].ctrlMode": ["automatic", "manual"],
                    "timeTask[].cfg.comCfg.type": ["charge", "discharge"],
                    "timeTask[].cfg.comCfg.timeRange.timeMode": [
                        "daily",
                        "weekly",
                        "monthly",
                        "date",
                    ],
                }[field["path"]]
                entities[key]["state"] = {k: states[k][lang == "de"] for k in ids}
        entities["unknown_quota"] = {
            "name": "Unbekanntes Quota-Feld {path}"
            if lang == "de"
            else "Unknown quota field {path}"
        }
        content["entity"] = {
            **content.get("entity", {}),
            "sensor": entities,
            "binary_sensor": {k: {"name": v["name"]} for k, v in entities.items()},
        }
        outputs[file] = content
        if lang == "en":
            outputs[INTEGRATION / "strings.json"] = content
    return {
        path: json.dumps(content, indent=2, ensure_ascii=False) + "\n"
        for path, content in outputs.items()
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    for path, text in generated().items():
        if args.check:
            if not path.exists() or path.read_text() != text:
                raise SystemExit(f"Out of date: {path.relative_to(ROOT)}")
        else:
            path.write_text(text)


if __name__ == "__main__":
    main()
