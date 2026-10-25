"""Offline checks for the Docker Compose development setup.

Only repository text is parsed. No Docker daemon or EcoFlow HTTP calls.
"""

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def test_devcontainer_starts_ha_as_sibling_without_nested_docker():
    cfg = json.loads((ROOT / ".devcontainer/devcontainer.json").read_text())
    assert cfg["dockerComposeFile"] == "ha.compose.yml"
    assert cfg["service"] == "workspace"
    assert cfg["workspaceFolder"] == "/workspaces/ecoflow_smart_home_panel_v1"
    assert cfg["runServices"] == ["workspace", "bootstrap"]
    assert "initializeCommand" not in cfg
    assert cfg["portsAttributes"]["8123"]["onAutoForward"] == "openBrowserOnce"
    assert "homeassistant:8123" in cfg["forwardPorts"]


def test_compose_has_only_disposable_ha_storage_and_separate_workspace():
    compose = yaml.safe_load((ROOT / ".devcontainer/ha.compose.yml").read_text())
    assert compose["name"] == "ecoflow-shp-v1-live-test"
    services = compose["services"]
    assert set(services) == {"seed", "homeassistant", "bootstrap", "workspace"}
    ha = services["homeassistant"]
    assert "127.0.0.1:8124:8123" in ha["ports"]
    assert "ha_config:/config" in ha["volumes"]
    assert "../custom_components:/config/custom_components:ro" in ha["volumes"]
    assert services["workspace"]["depends_on"]["homeassistant"]["condition"] == "service_started"
    assert services["bootstrap"]["depends_on"]["homeassistant"]["condition"] == "service_started"
    assert services["bootstrap"]["network_mode"] == "service:homeassistant"
    assert services["bootstrap"]["environment"]["ECOFLOW_DEV_BOOTSTRAP"] == "1"
    assert "networks" not in services["bootstrap"]
    assert "--compose-loopback" in services["bootstrap"]["command"]
    for service in services.values():
        assert "/var/run/docker.sock" not in str(service)
        assert "/config/ecoflow" not in str(service)


def test_devcontainer_uses_existing_dockerfile_and_ignores_prod_ha():
    cfg = json.loads((ROOT / ".devcontainer/devcontainer.json").read_text())
    compose = yaml.safe_load((ROOT / ".devcontainer/ha.compose.yml").read_text())
    workspace = compose["services"]["workspace"]
    assert workspace["build"]["dockerfile"] == ".devcontainer/Dockerfile"
    assert (ROOT / "custom_components/ecoflow_smart_home_panel_v1/manifest.json").is_file()
    assert "ha_config" in compose["volumes"]
    assert cfg["shutdownAction"] == "none"
